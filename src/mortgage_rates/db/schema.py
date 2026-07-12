"""SQLAlchemy Core table definitions.

Uses Core (not ORM) — the pipeline deals in plain pydantic models
(`RateObservation`), and Core keeps the mapping between the two explicit and
simple. All idempotency and determinism guarantees live in the unique
constraint below plus repository.py's upsert.
"""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    MetaData,
    Numeric,
    String,
    Table,
    UniqueConstraint,
)

metadata = MetaData()

lenders = Table(
    "lenders",
    metadata,
    Column("slug", String, primary_key=True),
    Column("name", String, nullable=False),
    Column("type", String, nullable=False),  # LenderType: "local" | "national"
    Column("region", String, nullable=True),
    Column("homepage", String, nullable=True),
)

rate_observations = Table(
    "rate_observations",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("lender_slug", String, ForeignKey("lenders.slug"), nullable=False),
    Column("observed_date", Date, nullable=False),
    # --- decomposed loan attributes (the "product") ---
    Column("loan_term_years", Integer, nullable=False),
    Column("is_fixed", Boolean, nullable=False, default=True),
    # 0 = "not an ARM" rather than NULL: this column is part of the identity
    # unique constraint below, and SQL treats NULL != NULL in uniqueness
    # checks, which would silently break upsert conflict-matching for every
    # non-ARM row. repository.py coalesces None -> 0 on write.
    Column("arm_fixed_period_years", Integer, nullable=False, server_default="0"),
    Column("is_fha", Boolean, nullable=False, default=False),
    Column("is_va", Boolean, nullable=False, default=False),
    Column("is_usda", Boolean, nullable=False, default=False),
    Column("is_jumbo", Boolean, nullable=False, default=False),
    # --- rate figures ---
    Column("interest_rate", Numeric(6, 3), nullable=False),
    Column("apr", Numeric(6, 3), nullable=True),
    Column("points", Numeric(6, 3), nullable=True),
    # --- provenance ---
    Column("source_url", String, nullable=False),
    Column("fetched_at", DateTime(timezone=True), nullable=False),
    Column("raw", JSON, nullable=True),
    UniqueConstraint(
        "lender_slug",
        "observed_date",
        "loan_term_years",
        "is_fixed",
        "arm_fixed_period_years",
        "is_fha",
        "is_va",
        "is_usda",
        "is_jumbo",
        name="uq_rate_observation_identity",
    ),
)

# The full attribute set that uniquely identifies an observation. Shared by
# the repository's upsert (conflict target) and the view definition below.
IDENTITY_COLUMNS = (
    "lender_slug",
    "observed_date",
    "loan_term_years",
    "is_fixed",
    "arm_fixed_period_years",
    "is_fha",
    "is_va",
    "is_usda",
    "is_jumbo",
)

_VIEW_BODY = """
SELECT
    ro.id,
    ro.observed_date,
    l.slug AS lender_slug,
    l.name AS lender_name,
    l.type AS lender_type,
    ro.loan_term_years,
    ro.is_fixed,
    ro.arm_fixed_period_years,
    ro.is_fha,
    ro.is_va,
    ro.is_usda,
    ro.is_jumbo,
    CASE
        WHEN ro.is_fha THEN 'FHA'
        WHEN ro.is_va THEN 'VA'
        WHEN ro.is_usda THEN 'USDA'
        WHEN ro.is_jumbo THEN 'Jumbo'
        ELSE 'Conventional'
    END || ' ' || ro.loan_term_years || 'yr ' ||
    CASE WHEN ro.is_fixed THEN 'Fixed' ELSE ro.arm_fixed_period_years || '/1 ARM' END
        AS product_label,
    ro.interest_rate,
    ro.apr,
    ro.points,
    ro.source_url,
    ro.fetched_at
FROM rate_observations ro
JOIN lenders l ON l.slug = ro.lender_slug
"""


def create_view_sql(dialect_name: str) -> str:
    """Return dialect-appropriate DDL for v_rate_observations.

    SQLite supports `CREATE VIEW IF NOT EXISTS`; Postgres does not (only
    `CREATE OR REPLACE VIEW`), so the statement must be chosen per-dialect.
    """
    if dialect_name == "sqlite":
        return f"CREATE VIEW IF NOT EXISTS v_rate_observations AS{_VIEW_BODY}"
    return f"CREATE OR REPLACE VIEW v_rate_observations AS{_VIEW_BODY}"
