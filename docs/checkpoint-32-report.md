# Checkpoint report

Checkpoint: 32 — Explicit Memory Expiration Workflow.

Files changed: Migration `0009_memory_expiration`; Memory model and public
schemas; expiration policy, locked repository transition, and Memory route;
focused unit, route, migration, and PostgreSQL behavior tests; README,
architecture, roadmap, checkpoint history, and chat handoff.

Behavior: `POST /memories/{memory_id}/expire` explicitly changes one active
Memory to `expired`. It captures one timezone-aware UTC request time. Null or
future `expires_at` becomes that time; equal or past `expires_at` is preserved.
The first transition returns `updated`. A consistent expired row returns
`unchanged` without a model write and preserves `expires_at` and `updated_at`.
No timestamp passing or background process expires a Memory automatically.

API: The endpoint has no request body. HTTP 200 returns `expiration_status`
(`updated` or `unchanged`) plus the complete existing `MemoryRead`. Exact errors
are 404 `memory not found`, 409 `memory not eligible for expiration`, 409
`memory expiration state is inconsistent`, validation 422, and generic 503
`database unavailable`. OpenAPI documents 200/404/409/422/503.

Database: Revision `0009_memory_expiration` replaces only
`ck_memories_status`, adding `expired` while preserving active, superseded,
invalid, and archived. It performs no data backfill and adds no table, column,
index, trigger, or extension. Clean downgrade restores the former set. Downgrade
with expired rows fails clearly and never rewrites them. Development and test
databases are at `0009_memory_expiration`.

Transactions: The route owns the existing Session transaction. A PostgreSQL
`SELECT ... FOR UPDATE` locks the target before eligibility evaluation. Updated
commits once; unchanged commits without a model write; 404 and conflicts roll
back; SQLAlchemy failures roll back and expose no internal detail. Repository
code creates no Session/engine and never commits.

Tests: Focused tests cover the new status and response literals, aware UTC time,
all timestamp-selection rules, every ineligible status, inconsistent state,
pure-policy field preservation, route commit/rollback/write behavior, migration
upgrade/downgrade/re-upgrade and unsafe-downgrade refusal, retrieval/filtering,
active-only quality candidate behavior, unchanged supersession behavior, and a
real PostgreSQL trigger-induced failure rollback. Two concurrent requests
produced exactly one `updated` and one `unchanged` with one final timestamp.
Field comparisons prove only status, `expires_at`, and `updated_at` change; the
full regression suite covers embeddings, Sources/MemorySource links, proposals,
Projects, ingestion, search, and supersession with no provider call.

PostgreSQL verification: Parsed and live identities were verified as
`second_brain` and `second_brain_test` on `127.0.0.1:5433`. Full verification
passed pip check, Ruff lint and format, strict mypy, all 504 tests with zero
skips, Alembic current and sole head `0009_memory_expiration`, Alembic check with
no new operations, and `git diff --check`.
PostgreSQL was then stopped with the documented volume-preserving script; its
container and named volume were preserved.

Smoke test: A temporary hidden Uvicorn process on `127.0.0.1:8014` returned
`health=ok` and HTTP 404 from the expiration endpoint for an all-zero missing
UUID. The exact process was stopped; the smoke made no write request.

API regression: All 504 tests passed. Creation, retrieval, structured filters,
lexical/semantic/hybrid search, quality endpoints, supersession, embeddings,
ingestion, and proposal workflows remain compatible. A past `expires_at` alone
does not change active status.

External calls: None. No provider was resolved or called.

Warnings: Existing Starlette/httpx and pytest-cache permission warnings did not
affect verification. Similarity retains its established behavior of accepting a
non-active target while selecting only active candidates; contradiction requires
an active target. Scheduled expiration remains deferred. One Full attempt after
the development upgrade encountered the known transient Windows invalid-handle
failure in database verification; a fresh required Full run passed completely.

Git status: Branch `main`; Checkpoint 31 is committed and pushed at `af9e56f`.
Checkpoint 32 changes are unstaged and uncommitted. No commit, push, or PR was
created.

Scope confirmation: Checkpoint 32 only. No scheduler, automatic timestamp
processing, retry, queue, provider call, supersession rewrite, unrelated schema
change, staging, commit, push, PR, or next-checkpoint work.
