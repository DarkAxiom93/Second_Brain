# Checkpoint 67 report

Checkpoint: 67 — Idempotency, Cancellation, Recovery, and Failure Injection.
Pending human review. Checkpoint 66 is complete at
`d4a3533282a8ed616fa0910fcea99b07b0f1b878`; its exact successful `Second Brain
CI` push run is `31959234267` (attempt 1, completed/success, zero artifacts).
Checkpoint 68 is not started.

Files changed: Agent executor/lifecycle/repository recovery behavior; private
test-only fault boundaries; explicit recovery runner and PowerShell command;
focused unit/PostgreSQL integration tests; and necessary stable documentation.

Behavior: The closed retry classes are `never`, `safe_transient_read`, and
`ambiguous_manual_recovery`. A Run has one global retry: original attempt 0 and
at most one durably reserved attempt 1. Only exact registered `read`/
`pure_read` failures `tool_timeout`, `tool_provider_unavailable`, and
`tool_provider_failed` retry automatically. Attempts remain immutable. Exact
terminal execute replay returns the durable safe projection with no writes or
Tool call. Cancellation and deadlines reconcile unfinished Steps/Invocations
under locks and discard late output. Stale detection uses each registry timeout
plus a fixed 30-second recovery grace. Recovery is an explicit synchronous
operator action for exactly one Run; scan is bounded and read-only.

API: No route was added. Existing execute and cancel routes were hardened while
preserving their safe projections and conflicts.

Database: Existing CP62 persistence is sufficient; no migration. Alembic stays
at sole/current head `0010_agent_runtime_persistence`. Registry remains
`agent-tools-v1`; Project export remains `second-brain-project-export` version 1.

Transactions: Run and child rows are locked in deterministic order for short
claim, reservation, finalization, cancellation, expiry, and recovery commits.
No lock/write transaction spans Tool/provider latency. Invocation uniqueness
and the Run lock remain final concurrency barriers.

Tests: The final acceptance audit expanded the focused suite to 31 passing cases
covering retry classification/budgets/concurrency, terminal replay, cancellation
and deadline races, durable crash boundaries, stale/ambiguous recovery,
idempotency, Project/unassigned scope, unchanged domain rows, event/revision
ordering, and lock release across Tool latency. The audit also corrected stale
classification to require exact captured registry, Step/Invocation identity,
`read` authority, and `pure_read` idempotency; impossible recovery state now
fails closed; and pre/post-Tool fault injection is no longer translated into a
controlled Tool failure.

PostgreSQL verification: Preflight verified parsed/live `second_brain` and
`second_brain_test` identities. `scripts/verify.ps1 -Mode Full` passed after the
final audit with 767 backend cases and zero skips, sole/current Alembic head and
clean autogenerate check, plus all
frontend gates.

Smoke test: The existing live API/integration route coverage is exercised by
Full verification; no paid/provider call is used.

API regression: Passed. Frontend lint/typecheck, 90 Vitest tests, and production
build also passed unchanged.

External calls: GitHub CI metadata read only. No provider call, connector,
external write, or paid call.

Warnings: Recovery is never automatic. There is no worker, scheduler, lease,
heartbeat, polling, startup recovery, Approval behavior, write/propose/execute
authority, dependency, CI, Docker, frontend, export-format, or migration change.

Git status: Checkpoint 67 changes are unstaged and uncommitted. Nothing was
staged, committed, pushed, or submitted as a PR.

Scope confirmation: Checkpoint 67 only. Checkpoint 68 was not started.
