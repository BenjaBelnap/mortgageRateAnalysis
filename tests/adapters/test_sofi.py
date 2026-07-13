"""SoFi's rate/APR figures are embedded as JS object-literal props on inline
`RateBox` component calls (server-rendered React), not <table>/<tr> markup --
see adapters/sofi.py. This fixture mirrors that real structure, including the
trailing JS-escaped footnote marker (literal backslash-u sequence) on each
label, which the adapter's label regex must stop short of.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from pathlib import Path

import httpx
import respx

from mortgage_rates.adapters.base import FetchContext, load_adapters, get_registry
from mortgage_rates.lenders_config import load_lender_configs

FIXTURES = Path(__file__).parent / "fixtures"
LENDERS_YAML = Path(__file__).parents[2] / "lenders.yaml"
TARGET_DATE = dt.date(2026, 7, 12)


def _fetch_sofi():
    configs = load_lender_configs(LENDERS_YAML)
    load_adapters()
    config = configs["sofi"]
    fixture_html = (FIXTURES / "sofi_rates.html").read_text(encoding="utf-8")

    with respx.mock:
        respx.get(config.rates_url).mock(return_value=httpx.Response(200, text=fixture_html))
        with httpx.Client() as client:
            ctx = FetchContext(target_date=TARGET_DATE, config=config, http_client=client)
            return get_registry()["sofi"].fetch(ctx)


def test_sofi_adapter_strips_footnote_markers_and_skips_unmapped_products():
    """The fixture includes a '5-year ARM' RateBox not in product_map (SoFi
    doesn't publish ARM rates on this page) -- it must be silently skipped."""
    observations = _fetch_sofi()
    by_label = {o.loan.product_label: o for o in observations}
    assert len(observations) == 4

    conv10 = by_label["Conventional 10yr Fixed"]
    assert conv10.interest_rate == Decimal("5.750")
    assert conv10.apr == Decimal("6.236")

    conv30 = by_label["Conventional 30yr Fixed"]
    assert conv30.interest_rate == Decimal("6.250")
    assert conv30.apr == Decimal("6.461")


def test_sofi_adapter_is_deterministic():
    first = _fetch_sofi()
    second = _fetch_sofi()
    first_rows = {(o.loan.product_label, o.interest_rate, o.apr) for o in first}
    second_rows = {(o.loan.product_label, o.interest_rate, o.apr) for o in second}
    assert first_rows == second_rows
