# Checkpoint report

Checkpoint: 51 — Controlled Project Export and Import UI.

Files changed: Operations routes and schemas, typed frontend API client,
Settings workflows, focused backend/frontend tests, stable architecture/API/
export documentation, checkpoint history, and this report.

Behavior: `/settings` provides explicit paginated Project export, raw bundle
validation, safe plan review, exact UUID confirmation, and irreversible
conflict-free execution. File replacement invalidates the plan. Actions are
single-flight, cancellable where safe, never persisted, and never retried
automatically.

API: Added only `POST /operations/project-exports/{project_id}`, `POST
/operations/project-imports/validate`, and `POST
/operations/project-imports/execute`. Each requires direct loopback and a
distinct exact operation header, ignores forwarding headers, returns
`Cache-Control: no-store`, and exposes only safe typed data. Export streams one
attachment; import bodies stream raw with the established archive-size limit.
Every request removes only its exact temporary bundle or upload.

Database: No schema, migration, model, format, or import semantic changed.
Alembic remains `0009_memory_expiration`.

Transactions: Export uses the established repeatable-read, database-enforced
read-only snapshot. Validation is read-only and never flushes or commits.
Execution requires and revalidates the exact manifest Project UUID and bundle
SHA-256, repeats target conflict checks, calls the established atomic service,
and commits exactly once. Every error rolls back the complete transaction; the
no-conflict, no-overwrite, no-remap, and no-partial-import guarantees remain.

Tests: Focused route coverage passed for direct-loopback and exact-header
protection, safe streamed attachment headers and cleanup, conflict plan shaping,
and exactly-once commit behavior. Authoritative Full verification passed 639
Python tests and the then-current 75 frontend tests, with zero skips. After
adding final focused UI workflow coverage, frontend verification passed all 78
tests plus lint, TypeScript, and production build.

PostgreSQL verification: Parsed and live development/test identities were
verified as `second_brain` and `second_brain_test`. Alembic current and sole head
were `0009_memory_expiration`; `alembic check` found no new upgrade operations.

Smoke test: Passed through `http://127.0.0.1:5173`. `/settings` returned 200.
Existing Project `b7fc847d-21ed-4507-aacc-834297730a75` produced one non-empty
bundle with the reviewed media type, `no-store`, and `nosniff`. Validation of
the same bundle returned valid but not importable with one target conflict.
Safe aggregate counts were identical before and after. Execute was not invoked.
The exact bundle and exact API/Vite processes were removed/stopped; PostgreSQL
was stopped with its container and named volume preserved.

API regression: Full verification passed pip check, Ruff lint/format, strict
mypy, all Python tests, Alembic checks, frontend ESLint/TypeScript/Vitest/build,
and `git diff --check`.

External calls: None. Export/import do not resolve a provider. No CORS behavior
changed.

Warnings: Version 1 bundles contain private data and are not encrypted. There
is no merge, overwrite, remap, repair, partial import, history, or automatic
restore. Checkpoint 50 documentation described its pre-commit state even though
Git proved `main` and `origin/main` matched its commit `c9112a5`; Checkpoint 51
corrects the history according to the explicit prerequisite and repository
state.

Git status: Checkpoint 51 changes remain unstaged and uncommitted. Nothing was
staged, committed, pushed, published, or opened as a PR.

Scope confirmation: Checkpoint 51 only. No dependency, migration, format,
provider, persistence, merge/overwrite/remap/repair mode, staging, commit, push,
PR, or later-checkpoint work was added.

Omitted headings: None.
