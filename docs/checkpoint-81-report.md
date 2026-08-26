# Checkpoint 81 report - Automations UI and local notification inbox

Status: **Approved and complete after human review.**

## Outcome and safety boundary

Checkpoint 81 adds the operator-facing Automations experience and a loopback
local notification inbox. It adds no migration, Agent definition, Tool,
authority, connector, background poller, browser persistence, service worker,
OS notification, or external delivery. `IMPLEMENTED_AUTOMATION_AGENT_IDENTITIES`
remains `frozenset()`: Daily Brief and Project Watch remain reserved and
unimplemented, `create_only` remains the usable/default mode, and the UI visibly
reports `automatic_read_only` as unavailable while preserving the API gate.

## Backend APIs and privacy

- `GET /automations/{automation_id}/occurrences` returns a bounded (1-100),
  offset-paginated, deterministic `scheduled_at DESC, id DESC` history page.
  Its allowlist contains occurrence identity, canonical local/UTC schedule and
  offset, state, safe attempt/retry/disposition/error metadata, linked Agent Run
  ID, and created/claimed/completed timestamps.
- `GET /automation-notifications` returns bounded deterministic newest-first
  pages, with optional unread-only and Automation filters.
- `POST /automation-notifications/{notification_id}/read` row-locks one item and
  atomically sets `read_at` only when null. Replay returns the original read
  timestamp without another transition.

Notification insertion uses the existing unique deduplication key inside the
scheduler transaction and treats duplicates as idempotent. Reachable missed,
failed occurrence/Run, retry exhaustion, and repeated meaningful capacity-delay
states create code-owned notices. Titles and bodies contain status/navigation
copy only; even the safe disposition code is not interpolated. The public
projection excludes the private deduplication key. Lease identity, occurrence
key, captured labels, prompts, content, provider/Tool payloads, evidence,
exceptions, secrets, and raw internal state are absent.

## Frontend and accessibility

The primary navigation adds `/automations`; `/automations/new`,
`/automations/:automationId`, and `/notifications` provide draft creation,
detail/edit, lifecycle, occurrence history, linked `/agents/:runId` navigation,
and inbox read actions. List and detail show fixed Agent identity, exact Project
or explicit unassigned scope, lifecycle, execution mode, timezone schedule,
next/latest occurrence, missed/failed and retry status, safe codes, and linked
Run. Cancelled definitions retain history.

Create and eligible draft/paused edit forms support one-time, daily, and weekly
schedules, IANA timezone, local date/time, weekdays, missed policy, and bounded
retry/capacity values. The current form must be previewed through the existing
calculation-only API before submission. Preview renders local time, timezone,
UTC offset, and UTC instant, with explicit DST-gap, DST-fold, missed-run, and
`create_only` explanations. Creation remains draft and requires a separate
confirmed enable action.

Enable, pause, resume, cancel, edit, and execution-mode requests carry the
displayed revision. Safety-sensitive enable/cancel transitions confirm intent.
A 409 never merges or overwrites local state: a live region announces the
conflict and directs the operator to explicit authoritative refresh. Native
inputs/selects/checkboxes, labels, fieldsets/legends, logical headings, textual
statuses, error summary, focusable live status, touch-sized controls, wrapping
responsive lists, and reduced-motion CSS provide focused accessibility.

## Verification

The focused backend Automation set contains **78 passed, zero skipped** across
reservation, lifecycle API, coordinator, operator history/inbox, persistence,
scheduler, catalog, and schedule coverage. The focused frontend run contains
**18 passed, zero skipped** across the Automations/operator and application-shell
files. The final authoritative `scripts/verify.ps1 -Mode Full` run passed:

- pip check, Ruff lint/format, strict mypy, and `git diff --check` passed;
- backend: **1019 passed, zero skipped** (11 warnings);
- frontend: **128 passed across 12 files, zero skipped**;
- frontend ESLint, TypeScript, Vitest, and production Vite build passed;
- Alembic current and sole head: `0011_automation_persistence`; and
- Alembic check: no new upgrade operations detected.

## Changed paths and invariant audit

The approved Checkpoint 81 change contains exactly these 19 paths:

- `app/api/router.py`
- `app/api/routes/automation_notifications.py`
- `app/api/routes/automations.py`
- `app/automations/scheduler.py`
- `app/repositories/automations.py`
- `app/schemas/automation.py`
- `docs/ARCHITECTURE.md`
- `docs/CHECKPOINTS.md`
- `docs/ROADMAP.md`
- `docs/checkpoint-81-report.md`
- `frontend/src/App.test.tsx`
- `frontend/src/App.tsx`
- `frontend/src/Automations.test.tsx`
- `frontend/src/Automations.tsx`
- `frontend/src/api/client.ts`
- `frontend/src/styles.css`
- `tests/integration/test_automation_operator_api.py`
- `tests/test_memory_routes.py`
- `tests/test_project_routes.py`

The exact working-tree summary is **19 files, 614 insertions, 6 deletions** (14
tracked modifications plus 5 untracked new files). Everything is unstaged and
uncommitted. Alembic remains `0011_automation_persistence`; Tool Registry remains
`agent-tools-v1`; Project export remains `second-brain-project-export` version
`1`; and `IMPLEMENTED_AUTOMATION_AGENT_IDENTITIES == frozenset()`.

No migration, new Agent, Tool, authority, connector, or external delivery path
was added. Daily Brief and Project Watch remain unimplemented. Checkpoint 82 was
not started. Checkpoint 81 is approved and complete after human review.
