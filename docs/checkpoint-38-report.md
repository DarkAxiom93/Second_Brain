# Checkpoint report

Checkpoint: 38 — Read-Only Memory Maintenance Audit.

Files changed: Typed audit models, read-only service and repository queries,
shared controlled re-embedding stale predicate, PowerShell command, focused
unit/PostgreSQL/script tests, README, architecture, roadmap, checkpoint history,
script guide, and chat handoff.

Behavior: One audit captures a timezone-aware UTC instant and reports total,
project-assigned, and unassigned Memories; counts for active, superseded,
invalid, archived, and expired; active missing/stale embeddings; active due and
future expiration timestamps; expired rows missing `expires_at`; and embeddings
on non-active Memories. Every actionable category retains its full count while
details are bounded from 0 through 1000 IDs, ordered by `created_at` then UUID.

API: No route or public API contract was added or changed.

Database: No table, column, index, constraint, or migration changed. Alembic
current and sole head remain `0009_memory_expiration`; check reports no pending
operations. Development and test parsed/live identities are verified before
work.

Transactions: The command issues `SET TRANSACTION READ ONLY`, performs only
SELECT statements, closes the Session, and rolls back the connection. The
service and repositories never add, flush, commit, update, or delete. Before
and after PostgreSQL snapshots prove Memory and embedding fields, `updated_at`,
and Memory/embedding/Project row counts remain identical.

Tests: Focused unit and safe script checks cover status aggregation,
missing/stale/due/future/inconsistent/non-active categories, one captured
timestamp, deterministic ID ordering, detail truncation with full counts, JSON
serialization/output, PowerShell 5.1 parsing, readable summary, identity
refusal, nonzero propagation, credential non-exposure, and absence of mutation
switches. PostgreSQL coverage exercises every status, assignment counts,
current exclusion, hash/provider/model/dimension staleness, expiration
boundaries, inactive embeddings, repeat determinism, test-database identity,
and persistent before/after equality.

PostgreSQL verification: Two Full runs, including the final documented tree,
passed all 568 tests with zero skips, pip check, Ruff lint/format, strict mypy,
Alembic current/heads/check, and `git diff --check`. Both parsed and live
identities were `second_brain`/`second_brain_test` on `127.0.0.1:5433`. Current
and sole migration head is `0009_memory_expiration`.

Smoke test: The developer command is the required safe behavior check; no
Uvicorn route changed. Test-mode summary and optional JSON output succeeded.
The final development run wrote no output file and reported: total 1, assigned
1, unassigned 0; active 1 and every other status 0; active missing embedding 1;
active stale embedding, due expiration, future expiration, expired missing
`expires_at`, and non-active with embedding all 0.

API regression: The complete suite covers all existing Memory, embedding,
expiration, supersession, refinement, search, answer, evaluation, ingestion,
proposal, Source, and Project behavior.

External calls: None. The audit consumes configured identity values directly,
does not resolve an embedding provider, and makes no HTTP request.

Warnings: Staleness means canonical input hash, configured provider, configured
model, or configured dimensions differs; timestamps do not imply staleness.
Expiration due means active with non-null `expires_at` less than or equal to the
captured instant. Future means strictly later. The audit is diagnostic only,
not historical or exhaustive maintenance execution.

Git status: Branch `main` still matches `origin/main` at committed/pushed
Checkpoint 37 hash `8af0e6a`. The working tree contains only unstaged/untracked
Checkpoint 38 files. Nothing was staged, committed, pushed, or published.

Scope confirmation: Checkpoint 38 only. No API, migration, provider call,
automatic expiration/embedding/re-embedding, repair, write, scheduler, job,
telemetry, counter, ranking, frontend, staging, commit, push, PR, or next
checkpoint work was added.

Omitted headings: None.
