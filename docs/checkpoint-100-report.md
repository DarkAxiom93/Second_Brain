# Checkpoint 100 report - inert Google Calendar persistence and closed catalogs

Status: **Approved and complete after human review.**

## Preflight and exact boundary

Clean synchronized `main`, `HEAD`, and `origin/main` were exactly approved CP99
commit `2779123d408ffb956a9916bfa03b260eb3fbfb54`. Exact push CI run
`33428674648` was completed/successful for that SHA. Live database identities
were `127.0.0.1:5433/second_brain` and
`127.0.0.1:5433/second_brain_test`; the initial Alembic current/sole head was
`0014_connector_refresh_schedules` and `alembic check` was clean. Tool Registry
was `agent-tools-v1`; Project export was `second-brain-project-export` version
`1`.

Checkpoint 100 adds only inert provider-specific persistence and pure closed
catalog/domain helpers. It performs no OAuth, credential-store, Google,
Calendar, browser, or other network operation. There is no Calendar API/UI,
sync executor, reconciliation, import, scheduling, Calendar Agent/Automation
authority, generic provider/OAuth/HTTP framework, or CP101 work.

## Migration and entities

The one additive revision is `0015_calendar_persistence`, directly after
`0014_connector_refresh_schedules`. It creates exactly:

- `calendar_account_revisions`: immutable configuration identity/revision,
  provider `google_calendar`, validated account fingerprint, opaque CP99
  credential reference, exact nullable Project scope, lifecycle/configuration
  state, and timestamps;
- `calendar_identities`: one immutable bounded operator-entered provider
  calendar ID bound to the exact account revision and fingerprint, without
  discovery, CalendarList, email, owner, organizer, or display metadata;
- `calendar_sync_runs`: exact account revision/calendar ownership, captured
  nullable Project scope, timezone-aware bounded window, manual/scheduled
  trigger kind, lifecycle/completeness, three bounded safe counters, safe
  code-owned failure code, and timestamps. A partial unique index permits only
  one `claimed`/`running` run per exact calendar identity;
- `calendar_event_revisions`: append-only normalized event revisions with exact
  account/calendar/run/scope provenance, provider event/series IDs, canonical
  occurrence key/original start, etag/updated time, monotonic application
  revision, content hash, minimized display/timing/state, and first/last-seen
  timestamps.

No existing GitHub connector table was altered or repurposed. The development
database was upgraded additively and was never downgraded.

## Identity, minimization, and closed catalogs

Standalone identity is the immutable provider event ID. Recurring identity is
the series ID plus canonical `originalStartTime`: a date for all-day events or
a validated timezone-aware instant for timed events. Current start/end are not
part of the key, so modified, moved/rescheduled, and cancelled occurrences
retain identity. No RRULE evaluation exists.

The closed event catalog is exactly `default`, `focus_time`, `out_of_office`,
`working_location`, and `birthday`. Unknown types fail closed. Private events
persist the fixed label `Busy`; special events persist fixed code-owned labels
`Focus time`, `Out of office`, `Working location`, or `Birthday`. Only ordinary
visible events may retain a bounded validated title.

The closed event projection catalog contains only `id`, `status`, `eventType`,
`summary`, `visibility`, `etag`, `updated`, `recurringEventId`, and the
date/dateTime/timeZone members of `originalStartTime`, `start`, and `end`.
Collection fields are only `items`, `nextPageToken`, and `nextSyncToken`. These
are pure catalogs for future review; CP100 implements no request transport and
persists no page/sync token.

Persisted event content is limited to title/fixed label, all-day flag,
date-only start/exclusive-end or timezone-aware timed start/end, optional
source timezone, closed event type/state, and private indicator. Identity and
provenance fields are limited to the exact account/config/calendar/run/Project
scope, provider event and optional series identity, canonical original start,
etag, provider updated time, application revision, normalized hash, and seen
timestamps.

Explicitly absent from the model, schema, hashable content, export, and public
surfaces are description, location, attendees, organizer, creator, guest
identities/counts/states, conference/meeting URLs, attachments, reminders,
extended properties, recurrence rules, Hangout/conference payloads, raw
provider JSON, email addresses, arbitrary URLs, access/refresh/ID tokens, auth
code, PKCE verifier, state, nonce, client secret, raw OAuth response, raw `sub`,
provider email/profile claims, and provider page/sync tokens.

## Deterministic invariants and isolation

Database constraints and repository validation enforce exact composite
ownership, account/calendar substitution rejection, monotonic configuration
and event application revisions, equal-replay uniqueness, occurrence/revision
uniqueness, bounded identifiers/text/counters/windows, one active sync per
calendar, exact nullable Project capture, valid all-day versus timed shapes,
timezone-aware timed values, end-after-start, recurrence shape, closed
types/states, fixed private/special labels, and immutable historical
scope/provenance. Null Project means only unassigned and is never interpreted as
all Projects.

Project export remains format version 1 and contains no Calendar file or field.
The synthetic credential reference and operator-entered calendar ID canaries
were absent from archive bytes. The existing import service's fixed v1 entity
inventory contains no Calendar entity; all four complete import integration
tests passed at revision 0015, proving import does not acquire a Calendar write
path or mutate Calendar persistence.

## Test-database recovery evidence

The first Full attempt exposed environmental damage in the disposable test
database: repeated historical migration downgrade/re-upgrade cycles had
accumulated PostgreSQL dropped-column attribute slots until reapplying migration
0004 failed with `psycopg.errors.TooManyColumns: tables can have at most 1600
columns`. This was not a CP100 schema or production migration failure.

After explicit human approval, the destructive safety gate connected through
maintenance database `postgres` at parsed external endpoint
`127.0.0.1:5433`. The server reported its Compose-internal address/port as
`172.18.0.2/32:5432`; both `second_brain` and `second_brain_test` existed, and
the exact drop target was `second_brain_test`. Zero test sessions required
termination. The only destructive SQL actions were equivalent to:

```sql
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = 'second_brain_test' AND pid <> pg_backend_pid();
DROP DATABASE second_brain_test;
CREATE DATABASE second_brain_test OWNER second_brain;
```

No command targeted `second_brain`; no container or volume was deleted,
recreated, or stopped. Immediately after recreation both exact databases still
existed, and a live connection to `second_brain_test` reported
`current_database() = 'second_brain_test'` with zero public tables. The normal
Alembic/test lifecycle alone prepared it.

Before and after recreation, development was exactly
`127.0.0.1:5433/second_brain` at `0015_calendar_persistence`. Its complete
ordered public-row fingerprint remained
`bfd5a94e7c4c8309ea3de9555cc30f565fdc13be9d8217197545712dc48c60c3`, and
every per-table row count was unchanged (including 2 Projects, 6 Memories, 5
embeddings, 16 Agent Runs, 21 Steps, 14 Tool Invocations, 89 Agent Events, and
zero rows in every Calendar table). Development data was not altered.

## Verification

- Post-recreation focused suite: **29 passed, 0 failed, 0 skipped**.
- Sandboxed Full backend run: schema/migration damage was resolved; **1,264
  passed**, with only the known Windows Credential Manager sandbox lock failing.
- Exact OS credential-store round-trip outside the sandbox: **1 passed**.
- Final authoritative Full run with OS-store access: **1,265 backend and 137
  frontend passed, 0 failed, 0 skipped**.
- `pip check`, Ruff lint/format, strict mypy over 195 production files,
  frontend ESLint/typecheck/build, and `git diff --check`: passed.
- Alembic current and sole head: `0015_calendar_persistence`; `alembic check`:
  no new upgrade operations.

Automated tests used only synthetic identities and credential references. Zero
real Google credential was read, created, modified, printed, or used. Zero real
OAuth/Google/JWK/revocation/Calendar request and zero Calendar data request
occurred. There is no remaining verification uncertainty.

## Exact changed paths

- `app/calendar/__init__.py`
- `app/calendar/catalog.py`
- `app/calendar/identity.py`
- `app/diagnostics/service.py`
- `app/models/__init__.py`
- `app/models/calendar.py`
- `app/project_export/models.py`
- `app/repositories/calendar.py`
- `docs/ARCHITECTURE.md`
- `docs/CHECKPOINTS.md`
- `docs/LOCAL_V1_RUNBOOK.md`
- `docs/ROADMAP.md`
- `docs/V1_5_CALENDAR_ROADMAP.md`
- `docs/checkpoint-100-report.md`
- `migrations/versions/0015_calendar_persistence.py`
- `tests/integration/test_calendar_persistence.py`
- `tests/integration/test_migrations.py`
- `tests/integration/test_project_memory_migration.py`
- `tests/test_calendar_catalog.py`
- `tests/test_models.py`
- `tests/test_operations_routes.py`

Checkpoint 100 is approved and complete after human review. CP101 was not
started.

## Postscript - CP102 architecture-gate remediation

The later CP102 preflight confirmed that this intentionally inert schema has no
provider sync-token, immutable incremental-request-fingerprint, or captured
credential-generation column. Implementation correctly stopped before any
production change. A subsequent human architecture decision removed
incremental sync from the Local V1.5 baseline rather than authorizing a new
migration for an optimization.

Future V1.5 Calendar refresh is independent bounded manual full-sync only.
`nextPageToken` may exist only as bounded, loop-detected in-memory continuation
for one executing refresh. `syncToken` and `nextSyncToken` are never requested,
consumed, stored, hashed, exposed, or persisted. The historical CP100 catalog
did include `nextSyncToken` as an inert reviewed collection field, but CP102 may
remove it from the active projection. Alembic remains
`0015_calendar_persistence`; CP100's approved status is unchanged.
The documentation-only CP102 architecture remediation was subsequently approved
after human review; CP102 production implementation and CP103 remain not
started.
