"""AWS Lambda entrypoint. A thin wrapper over pipeline.run() — all real logic
lives in pipeline.py so the Lambda and the local CLI stay behaviorally identical.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from mortgage_rates.config import get_settings
from mortgage_rates.db.engine import init_db, make_engine
from mortgage_rates.pipeline import run as run_pipeline


def _resolve_database_url_from_secrets_manager() -> None:
    """If MORTGAGE_RATES_DATABASE_URL isn't set but DB_SECRET_ARN is (the
    prod Lambda config — see infra/lambda.tf), fetch it from Secrets Manager
    at cold start. Uses the `boto3` bundled in the Lambda Python runtime
    rather than adding it as a project dependency."""
    if os.environ.get("MORTGAGE_RATES_DATABASE_URL") or not os.environ.get("DB_SECRET_ARN"):
        return
    import boto3

    client = boto3.client("secretsmanager")
    secret = json.loads(client.get_secret_value(SecretId=os.environ["DB_SECRET_ARN"])["SecretString"])
    os.environ["MORTGAGE_RATES_DATABASE_URL"] = (
        f"postgresql+psycopg://{secret['username']}:{secret['password']}"
        f"@{secret['host']}:{secret['port']}/{secret['dbname']}"
    )


_resolve_database_url_from_secrets_manager()
_settings = get_settings()
logging.basicConfig(level=_settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
_engine = make_engine(_settings.database_url)


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """EventBridge invokes this on the daily schedule with no meaningful event
    payload; `target_date` defaults to today (UTC) unless explicitly passed
    (e.g. for a manual backfill invoke)."""
    init_db(_engine)

    target_date = None
    if event and event.get("target_date"):
        import datetime as dt

        target_date = dt.date.fromisoformat(event["target_date"])

    result = run_pipeline(_engine, _settings, target_date=target_date)

    return {
        "target_date": result.target_date.isoformat(),
        "observation_count": result.observation_count,
        "failed_adapters": [r.slug for r in result.failed],
    }
