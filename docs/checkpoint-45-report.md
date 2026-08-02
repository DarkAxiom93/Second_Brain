# Checkpoint report

Checkpoint: 45 — Document Ingestion and Document Browser UI.

Files changed: Minimal SourceDocument/SourceChunk read schemas, repository queries,
routes, focused backend tests, typed frontend API functions, ingestion/document
screens and tests, routing/styles, architecture, roadmap, checkpoint ledger,
handoff, and this report.

Behavior: Source detail exposes an accessible ingestion action and paginated real
document list. JSON text, TXT, and PDF use the existing ingestion writes exactly.
Successful validated responses navigate to document detail. Document detail shows
public metadata and paginated chunk evidence; chunk content appears only there.

API: Existing writes remain unchanged. Added `GET /sources/{source_id}/documents`,
`GET /source-documents/{document_id}`, and
`GET /source-documents/{document_id}/chunks`. Lists use validated bare-array
`limit`/`offset` pagination. Missing responses and generic database errors follow
the checkpoint contract; malformed UUIDs retain FastAPI validation.

Database: No migration or model change. Alembic remains
`0009_memory_expiration`. Reads use deterministic SQL ordering and exclude
unrelated rows.

Transactions: New endpoints are read-only with no commit, flush, mutation, or
provider resolution. Existing ingestion retains its route-owned transaction.

Tests: Focused backend (72 affected route tests) and frontend tests cover route contracts, scoping,
pagination, formats, validation, exact requests, duplicate prevention, strict
payload validation, navigation, safe failures, accessibility, and cancellation.
Full verification passed pip check, Ruff lint/format, mypy, all 630 Python tests
with zero skips, Alembic current/heads/check, ESLint, TypeScript, all 42 Vitest
tests, the production Vite build, and `git diff --check`.

PostgreSQL verification: Full verification validated parsed and live identities
for `second_brain` and isolated `second_brain_test` at `127.0.0.1:5433`.
Integration tests ran without skips; development was not downgraded and the
Docker volume was preserved.

Smoke test: Hidden FastAPI and Vite processes served the current application
through `http://127.0.0.1:5173`. Proxy health returned `ok`; the development
database contained no Source, so the Source/document empty path was verified and
existing-document rendering could not be exercised against development data.
Valid missing document returned 404, malformed document UUID returned 422, and
`/proposals` remained a 200 placeholder. Focused browser tests verify ingestion
screen rendering, local empty/unsupported validation, and populated document/chunk
rendering. Smoke used GET requests only: no application row was created, updated,
or deleted, and no provider or CORS behavior was involved. FastAPI and Vite were
stopped; PostgreSQL was stopped afterward with its named volume preserved.

API regression: Existing Source creation/ingestion, Memory, Project, proposal,
and all unrelated behavior passed the complete suite.

External calls: None. No provider is resolved or called.

Warnings: The Checkpoint ledger at the start still called Checkpoint 44 in progress,
but clean `main`, `origin/main`, and HEAD all matched committed Checkpoint 44
`892791f`; the ledger is corrected here.

Git status: Checkpoint changes are unstaged and uncommitted on `main`; final
status was inspected after service cleanup. No staging, commit, push, or PR.

Scope confirmation: Checkpoint 45 only. No OCR, new format, queue, polling,
replacement/deletion/editing, proposal UI, provider call, migration, dependency,
CORS, persistence, or second request layer. No report headings omitted.
