"""Granite's rate cells are populated client-side via
document.write(getRateTweak('KEY')) rather than plain text, with the real
values embedded statically as JSON elsewhere on the page (confirmed against
the live page, 2026-07) — see adapters/granite.py. This fixture mirrors that
real structure rather than a generic table.
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


def _fetch_granite():
    configs = load_lender_configs(LENDERS_YAML)
    load_adapters()
    config = configs["granite"]
    fixture_html = (FIXTURES / "granite_rates.html").read_text(encoding="utf-8")

    with respx.mock:
        respx.get(config.rates_url).mock(return_value=httpx.Response(200, text=fixture_html))
        with httpx.Client() as client:
            ctx = FetchContext(target_date=TARGET_DATE, config=config, http_client=client)
            return get_registry()["granite"].fetch(ctx)


def test_granite_adapter_resolves_js_tweak_values_and_skips_call_for_details():
    observations = _fetch_granite()
    by_label = {o.loan.product_label: o for o in observations}
    assert len(observations) == 3

    conv30 = by_label["Conventional 30yr Fixed"]
    assert conv30.interest_rate == Decimal("6.125")
    assert conv30.points == Decimal("0")
    assert conv30.apr == Decimal("6.192")

    arm = by_label["Conventional 30yr 7/1 ARM"]
    assert arm.interest_rate == Decimal("5.75")
    assert arm.loan.is_fixed is False
    assert arm.loan.arm_fixed_period_years == 7

    conv15 = by_label["Conventional 15yr Fixed"]
    assert conv15.apr == Decimal("5.51")


def test_granite_adapter_is_deterministic():
    first = _fetch_granite()
    second = _fetch_granite()
    first_rows = {(o.loan.product_label, o.interest_rate, o.apr, o.points) for o in first}
    second_rows = {(o.loan.product_label, o.interest_rate, o.apr, o.points) for o in second}
    assert first_rows == second_rows
