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


def test_afcu_adapter_parses_all_products_and_ignores_unmapped_rows(configs, registry):
    """The fixture includes an auto loan row and two 'Utah Housing' rows not
    in product_map — they must be silently skipped, not mis-parsed."""
    observations = _fetch("afcu", "afcu_rates.html", configs, registry)

    by_label = {o.loan.product_label: o for o in observations}
    assert len(observations) == 6

    conv30 = by_label["Conventional 30yr Fixed"]
    assert conv30.interest_rate == Decimal("6.375")
    assert conv30.points == Decimal("0.5")
    assert conv30.apr == Decimal("6.517")

    fha30 = by_label["FHA 30yr Fixed"]
    assert fha30.interest_rate == Decimal("5.875")
    assert fha30.apr == Decimal("6.73")
    assert fha30.loan.is_fha is True


def test_zions_adapter_parses_div_based_pseudo_table(configs, registry):
    observations = _fetch("zions", "zions_rates.html", configs, registry)

    by_label = {o.loan.product_label: o for o in observations}
    assert len(observations) == 6

    conv15 = by_label["Conventional 15yr Fixed"]
    assert conv15.interest_rate == Decimal("5.625")
    assert conv15.apr == Decimal("5.909")

    jumbo_arm = by_label["Jumbo 30yr 7/1 ARM"]
    assert jumbo_arm.loan.is_jumbo is True
    assert jumbo_arm.loan.is_fixed is False
    assert jumbo_arm.loan.arm_fixed_period_years == 7

    va = by_label["VA 30yr Fixed"]
    assert va.interest_rate == Decimal("6.000")
    assert va.loan.is_va is True


def test_goldenwest_adapter_ignores_empty_fha_va_tables(configs, registry):
    """FHA/VA rate tables exist on the live page but currently have no rows
    (no data yet, not a parsing failure) -- only the 3 conventional fixed
    products with real numbers should come through."""
    observations = _fetch("goldenwest", "goldenwest_rates.html", configs, registry)

    by_label = {o.loan.product_label: o for o in observations}
    assert len(observations) == 3

    conv30 = by_label["Conventional 30yr Fixed"]
    assert conv30.interest_rate == Decimal("6.250")
    assert conv30.apr == Decimal("6.421")

    conv15 = by_label["Conventional 15yr Fixed"]
    assert conv15.interest_rate == Decimal("5.490")
    assert conv15.apr == Decimal("5.802")


def test_utahfirst_adapter_parses_composite_type_product_term_labels(configs, registry):
    """Utah First splits each row's label across Type/Product/Term cells
    instead of one cell, and the page has other unrelated rate tables
    (auto, RV, HELOC) sharing the same table class -- row_selector scopes to
    the Home Mortgages tab and product_map keys match the concatenated
    Type+Product+Term text as a substring."""
    observations = _fetch("utahfirst", "utahfirst_rates.html", configs, registry)

    by_label = {o.loan.product_label: o for o in observations}
    assert len(observations) == 7

    conv30 = by_label["Conventional 30yr Fixed"]
    assert conv30.interest_rate == Decimal("6.250")
    assert conv30.apr == Decimal("6.300")

    arm = by_label["Conventional 30yr 5/1 ARM"]
    assert arm.loan.is_fixed is False
    assert arm.loan.arm_fixed_period_years == 5

    fha15 = by_label["FHA 15yr Fixed"]
    assert fha15.interest_rate == Decimal("5.125")
    assert fha15.loan.is_fha is True

    va = by_label["VA 30yr Fixed"]
    assert va.loan.is_va is True


def test_usucu_adapter_ignores_empty_fha_va_tables(configs, registry):
    """Same platform/markup as Goldenwest (USU CU is a branded division of
    Goldenwest Credit Union) -- FHA/VA tables exist but have no rows yet."""
    observations = _fetch("usucu", "usucu_rates.html", configs, registry)

    by_label = {o.loan.product_label: o for o in observations}
    assert len(observations) == 3

    conv30 = by_label["Conventional 30yr Fixed"]
    assert conv30.interest_rate == Decimal("6.250")
    assert conv30.apr == Decimal("6.421")

    conv20 = by_label["Conventional 20yr Fixed"]
    assert conv20.interest_rate == Decimal("5.875")
    assert conv20.apr == Decimal("6.096")
