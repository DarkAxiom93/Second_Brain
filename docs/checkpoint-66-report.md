# Checkpoint 66 report

Checkpoint: 66 — Bounded Read-Only Executor. Human review approved; complete at
`d4a3533282a8ed616fa0910fcea99b07b0f1b878`. Checkpoint 65 is complete at
`1b32d91e62feb10efd5c2f2c241ee43b75b5b5e2`.

Files changed: Agent execution coordinator, exact dispatch/read wrappers,
Agent Runtime repository primitives, public execution schemas/routes, focused
unit and PostgreSQL integration tests, and the minimum stable Agent architecture,
roadmap, API, checkpoint, and handoff documentation.

Behavior: A complete frozen `ready` plan is claimed synchronously, then executed
strictly by ascending Step ordinal with one attempt-zero ToolInvocation per Step.
Each invocation revalidates Checkpoint 64 policy from persisted state, reserves
and commits before Tool latency, calls outside the Run lock/write transaction,
and finalizes in a new short transaction. Only exact version-1 `project.get`,
`memory.get`, `memory.search_explained`, `source.get`, and `source_chunk.get`
dispatch. `operations.diagnostics` and `maintenance.audit` remain denied. All
reads re-enforce exact Project or explicit unassigned scope. Validated output is
size-bounded and reduced to an allowlisted summary plus typed evidence IDs; raw
Tool/provider output and exception text are not persisted.

API: Added exactly `POST /agent-runs/{run_id}/execute` with only
`expected_revision`, and `GET /agent-runs/{run_id}/execution`. The execution
projection contains the existing safe Run projection and ordered allowlisted
Step/invocation summaries. No generic transition or child-entity API was added.

Database: No migration. Sole Alembic head remains
`0010_agent_runtime_persistence`. Registry remains `agent-tools-v1`. Project
export remains `second-brain-project-export` version 1.

Transactions: Claim, reservation, finalization, and completion each use short
caller-owned transactions. No Run lock or write transaction spans Tool/provider
latency. A late result rechecks the locked Run and is discarded rather than
advancing a non-running Run.

Tests: Focused unit tests cover exact dispatch inventory, case/version/aggregate
denial, all five wrappers, strict input/output behavior, nullable scope,
provider-free lexical search, and safe summary/evidence reduction. PostgreSQL
tests cover successful ordered multi-Step execution, one claimant, committed
`running` state and an available Run lock during Tool latency, one reservation
per Step, controlled failure stopping later Steps, and bounded projections.
Final Full verification results are recorded below after completion.

PostgreSQL verification: `scripts/verify.ps1 -Mode Full` passed with 739 tests,
zero skips, `alembic current`, `heads`, and `check` all green at sole head
`0010_agent_runtime_persistence`. PostgreSQL was stopped afterward with
`docker compose --env-file .env.example stop db`; the container and named
volume were preserved.

Smoke test: A hidden loopback Uvicorn process served `/openapi.json` and exposed
both exact execution routes; it was stopped immediately afterward. FastAPI
TestClient also exercised successful, failed, and concurrent execution.

API regression: Existing Agent Run and planning operations remain present; the
OpenAPI inventory now contains exactly the two approved execution operations in
addition to the prior six operations.

External calls: Preflight verified successful GitHub Actions run `31950242783`
(`Second Brain CI`, push to `main`, SHA
`ad3c143a568be7c09a73b170f2b5be6347a27a40`, attempt 1). Tests use fake
providers and no paid provider call. The security remediation base is
`ad3c143a568be7c09a73b170f2b5be6347a27a40`. The final npm security audit was
attempted but the registry connection reset, so no new audit result was
available; the exact required CI gate's successful audit remains the reachable
security evidence for this base.

Warnings: Checkpoint 66 deliberately adds no retry, stale-run detector,
recovery command, worker, scheduler, lease, propose/execute authority, write
Tool, connector, dependency, Docker, CI, frontend, migration, or export-format
change. Those recovery concerns remain for Checkpoint 67.

Final lifecycle: Committed as
`d4a3533282a8ed616fa0910fcea99b07b0f1b878`, pushed to `origin/main`, and
validated by successful `Second Brain CI` push run `31959234267`.

Scope confirmation: Checkpoint 66 only. Checkpoint 67 subsequently completed at
`7b6c6bb8c4c67f9e8a5a34c363331bc94dbb094e`; Checkpoint 68 is not started.
