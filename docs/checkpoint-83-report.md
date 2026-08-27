# Checkpoint 83 report - Project Watch Agent v1

Status: **Approved and complete after human review.**

## Outcome and activation boundary

Checkpoint 83 installs `("project_watch", "1")` as the second fixed production
Automation Agent identity. The implemented identity set is exactly:

- `("daily_brief", "1")`
- `("project_watch", "1")`

Project Watch is scheduled-only, read-only, requires one non-null exact Project,
supports `create_only` and explicit `automatic_read_only`, and rejects public
manual/free-form Run creation. Research and Memory Curator remain
unschedulable. No proposal or Approval path is reachable. Checkpoint 84 was not
started.

The immutable definition uses authority `read`, registry `agent-tools-v1`,
planning contract `project-watch-planning-v1`, synthesis contract
`project-watch-changes-v1`, exact-non-null-Project scope, at most 20 evidence
items, five findings, and twenty citations. Its dedicated reviewed allowlist is
`project.get`, `memory.get`, `memory.search_explained`, `source.get`, and
`source_chunk.get`, all version 1. Daily Brief behavior and definition remain
unchanged.

## Fixed goal, watermark, and successful predecessor

The scheduler constructs the Project Watch goal entirely from fixed code-owned
text. It includes neither the editable Automation label nor arbitrary operator
text. The Project predicate and time window are never provider-controlled.

The existing schema safely represents the watermark without a migration. For
the current occurrence, the deterministic upper boundary is its canonical
captured `scheduled_at`. The interval is `(lower, upper]`. The lower boundary is
the greatest prior `scheduled_at` for the same Automation, exact Project, and
Project Watch v1 identity only when all three durable success facts exist:

1. the occurrence is `completed`;
2. its linked Agent Run is `completed`; and
3. that Run has a persisted `project_watch.result` event.

Failed, cancelled, expired, invalid, ambiguous, unreconciled, or result-less
Runs cannot advance the watermark. The first-run lower boundary is
`max(Automation.created_at, upper - 7 days)` when that precedes the upper bound;
an overdue schedule deterministically falls back to `upper - 7 days`. This is
bounded, application-owned, replay-stable, and independent of provider output
or execution wake time.

Occurrence uniqueness, one linked Run, occurrence-derived Run idempotency, and
the existing coordinator preserve exact replay. Repeated or concurrent ticks
reuse the same occurrence, Run, and window. No Automation lock spans planning,
Tool, or synthesis latency. Schedule edits cannot change the captured
historical occurrence scope or upper boundary.

## Closed change and result contracts

The conservative change-kind allowlist is exactly `project_state` and
`memory_state`. It projects only the exact current Project and reviewed Memory
rows whose deterministic `updated_at` lies inside `(lower, upper]`. At most 20
items are selected in deterministic `(updated_at, id)` order. Project and
Memory versions reuse the existing reviewed Research evidence-version logic.
Source and SourceChunk state were deliberately excluded because their existing
ownership/timestamp facts do not provide an equally direct exact-Project
mutable-state boundary.

Every captured item stores a code-owned kind, identity, current version,
change timestamp, exact Project, and bounded safe projection. Before result
persistence the application re-derives the window and revalidates Project
existence, exact scope, window membership, entity existence, timestamp,
projection, and current version. Project deletion, scope drift, stale/version-
changed rows, forged evidence IDs, and out-of-window evidence fail closed.
Other Projects, unreviewed proposals, Approval mutation state, raw Agent events,
provider/Tool payloads, prompts, secrets, and external/network data are absent.
Prompt-injection text is explicitly delimited as untrusted evidence data.

The closed synthesis statuses are `changes_found` and
`no_meaningful_change`. Changes require one to five factual findings and every
finding must cite supplied captured evidence; unknown or duplicate evidence IDs
and more than twenty citations are rejected. No-change requires zero findings
and still persists a successful durable result, allowing its occurrence to
become a future predecessor. Provider unavailability, timeout, failure,
malformed output, or revalidation failure transitions the Run with a safe code
and does not advance the watermark.

## Notifications, UI, and mutation boundary

Successful persisted Project Watch results use the existing content-free,
database-deduplicated `run_completed` notification. Its title/body remain
status/navigation-only and contain no finding, change text, citation, Project
content, provider/Tool output, prompt, or secret.

The Automations UI identifies Project Watch v1 as implemented, requires an
exact Project at create/edit time, preserves draft `create_only` creation,
offers explicit automatic read-only mode, and explains exact-Project behavior.
The Agent Run detail renders the deterministic window and both changes-found
and no-meaningful-change states. No polling or browser persistence was added.

Automatic execution can mutate only existing Agent Runtime rows, Automation
occurrence state, and safe notification state. The fixed policy is `read`; all
Tools remain application-owned reads and the change projection is query-only.
There is no reachable mutation of Projects, Memories, Sources/documents/chunks,
Memory proposals, or Approval Requests.

## Verification and stable identities

Focused Project Watch unit coverage passed **8 tests**. The dedicated
PostgreSQL watermark/scope/version proof passed **1 test**. Affected frontend
Agent/Automation coverage passed **34 tests**, zero skipped.

The authoritative `scripts/verify.ps1 -Mode Full` run passed dependency
validation, Ruff lint/format, strict mypy, and `git diff --check`; backend passed
**1,033 tests, zero skipped** with 12 warnings. Frontend ESLint, TypeScript,
**128 tests across 12 files, zero skipped**, and the production Vite build all
passed.

Alembic current and sole head are `0011_automation_persistence`; `alembic check`
reports no new upgrade operations. Tool Registry remains `agent-tools-v1`.
Project export remains `second-brain-project-export` version `1`.

## Exact path inventory and repository state

Checkpoint 83 changes exactly 26 paths: 17 tracked modifications and nine new
files (including this report):

1. `app/agent_planning/service.py`
2. `app/agent_runs/executor.py`
3. `app/agent_runs/orchestration.py`
4. `app/api/routes/agent_runs.py`
5. `app/automations/catalog.py`
6. `app/automations/coordinator.py`
7. `app/automations/scheduler.py`
8. `app/automations/scheduler_runner.py`
9. `app/project_watch/__init__.py`
10. `app/project_watch/changes.py`
11. `app/project_watch/dependencies.py`
12. `app/project_watch/openai_provider.py`
13. `app/project_watch/provider.py`
14. `app/project_watch/service.py`
15. `app/schemas/agent_run.py`
16. `docs/API_CONVENTIONS.md`
17. `docs/ARCHITECTURE.md`
18. `docs/CHECKPOINTS.md`
19. `docs/ROADMAP.md`
20. `docs/checkpoint-83-report.md`
21. `frontend/src/Agents.tsx`
22. `frontend/src/Automations.tsx`
23. `frontend/src/api/client.ts`
24. `tests/integration/test_project_watch_changes.py`
25. `tests/test_automation_catalog.py`
26. `tests/test_project_watch_agent.py`

Before adding the untracked files, the tracked diff summary was 17 files,
151 insertions, and 23 deletions. The final tree is intentionally unstaged and
uncommitted. No migration, new authority, general Tool, connector, external
access, write/proposal/Approval execution, staging, commit, push, PR, or
Checkpoint 84 work was added.

Checkpoint 83 is approved and complete after human review.
