"""RANLife's Rate/APR cells are plain numbers with no literal '%' character,
so this doesn't fit HtmlTableLenderAdapter -- see adapters/ranlife.py. The
fixture also includes two other tables sharing the same class (30yr/15yr
buydown pricing options) to prove the adapter scopes to the right one by
header text, not position.
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


def _fetch_ranlife():
    configs = load_lender_configs(LENDERS_YAML)
    load_adapters()
    config = configs["ranlife"]
    fixture_html = (FIXTURES / "ranlife_rates.html").read_text(encoding="utf-8")

    with respx.mock:
        respx.get(config.rates_url).mock(return_value=httpx.Response(200, text=fixture_html))
        with httpx.Client() as client:
            ctx = FetchContext(target_date=TARGET_DATE, config=config, http_client=client)
            return get_registry()["ranlife"].fetch(ctx)


def test_ranlife_adapter_parses_percent_less_cells_and_skips_na_and_other_tables():
    """'VA 30 IRRL Fixed' isn't in product_map (refi-only, excluded by
    config) and '7/6 ARM' publishes N/A instead of numbers -- both must be
    skipped, along with the two buydown/par tables lower on the page."""
    observations = _fetch_ranlife()
    by_label = {o.loan.product_label: o for o in observations}
    assert len(observations) == 4

    conv30 = by_label["Conventional 30yr Fixed"]
    assert conv30.interest_rate == Decimal("6")
    assert conv30.apr == Decimal("6.466")

    fha30 = by_label["FHA 30yr Fixed"]
    assert fha30.interest_rate == Decimal("5.375")
    assert fha30.loan.is_fha is True

    va30 = by_label["VA 30yr Fixed"]
    assert va30.loan.is_va is True

    usda30 = by_label["USDA 30yr Fixed"]
    assert usda30.loan.is_usda is True


def test_ranlife_adapter_is_deterministic():
    first = _fetch_ranlife()
    second = _fetch_ranlife()
    first_rows = {(o.loan.product_label, o.interest_rate, o.apr) for o in first}
    second_rows = {(o.loan.product_label, o.interest_rate, o.apr) for o in second}
    assert first_rows == second_rows
