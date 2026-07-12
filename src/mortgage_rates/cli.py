"""Local-first CLI. Calls the same pipeline.run() the Lambda handler calls,
so a local invocation exercises exactly what ships to prod."""

from __future__ import annotations

import datetime as dt
import logging

import typer

from mortgage_rates.adapters.base import get_registry, load_adapters
from mortgage_rates.config import get_settings
from mortgage_rates.db.engine import init_db, make_engine
from mortgage_rates.pipeline import run as run_pipeline

app = typer.Typer(add_completion=False)


def _configure_logging(level: str) -> None:
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@app.command()
def run(
    date: dt.datetime = typer.Option(None, help="Target date (YYYY-MM-DD). Defaults to today (UTC)."),
    adapter: list[str] = typer.Option(None, "--adapter", help="Limit to one or more lender slugs. Repeatable."),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Fetch real data but skip DB writes — validates adapters without persisting."
    ),
) -> None:
    """Run the daily pipeline once for a given date."""
    settings = get_settings()
    _configure_logging(settings.log_level)
    engine = make_engine(settings.database_url)
    init_db(engine)

    target_date = date.date() if date else None
    only = set(adapter) if adapter else None

    result = run_pipeline(engine, settings, target_date=target_date, only_adapters=only, dry_run=dry_run)

    typer.echo(f"target_date={result.target_date} observations={result.observation_count} dry_run={dry_run}")
    for r in result.adapter_results:
        status = f"ERROR: {r.error}" if r.error else f"{len(r.observations)} observations"
        typer.echo(f"  {r.slug}: {status}")
    if result.failed:
        raise typer.Exit(code=1)


@app.command()
def backfill(
    date_from: dt.datetime = typer.Option(..., "--from", help="Start date (YYYY-MM-DD), inclusive."),
    date_to: dt.datetime = typer.Option(..., "--to", help="End date (YYYY-MM-DD), inclusive."),
    adapter: list[str] = typer.Option(None, "--adapter", help="Limit to one or more lender slugs. Repeatable."),
) -> None:
    """Run the pipeline once per day across a date range (deterministic replay)."""
    settings = get_settings()
    _configure_logging(settings.log_level)
    engine = make_engine(settings.database_url)
    init_db(engine)

    only = set(adapter) if adapter else None
    start, end = date_from.date(), date_to.date()
    if start > end:
        raise typer.BadParameter("--from must be on or before --to")

    day = start
    while day <= end:
        result = run_pipeline(engine, settings, target_date=day, only_adapters=only)
        typer.echo(f"{day}: {result.observation_count} observations, {len(result.failed)} failures")
        day += dt.timedelta(days=1)


@app.command("list-adapters")
def list_adapters() -> None:
    """Show every adapter registered in code (independent of lenders.yaml)."""
    load_adapters()
    for slug in sorted(get_registry()):
        typer.echo(slug)


if __name__ == "__main__":
    app()
