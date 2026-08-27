# Checkpoint 82 report - Daily Brief Agent v1

Status: **Approved and complete after human review.**

## Outcome and activation boundary

Checkpoint 82 installs exactly `("daily_brief", "1")` as the sole production
Automation Agent identity. It is fixed, application-owned, scheduled-only, and
read-only. `project_watch` remains reserved and unimplemented; Research and
Memory Curator remain manual; no proposal or Approval execution is schedulable.
Checkpoint 83 was not started.

The immutable definition captures authority `read`, registry
`agent-tools-v1`, planning contract `daily-brief-planning-v1`, synthesis
contract `daily-brief-claims-v1`, exact Project-or-explicitly-unassigned scope,
versioned evidence rules, maximum 20 evidence items, five claims, and twenty
citations. Its dedicated allowlist is `project.get`, `memory.get`,
`memory.search_explained`, `source.get`, and `source_chunk.get`, all version 1.
Catalog membership grants no authority.

## Fixed construction, evidence, and synthesis

Scheduler-created Daily Brief Runs use a code-owned goal based only on captured
nullable scope. The editable Automation label never enters the goal, planning
context, or synthesis input. The public manual Run route explicitly rejects the
exact Daily Brief identity.

Evidence identity and deterministic current version are captured inside the
existing Tool handler read. Collection binds each item to its exact Run, Step,
and Invocation. Persistence re-locks the Run and revalidates ownership,
successful invocation, entity existence, exact nullable scope, and current
version. Deleted, stale, or out-of-scope evidence fails closed. Source and chunk
evidence must be connected to a reviewed Memory in the exact scope. Drafts,
pending proposals, Approval mutations, secrets, provider payloads, unrelated
Projects, external systems, and write paths are unavailable.

The architecture remediation audited raw `AgentEvent`, `AutomationOccurrence`,
`AutomationNotification`, `MemoryExtractionRun`, and `MemoryProposal` stores.
Raw Agent events can contain synthesis metadata and generic runtime audit facts;
notifications lack direct scope and intentionally contain no result evidence;
extraction runs expose provider/model identity and are coupled to draft proposal
work; proposals contain unreviewed model content and mutation-review state.
None is admitted directly.

Terminal `AutomationOccurrence` is the safe existing representation. It already
captures exact nullable Project scope and a durable UUID. A Daily Brief-only
projection admits only completed, missed, failed, and cancelled terminal kinds;
selects at most five rows by `completed_at DESC, id DESC`; and exposes only the
code-owned event kind, occurrence UUID/version, completion/schedule timestamps,
and fixed Agent kind/version. It excludes the editable label, occurrence key,
lease fields, attempts, notifications, Run/Tool/provider data, prompts, raw
errors, proposals, and Approvals. The projection version is a SHA-256 digest of
those safe fields and is recomputed with exact scope before result persistence.
It consumes the existing overall 20-item evidence cap and citations use entity
type `application_event`. No raw `AgentEvent` access or generic event authority
was added.

The closed result contains at most five claims citing only supplied `eN`
evidence labels, or `insufficient_evidence`. Application validation maps labels
to at most twenty captured public identities and rejects forged, unknown,
duplicate, stale, deleted, or out-of-scope evidence. Public result JSON is
bounded to 3,500 bytes. Instructions treat all local content as untrusted data
and deny embedded attempts to change goal, scope, Tool, authority, citations,
external access, proposals, Approvals, or mutation.

## Coordinator, notification, API, and UI

Checkpoint 80 coordination still reuses the one exact linked Run and ordinary
planning/execution reservation state machines. Locks and transactions end
before planning-provider, Tool, and synthesis-provider latency. Minimal evidence
capture and synthesis hooks extend the existing read-only orchestration; replay
never creates a replacement Run.

A `run_completed` notification is inserted only when the linked Run completed
successfully with a persisted Daily Brief result. Its code-owned title/body
contain status/navigation copy only. Database uniqueness deduplicates the
occurrence/event key; no claim, citation, evidence, model/Tool/provider output,
or content is stored in the notification.

The UI identifies Daily Brief v1 as implemented, keeps draft `create_only` as
the creation default, exposes an explicit automatic-read-only switch only for
Daily Brief, displays exact Project or explicitly unassigned scope, renders the
safe linked-Run result and insufficient-evidence state, and keeps Project Watch
visibly unavailable.

## Mutation and stable-boundary proof

Automatic work can mutate only Agent Runtime rows, Automation occurrence state,
and safe notification state. The dedicated policy is `read`; the five dispatch
handlers are application-owned reads. No Project, Memory, Source,
SourceDocument, SourceChunk, MemoryProposal, proposal target, or Approval
Request mutation path is reachable. No migration, Tool Registry identity,
general Tool, connector, network/browser research, write authority, proposal or
Approval execution, or external delivery was added.

## Verification

The approved Checkpoint 82 path inventory is exactly:

- `app/agent_planning/service.py`
- `app/agent_runs/executor.py`
- `app/agent_runs/orchestration.py`
- `app/api/routes/agent_runs.py`
- `app/automations/catalog.py`
- `app/automations/coordinator.py`
- `app/automations/scheduler.py`
- `app/automations/scheduler_runner.py`
- `app/daily_brief/__init__.py`
- `app/daily_brief/dependencies.py`
- `app/daily_brief/events.py`
- `app/daily_brief/openai_provider.py`
- `app/daily_brief/provider.py`
- `app/daily_brief/service.py`
- `app/research/service.py`
- `app/schemas/agent_run.py`
- `docs/API_CONVENTIONS.md`
- `docs/ARCHITECTURE.md`
- `docs/CHECKPOINTS.md`
- `docs/ROADMAP.md`
- `docs/checkpoint-82-report.md`
- `frontend/src/Agents.tsx`
- `frontend/src/Automations.test.tsx`
- `frontend/src/Automations.tsx`
- `frontend/src/api/client.ts`
- `tests/integration/test_automation_api.py`
- `tests/integration/test_automation_scheduler.py`
- `tests/integration/test_daily_brief_events.py`
- `tests/test_automation_catalog.py`
- `tests/test_daily_brief_agent.py`

Focused backend Daily Brief/Automation remediation coverage passed **65 tests,
zero skipped**. Focused affected frontend Agent/Automation coverage passed
**34 tests, zero skipped**. The authoritative `scripts/verify.ps1 -Mode Full`
run passed dependency validation, Ruff lint/format, strict mypy, and
`git diff --check`; backend passed **1,028 tests, zero skipped** with 11
warnings; frontend ESLint, TypeScript, **128 tests across 12 files, zero
skipped**, and production Vite build passed.

Alembic current and sole head are `0011_automation_persistence`; `alembic check`
reports no new upgrade operations. Tool Registry remains `agent-tools-v1` and
Project export remains `second-brain-project-export` version `1`.

The exact approved Checkpoint 82 change contains **30 paths**: 21 tracked
modifications plus nine new files at the verification boundary. Checkpoint 82
is approved and complete after human review.

Exact approved path inventory (30 paths):

1. `app/agent_planning/service.py`
2. `app/agent_runs/executor.py`
3. `app/agent_runs/orchestration.py`
4. `app/api/routes/agent_runs.py`
5. `app/automations/catalog.py`
6. `app/automations/coordinator.py`
7. `app/automations/scheduler.py`
8. `app/automations/scheduler_runner.py`
9. `app/daily_brief/__init__.py`
10. `app/daily_brief/dependencies.py`
11. `app/daily_brief/events.py`
12. `app/daily_brief/openai_provider.py`
13. `app/daily_brief/provider.py`
14. `app/daily_brief/service.py`
15. `app/research/service.py`
16. `app/schemas/agent_run.py`
17. `docs/API_CONVENTIONS.md`
18. `docs/ARCHITECTURE.md`
19. `docs/CHECKPOINTS.md`
20. `docs/ROADMAP.md`
21. `docs/checkpoint-82-report.md`
22. `frontend/src/Agents.tsx`
23. `frontend/src/Automations.test.tsx`
24. `frontend/src/Automations.tsx`
25. `frontend/src/api/client.ts`
26. `tests/integration/test_automation_api.py`
27. `tests/integration/test_automation_scheduler.py`
28. `tests/integration/test_daily_brief_events.py`
29. `tests/test_automation_catalog.py`
30. `tests/test_daily_brief_agent.py`
