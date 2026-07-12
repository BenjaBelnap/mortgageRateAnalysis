"""Shared parsing for lenders that publish rates as an HTML table: one row
per product, with a text label plus one or more percentage figures (rate,
then APR). Most bank/credit-union rate pages follow this shape, so adapters
share this instead of each re-implementing table walking.

A lender whose page doesn't fit this shape (e.g. a JSON widget) just skips
this helper and implements LenderAdapter.fetch directly — the shared base
class below is a convenience, not a requirement.
"""

from __future__ import annotations

import datetime as dt
import re
from decimal import Decimal

from selectolax.lexbor import LexborHTMLParser

from mortgage_rates.adapters.base import FetchContext
from mortgage_rates.models import RateObservation
from mortgage_rates.normalize import loan_attributes_from_label, parse_percent

_PERCENT_RE = re.compile(r"\d+(?:\.\d+)?\s*%")


def extract_labeled_rate_rows(html: str, labels: list[str]) -> dict[str, list[Decimal]]:
    """Scan every <tr> for text containing one of `labels`; return the
    ordered percentage figures found in that row (typically [rate, apr])."""
    tree = LexborHTMLParser(html)
    results: dict[str, list[Decimal]] = {}
    for row in tree.css("tr"):
        text = row.text(separator=" ", strip=True)
        if not text:
            continue
        label = next((candidate for candidate in labels if candidate in text and candidate not in results), None)
        if label is None:
            continue
        percents = [parse_percent(m.group()) for m in _PERCENT_RE.finditer(text)]
        if percents:
            results[label] = percents
    return results


class HtmlTableLenderAdapter:
    """Base class for lenders whose rates page is a simple label+percent table.

    Subclasses only need to set `slug`; the raw-label -> LoanAttributes
    mapping and the URL both come from lenders.yaml (config), keeping the
    adapter itself free of hardcoded product knowledge.
    """

    slug: str

    def fetch(self, ctx: FetchContext) -> list[RateObservation]:
        config = ctx.config
        response = ctx.http_client.get(config.rates_url)
        response.raise_for_status()
        fetched_at = dt.datetime.now(dt.UTC)

        rows = extract_labeled_rate_rows(response.text, list(config.product_map))

        observations: list[RateObservation] = []
        for label, percents in rows.items():
            rate, *rest = percents
            apr = rest[0] if rest else None
            observations.append(
                RateObservation(
                    lender_slug=config.slug,
                    observed_date=ctx.target_date,
                    loan=loan_attributes_from_label(label, config.product_map),
                    interest_rate=rate,
                    apr=apr,
                    source_url=config.rates_url,
                    fetched_at=fetched_at,
                    raw={"label": label, "percents": [str(p) for p in percents]},
                )
            )
        return observations
