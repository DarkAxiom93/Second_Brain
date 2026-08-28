# Local V1.3 Automations roadmap

Status: **Implementation and release hardening complete through approved Checkpoint 86.**

This document plans Local V1.3 only. It authorizes no implementation. Local
V1.2.1 at `04e9db33dc0de7529b1599871c58cace6ed9f9e2` remains the published
baseline, with Alembic head `0010_agent_runtime_persistence`, Tool Registry
`agent-tools-v1`, and Project export `second-brain-project-export` version 1.

## Recommendation and release boundary

V1.3 should deliver **Local Automations & Scheduled Agents** inside the existing
single-maintainer, loopback-only deployment. Its useful end state is durable
one-time and recurring Automations, deterministic local scheduling, safe
occurrence claiming and recovery, bounded history and notifications, and two
fixed read-only Agent definitions: Daily Brief and Project Watch.

V1.3 should permit automatic planning and execution only for these code-owned,
read-only Agent definitions, only after the trigger-only scheduler and recovery
foundation passes independent review. Merely creating a Run that always waits
for a manual execute action is a safe intermediate checkpoint, but is not a
useful final automation product. Automatic execution is acceptable because it:

- uses the unchanged bounded Agent Run authority boundary;
- cannot approve, execute a proposal, or mutate reviewed knowledge;
- is opt-in per Automation and defaults to `create_only` until explicitly
  enabled by the operator;
- revalidates the captured Agent, policy, Tool Registry, scope, capacity, and
  evidence rules at every Run lifecycle boundary; and
- fails closed to an operator-visible occurrence instead of widening authority
  or improvising recovery.

The Memory Curator is not schedulable in V1.3 because its `propose` authority
would make unattended proposal creation an unnecessary expansion. Arbitrary
Research goals are also excluded: Automation configuration selects a fixed
code-owned definition and bounded settings, not free-form instructions that
change authority.

Explicitly deferred beyond V1.3 are Gmail, Calendar, GitHub, and all other
connectors; arbitrary network or external research; external writes; proposal
execution; automatic Approval; authentication and multi-user isolation;
remote/cloud/mobile operation; arbitrary shell, Python, SQL, filesystem, HTTP,
browser, or Git execution; import merge/overwrite/remap; encrypted export
redesign; and credential storage. Connector trust and approval-gated external
writes require a separate roadmap and threat model.

## Core invariant: Automation is not an Agent Run

An `Automation` is a durable, operator-owned trigger configuration. It answers
*whether and when* application code may request work. An `AgentRun` is one
bounded, immutable execution instance governed by its captured Agent version,
Tool Registry, policy, scope, budgets, goal, and existing state machine.

One scheduled occurrence may create at most one Agent Run. The occurrence owns
the trigger identity and links to the Run; the Run never becomes a schedule and
does not reschedule itself. Editing, enabling, or pausing an Automation cannot
modify an existing Run. A schedule definition grants no Tool, authority, scope,
budget, retry, Approval, or proposal-execution capability. Run creation must use
the ordinary capacity and validation service with an application-derived
idempotency identity. A rejected or failed Run creation remains a durable
occurrence outcome and is never silently replaced by a broader Run.

## Minimal domain model

Three new tables are sufficient. A separate `AutomationSchedule` table and a
separate claim table would add one-to-one records without an independent
lifecycle, so V1.3 should not create them.

### Automation

The durable definition contains:

- UUID, bounded operator label, fixed Automation kind and immutable Agent
  kind/version selected from a code-owned schedulable catalog;
- exact nullable Project scope, where null means explicit unassigned scope and
  never all Projects;
- lifecycle `draft | enabled | paused | cancelled` and monotonic revision;
- execution mode `create_only | automatic_read_only`, default `create_only`;
- schedule kind `one_time | daily | weekly`, IANA timezone name, local wall
  time, optional weekday set, and one-time local date/time as applicable;
- deterministic DST policies, missed-run policy, retry limit, and capacity
  bounds selected from closed application-owned enums and ceilings;
- `schedule_revision`, `next_occurrence_at` in UTC, created/updated timestamps,
  and nullable cancelled timestamp.

The schedule is an owned value object stored in this row because it is required,
singular, and has no independent identity or lifecycle. All fields are typed
columns or bounded closed JSON validated by application and database checks;
there is no cron string, executable expression, prompt template, or arbitrary
configuration object.

### AutomationOccurrence

This is the durable trigger occurrence and scheduler work item. It contains:

- UUID, Automation FK, captured `schedule_revision`, scheduled UTC instant,
  captured local date/time and timezone, and a canonical occurrence key;
- state `due | claimed | run_created | completed | missed | failed |
  cancelled` and monotonic revision;
- nullable linked Agent Run FK, disposition/error safe code, attempt count,
  retry-not-before UTC, and created/claimed/completed timestamps;
- nullable lease owner token, opaque lease generation, lease expiry UTC, and
  last-renewed UTC; and
- captured definition identity and scope needed to explain historical work
  without consulting a later-edited Automation.

A unique constraint on `(automation_id, schedule_revision, scheduled_at)` is the
primary duplicate barrier. The Run creation idempotency identity is derived
from the occurrence UUID and immutable fingerprint. The occurrence row itself
is the lease/claim record; a separate claim entity is unnecessary because only
the current owner may act, generation fencing rejects stale owners, and state,
attempt, and timestamps preserve the required recovery history. Agent Run
events retain execution detail after Run creation.

### AutomationNotification

This is an append-only local inbox item, not an external delivery queue. It
contains UUID, Automation and optional occurrence/Run FKs, a closed event kind,
severity, bounded safe title/body, read timestamp, creation timestamp, and one
deduplication key. It stores no prompts, raw goals, retrieved content, provider
output, exception text, secrets, or cross-Project detail. A separate table is
justified because notification read/dismiss lifecycle and retention differ from
an occurrence, and multiple safe notices may refer to one occurrence.

## Lifecycle and operator actions

### Automation lifecycle

`draft -> enabled -> paused -> enabled` is the ordinary path. `draft`, `enabled`,
or `paused` may transition to terminal `cancelled`; cancellation is irreversible.
Enabling validates the complete definition and atomically calculates the next
occurrence. Pausing prevents creation/claim of future occurrences but does not
cancel a linked Run. Resume increments the Automation revision, recalculates
from the captured resume instant, and applies the selected missed-run policy.

Schedule-affecting edits are allowed only while `draft` or `paused`, increment
both revision and schedule revision, and calculate a new next occurrence in one
transaction. Non-schedule label edits increment only revision. Already-created
occurrences and Runs remain immutable historical facts. Cancellation marks
unclaimed future occurrences cancelled in the same transaction; claimed work
must observe the revision fence before Run creation. Cancelling an in-flight Run
remains a separate explicit Agent Run action.

### Occurrence lifecycle

The normal path is `due -> claimed -> run_created -> completed`. `due` may
become `missed`, `failed`, or `cancelled`; an expired `claimed` occurrence may be
reclaimed with a new lease generation. Once a Run is linked, the occurrence
mirrors only its terminal summary and never drives the Run backward. Terminal
occurrences never become due again. Retrying Run creation reuses the same
occurrence; it never creates a second occurrence or Run.

## Time, recurrence, and DST

PostgreSQL UTC instants are authoritative for due selection and leases. The
application obtains one timezone-aware UTC instant per transaction from its
injectable clock. Display uses the Automation's captured IANA timezone, never
the host's current zone. Changing the host clock or timezone does not rewrite
stored occurrences.

V1.3 supports only closed schedule forms:

- `one_time`: one local date and wall time;
- `daily`: one local wall time every positive bounded number of days; and
- `weekly`: one local wall time on a non-empty bounded weekday set, optionally
  every positive bounded number of weeks.

No cron, seconds-level schedule, or arbitrary recurrence expression is allowed.
The minimum recurrence interval is 24 hours by schedule semantics. Calculation
uses the stored IANA zone and deterministic library version behavior. For a
nonexistent spring-forward wall time, run at the first valid instant after the
gap. For an ambiguous fall-back wall time, choose the earlier UTC occurrence
(`fold=0`) and create exactly one occurrence. The calculated local time, offset,
zone, and UTC instant are captured on the occurrence and covered by tests.

`next_occurrence_at` is a cache guarded by the Automation row lock, not the
source of historical truth. Each successful materialization advances it from
the prior scheduled local occurrence, never from worker wake time, preventing
drift.

## Due selection, transactions, and concurrency

The local scheduler is an explicit application process started by a dedicated
operator command; it is not embedded in every Uvicorn worker or API startup.
Only one scheduler is expected, but correctness supports concurrent instances.

Each bounded tick:

1. Capture one UTC `now` and lock at most the configured batch size of enabled
   due Automations with `FOR UPDATE SKIP LOCKED` in deterministic
   `(next_occurrence_at, id)` order.
2. In one short transaction per batch, insert each occurrence with its unique
   identity, advance the Automation's next occurrence, and commit. A uniqueness
   conflict resolves to the existing occurrence; it never creates new work.
3. Claim due/retryable occurrences in deterministic order using row locks.
   Claiming sets an owner token, increments lease generation, sets expiry, and
   commits before any Run or provider work.
4. The claimant revalidates owner, generation, Automation lifecycle/revision,
   scope, schedulable Agent catalog, mode, and capacity in a short transaction.
   It creates the Agent Run through the existing service with the occurrence-
   derived idempotency key, links it atomically, and commits.
5. In `create_only`, stop and notify. In `automatic_read_only`, use the existing
   Agent Run planning/execution services outside scheduler transactions. The
   occurrence observes the durable Run result; it never substitutes its own
   execution state machine.

No database lock is held across provider or Tool latency. The lock order is
Automation, occurrence, then Agent Run when more than one is required. The
scheduler may renew a lease only before expiry and only with exact owner and
generation. A default 60-second lease, configurable only within reviewed
application bounds, should cover short claim/link transactions; Run execution
does not remain under that lease because the durable Agent Run owns execution.

## Recovery, idempotency, and restart behavior

Occurrence insertion and advancement of `next_occurrence_at` commit together,
so a crash produces either neither fact or both. Run creation and occurrence
linking must also commit together using a caller-owned session. If existing Run
service boundaries cannot support that atomicity, the implementation checkpoint
must stop for architecture review rather than use two commits. Exact Run-create
replay resolves the same Run before capacity rejection.

On restart, the scheduler:

- materializes missed due definitions according to policy;
- reclaims only `claimed` occurrences whose database-time lease has expired;
- fences all stale owners by generation;
- resolves a linked Run from its durable state without creating another;
- retries only occurrence setup failures classified as safe and only within the
  occurrence retry budget; and
- leaves ambiguous or invariant-violating state `failed` for explicit operator
  inspection.

Automatic planning/execution uses the Agent Run's existing idempotency,
cancellation, deadline, classified retry, and explicit recovery rules. The
scheduler must not automatically call the V1.2 manual recovery command and must
not retry an ambiguous provider or Tool outcome.

## Missed runs, retries, and capacity

The closed missed-run policies are:

- `skip` (default): record one `missed` occurrence for the latest overdue slot,
  advance to the first future slot, and do not execute it;
- `run_once`: create at most one occurrence for the latest overdue slot and run
  it once, then advance to the first future slot.

There is no replay-all policy. One-time schedules use `run_once` by default;
the operator may select `skip`. A global maximum lookback (recommended seven
days) prevents ancient catch-up. Slots older than the lookback become a bounded
aggregate missed record/notification without per-slot expansion.

Only failures before an Agent Run is durably linked may be retried by the
scheduler. Retryable classes are database serialization/deadlock, transient
database unavailability, and exact capacity deferral. Capacity deferral does not
consume the small failure retry budget. Validation, scope, lifecycle, policy,
catalog, uniqueness invariant, cancellation, and ambiguous outcomes never
retry automatically. Use capped exponential delays with deterministic jitter,
a recommended maximum of three setup attempts, and a global retry-not-before
ceiling. Agent planning/Tool retry remains governed solely by the Agent Run.

The existing maximum of 32 nonterminal Agent Runs is unchanged. Automation adds
separate bounds: maximum 100 non-cancelled Automations, batch 16, at most one
nonterminal occurrence per Automation, and maximum 32 claimed/run-created
occurrences instance-wide. Exact values must be confirmed with focused load
tests before implementation. When full, due work remains durable and visible;
the scheduler neither drops it nor bypasses capacity.

## History, retention, and notifications

Automation definitions and occurrences linked to Runs are audit-sensitive.
V1.3 performs no automatic deletion. List APIs default to bounded pagination
and deterministic newest-first order. A future retention/archival checkpoint
may propose deletion only after defining Run/Approval FK behavior, notification
privacy, audit requirements, and an explicit operator action. Cancelling an
Automation preserves history.

Notifications are local inbox records shown only on loopback. Create notices
for missed/failed occurrences, retry exhaustion, paused/cancelled races,
capacity delay beyond a threshold, and completed Daily Brief/Project Watch
results. Completion notices contain only safe status and links, not knowledge
content. There is no OS toast, email, webhook, push, or browser persistence.

## Product and accessibility behavior

The UI adds an Automations list, create flow, detail/history view, and local
notification inbox. It must show label, fixed kind, exact Project/unassigned
scope, lifecycle, execution mode, timezone-aware schedule description, next run,
last occurrence, last linked Run, missed/failed state, retry eligibility, and
safe error code. History links each occurrence to at most one Agent Run.

Create and schedule-edit screens preview the next several local and UTC
occurrences, explicitly describe DST handling and missed-run policy, default to
paused/draft plus `create_only`, and require an explicit enable action. Pause,
resume, cancel, and switch-to-automatic actions require revision-aware
confirmation. The UI never predicts a scheduler outcome and uses explicit
refresh rather than hidden high-frequency polling.

All controls require keyboard operation, visible focus, programmatic labels,
logical headings, non-color status text, error summaries linked to fields,
screen-reader announcements for confirmed state changes, touch-sized targets,
responsive layouts, zoom/reflow support, reduced-motion compliance, and local
date/time text that includes timezone and UTC offset where ambiguity exists.

## Fixed Agents

`daily_brief` version 1 is read-only and summarizes bounded reviewed local
Memories and recorded local application events for one exact Project or explicit
unassigned scope. It has no web, connector, draft action, proposal, Approval,
or mutation access. Its result is persisted only through the existing safe Run
projection and linked from a content-free notification.

`project_watch` version 1 is read-only and inspects exactly one non-null Project
for meaningful local changes since the prior successful occurrence's captured
watermark. The application, not the model, derives and bounds the time window
and Project predicate. Deleted Projects fail the occurrence closed; scope is
never widened to all or unassigned data. The Agent may report no meaningful
change. It cannot modify the Project, create proposals, or expand Tool authority.

Both definitions require an immutable code-owned catalog version, fixed bounded
goal construction, the same five executable read Tools or a reviewed strict
subset, current evidence-version checks, prompt-injection resistance, and no new
Tool Registry identity unless a later checkpoint explicitly reviews it.

## Implementation sequence after Checkpoint 75

Every checkpoint depends on the preceding checkpoint, remains independently
reviewable, and leaves V1.2.1 as the recovery release. Database rollback in a
real environment is forward-only unless separately approved; migration
downgrades occur only in the verified test database.

### 76 - Automation persistence foundation

- **Dependency:** human approval of Checkpoint 75.
- **Goal:** Add the three normalized entities, closed enums, constraints,
  indexes, and repository primitives without scheduling behavior.
- **Production areas:** models, repositories, internal schemas.
- **Persistence/migration:** one additive migration after `0010`; Project export
  v1 explicitly remains unchanged and excludes Automation data.
- **API/UI:** none.
- **Concurrency/transactions:** repositories never commit; prove occurrence
  uniqueness, revisions, lease fencing fields, FK ownership, and timestamps.
- **Security acceptance:** no executable configuration or added Agent authority;
  safe fields only.
- **Focused tests:** migration lifecycle on verified test DB, model constraints,
  indexes, enum rejection, export exclusion.
- **Rollback:** revert code; test DB downgrade only; production uses separately
  reviewed forward repair.

### 77 - Automation API and lifecycle

- **Dependency:** approved Checkpoint 76 persistence and invariants.
- **Goal:** Typed create/read/list/update/enable/pause/resume/cancel behavior and
  deterministic schedule preview/calculation.
- **Production areas:** Automation schemas, service, routes, schedule module.
- **Persistence/migration:** none expected.
- **API/UI:** additive loopback Automation API; no UI.
- **Concurrency/transactions:** Automation row lock, revision compare-and-set,
  atomic lifecycle plus next-run calculation, schedule revision fencing.
- **Security acceptance:** fixed catalog, closed schedule/configuration, no
  free-form authority, automatic mode default off.
- **Focused tests:** full transition matrix, edits/races, timezone/DST fixtures,
  pagination/scope/safe errors.
- **Rollback:** remove additive routes/service; retained inert rows are safe.

### 78 - Scheduler materialization and claiming

- **Dependency:** approved Checkpoint 77 lifecycle and schedule calculator.
- **Goal:** Bounded scheduler command, due occurrence materialization, leasing,
  and trigger-only Run creation in `create_only` mode.
- **Production areas:** scheduler service/runner, occurrence repository, config.
- **Persistence/migration:** only if C76 review explicitly identifies a missing
  constraint; otherwise none.
- **API/UI:** scheduler operator command; existing Run API unchanged.
- **Concurrency/transactions:** `SKIP LOCKED`, unique occurrence key, atomic
  advance, owner/generation lease fencing, atomic Run link.
- **Security acceptance:** concurrent schedulers cannot duplicate Runs; no
  provider/Tool call; stopped scheduler is safe.
- **Focused tests:** concurrent claimers, crash at each commit boundary, stale
  owner, capacity, pause/cancel/edit races.
- **Rollback:** stop/disable scheduler command, revert runner; definitions and
  history remain inert.

### 79 - Restart, recovery, idempotency, and missed-run policy

- **Dependency:** approved Checkpoint 78 trigger-only scheduler.
- **Goal:** Deterministic restart reconciliation, safe setup retry, catch-up,
  and operator-visible failure outcomes.
- **Production areas:** scheduler recovery, diagnostics, fault hooks.
- **Persistence/migration:** none expected.
- **API/UI:** bounded occurrence retry/status operations if required; no
  execution expansion.
- **Concurrency/transactions:** database-time lease expiry, generation CAS,
  same-occurrence retry, never replay all missed slots.
- **Security acceptance:** ambiguous outcomes fail closed; no retry storm or
  automatic Agent recovery.
- **Focused tests:** clock jumps, downtime windows, retry exhaustion, restart
  before/after occurrence and Run commits, linked terminal Runs.
- **Rollback:** disable recovery loop; trigger-only durable facts remain.

### 80 - Automatic read-only scheduled Agent execution

- **Dependency:** approved Checkpoint 79 recovery and idempotency gate.
- **Goal:** Allow explicit opt-in `automatic_read_only` planning/execution for
  approved fixed Agent definitions.
- **Production areas:** coordinator around existing Agent Run services and fixed
  schedulable catalog.
- **Persistence/migration:** none expected.
- **API/UI:** additive mode action; existing Run projections reused.
- **Concurrency/transactions:** occurrence never owns execution; one linked Run;
  no locks across provider/Tool calls; durable Run replay wins.
- **Security acceptance:** read-only only, no Curator/proposal/Approval execution,
  unchanged registry authority and 32-Run capacity.
- **Focused tests:** policy/scope drift, malicious goal/evidence, cancellation,
  timeout, ambiguous results, proof of zero protected-table mutation.
- **Rollback:** force all Automations to `create_only` and disable coordinator;
  linked Runs/history remain valid.

### 81 - Automations UI and local notification inbox

- **Dependency:** approved Checkpoint 80 product state/API behavior.
- **Goal:** Accessible operator creation, lifecycle, schedule inspection,
  history, linked Runs, and safe local notices.
- **Production areas:** frontend routes/components/client and notification API.
- **Persistence/migration:** notification table already supplied by C76; none.
- **API/UI:** additive inbox/read action and full Automations UI.
- **Concurrency/transactions:** revision conflicts require refresh; notification
  dedupe/read update is atomic.
- **Security acceptance:** no raw result/content leakage, no browser persistence,
  no external delivery.
- **Focused tests:** every state/error, keyboard/focus/live regions, DST copy,
  responsive/reduced-motion, notification redaction.
- **Rollback:** remove frontend routes and notification endpoints; scheduler
  remains operable by API/command.

### 82 - Daily Brief Agent

- **Dependency:** approved Checkpoint 81 operator UI and notification boundary.
- **Goal:** Add fixed `daily_brief` v1 over reviewed local knowledge/events.
- **Production areas:** immutable Agent catalog, synthesis contract, tests, UI
  kind selection.
- **Persistence/migration:** none expected.
- **API/UI:** additive fixed kind only.
- **Concurrency/transactions:** ordinary linked Run semantics; exact captured
  scope/evidence versions.
- **Security acceptance:** local read-only evidence, bounded content-free
  notification, no external data/proposal.
- **Focused tests:** citations, insufficiency, injection, deleted scope, bounds,
  no mutation.
- **Rollback:** unregister/disable kind; existing historical Runs remain readable.

### 83 - Project Watch Agent

- **Dependency:** approved Checkpoint 82 fixed-Agent pattern.
- **Goal:** Add fixed `project_watch` v1 for meaningful local changes in one
  exact Project.
- **Production areas:** immutable Agent catalog, application-derived watermark,
  synthesis contract, UI selection.
- **Persistence/migration:** none expected; stop for review if a watermark field
  proves necessary.
- **API/UI:** additive fixed kind only, requires non-null Project.
- **Concurrency/transactions:** watermark derives from prior successful
  occurrence; changes/cancellation cannot widen scope.
- **Security acceptance:** exact Project isolation, read-only/no-change result,
  no external data or authority expansion.
- **Focused tests:** version/change windows, Project deletion/edit races,
  injections, duplicate occurrence, no mutation.
- **Rollback:** unregister/disable kind; preserve history.

### 84 - Automation security and evaluation harness

- **Dependency:** approved Checkpoint 83 complete proposed capability surface.
- **Goal:** Turn the V1.3 threat model into deterministic release gates.
- **Production areas:** fake clocks/schedulers/providers, concurrency and fault
  harness, evaluation documentation.
- **Persistence/migration:** none intended.
- **API/UI:** no new product behavior except narrow reviewed defect fixes.
- **Concurrency/transactions:** exercise PostgreSQL locks only on verified
  `second_brain_test`.
- **Security acceptance:** every A01-A18 case and zero unauthorized mutation.
- **Focused tests:** adversarial schedule/configuration, concurrent workers,
  crash/restart, capacity, redaction, accessibility.
- **Rollback:** revert harness/isolated fixes; do not release.

### 85 - Local V1.3 end-to-end acceptance

- **Dependency:** approved Checkpoint 84 security/evaluation gate.
- **Goal:** Prove real loopback scheduler/API/UI integration and restart safety.
- **Production areas:** acceptance evidence and blocker fixes only.
- **Persistence/migration:** none intended.
- **API/UI:** exercise all lifecycle/history/notification paths.
- **Concurrency/transactions:** real concurrent scheduler and restart drills on
  verified test fixtures; development DB read only unless explicitly approved.
- **Security acceptance:** no duplicates, scope leaks, external calls, writes,
  proposal execution, or missed terminal state.
- **Focused tests:** one-time/daily/weekly across DST, create-only/automatic,
  pause/resume/cancel, capacity/restart, Full zero-skip verification.
- **Rollback:** revert isolated blocker fixes; disable scheduler.

### 86 - Local V1.3 release hardening

- **Dependency:** approved Checkpoint 85 acceptance evidence.
- **Goal:** Synchronize stable documents, migration/export/registry identities,
  clean installs, recovery instructions, and release evidence.
- **Production areas:** release/runbook documentation and inventories only.
- **Persistence/migration:** verify approved head; no new migration.
- **API/UI:** no feature changes.
- **Concurrency/transactions:** stopped-service recovery drill, preserved volume,
  no application writes during audit.
- **Security acceptance:** dependency/privacy review, deterministic harness,
  exact deferred-scope audit.
- **Focused tests:** complete Full verification and clean-install/restart checks.
- **Rollback:** documentation revert; V1.2.1 remains the recovery release.

Checkpoints 75-85 are approved and complete after separate human review.
Checkpoint 86 release hardening is approved and complete after human review; no
tag or GitHub Release has been created.
