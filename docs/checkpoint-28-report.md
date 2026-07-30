# Checkpoint report

Checkpoint: 28 — Memory duplicate and similarity detection.

Files changed: `app/memory_quality/` adds the advisory policy;
`app/repositories/memories.py` adds bounded read queries; the Memory schemas and
route add the public contract; focused unit/integration tests prove policy and
safety; README, architecture, checkpoint history, and handoff document the
capability.

Behavior: Exact duplicates and similar candidates are distinguishable. Exact
normalization strips surrounding ASCII space/tab/LF/CR/form-feed/vertical-tab
characters and collapses internal runs of those characters to a single space;
Unicode separators remain significant. Case and punctuation are preserved.
Similar candidates require
lexical token Jaccard >= 0.60 with at least three shared tokens, stored-vector
cosine similarity >= 0.85, or both. Exact results precede similar results;
semantic score, lexical score, and UUID provide deterministic tie-breaking.
Only active candidates in the target's project scope are considered, and the
target is excluded. Exact matching is queried independently and exhaustively
within that scope before the public limit. Similar discovery is approximate:
the lexical and compatible-semantic branches each use a relevance-ranked pool
of at most 250 rows. Stored semantic comparisons require matching provider,
model, and dimensions and discard undefined/non-finite cosine results.

API: `GET /memories/{memory_id}/similarities`, with `limit` default 10 and range
1..50, returns `target_memory_id` and candidates containing `memory_id`,
`classification`, nullable lexical and semantic scores, and a deterministic
reason. Missing targets return the established `404 memory not found`; invalid
limits return 422; database failures return the established generic 503. The
public limit may truncate exact duplicates when more matches exist than the
requested number; no separate completeness flag is returned.

Database: No migration or persisted result/cache. Alembic head remains
`0008_memory_proposals`.

Transactions: SELECT-only. The route does not commit, roll back, flush, or
modify any Memory, embedding, Source, proposal, or Project.

Tests: Unit coverage fixes exact-normalization and threshold policy. PostgreSQL
API coverage proves multiple exact matches, whitespace handling, lexical and
semantic similar candidates, threshold inclusion, unrelated exclusion,
self/cross-project/inactive exclusion, exact-first and UUID ordering, limits,
empty/missing/invalid responses, embedding-unavailable fallback, stored
embedding use, and full relevant-state equality before/after detection.
Adversarial additions prove exact and lexical discovery with 300 unrelated
in-scope rows, ASCII/Unicode whitespace parity, provider/model compatibility,
undefined zero-vector cosine safety, all nullable-score ordering combinations,
and bidirectional assigned/unassigned isolation.

PostgreSQL verification: `scripts/verify-databases.ps1` verified parsed and live
identity for `second_brain` and `second_brain_test` on `127.0.0.1:5433`.
`scripts/verify.ps1 -Mode Full` passed: pip check, Ruff lint/format, mypy, all
435 tests with zero skips, Alembic current/heads/check, and `git diff --check`.
Current and only head is `0008_memory_proposals`; autogenerate found no schema
changes.

Smoke test: A temporary host Uvicorn process on `127.0.0.1:8011` returned 200
from `/health` and the expected 404 from the new route for a nonexistent UUID.
It was then stopped. The smoke performed no write or cleanup request.

API regression: All 435 tests passed with zero skips. Existing CRUD, lexical,
semantic, hybrid, embedding, ingestion, proposal, health/readiness, migration,
and workflow behavior remains covered.

External calls: None. Detection has no provider dependency and tests use only
stored fake vectors.

Warnings: The requested separate attached Checkpoint 27 report was not present;
the committed Checkpoint 27 handoff, stable docs, scripts, tests, and repository
state were used. No instruction conflict required resolution.

Git status: Branch `main`; initial `HEAD` and local `origin/main` both
`afb4871feaf33252dedae0e9b504d4e051f2a7e4`. Checkpoint changes intentionally
remain uncommitted for human review. No commit, push, PR, branch switch, database
downgrade, or volume deletion occurred.

Scope confirmation: Detection only. No merge, deletion, rewrite, superseding,
expiration, archive, confidence/importance change, contradiction resolution,
proposal transition, cleanup command, background work, or provider call was
added.
