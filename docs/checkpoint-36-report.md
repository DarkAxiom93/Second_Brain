# Checkpoint report

Checkpoint: 36 — Explicit Batch Memory Embedding Generation

Files changed: embedding provider protocol/OpenAI adapter; batch route, schemas,
service, and repository; focused unit/PostgreSQL tests; route inventories; README,
architecture, roadmap, checkpoint history, and handoff documentation.

Behavior: `POST /memory-embeddings/batch` explicitly selects at most 50 active
Memories missing embeddings in `created_at`, UUID order. Project, unassigned,
and all scopes are supported. Existing embeddings are excluded and never
replaced. Empty selection returns an empty result without provider resolution.

API: Extra fields are rejected. Project scope requires `project_id`; other
scopes forbid it. Limit defaults to 20 with range 1–50. HTTP 200 reports batch
status; selected, created, unchanged, and skipped counts; and candidate-ordered
items. Items expose the existing public metadata fields but never vectors.

Database: SQL applies active/missing filters, scope, deterministic ordering, and
limit. Unknown project UUIDs naturally return empty without a Project existence
query. No model or migration changed; Alembic remains
`0009_memory_expiration`.

Transactions: Provider execution occurs before row locking. After complete
output validation, selected Memory rows lock in UUID order and status/embedding
state is rechecked. PostgreSQL conflict-safe inserts make concurrent winners
`unchanged`; newly non-active rows are `skipped` with `memory_not_active`.
Created rows commit once as one transaction; empty/no-create outcomes do not
commit. Provider, validation, and database failures roll back the batch.

Tests: Focused schema coverage verifies scope/project combinations, unknown
fields, and limits. The focused route test verifies the exact empty response,
provider bypass, and absence of a commit. Existing provider validation tests
cover dimensions and finite values. Real PostgreSQL batch coverage verifies
active/missing selection, all-scope SQL order/limit, canonical hash and provider
metadata, preservation of an existing embedding, and empty project,
unassigned, and project follow-up selections without an additional provider
call. The Full suite supplies the stated API and retrieval regressions.

PostgreSQL verification: Full verification passed with 554 tests and zero
skips. Parsed and live development/test identities were verified. Ruff lint and
format, mypy, pip check, Alembic current/heads/check, and `git diff --check` all
passed. Alembic current/head is `0009_memory_expiration`; no migration exists.

Smoke test: A live in-process Uvicorn request used project scope with a new
unknown UUID and a dependency override that raises if provider resolution is
attempted. It returned HTTP 200 with `batch_status=empty`, every count zero, and
an empty item list. The provider was not resolved, no row was created, and no
cleanup was required.

API regression: Full lexical, semantic, hybrid, answer, evaluation, single
Memory embedding, ingestion, proposal, Memory-quality, Source, and Project tests
passed unchanged.

External calls: None. Automated tests use deterministic fake providers; the
smoke path resolves no provider. No live or paid provider request occurred.

Warnings: One existing Starlette/httpx deprecation warning remains. Controlled
re-embedding, stale detection, retrying, scheduling, queues, and background
processing remain deferred.

Git status: Working tree contains only unstaged Checkpoint 36 changes. Nothing
was staged, committed, pushed, or published.

Scope confirmation: Checkpoint 36 only. No migration, replacement/re-embedding,
ranking/retrieval change, background job, CLI, frontend, provider/model request
override, distributed lock, retry, or later-checkpoint capability was added.

Omitted headings: None.
