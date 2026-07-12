# Mortgage Rate Analysis

Daily, idempotent ingestion of mortgage rates (by loan term, FHA/VA/USDA/jumbo,
fixed/ARM) from local and national lenders into Postgres, visualized in Grafana.

## Architecture

```
EventBridge Scheduler (daily) -> Lambda -> pipeline.run() -> Postgres <- Grafana
```

- **Adapters** (`src/mortgage_rates/adapters/`) — one module per lender. Each
  either reuses `HtmlTableLenderAdapter` (for a plain label+rate%+APR% table)
  or implements `fetch()` directly for a page with different structure.
  Adding a lender = drop a module + a block in `lenders.yaml`.
- **Pipeline** (`pipeline.py`) — runs every enabled adapter, isolates one
  lender's failure from the rest, upserts into Postgres. Called identically by
  the Lambda handler and the CLI, so local runs are faithful to prod.
- **Storage** — the loan "product" is decomposed into columns
  (`loan_term_years`, `is_fixed`, `is_fha`, `is_va`, `is_usda`, `is_jumbo`,
  `arm_fixed_period_years`), not a single enum, so Grafana can filter/group on
  any dimension. `UNIQUE(lender, date, + all loan attributes)` is what makes a
  re-run idempotent (upsert, not insert).
- **Viz** — Grafana (open source) queries the `v_rate_observations` view
  directly. No custom API.

## Local development

```bash
uv sync
docker compose up -d          # Postgres + Grafana (localhost:3000, admin/admin)
uv run alembic upgrade head   # create schema against MORTGAGE_RATES_DATABASE_URL
export MORTGAGE_RATES_DATABASE_URL="postgresql+psycopg://mortgage_rates:mortgage_rates@localhost:5432/mortgage_rates"

uv run mortgage-rates list-adapters
uv run mortgage-rates run                       # today, all enabled lenders
uv run mortgage-rates run --adapter rocket       # one lender
uv run mortgage-rates run --date 2026-07-01      # deterministic backfill for one day
uv run mortgage-rates run --dry-run              # fetch real data, skip DB writes
uv run mortgage-rates backfill --from 2026-07-01 --to 2026-07-10

uv run python scripts/invoke_local.py            # exercises the exact Lambda handler
```

Without `docker compose`, omit `MORTGAGE_RATES_DATABASE_URL` and it defaults to
a local SQLite file (`mortgage_rates.db`) — fastest inner loop, same code path.

## Tests

```bash
uv run pytest
```

Adapter tests run fully offline against recorded HTML fixtures
(`tests/adapters/fixtures/`) via `respx` — no network, deterministic by
construction. `tests/test_pipeline_idempotency.py` proves that running the
pipeline twice for the same date does not duplicate rows.

## Known limitation: lender scraping is fragile by nature

Verified live (2026-07):
- **Rocket Mortgage** — works. Needed a standard browser `User-Agent` (its
  basic bot filter blocks the default httpx client string) and a bespoke
  parser (`adapters/rocket.py`) — the page uses custom `<sc-rate-card>` web
  components, not an HTML `<table>`.
- **MACU** — currently blocked entirely by an Incapsula JS bot-challenge; a
  plain HTTP client gets a challenge page, not rate data, regardless of
  headers. This project does not attempt to defeat that (headless-browser
  stealth automation to bypass a bot-detection challenge is a different,
  more adversarial thing than polite scraping, and likely violates MACU's
  terms of service). Options: find an official/licensed rate-data source,
  reach out to MACU directly, or swap in a different local lender whose page
  doesn't sit behind this kind of wall — `enabled: false` it in
  `lenders.yaml` in the meantime.

This is exactly the kind of thing `product_map` labels and adapter code will
need to be re-checked against periodically — see the comment at the top of
`lenders.yaml`.

## Deploying

See [infra/README.md](infra/README.md).
