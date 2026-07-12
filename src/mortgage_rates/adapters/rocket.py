"""Rocket Mortgage doesn't fit the generic HTML-table shape: its rates page
is built from custom `<sc-rate-card>` web components (verified against the
live page, 2026-07), not <table>/<tr> markup, so it implements fetch()
directly instead of using HtmlTableLenderAdapter.

Each card's flattened text looks like:
    "30-year fixed Rate 6.75% APR ⓘ <disclaimer text> 7.039% Monthly
     payment $2,271 Points ⓘ <disclaimer text> 1.875 ($6,563) ..."
so label/rate/APR/points are pulled out by position relative to those
fixed section markers.
"""

from __future__ import annotations

import datetime as dt
import re

from mortgage_rates.adapters.base import FetchContext, register
from mortgage_rates.models import RateObservation
from mortgage_rates.normalize import loan_attributes_from_label

_WHITESPACE_RE = re.compile(r"\s+")
_LABEL_RE = re.compile(r"^(.*?)\s+Rate\s")
_RATE_RE = re.compile(r"Rate\s+(\d+\.?\d*)%")
_APR_RE = re.compile(r"(\d+\.?\d*)%\s+Monthly payment")
_POINTS_RE = re.compile(r"(\d+\.?\d*)\s*\(\$")


@register
class RocketAdapter:
    slug = "rocket"

    def fetch(self, ctx: FetchContext) -> list[RateObservation]:
        config = ctx.config
        response = ctx.http_client.get(config.rates_url)
        response.raise_for_status()
        fetched_at = dt.datetime.now(dt.UTC)

        from selectolax.lexbor import LexborHTMLParser

        tree = LexborHTMLParser(response.text)
        observations: list[RateObservation] = []

        for card in tree.css("sc-rate-card"):
            text = _WHITESPACE_RE.sub(" ", card.text(separator=" ", strip=True))

            label_match = _LABEL_RE.search(text)
            rate_match = _RATE_RE.search(text)
            if not label_match or not rate_match:
                continue
            label = label_match.group(1).strip()
            if label not in config.product_map:
                continue

            apr_match = _APR_RE.search(text)
            points_match = _POINTS_RE.search(text)

            observations.append(
                RateObservation(
                    lender_slug=config.slug,
                    observed_date=ctx.target_date,
                    loan=loan_attributes_from_label(label, config.product_map),
                    interest_rate=rate_match.group(1),
                    apr=apr_match.group(1) if apr_match else None,
                    points=points_match.group(1) if points_match else None,
                    source_url=config.rates_url,
                    fetched_at=fetched_at,
                    raw={"label": label, "text": text},
                )
            )
        return observations
