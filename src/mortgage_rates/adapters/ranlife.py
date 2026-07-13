"""RANLife's rates page is a real HTML <table>, but the Rate/APR cells are
plain numbers with no literal '%' character ("6", "6.466"), so it doesn't
match HtmlTableLenderAdapter's percent-figure regex which requires one
(confirmed against the live page, 2026-07). The page also has three tables
sharing the same "table mb-5" class (a combined-programs table plus two
buydown/par pricing-option tables for 30yr/15yr) -- this adapter scopes to
the first one, identified by its "Mortgage Program & Term" header cell,
rather than relying on position.
"""

from __future__ import annotations

import datetime as dt

from selectolax.lexbor import LexborHTMLParser

from mortgage_rates.adapters.base import FetchContext, register
from mortgage_rates.models import RateObservation
from mortgage_rates.normalize import loan_attributes_from_label, parse_percent


@register
class RanlifeAdapter:
    slug = "ranlife"

    def fetch(self, ctx: FetchContext) -> list[RateObservation]:
        config = ctx.config
        response = ctx.http_client.get(config.rates_url)
        response.raise_for_status()
        fetched_at = dt.datetime.now(dt.UTC)

        tree = LexborHTMLParser(response.text)
        table = next(
            (
                t
                for t in tree.css("table")
                if (header := t.css_first("th")) and "Mortgage Program" in header.text(strip=True)
            ),
            None,
        )
        if table is None:
            return []

        observations: list[RateObservation] = []
        for row in table.css("tr"):
            cells = row.css("td")
            if len(cells) < 3:
                continue
            label = cells[0].text(strip=True)
            if label not in config.product_map:
                continue
            rate_text = cells[1].text(strip=True)
            apr_text = cells[2].text(strip=True)
            if "N/A" in rate_text or "N/A" in apr_text:
                continue
            observations.append(
                RateObservation(
                    lender_slug=config.slug,
                    observed_date=ctx.target_date,
                    loan=loan_attributes_from_label(label, config.product_map),
                    interest_rate=parse_percent(rate_text),
                    apr=parse_percent(apr_text),
                    source_url=config.rates_url,
                    fetched_at=fetched_at,
                    raw={"label": label, "rate": rate_text, "apr": apr_text},
                )
            )
        return observations
