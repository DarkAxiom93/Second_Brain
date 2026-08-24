# Checkpoint 77 report - Automation API and lifecycle

Status: **Approved and complete after human review.**

## Outcome

Checkpoint 77 adds a typed loopback Automation API, a strict revision-aware
lifecycle service, and a pure deterministic schedule calculator and preview.
The persistence contract remains at `0011_automation_persistence`; no migration
was added. Checkpoint 78 was not started.

There is no scheduler, worker, background polling, occurrence materialization,
lease claim, Agent Run creation, planning, provider or Tool call, automatic
execution, proposal execution, or automatic Approval. Selecting
`automatic_read_only` persists configuration only.

## API surface

- `POST /automations` creates a draft definition.
- `GET /automations/{automation_id}` retrieves one definition.
- `GET /automations?limit=&offset=` lists newest-first by
  `(created_at DESC, id DESC)` with limit `1..100`.
- `PATCH /automations/{automation_id}` performs a revision-aware update.
- `POST /automations/{automation_id}/enable` enables a draft.
- `POST /automations/{automation_id}/pause` pauses an enabled definition.
- `POST /automations/{automation_id}/resume` resumes a paused definition.
- `POST /automations/{automation_id}/cancel` irreversibly cancels a draft,
  enabled, or paused definition.
- `POST /automations/preview` calculates `1..10` future points and persists
  nothing.

Request models reject unknown fields. Safe public errors preserve the existing
404/409/422/503 conventions without exposing database or exception detail.

## Lifecycle and revision behavior

The implemented ordinary path is `draft -> enabled -> paused -> enabled`.
Cancellation is terminal from draft, enabled, or paused. Cancelled definitions
cannot be edited, resumed, or cancelled again. Enabling validates the entire
definition and atomically stores the first future UTC occurrence. Pausing
changes eligibility only and preserves the cached historical schedule fact.
Resume captures one UTC instant, increments `revision`, and atomically
recalculates the next occurrence from that instant. Cancellation records the
captured UTC terminal timestamp and clears future eligibility.

Every update and lifecycle request carries `expected_revision`. The service
locks the Automation row, compares the exact revision, applies the transition
and revision increment, and flushes without committing. Routes own commit and
rollback. A stale request returns a safe conflict. Concurrent equal-revision
pause requests deterministically produce one winner and one stale conflict.

Typed schedule edits are allowed only in draft or paused, increment both
`revision` and `schedule_revision`, and recalculate the cached next slot while
paused. Label-only edits increment only `revision` and may occur in any
nonterminal state. Project scope, execution mode, missed-run policy, retry, and
capacity edits are definition-sensitive and therefore restricted to draft or
paused, but increment only `revision`. Historical occurrence and Run rows are
never updated.

## Schedule and timezone behavior

The pure calculator accepts only `one_time`, `daily`, and `weekly`; local wall
times have minute precision, intervals are `1..365`, and weekly schedules use a
non-empty unique ISO weekday set. It rejects cron, seconds, arbitrary
expressions, invalid shapes, unknown IANA zones, naive reference instants, and
non-progressing results.

UTC instants are authoritative. All display fields derive from the stored IANA
zone, never the host timezone. A nonexistent spring-forward wall time resolves
to the first valid local minute after the gap. An ambiguous fall-back wall time
uses `fold=0`, the earlier UTC occurrence, exactly once. Subsequent recurrence
advances from the prior scheduled local slot, not worker wake time. The first
slot after enable or resume anchors the bounded interval sequence. One-time
schedules default to `run_once`; recurring schedules default to `skip`.

Preview accepts an explicit aware `after_utc` and returns local date, local
time, IANA zone, UTC offset minutes, and UTC instant. It does not open a database
session or modify lifecycle, `next_occurrence_at`, occurrences, or Runs.

## Scope, catalog, and authority

Nullable Project scope is exact: null means unassigned and never all Projects.
Non-null Projects must exist. `project_watch` version 1 requires an exact
non-null Project; `daily_brief` version 1 permits either an exact Project or
explicit unassigned scope. The small code-owned catalog validates configuration
identity only and grants no execution authority. The API accepts no prompt,
goal, Tool list, authority, URL, path, SQL, executable expression, or arbitrary
configuration object.

The planned Daily Brief and Project Watch implementations do not yet exist, so
this checkpoint deliberately provides no goal construction, Run creation, or
executable placeholder. Later checkpoints must revalidate the catalog and
ordinary Agent authority boundary before any work can run.

## Verification evidence

Focused pure schedule/schema tests: **10 passed**. Focused PostgreSQL Automation
API tests: **8 passed** as part of Full verification. They cover create/read/
list, bounded pagination/order, lifecycle and terminal cancellation, stale and
invalid transitions, schedule versus metadata revisions, atomic enable and
pause/resume behavior, preview side effects, exact nullable scope, Project and
catalog failures, no occurrence/Run creation, caller-owned rollback, and a
concurrent row-lock/CAS race.

The authoritative `scripts/verify.ps1 -Mode Full` run passed:

- pip check, Ruff lint/format, and strict mypy passed;
- backend: **971 passed, zero skipped** (six pre-existing deprecation warnings);
- frontend: **124 passed across 11 files, zero skipped**;
- frontend ESLint, TypeScript, and production Vite build passed;
- Alembic current and sole head: `0011_automation_persistence`;
- Alembic check: no new upgrade operations detected; and
- `git diff --check`: passed.

A live Uvicorn read-only smoke returned HTTP 200 for the Automation list and
HTTP 200 with two calculated points for preview. The ignored maintainer `.env`
was temporarily moved aside without being read during authoritative verification
and restored in `finally`.

Tool Registry identity remains `agent-tools-v1`; its inventory is unchanged.
Project export remains `second-brain-project-export` version `1`; Automation
state remains excluded.

## Security acceptance

Checkpoint 77 implements the relevant A02, A05, A06, A10, A12-A15, and A18
protections through lifecycle/revision fencing, UTC/IANA calculation, bounded
closed schedules, exact scope/catalog validation, strict schemas, and the
absence of executable authority. No occurrence, Agent Run, protected domain
record, provider, Tool, or external system is touched by Automation operations.

Checkpoint 77 was approved by human review and is complete. Checkpoint 78 was
not started.
