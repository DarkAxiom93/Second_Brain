# Checkpoint 103 architecture-gate remediation report

Status: **Documentation-only remediation approved after human review. CP103
production implementation remains gated and CP104 has not started.**

## Preflight

Preflight passed on clean synchronized `main` at exact approved CP102 commit
`41a8728695904be3a70b0dc22a63cc1f55beb576`; `HEAD` and freshly fetched
`origin/main` matched. Exact push CI run `33777189314` was completed/successful
for that SHA. Development and test database identities were verified as
`127.0.0.1:5433/second_brain` and
`127.0.0.1:5433/second_brain_test`. Alembic current and sole head were
`0015_calendar_persistence`, and `alembic check` was clean. Tool Registry was
`agent-tools-v1`; Project export was `second-brain-project-export` version `1`.

Preflight and documentation work accessed no credential and made no OAuth,
Google, or Calendar request.

## Mandatory architecture-gate result

The gate failed before production changes. CP102 intentionally treats equal
normalized content as write-free replay. `record_event_revision` returns the
historical `CalendarEventRevision`, so that row retains its original
`sync_run_id`. The newly successful run records only aggregate `items_seen`,
`items_written`, and `items_unchanged` counters. There is no durable exact
run-to-occurrence observation relation.

Aggregate counts cannot identify which occurrence was unchanged. Timestamps
cannot prove membership in one run, and reconstruction from current rows or
provider assumptions cannot distinguish a positively observed unchanged
occurrence from an absent occurrence. Those signals therefore cannot authorize
negative absence evidence. The implementation stop was correct. Zero files
were changed before that stop, and CP104 was not started.

## Approved future migration and observation evidence

The human architecture decision authorizes CP103 production implementation to
create one future additive migration:
`0016_calendar_event_observations`. This remediation does not create it.
Production work may begin only after this approved amendment is committed,
pushed, and its exact push CI succeeds.

The future migration must add a minimal provider-content-free observation
relation. Each row binds:

- the exact `CalendarSyncRun`;
- its exact account/configuration revision and calendar identity;
- its immutable historical Project or explicit-unassigned scope, derived
  through that exact account revision and run rather than caller input;
- the exact occurrence key; and
- the exact existing or newly created `CalendarEventRevision` whose normalized
  content was observed.

It may include only a safe application observation timestamp and closed schema
version if implementation requires them. It must contain no event content, raw
provider payload, provider response, token, OAuth data, email, URL, or secret.

Database constraints must make `(sync_run_id, occurrence_key)` unique. Composite
foreign keys and supporting unique ownership keys must make the run's account
revision/calendar lineage match the referenced event revision's lineage and
occurrence key. Because `CalendarAccountRevision.project_id` is immutable and a
run already captures that same nullable value, exact account-revision ownership
also binds the historical scope without a separately forgeable nullable scope
column. Cross-calendar, cross-account, cross-configuration, cross-scope, event-
revision, and duplicate run-occurrence substitution must fail closed.

Every observation-aware page transaction must atomically record or reuse the
event revision and insert the corresponding observation. Equal content still
creates no duplicate `CalendarEventRevision`; it creates a new observation that
points to the historical revision. Changed content appends the next revision;
new content creates revision 1. Provider/content history and per-run observation
evidence remain separate.

## Evidence version and historical-run policy

The future schema must add a nullable closed code-owned evidence version such as
`calendar-observations-v1` to `calendar_sync_runs`, or an equivalent one-to-one
manifest. All historical CP102 runs remain null. There is no observation
backfill and no inference of historical identities.

A run is reconciliation-eligible only when it is `succeeded`/`complete`, has the
exact supported evidence version, retains exact calendar/account-revision/scope/
window lineage, and its distinct durable observation count equals its accepted-
item accounting. The marker is written only after this internal completeness
check. A zero-item run must still carry this explicit versioned manifest; the
absence of observation rows alone is never evidence. Incomplete, failed,
partial, cancelled, drifted, ambiguous, unversioned, or internally inconsistent
runs infer nothing.

## Effective state and exact-window semantics

Provider `CalendarEventRevision` rows remain immutable provider-observation
history. CP103 must not copy prior provider fields into a fabricated stale
revision. Effective state is application-derived from eligible evidence:

- a positive observation makes the occurrence `current`;
- a later complete eligible run that covered the prior projection but omitted
  its exact occurrence identity makes it locally `stale`;
- a later positive observation makes it `current` again; and
- the latest applicable positive or negative evidence wins deterministically.

Replaying reconciliation for the same evidence is write-free/idempotent.
Absence never creates provider `cancelled` or `deleted` state.

For a timed projection, exact coverage follows the approved Calendar list
boundaries: `end_instant > window_start` and
`start_instant < window_end`. For an all-day projection, apply the corresponding
half-open date-interval predicate only after deterministic conversion using its
persisted safe source timezone. If the persisted projection lacks enough
timezone evidence to prove coverage, it receives no negative evidence. A run
outside this predicate has no effect. A moved-outside-window occurrence can
become only locally stale when its prior projection was covered; this remains
uncertainty and never proves deletion or cancellation.

No evidence crosses `calendar_identity_id`, exact account/configuration
revision, or the immutable historical Project/unassigned scope. Null means
unassigned only, never all Projects. Later configuration or scope revisions do
not retrofit earlier observations.

## Documentation scope and next gate

This remediation updates the architecture, checkpoint lifecycle, roadmap, V1.5
Calendar roadmap, and existing G01-G18 threat register. G05, G09, G10, G11,
G13, and G18 now explicitly cover exact observation ownership, unchanged
replay, historical/unversioned and zero-item manifests, complete-only evidence,
application-owned stale state, lineage isolation, atomic page evidence, and
zero reconciliation network/write authority. No new threat ID was needed.

There is no production code, migration, dependency, API, UI, database schema,
credential, Google/Calendar request, Calendar write, import, scheduling, Agent,
or Automation change. CP99-CP102 remain approved and complete. CP103 production
implementation remains not started and gated on commit/push/CI; the remediation
is now approved, while those lifecycle steps remain pending. CP104 remains not
started.

## Changed paths and verification

Exact changed paths:

- `docs/ARCHITECTURE.md`
- `docs/CHECKPOINTS.md`
- `docs/ROADMAP.md`
- `docs/V1_5_CALENDAR_ROADMAP.md`
- `docs/V1_5_CALENDAR_THREAT_MODEL.md`
- `docs/checkpoint-103-report.md`

Focused Calendar verification passed **27 backend tests** and **6 frontend
tests**, zero failed and zero skipped.

The first Full attempt passed database identity, dependency, Ruff lint/format,
and strict mypy gates, then collected 1,288 backend tests and reported **1,287
passed, 1 failed, 0 skipped**. The sole failure was the known environmental
Windows Credential Manager availability lock in the existing real-adapter
synthetic round-trip test; it was not a product or documentation failure.

After explicit authorization limited to the established deterministic test
path, the authoritative Full rerun passed **1,288 backend tests** and **143
frontend tests**, zero failed and zero skipped. The credential test used only a
fresh random application target and synthetic test bytes with cleanup; it did
not enumerate or access a real Google/Calendar credential. `pip check`, Ruff
lint/format, strict mypy over 201 production files, frontend lint/typecheck/
build, and `git diff --check` passed. Both database identities passed. Alembic
current and sole head remained `0015_calendar_persistence`; `alembic check`
reported no new upgrade operations. Tool Registry remained `agent-tools-v1`;
Project export remained `second-brain-project-export` version `1`.

No migration was created. Outside the isolated synthetic credential-store
verification required by the existing Full suite, this remediation performed
zero credential access and made zero OAuth, Google, or Calendar request. It is
documentation-only and safe for human review.

## Production implementation (2026-09-03)

Status: **CP103 production implementation approved and complete after human
review. CP104 has not started.**

Production preflight passed on clean synchronized `main` at exact approved
architecture-remediation commit
`3035152910dbb535609fbe2f28770b79c1ea4206`; freshly fetched `origin/main`
matched and exact push CI run `33783128054` completed successfully. Development
and test identities were `127.0.0.1:5433/second_brain` and
`127.0.0.1:5433/second_brain_test`. Alembic current/head was
`0015_calendar_persistence` with a clean check. Tool Registry remained
`agent-tools-v1`; Project export remained `second-brain-project-export` version
`1`.

The additive `0016_calendar_event_observations` migration adds a provider-
content-free observation relation, a nullable closed
`calendar-observations-v1` run marker, and composite ownership constraints.
Each observation is unique by run and occurrence and must reference both the
exact run account/calendar lineage and an event revision with the same account,
calendar, and occurrence. Scope remains inherited from the immutable account
revision; there is no caller-controlled observation scope. Historical runs are
not backfilled and remain unversioned.

CP102 page persistence now records the created or reused event revision and its
observation atomically. Equal normalized replay still creates no content
revision, but does create new evidence pointing to the historical revision.
The terminal marker is written only after the durable observation count equals
accepted-item accounting; explicit zero-item success is versioned only after
the same zero-count proof. Failed, incomplete, unversioned, or inconsistent
runs infer nothing.

Calendar External Context derives one latest positive projection per exact
account revision, calendar, and occurrence, then scans eligible run evidence in
deterministic completion order. A positive observation yields `current`; a
later covering omission yields application-local `stale`; later positive
evidence restores `current`. Reconciliation is PostgreSQL-only and write-free.
Timed coverage uses exact half-open overlap. All-day negative evidence requires
safe persisted timezone conversion; insufficient timezone evidence produces no
negative conclusion. Absence never creates a provider cancellation, deletion,
or fabricated revision.

The new exact-scope list/detail API and accessible UI accept one Project or
explicit unassigned scope, use bounded filter-bound keyset pagination, render
hostile titles as inert text, and disclose only reviewed local metadata. They
expose no provider identifiers, etags, raw update values, run/observation
internals, payloads, credentials, emails, attendees, descriptions, locations,
conference/link data, or Google hyperlink/action. Browsing makes no provider
request. Project export/import stays version `1` and has no Calendar data or
mutation path; Tool Registry, Agent, Automation, OAuth, and CP102 GET-only
authority are unchanged.

Production changed paths and final verification evidence are recorded in the
handoff for this working tree. No dependency changed. All work is unstaged and
uncommitted for the approved lifecycle commit.

Focused verification passed **99 backend tests** and **6 frontend tests**, zero
failed and zero skipped. The first Full attempt passed all CP103/product checks
but reported the known host-context Windows Credential Manager lock: **1,290
passed, 1 environmental failure, 0 skipped**. The authoritative rerun in the
normal Windows user context used only the existing test's fresh random target
and synthetic bytes with cleanup. It passed **1,291 backend tests** and **145
frontend tests**, zero failed and zero skipped. `pip check`, Ruff lint/format,
strict mypy over 203 production files, frontend lint/typecheck/build, and
`git diff --check` passed. Alembic current and sole head were
`0016_calendar_event_observations`; `alembic check` reported no new upgrade
operations. Both database identities passed. Tool Registry remained
`agent-tools-v1`; Project export remained `second-brain-project-export` version
`1`.

Exact production changed paths:

- `migrations/versions/0016_calendar_event_observations.py`
- `app/models/calendar.py`
- `app/models/__init__.py`
- `app/repositories/calendar.py`
- `app/calendar/sync.py`
- `app/calendar/query.py`
- `app/api/routes/calendar_events.py`
- `app/api/router.py`
- `app/schemas/calendar.py`
- `app/diagnostics/service.py`
- `app/project_export/models.py`
- `frontend/src/api/client.ts`
- `frontend/src/ExternalContext.tsx`
- `frontend/src/ExternalContext.test.tsx`
- `frontend/src/App.tsx`
- `tests/integration/test_calendar_account_api.py`
- `tests/integration/test_calendar_persistence.py`
- `tests/integration/test_migrations.py`
- `tests/integration/test_project_memory_migration.py`
- `tests/test_memory_routes.py`
- `tests/test_models.py`
- `tests/test_operations_routes.py`
- `tests/test_project_routes.py`
- `docs/ARCHITECTURE.md`
- `docs/CHECKPOINTS.md`
- `docs/LOCAL_V1_RUNBOOK.md`
- `docs/ROADMAP.md`
- `docs/checkpoint-103-report.md`

No dependency, Tool Registry, export-format, OAuth, provider-authority, import,
scheduling, Agent, or Automation change was made. No Calendar write was added;
CP103 browsing and reconciliation make zero Google requests. CP104 was not
started. CP103 is approved and complete after human review.

### Post-commit authoritative revalidation (2026-09-04)

The final integrity audit corrected the two ORM observation-ownership composite
foreign-key names in `app/models/calendar.py` so they exactly match migration
`0016_calendar_event_observations`:
`fk_calendar_observations_run_owner` and
`fk_calendar_observations_event_owner`. No schema or behavioral contract
changed. After that correction, focused model, migration, persistence,
ownership, and equal-replay verification passed **56 backend tests**, zero
failed and zero skipped; Ruff, format, strict mypy, Alembic current/head/check,
and the exact ORM-to-migration name audit also passed.

A fresh authoritative Full run was then executed against exact committed CP103
production code containing the corrected ORM definitions. It passed **1,291
backend tests** and **145 frontend tests**, zero failed and zero skipped. Both
database identities, `pip check`, Ruff lint/format, strict mypy over 203
production files, frontend lint/typecheck/tests/build, and `git diff --check`
passed. Alembic current and sole head remained
`0016_calendar_event_observations`, with no new upgrade operations. Tool
Registry remained `agent-tools-v1`; Project export remained
`second-brain-project-export` version `1`. Verification used deterministic
fake/synthetic provider boundaries and made no real Google or Calendar request.
