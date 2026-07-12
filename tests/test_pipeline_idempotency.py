"""Integration test: running the pipeline twice for the same date must not
duplicate rows — this is the idempotency guarantee the daily job relies on
to be safely re-run or retried."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import httpx
import respx
from sqlalchemy import func, select

from mortgage_rates.config import Settings
from mortgage_rates.db.engine import init_db, make_engine
from mortgage_rates.db.schema import rate_observations
from mortgage_rates.pipeline import run as run_pipeline

FIXTURES = Path(__file__).parent / "adapters" / "fixtures"
LENDERS_YAML = Path(__file__).parent.parent / "lenders.yaml"
TARGET_DATE = dt.date(2026, 7, 12)


def _mock_lender_pages():
    respx.get("https://www.macu.com/rates/home").mock(
        return_value=httpx.Response(200, text=(FIXTURES / "macu_rates.html").read_text())
    )
    respx.get("https://www.rocketmortgage.com/mortgage-rates").mock(
        return_value=httpx.Response(200, text=(FIXTURES / "rocket_rates.html").read_text())
    )
    respx.get("https://www.americafirst.com/rates/loan-rates.html").mock(
        return_value=httpx.Response(200, text=(FIXTURES / "afcu_rates.html").read_text())
    )
    respx.get("https://www.zionsbank.com/personal/home-loans/mortgage-rates/").mock(
        return_value=httpx.Response(200, text=(FIXTURES / "zions_rates.html").read_text())
    )


def test_running_pipeline_twice_does_not_duplicate_rows(tmp_path):
    db_path = tmp_path / "test.db"
    settings = Settings(database_url=f"sqlite:///{db_path}", lenders_config_path=LENDERS_YAML)
    engine = make_engine(settings.database_url)
    init_db(engine)

    with respx.mock:
        _mock_lender_pages()
        first = run_pipeline(engine, settings, target_date=TARGET_DATE)

    with engine.connect() as conn:
        count_after_first = conn.execute(select(func.count()).select_from(rate_observations)).scalar_one()

    assert not first.failed
    assert first.observation_count == 18  # macu disabled (Incapsula-blocked); 6 rocket + 6 afcu + 6 zions
    assert count_after_first == 18

    with respx.mock:
        _mock_lender_pages()
        second = run_pipeline(engine, settings, target_date=TARGET_DATE)

    with engine.connect() as conn:
        count_after_second = conn.execute(select(func.count()).select_from(rate_observations)).scalar_one()

    assert second.observation_count == 18
    assert count_after_second == 18  # unchanged: upsert refreshed, didn't append
