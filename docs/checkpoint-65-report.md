# Checkpoint report

Checkpoint: 65 — Structured Planning Provider; pending human review.

Files changed: Agent planning provider/dependencies/service, Agent Run routes and
schemas, transaction-neutral Agent repository typing/query support, focused and
PostgreSQL tests, and the approved checkpoint documentation set.

Exact 22-file inventory:

1. `app/agent_planning/__init__.py`
2. `app/agent_planning/dependencies.py`
3. `app/agent_planning/openai_provider.py`
4. `app/agent_planning/provider.py`
5. `app/agent_planning/service.py`
6. `app/api/routes/agent_runs.py`
7. `app/models/agent_runtime.py`
8. `app/repositories/agent_runtime.py`
9. `app/schemas/agent_run.py`
10. `docs/API_CONVENTIONS.md`
11. `docs/ARCHITECTURE.md`
12. `docs/CHAT_HANDOFF.md`
13. `docs/CHECKPOINTS.md`
14. `docs/KNOWN_LIMITATIONS.md`
15. `docs/ROADMAP.md`
16. `docs/V1_2_AGENT_ROADMAP.md`
17. `docs/checkpoint-65-report.md`
18. `tests/integration/test_agent_planning_api.py`
19. `tests/test_agent_planning.py`
20. `tests/test_agent_run_service.py`
21. `tests/test_memory_routes.py`
22. `tests/test_project_routes.py`

Behavior: One manually created Run can be claimed once, planned through an
application-owned configured provider, fully validated against
`agent-tools-v1`, and frozen as deterministic pending Steps. No Tool is invoked.

API: Added exactly `POST /agent-runs/{run_id}/plan` and
`GET /agent-runs/{run_id}/plan`. Existing four Agent Run contracts are unchanged.

Database: No migration or column change. Alembic current and sole head remain
`0010_agent_runtime_persistence`; Project export remains version 1.

Transactions: The planning claim commits before provider resolution/call. The
provider runs outside every database transaction and row lock. Whole-plan
validation precedes one atomic Step insertion and `ready` transition. Safe
failure finalization is atomic; cancellation or another committed transition
wins and discards a late result.

Tests: Focused unit and PostgreSQL tests cover strict JSON, deterministic fake
planning, policy/scope/provider rejection, safe projection/retrieval, replay,
failure, cancellation latency, one claimant, event/revision ordering, and zero
ToolInvocation rows. Focused verification passed 40 tests; the corrected route
inventory regression run passed 62 tests. Authoritative Full verification passed
729 backend tests and 90 frontend tests with zero failures and zero skipped
tests. `pip check`, Ruff lint and format, mypy, frontend lint, typecheck, tests,
production build, and `git diff --check` passed.

PostgreSQL verification: Parsed and live identities for `second_brain` and
`second_brain_test` were verified before integration tests. `alembic current`,
`heads`, and `check` passed with sole head `0010_agent_runtime_persistence` and
no new upgrade operations. PostgreSQL was stopped safely afterward with its
container and named volume preserved.

Smoke test: A live loopback Uvicorn process returned `status=ok` from `/health`
and the new missing-Run plan route returned 404. The exact smoke process was
stopped afterward.

API regression: OpenAPI contains the unchanged four Agent Run operations and
exactly two additive plan operations.

External calls: Authenticated GitHub preflight only. `Second Brain CI` run
`30892198522` (`push`, `main`, exact SHA
`35950c60fd842a4ad022f130a3074ce8d21d9bbc`) was completed/success on attempt 1
at https://github.com/DarkAxiom93/Second_Brain/actions/runs/30892198522 with zero
artifacts. Tests use fake providers; no paid provider call occurred.

Warnings: Three existing Starlette deprecation warnings remain; no warning was
ignored as a failure. Checkpoint 64 is complete at
`35950c60fd842a4ad022f130a3074ce8d21d9bbc`; Checkpoint 65 is pending human
review; Checkpoint 66 is not started. No executor, UI, Approval execution,
Automation, worker, scheduler, or connector exists.

Git status: Changes remain unstaged and uncommitted.

Scope confirmation: No migration, dependency/lockfile, frontend, CI, Docker,
export format, Tool handler/executor, ToolInvocation reservation, scheduler,
worker, connector, authentication, or remote/multi-user change was made.
