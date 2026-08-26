# Checkpoint 80 report - Automatic read-only scheduled Agent execution

Status: **Approved and complete after human review.**

## Outcome and safety boundary

Checkpoint 80 adds a reusable coordinator for an exact already-linked
`automatic_read_only` occurrence. It revalidates the Automation revision and
lifecycle fence, occurrence identity, unique linked Run, Agent identity and
scope, fixed code-owned definition, read authority, dedicated non-empty Tool
allowlist, Tool Registry and Run policy identities, Project existence, and Run
deadline/cancellation state. Catalog membership alone grants nothing.

`IMPLEMENTED_AUTOMATION_AGENT_IDENTITIES` and the production definition map
remain empty. Consequently `daily_brief` and `project_watch` remain reserved,
persisted automatic placeholders remain inert, generic Research is not
scheduled, and normal production ticks perform zero provider or Tool work.
Tests inject an exact fixed read-only definition without installing a
production placeholder.

## Reusable Run orchestration and transactions

`app.agent_runs.orchestration` composes the existing planning claim,
provider-context construction, complete-plan validation, atomic plan freeze,
execution claim, per-Step reservation/dispatch/finalization, retry classifier,
deadline/cancellation reconciliation, and terminal completion services. The
Automation coordinator does not call FastAPI routes or use internal HTTP and
does not create an Automation-specific Tool path.

The coordinator uses three phases: a short Automation/occurrence/Run validation
transaction in Automation-occurrence-Run lock order; ordinary Run planning and
execution transactions with every provider/Tool call outside locks; and a
short occurrence reconciliation transaction. The occurrence never owns
execution, no replacement Run is created, terminal replay is write-free at the
Run boundary, and the scheduler never invokes the manual recovery command.

## Execution-mode API

`POST /automations/{automation_id}/execution-mode` accepts only
`expected_revision` and the closed execution mode. `create_only` is allowed
unless the Automation is cancelled. `automatic_read_only` requires the exact
implemented automatic-safe definition. Stale revisions conflict; cancellation
fails closed; success atomically increments only the Automation revision. It
does not increment `schedule_revision` and creates no occurrence or Run.
Create and generic update also reject attempts to persist a newly selected
unimplemented automatic identity, while historical rows remain readable.

## Failure and mutation proof

Definition, authority, allowlist, registry, policy, lifecycle/revision, linked
Run, scope/Project, deadline, and cancellation mismatches fail before planning.
Existing plan validation and Tool policy reject catalog drift, invalid plans,
authority widening, unsupported Tools, and scope changes. Existing Agent Run
semantics remain authoritative for provider/Tool failures and ambiguous
outcomes; neither automatic setup nor execution invokes manual recovery,
chooses another Agent, widens scope, approves anything, or creates another Run.

Focused PostgreSQL coverage snapshots Projects, Memories, Sources, source
chunks, Memory proposals, and Approval Requests around injected automatic
execution and proves their counts are unchanged. The same test proves one
planning call, one Step, one Tool invocation, exact linked-Run reuse, terminal
reconciliation, and replay without a second Run. Curator/proposal/Approval
execution and generic Research scheduling remain absent.

## Changed paths

The approved Checkpoint 80 change contains exactly these 20 paths:

- `app/agent_planning/service.py`
- `app/agent_runs/executor.py`
- `app/agent_runs/orchestration.py`
- `app/api/routes/automations.py`
- `app/automations/catalog.py`
- `app/automations/coordinator.py`
- `app/automations/scheduler.py`
- `app/automations/scheduler_runner.py`
- `app/automations/service.py`
- `app/repositories/automations.py`
- `app/schemas/automation.py`
- `docs/ARCHITECTURE.md`
- `docs/CHECKPOINTS.md`
- `docs/ROADMAP.md`
- `docs/checkpoint-80-report.md`
- `tests/integration/test_automation_api.py`
- `tests/integration/test_automation_coordinator.py`
- `tests/test_automation_catalog.py`
- `tests/test_memory_routes.py`
- `tests/test_project_routes.py`

## Verification

The first Full run reached **1015 passed, zero skipped** and exposed two route
inventory assertions that correctly required the new explicit endpoint. Those
assertions were updated. The final Automation-focused set comprises **43 tests,
zero skipped** across catalog, API, scheduler/recovery, coordinator, replay, and
protected-mutation coverage. The final authoritative Full run passed:

- pip check, Ruff lint/format, and strict mypy passed;
- backend: **1017 passed, zero skipped** (11 warnings in the final audit run);
- frontend: **124 passed across 11 files, zero skipped**;
- frontend ESLint, TypeScript, Vitest, and production Vite build passed;
- Alembic current and sole head: `0011_automation_persistence`;
- Alembic check: no new upgrade operations detected; and
- `git diff --check`: passed.

- Alembic remains `0011_automation_persistence`; no migration was added.
- Tool Registry remains `agent-tools-v1`; no Tool was added.
- Project export remains `second-brain-project-export` version `1`.
- The 32 nonterminal Agent Run capacity and read-only maximum automatic
  authority remain unchanged.
- No Daily Brief or Project Watch definition was implemented.
- Checkpoint 81 UI/notification work was not started.

Checkpoint 80 is approved and complete after human review. Checkpoint 81 was
not started.
