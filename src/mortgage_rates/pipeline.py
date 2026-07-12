"""Orchestrates adapters end-to-end: fetch -> isolate failures -> upsert.

This is the single entrypoint both the Lambda handler and the CLI call, so
local runs and prod runs execute identical logic.
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass, field

import httpx
from sqlalchemy import Engine

from mortgage_rates.adapters.base import FetchContext, get_registry, load_adapters
from mortgage_rates.config import Settings
from mortgage_rates.db.repository import upsert_lender, upsert_observations
from mortgage_rates.lenders_config import load_lender_configs
from mortgage_rates.models import RateObservation

logger = logging.getLogger(__name__)


@dataclass
class AdapterResult:
    slug: str
    observations: list[RateObservation] = field(default_factory=list)
    error: str | None = None


@dataclass
class PipelineResult:
    target_date: dt.date
    adapter_results: list[AdapterResult]

    @property
    def observation_count(self) -> int:
        return sum(len(r.observations) for r in self.adapter_results)

    @property
    def failed(self) -> list[AdapterResult]:
        return [r for r in self.adapter_results if r.error is not None]


def run(
    engine: Engine,
    settings: Settings,
    *,
    target_date: dt.date | None = None,
    only_adapters: set[str] | None = None,
    dry_run: bool = False,
) -> PipelineResult:
    """Fetch rates from every enabled, selected lender and persist them.

    Deterministic: `target_date` defaults to today (UTC) but is always an
    explicit input, so re-running for a past date reproduces the same run.
    Resilient: one adapter raising never stops the others — its failure is
    recorded on its AdapterResult and everything else still persists.
    """
    target_date = target_date or dt.datetime.now(dt.UTC).date()
    load_adapters()
    registry = get_registry()
    configs = load_lender_configs(settings.lenders_config_path)

    results: list[AdapterResult] = []
    # A standard browser UA, not a spoofed/stealth one: several lender sites
    # basic-filter on the default httpx/requests client string. This is
    # ordinary polite-scraper practice, not evasion of anything designed to
    # keep automated *and identified-as-such* clients out (see adapters that
    # sit behind a JS bot-challenge instead, e.g. Incapsula — those are left
    # failing on purpose rather than defeated).
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
        )
    }
    with httpx.Client(timeout=settings.request_timeout_seconds, headers=headers) as client:
        for slug, config in configs.items():
            if not config.enabled:
                continue
            if only_adapters is not None and slug not in only_adapters:
                continue
            adapter = registry.get(slug)
            if adapter is None:
                logger.warning("No adapter registered for lender %r; skipping", slug)
                continue

            ctx = FetchContext(target_date=target_date, config=config, http_client=client)
            try:
                observations = adapter.fetch(ctx)
                results.append(AdapterResult(slug=slug, observations=observations))
                logger.info("adapter=%s observations=%d", slug, len(observations))
            except Exception as exc:  # noqa: BLE001 - isolate one lender's failure from the rest
                logger.exception("Adapter %r failed", slug)
                results.append(AdapterResult(slug=slug, error=str(exc)))

    if not dry_run:
        with engine.begin() as conn:
            for slug, config in configs.items():
                upsert_lender(
                    conn,
                    slug=slug,
                    name=config.name,
                    type_=config.type,
                    region=config.region,
                    homepage=config.homepage,
                )
            for result in results:
                upsert_observations(conn, result.observations)

    return PipelineResult(target_date=target_date, adapter_results=results)
