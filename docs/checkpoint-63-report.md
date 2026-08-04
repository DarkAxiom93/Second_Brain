# Checkpoint report

Checkpoint: 63 - Agent Run State Machine and API (pending human review)

Files changed: exactly 18 changed or untracked files:

1. `app/agent_runs/__init__.py`
2. `app/agent_runs/service.py`
3. `app/api/router.py`
4. `app/api/routes/agent_runs.py`
5. `app/repositories/agent_runtime.py`
6. `app/schemas/agent_run.py`
7. `docs/API_CONVENTIONS.md`
8. `docs/ARCHITECTURE.md`
9. `docs/CHAT_HANDOFF.md`
10. `docs/CHECKPOINTS.md`
11. `docs/KNOWN_LIMITATIONS.md`
12. `docs/ROADMAP.md`
13. `docs/V1_2_AGENT_ROADMAP.md`
14. `docs/checkpoint-63-report.md`
15. `tests/integration/test_agent_run_api.py`
16. `tests/test_agent_run_service.py`
17. `tests/test_memory_routes.py`
18. `tests/test_project_routes.py`

These are limited to Agent Run schemas/service/routes, transaction-neutral
repository additions, router registration, focused unit/PostgreSQL/API tests,
existing OpenAPI inventories, and approved Checkpoint 63 documentation. No
migration, dependency, lockfile, CI, Docker, frontend, export/import, provider,
Tool, Approval execution, worker, scheduler, connector, or authentication file
changed.

Behavior: Adds manual create, retrieve, list, and cancellation only. The exact
internal matrix is `created -> planning|cancelled|expired`, `planning ->
ready|failed|cancelled|expired`, `ready -> running|cancelled|expired`, `running
-> running|awaiting_approval|completed|failed|cancelled|expired`, and
`awaiting_approval -> running|failed|cancelled|expired`; terminal states have no
successors. Expiry is an explicit deadline-checked transition.

API: Exactly `POST /agent-runs`, `GET /agent-runs`, `GET
/agent-runs/{run_id}`, and `POST /agent-runs/{run_id}/cancel`. Public responses
use the explicit safe Run projection and expose no hashes, correlation identity,
events, children, metadata, prompts, payloads, secrets, SQL, or exceptions.

Database: No schema change. Alembic current and sole head remain
`0010_agent_runtime_persistence`; Project export remains
`second-brain-project-export` version 1. Checkpoint 62 is complete at
`3da0cdd875dc8af7a60fd8af5b6f9878be5a769a`.

Transactions: Routes own commit/rollback; services and repositories never
commit. Creation/cancellation and their events share one transaction. Run row
locks, expected state/revision checks, monotonic revisions and event sequences,
and the unique idempotency hash serialize competing operations. Only the hash of
the raw key is stored. Exact canonical-payload replay returns the original Run;
changed reuse conflicts.

Tests: Focused verification passed: 15 tests, zero skipped. Full verification
passed: 697 backend tests and 90 frontend tests, zero skipped; pip check, Ruff
lint/format, mypy, Alembic current/heads/check, frontend lint/typecheck/build,
and `git diff --check` passed.

PostgreSQL verification: Both parsed/live identities were verified before work.
Real PostgreSQL tests cover atomic rollback, exact/changed/concurrent
idempotency, scope/list behavior, cancellation replay, event count/content, and
expiry boundaries. Alembic current and sole head were both confirmed as
`0010_agent_runtime_persistence`, and autogenerate found no schema change.
PostgreSQL was stopped safely afterward; its container and named volume were
preserved.

Smoke test: A live loopback Uvicorn smoke against the verified
`second_brain_test` database exercised create, retrieve, unassigned list, and
cancel successfully. Cleanup verified the exact captured Run identity and exact
two-event count, removed only those rows, and rechecked success.

API regression: Existing route inventories were updated only for the exact
three new paths/four operations; the complete suite passed.

External calls: One authenticated, read-only GitHub lookup verified `Second
Brain CI` run 30881615278 at
https://github.com/DarkAxiom93/Second_Brain/actions/runs/30881615278: workflow
`Second Brain CI`, event `push`, branch `main`, exact SHA
`3da0cdd875dc8af7a60fd8af5b6f9878be5a769a`, completed, success, attempt 1,
zero artifacts. No provider or Tool call occurred.

Warnings: The Checkpoint 62 constraint requires every terminal Run to have a
non-null `started_at`. For the legal direct `created -> cancelled|expired`
transitions, the service therefore captures `started_at` and `finished_at` at
the same operation instant. This preserves the safer existing database rule
without the forbidden migration change.

Git status: All changes remain unstaged and uncommitted. No commit, push, tag,
Release, or PR was created.

Scope confirmation: Checkpoint 63 only, pending human review. Checkpoint 64 is
not started. No planning, Tool Registry, execution, Agent UI, Approval execution,
Automation, provider, worker, scheduler, connector, external write, or
authentication behavior exists.
