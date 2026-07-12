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

## Lender status (verified live, 2026-07)

| Lender | Type | Status | Notes |
|---|---|---|---|
| Rocket Mortgage | national | ✅ working | Needed a standard browser `User-Agent` (basic bot filter). Page uses custom `<sc-rate-card>` elements, not a table — bespoke parser (`adapters/rocket.py`). |
| America First Credit Union | local (UT) | ✅ working | Plain HTML table; three percent columns (rate, points, APR) — `percent_field_order` in `lenders.yaml`. |
| Zions Bank | local (UT) | ✅ working | Real table data, but rendered as divs with BEM classes, not `<tr>` — `row_selector: ".cmp-rates-tables__tr"` in `lenders.yaml`. |
| Goldenwest Credit Union | local (UT) | ✅ working | Plain HTML table (`table.rates-table`). FHA/VA tables exist on the page but are currently empty — only the 3 conventional fixed products with real numbers are mapped. |
| Granite Credit Union | local (UT) | ✅ working | Rate cells are populated client-side via `document.write(getRateTweak('KEY'))`, not plain text. The same KEY → value pairs are embedded statically as JSON elsewhere on the page, so `adapters/granite.py` reads them directly out of the raw HTML — no JS execution needed. |
| MACU | local (UT) | ❌ disabled | Sits behind an Incapsula JS bot-challenge — a plain HTTP client gets a challenge page regardless of headers. **Not attempting to defeat this**: headless-browser stealth automation to bypass a bot-detection challenge is a different, more adversarial thing than polite scraping, and likely violates MACU's terms of service. Options: an official/licensed data source, contacting MACU directly, or leaving it disabled. |
| Utah First Credit Union | local (UT) | ❌ disabled | Consistently returns 403 via `httpx` despite an identical UA succeeding via `curl` — points to TLS/client fingerprinting (Cloudflare), not a UA-string filter. Same "don't defeat a bot wall" line as MACU. Adapter/fixture/tests are kept working in case a different access path turns up. |
| UCCU | local (UT) | ⏸ not implemented | No mortgage rate content found on a plain GET of the obvious rates page — likely lives behind a third-party widget (`mymortgage-online.com`). Needs investigation before an adapter is worth writing. |
| Cyprus Credit Union | local (UT) | ⏸ no usable data | Standard first-mortgage rate table exists but is empty ("get a personalized quote"). Only a niche short-term/2nd-mortgage product publishes numbers, not comparable to the primary products tracked for other lenders. |
| Canyon View Federal Credit Union | local (UT) | ⏸ no usable data | Standard products (conventional/FHA/VA/jumbo) show "call for quote", no numbers. Only a niche "No-Fee First Mortgage" product (pivoted by LTV tier, not term) publishes numbers. |
| Bank of Utah | local (UT) | ⏸ no usable data | Rates page has no table at all — explicitly directs customers to call a loan officer. |
| Altabank | local (UT) | ⏸ no usable data | No numeric mortgage rates published anywhere on the site — product-category descriptions only. |
| Central Bank | local (UT) | ⏸ no usable data | A real rate table exists but is explicitly deposit rates only; the mortgage page is product-category cards with no numbers. |
| Primary Residential Mortgage Inc. (PRMI) | national | ⏸ no usable data | Mortgage broker — per-loan-officer branded microsites, no centralized public rate table. |
| First Colony Mortgage | national | ⏸ no usable data | Mortgage broker — no `/rates` page exists on the site (404s); only a calculator and quote request. |
| SecurityNational Mortgage Company | national | ⏸ no usable data | The `/rates/` page body is a single lazy-loaded scheduling/consultation iframe widget, not a rate table. |
| Guild Mortgage | national | ⏸ no usable data | The "rates" page is an educational article, not a live numeric table — actual quotes require a loan officer. |
| Intercap Lending | local (UT) | ⏸ no usable data | The "rate-quote" page is a lead-gen form, no published rates. |

This is exactly the kind of thing `product_map`, `row_selector`, and
`percent_field_order` in `lenders.yaml` will need to be re-checked against
periodically as lenders redesign their pages — see the comment at the top of
that file. `HtmlTableLenderAdapter` covers any lender whose rates page is a
real or div-based label+percentage table (most of them); a lender with a
genuinely different shape (like Rocket) implements `fetch()` directly instead.

## Deploying

See [infra/README.md](infra/README.md).
