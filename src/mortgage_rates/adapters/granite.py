"""Granite Credit Union's rate table cells are populated client-side via
`document.write(getRateTweak('KEY'))` — but the same KEY -> value pairs are
embedded statically as JSON elsewhere in the page's Squarespace tweak blob
(verified against the live page, 2026-07), so no JS execution is needed: the
numbers are already present in the raw HTML response, just not inside the
<td> as plain text. That's why this doesn't use HtmlTableLenderAdapter (which
expects the percent literally inside the cell).
"""

from __future__ import annotations

import datetime as dt
import re

from mortgage_rates.adapters.base import FetchContext, register
from mortgage_rates.models import RateObservation
from mortgage_rates.normalize import loan_attributes_from_label, parse_percent

_ROW_RE = re.compile(r"<tr>(.*?)</tr>", re.DOTALL)
_CELL_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")
_TWEAK_CALL_RE = re.compile(r"getRateTweak\('([^']+)'\)")
# Squarespace sometimes embeds this as a real JSON object and sometimes as a
# JSON-encoded string nested inside a larger blob (backslash-escaped quotes)
# -- tolerate both rather than assume one.
_TWEAK_VALUE_RE = re.compile(r'\\?"([A-Za-z0-9]+(?:RATE|FEE|APR))\\?":\\?"(-?\d+(?:\.\d+)?%)\\?"')


@register
class GraniteAdapter:
    slug = "granite"

    def fetch(self, ctx: FetchContext) -> list[RateObservation]:
        config = ctx.config
        response = ctx.http_client.get(config.rates_url)
        response.raise_for_status()
        fetched_at = dt.datetime.now(dt.UTC)
        html = response.text

        tweak_values = dict(_TWEAK_VALUE_RE.findall(html))

        observations: list[RateObservation] = []
        seen: set[str] = set()
        for row_match in _ROW_RE.finditer(html):
            row_html = row_match.group(1)
            cell_match = _CELL_RE.search(row_html)
            if not cell_match:
                continue
            label = _TAG_RE.sub("", cell_match.group(1)).strip()
            if label not in config.product_map or label in seen:
                continue

            keys = _TWEAK_CALL_RE.findall(row_html)
            percents = [parse_percent(tweak_values[key]) for key in keys if key in tweak_values]
            if not percents:
                continue

            fields = dict(zip(config.percent_field_order, percents))
            if "interest_rate" not in fields:
                continue

            seen.add(label)
            observations.append(
                RateObservation(
                    lender_slug=config.slug,
                    observed_date=ctx.target_date,
                    loan=loan_attributes_from_label(label, config.product_map),
                    interest_rate=fields["interest_rate"],
                    apr=fields.get("apr"),
                    points=fields.get("points"),
                    source_url=config.rates_url,
                    fetched_at=fetched_at,
                    raw={"label": label, "tweak_keys": keys},
                )
            )
        return observations
