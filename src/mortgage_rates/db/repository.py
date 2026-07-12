"""Idempotent persistence for RateObservations.

The upsert is what makes the daily job idempotent: re-running for a date
that already has rows updates them in place instead of duplicating.
"""

from __future__ import annotations

from sqlalchemy import Connection, Engine

from mortgage_rates.db.schema import IDENTITY_COLUMNS, lenders, rate_observations
from mortgage_rates.models import LenderType, RateObservation


def _insert_builder(dialect_name: str):
    if dialect_name == "sqlite":
        from sqlalchemy.dialects.sqlite import insert

        return insert
    from sqlalchemy.dialects.postgresql import insert

    return insert


def upsert_lender(conn: Connection, *, slug: str, name: str, type_: LenderType, region: str | None, homepage: str | None) -> None:
    insert = _insert_builder(conn.engine.dialect.name)
    stmt = insert(lenders).values(slug=slug, name=name, type=type_.value, region=region, homepage=homepage)
    stmt = stmt.on_conflict_do_update(
        index_elements=["slug"],
        set_={"name": stmt.excluded.name, "type": stmt.excluded.type, "region": stmt.excluded.region, "homepage": stmt.excluded.homepage},
    )
    conn.execute(stmt)


def _row_from_observation(obs: RateObservation) -> dict:
    return {
        "lender_slug": obs.lender_slug,
        "observed_date": obs.observed_date,
        "loan_term_years": obs.loan.loan_term_years,
        "is_fixed": obs.loan.is_fixed,
        # Coalesce None -> 0: see schema.py comment on this column re: NULL
        # breaking unique-constraint conflict matching.
        "arm_fixed_period_years": obs.loan.arm_fixed_period_years if obs.loan.arm_fixed_period_years is not None else 0,
        "is_fha": obs.loan.is_fha,
        "is_va": obs.loan.is_va,
        "is_usda": obs.loan.is_usda,
        "is_jumbo": obs.loan.is_jumbo,
        "interest_rate": obs.interest_rate,
        "apr": obs.apr,
        "points": obs.points,
        "source_url": obs.source_url,
        "fetched_at": obs.fetched_at,
        "raw": obs.raw,
    }


def upsert_observations(conn: Connection, observations: list[RateObservation]) -> int:
    """Insert or refresh observations. Returns the number processed.

    Idempotent by construction: the conflict target is the full identity
    (lender + date + every loan attribute), so re-running the same day's
    job replaces values rather than appending duplicate rows.
    """
    if not observations:
        return 0

    insert = _insert_builder(conn.engine.dialect.name)
    update_cols = ("interest_rate", "apr", "points", "source_url", "fetched_at", "raw")

    for obs in observations:
        stmt = insert(rate_observations).values(**_row_from_observation(obs))
        stmt = stmt.on_conflict_do_update(
            index_elements=list(IDENTITY_COLUMNS),
            set_={col: getattr(stmt.excluded, col) for col in update_cols},
        )
        conn.execute(stmt)

    return len(observations)
