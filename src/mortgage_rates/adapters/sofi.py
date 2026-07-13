"""SoFi's rates page is a server-rendered React SPA: the current rate/APR
figures are embedded verbatim as JS object-literal props passed to a
`RateBox` component call inside an inline <script> block, e.g.

    React.createElement(RateBox,{boxAprText:"6.236%",...,
        boxRateText:"5.750%",...,eyeBrowText:"10-year fixed\\u2075"})

not inside a <table>/<tr> -- doesn't fit HtmlTableLenderAdapter. No JS
execution needed, the numbers are already literal text in the raw HTML
response (confirmed against the live page, 2026-07). `eyeBrowText` carries a
trailing JS-escaped footnote marker (`\\u2075` etc, literal backslash-u
sequence in the source, not a real unicode character) which the label regex
stops short of rather than trying to strip.
"""

from __future__ import annotations

import datetime as dt
import re

from mortgage_rates.adapters.base import FetchContext, register
from mortgage_rates.models import RateObservation
from mortgage_rates.normalize import loan_attributes_from_label, parse_percent

_RATE_BOX_RE = re.compile(
    r'RateBox,\{boxAprText:"(?P<apr>-?\d+(?:\.\d+)?%)\s*",'
    r'boxAprTextColor:"[^"]*",boxClassName:"[^"]*",'
    r'boxRateText:"(?P<rate>-?\d+(?:\.\d+)?%)\s*",'
    r'boxRateTextColor:"[^"]*",eyeBrowClassName:"[^"]*",'
    r'eyeBrowText:"(?P<label>[^"\\]+)'
)


@register
class SofiAdapter:
    slug = "sofi"

    def fetch(self, ctx: FetchContext) -> list[RateObservation]:
        config = ctx.config
        response = ctx.http_client.get(config.rates_url)
        response.raise_for_status()
        fetched_at = dt.datetime.now(dt.UTC)

        observations: list[RateObservation] = []
        for match in _RATE_BOX_RE.finditer(response.text):
            label = match.group("label").strip()
            if label not in config.product_map:
                continue
            observations.append(
                RateObservation(
                    lender_slug=config.slug,
                    observed_date=ctx.target_date,
                    loan=loan_attributes_from_label(label, config.product_map),
                    interest_rate=parse_percent(match.group("rate")),
                    apr=parse_percent(match.group("apr")),
                    source_url=config.rates_url,
                    fetched_at=fetched_at,
                    raw={"label": label, "rate": match.group("rate"), "apr": match.group("apr")},
                )
            )
        return observations
