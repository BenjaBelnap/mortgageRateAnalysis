"""Deterministic adapter tests: no live network, recorded HTML fixtures only.

Running an adapter twice against the same fixture must yield identical
results — that's the determinism guarantee the daily job depends on.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
import respx

from mortgage_rates.adapters.base import FetchContext, load_adapters, get_registry
from mortgage_rates.lenders_config import load_lender_configs

FIXTURES = Path(__file__).parent / "fixtures"
LENDERS_YAML = Path(__file__).parents[2] / "lenders.yaml"
TARGET_DATE = dt.date(2026, 7, 12)


@pytest.fixture(scope="module")
def configs():
    return load_lender_configs(LENDERS_YAML)


@pytest.fixture(scope="module")
def registry():
    load_adapters()
    return get_registry()


def _fetch(slug: str, fixture_name: str, configs, registry) -> list:
    config = configs[slug]
    fixture_html = (FIXTURES / fixture_name).read_text()
    with respx.mock:
        respx.get(config.rates_url).mock(return_value=httpx.Response(200, text=fixture_html))
        with httpx.Client() as client:
            ctx = FetchContext(target_date=TARGET_DATE, config=config, http_client=client)
            return registry[slug].fetch(ctx)


def test_macu_adapter_parses_all_products(configs, registry):
    observations = _fetch("macu", "macu_rates.html", configs, registry)

    by_label = {o.loan.product_label: o for o in observations}
    assert len(observations) == 5

    conv30 = by_label["Conventional 30yr Fixed"]
    assert conv30.interest_rate == Decimal("6.250")
    assert conv30.apr == Decimal("6.381")
    assert conv30.lender_slug == "macu"
    assert conv30.observed_date == TARGET_DATE

    fha30 = by_label["FHA 30yr Fixed"]
    assert fha30.interest_rate == Decimal("5.990")
    assert fha30.loan.is_fha is True

    arm = by_label["Conventional 30yr 5/1 ARM"]
    assert arm.loan.is_fixed is False
    assert arm.loan.arm_fixed_period_years == 5


def test_adapter_fetch_is_deterministic(configs, registry):
    first = _fetch("macu", "macu_rates.html", configs, registry)
    second = _fetch("macu", "macu_rates.html", configs, registry)

    first_rows = {(o.loan.product_label, o.interest_rate, o.apr) for o in first}
    second_rows = {(o.loan.product_label, o.interest_rate, o.apr) for o in second}
    assert first_rows == second_rows
