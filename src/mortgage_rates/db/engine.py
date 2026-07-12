"""Engine factory — the only place that knows about sqlite vs. postgres."""

from __future__ import annotations

from sqlalchemy import Engine, create_engine, text

from mortgage_rates.db.schema import create_view_sql, metadata


def make_engine(database_url: str) -> Engine:
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, connect_args=connect_args)


def init_db(engine: Engine) -> None:
    """Create tables and the reporting view if they don't already exist."""
    metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text(create_view_sql(engine.dialect.name)))
