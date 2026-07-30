# Checkpoint report

Checkpoint: 31 — Explicit Memory Superseding Workflow.

Files changed: Memory schemas add the focused request/result contract;
`app/memory_quality/supersession.py` classifies transitions and conflicts; the
Memory repository adds locking, ancestry traversal, and the two-field
transition; the Memory route adds the endpoint; focused unit and PostgreSQL
tests cover validation, state, conflicts, chains, and concurrency; README,
architecture, checkpoint history, and handoff document the capability.

Behavior: `POST /memories/{memory_id}/supersede` treats the path UUID as the
older Memory and `replacement_memory_id` as the existing replacement. The first
valid request sets `replacement.supersedes_id` to the older UUID, changes the
older status from `active` to `superseded`, preserves replacement status as
`active`, and returns `updated`. An exact consistent repeat returns `unchanged`
without a model write or timestamp change. Both rows must initially be active,
distinct, and in equal nullable project scope. No content, structured metadata,
provenance, proposal, or embedding is copied or rewritten, and contradiction
detection never invokes the workflow automatically.

API: Request body is the extra-forbidden typed
`{"replacement_memory_id": UUID}`. HTTP 200 returns `supersession_status`, a
complete `superseded_memory: MemoryRead`, and a complete
`replacement_memory: MemoryRead`. Exact public 404s distinguish `older memory
not found` and `replacement memory not found`. Exact 409 details distinguish
self-superseding, scope mismatch, ineligible status, a replacement already
linked to another predecessor, an older Memory already having another
replacement, cycles, and inconsistent existing state. SQLAlchemy failures use
the generic `database unavailable` 503 without internal details.

Database: No migration or schema change. Alembic current and sole head remain
`0008_memory_proposals`; `alembic check` found no upgrade operations.

Transactions: The API route owns the Session transaction. Repository functions
reuse that Session, never commit, and expose SQLAlchemy exceptions. Requested
rows are locked with PostgreSQL `FOR UPDATE` in ascending UUID order. Holding
the older lock serializes the direct-successor `FOR UPDATE` query before the
one-successor decision. The route commits once for `updated`; `unchanged` may
commit once but makes no model write. Expected conflicts and database failures
roll back, so status and relationship cannot partially persist.

Chain and cycle policy: Acyclic chains such as `A <- B <- C` are valid. Before
transition, a recursive CTE follows the older Memory's complete predecessor
ancestry with set semantics and no shallow depth limit. Finding the proposed
replacement rejects direct or indirect cycles. Existing chains are never
rewritten, and inconsistent pre-existing states are conflicts rather than
automatic repairs.

Tests: Focused schema/policy/route tests cover strict request/response
validation, self-rejection, nullable-project equality, exact unchanged state,
conflict classification, generic database failure, and rollback/commit rules.
PostgreSQL tests prove the active-to-active transition, complete response state,
field preservation, stored status/link state, timestamp-stable idempotency,
both missing rows, self/scope/inactive/predecessor/successor conflicts, valid
multi-level chains, direct and indirect cycle rejection, and real concurrent
identical and competing requests. Existing full-suite tests retain creation,
retrieval, lexical/semantic/hybrid search, similarity, contradiction,
embedding, ingestion, Source/MemorySource, and proposal behavior.

Concurrency results: Two simultaneous identical requests produced exactly one
`updated` and one `unchanged`, with one persisted relationship. Two simultaneous
different replacements produced one HTTP 200 winner and one HTTP 409 loser,
with exactly one persisted successor and no overwrite.

PostgreSQL verification: Parsed and live identities were verified as
`second_brain` and `second_brain_test` on `127.0.0.1:5433`. Full verification
passed pip check, Ruff lint and format, strict mypy, all 482 tests with zero
skips, Alembic current/heads/check, and `git diff --check`. PostgreSQL was then
stopped with the documented volume-preserving script; the container and named
volume were preserved.

Smoke test: A temporary hidden Uvicorn process on `127.0.0.1:8013` returned 200
from `/health` and the exact `404 older memory not found` response from the new
route for nonexistent UUIDs. The exact process was stopped afterward. The smoke
performed no database write or cleanup request.

API regression: All 482 tests passed with zero skips. Similarity and
contradiction endpoints remain read-only, and existing search and workflow
behavior remains compatible.

External calls: None. No provider was resolved or called.

Warnings: The existing Starlette/httpx deprecation warning and a sandbox-related
pytest cache write warning appeared without affecting verification. The
one-successor invariant is transactionally enforced in this checkpoint and has
no new unique database constraint. Legacy inconsistent supersession state is
reported, not repaired.

Git status: Branch `main`; Checkpoint 30 was committed and pushed at `86245e2`
before work began. Checkpoint 31 changes remain unstaged and uncommitted for
human review. No commit, push, PR, migration, database downgrade, or volume
deletion occurred.

Scope confirmation: Checkpoint 31 only. No automatic contradiction resolution,
automatic superseding, content/metadata/provenance/embedding rewrite, migration,
new service/framework, staging, commit, push, PR, or Checkpoint 32 work.
