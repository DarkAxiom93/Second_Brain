# Checkpoint report

Checkpoint: 37 — Controlled Batch Memory Re-Embedding

Files changed: re-embedding schemas, route, service, and SQL repository
primitives; focused schema/route and PostgreSQL tests; route inventories;
README, architecture, roadmap, checkpoint history, and handoff documentation.

Behavior: `POST /memory-embeddings/reembed` explicitly selects at most 50 active
Memories with existing embeddings. Project, unassigned, and all scopes are
supported. `stale` compares the canonical input hash and configured provider,
model, and dimensions; `all` is a forced replacement selection. Timestamps do
not imply staleness. Missing embeddings and non-active Memories are ineligible.

API: Extra fields are rejected. Project scope requires `project_id`; other
scopes forbid it. Limit defaults to 20 with range 1–50. HTTP 200 reports
completed or empty status, selected/updated/unchanged/skipped counts, and
candidate-ordered items with previous and current metadata but no vectors.
Allowed skips are `memory_not_active` and `embedding_missing`.

Database: SQL applies scope, active/existing eligibility, stale criteria,
creation-time/UUID order, and limit. Unknown projects naturally return empty
without a Project query. Replacement updates the existing row and preserves its
ID, `memory_id`, `created_at`, Memory, and provenance data. No model or migration
changed; Alembic remains `0009_memory_expiration`.

Transactions: Empty selection resolves no provider and writes or commits
nothing. Non-empty selection uses one canonical-order provider batch. All output
is count-, dimension-, type-, and finite-value-validated before deterministic
Memory and embedding locks. Eligibility is rechecked under lock. Updates flush
in one transaction and commit once; unchanged-only outcomes write nothing.
Provider, malformed-output, and database failures roll back the complete batch.

Tests: Focused tests cover request validation, unknown fields, limits, empty
selection, provider bypass, route registration, canonical input reuse, and
existing batch compatibility. PostgreSQL coverage verifies stale detection,
forced-all exact-result unchanged behavior, active/existing eligibility,
deterministic selection, one provider call, metadata replacement, and embedding
identity/creation-time preservation. The Full suite supplies provider-output,
single-Memory embedding, retrieval, answers, evaluation, and persistence
regressions.

PostgreSQL verification: `scripts/verify.ps1 -Mode Full` passed with 562 tests
and zero skips. Parsed and live development/test database identities were
verified. Pip check, Ruff lint/format, mypy, Alembic current/heads/check, and
`git diff --check` passed. Current and sole head is
`0009_memory_expiration`; no migration exists.

Smoke test: A live Uvicorn request used project scope, a newly generated unknown
project UUID, and stale selection. It returned HTTP 200 with `batch_status`
`empty`, all counts zero, and no items. The empty path did not resolve a
provider, created no data, and required no cleanup.

API regression: Full lexical, semantic, hybrid, answers, evaluation,
single-Memory embedding, missing-embedding batch, ingestion, proposal,
Memory-quality, Source, and Project tests passed unchanged.

External calls: None. Automated tests use deterministic fake providers, and the
smoke selection was empty. No live or paid provider request occurred.

Warnings: One existing Starlette/httpx deprecation warning remains. The current
limit is 50; execution is synchronous and explicitly requested. Jobs, histories,
retries, scheduling, queues, automatic processing, and missing-embedding
generation remain outside this endpoint.

Git status: Working tree contains only unstaged Checkpoint 37 changes. Nothing
was staged, committed, pushed, or published.

Scope confirmation: Checkpoint 37 only. No migration, new provider/model request
override, Memory mutation, missing-embedding creation, ranking change,
background job, queue, advisory lock, retry, CLI, frontend, or later-checkpoint
capability was added.

Omitted headings: None.
