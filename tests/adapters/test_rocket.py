"""Rocket's rates page uses custom <sc-rate-card> web components, not a plain
HTML table (confirmed against the live page, 2026-07) — see adapters/rocket.py.
This fixture mirrors that real structure rather than a generic table.
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


def _fetch_rocket():
    configs = load_lender_configs(LENDERS_YAML)
    load_adapters()
    config = configs["rocket"]
    fixture_html = (FIXTURES / "rocket_rates.html").read_text()

    with respx.mock:
        respx.get(config.rates_url).mock(return_value=httpx.Response(200, text=fixture_html))
        with httpx.Client() as client:
            ctx = FetchContext(target_date=TARGET_DATE, config=config, http_client=client)
            return get_registry()["rocket"].fetch(ctx)


def test_rocket_adapter_parses_all_products():
    observations = _fetch_rocket()
    by_label = {o.loan.product_label: o for o in observations}
    assert len(observations) == 6

    jumbo = by_label["Jumbo 30yr Fixed"]
    assert jumbo.interest_rate == Decimal("5.875")
    assert jumbo.apr == Decimal("6.109")
    assert jumbo.points == Decimal("2")
    assert jumbo.loan.is_jumbo is True

    va = by_label["VA 30yr Fixed"]
    assert va.interest_rate == Decimal("5.875")
    assert va.apr == Decimal("6.278")
    assert va.loan.is_va is True

    fha = by_label["FHA 30yr Fixed"]
    assert fha.interest_rate == Decimal("5.875")
    assert fha.points == Decimal("1.875")


def test_rocket_adapter_is_deterministic():
    first = _fetch_rocket()
    second = _fetch_rocket()
    first_rows = {(o.loan.product_label, o.interest_rate, o.apr, o.points) for o in first}
    second_rows = {(o.loan.product_label, o.interest_rate, o.apr, o.points) for o in second}
    assert first_rows == second_rows
