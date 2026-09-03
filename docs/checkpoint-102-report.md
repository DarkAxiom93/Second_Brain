# Checkpoint 102 architecture-gate remediation report

Status: **Approved after human review; documentation only.**

## Preflight and implementation stop

The CP102 preflight succeeded on clean synchronized `main` at exact approved
CP101 commit `3c9bdf663d0a5c7d473a9288c40f25f76487eba1`. Exact push CI run
`33672237774` was completed/successful for that SHA. Live development and test
database identities were `127.0.0.1:5433/second_brain` and
`127.0.0.1:5433/second_brain_test`. Alembic current and sole head were
`0015_calendar_persistence`, and `alembic check` was clean. Tool Registry was
`agent-tools-v1`; Project export was `second-brain-project-export` version `1`.

Implementation correctly stopped because CP100 intentionally persists no
provider sync token, immutable incremental request fingerprint, or captured
credential-envelope generation. These omissions made the originally planned
incremental sync contract unrepresentable without a schema change. Zero
production code, migration, dependency, API/UI, credential, Google, or Calendar
request change occurred before the stop.

## Human-approved remediation

Local V1.5 is narrowed to bounded manual full-sync only. Every explicit refresh
will independently read the exact active CP101 allowlist through only
`GET https://www.googleapis.com/calendar/v3/calendars/{allowlistedCalendarId}/events`.
Before implementation, CP102 must verify the final exact `events.list` parameter
inventory against current official Google Calendar documentation and stop on a
contract conflict rather than widen scope.

The code-owned window is exactly 30 days past and 60 days future, never more
than 90 days. Full-sync requests use `singleEvents=true`, `showDeleted=true`, a
maximum 250 items per page, 10 pages and 1,000 accepted events per calendar,
5,000 accepted events and 50 Calendar requests per run, 1 MiB per response,
10 MiB cumulatively, and 60 seconds wall clock. Operators cannot provide a
window or arbitrary filters.

No `syncToken` is requested or consumed, and no `nextSyncToken` is collected,
stored, hashed, exposed, or persisted. A bounded `nextPageToken` may exist only
in memory for one active exact request, must be loop-detected, and disappears
when the refresh succeeds or terminates. Consequently no durable incremental
request fingerprint or credential generation is required, and migration
`0016` is neither needed nor authorized. Alembic remains
`0015_calendar_persistence`.

CP102 must still validate the exact current CP101 configuration revision,
allowlisted calendar, Project/unassigned scope, CP99 credential reference,
same-account fingerprint, lifecycle, and exact scopes before Calendar access.
It obtains memory-only access through CP99 and relies on CP99's generation fence
for token rotation. Network and backoff occur outside SQL transactions. Current
configuration and account eligibility are rechecked before each persisted page
and terminal success so stale, disabled, revoked, or substituted work fails
closed.

Every partial, failed, timed-out, ceiling-exhausted, malformed,
revision-drifted, or otherwise incomplete run preserves accepted history,
infers no absence/deletion, starts no replacement sync, and never widens its
window. Unexpected provider 4xx responses fail closed. There is no token-reset
or 410 recovery workflow in V1.5.

CP102 performs no absence-based reconciliation. CP103 may later reconcile only
from a fully complete bounded full-sync run and only for identities proven
covered by that exact calendar, configuration, and window. Events outside the
current rolling window cannot become stale or deleted merely through absence.

Threat-model entries G10, G11, G13, and G18 now encode complete exact-window
evidence, ephemeral loop-detected pagination, zero sync-token state, CP99 and
configuration fencing, fail-closed unexpected 4xx behavior, and zero Calendar
write or generic-provider authority. The future CP106 gate must prove these
properties without expanding authority.

## Boundary and next step

CP100 and CP101 remain approved and complete. The CP102 architecture blocker
correctly stopped production implementation, and this full-sync-only
documentation remediation is approved after human review. Published Local V1.4, Tool
Registry `agent-tools-v1`, Project export `second-brain-project-export` version
`1`, and Alembic `0015_calendar_persistence` are unchanged. CP102 production
implementation and CP103 have not started. CP102 may resume only after this
amendment is committed, pushed, and its exact push CI is successful.

No files are staged or committed by this remediation.

## Changed paths and verification

Exact changed paths:

- `docs/ARCHITECTURE.md`
- `docs/CHECKPOINTS.md`
- `docs/ROADMAP.md`
- `docs/V1_5_CALENDAR_ROADMAP.md`
- `docs/V1_5_CALENDAR_THREAT_MODEL.md`
- `docs/checkpoint-100-report.md`
- `docs/checkpoint-102-report.md`

Focused Calendar regression verification passed **20 backend tests**, zero
failed and zero skipped. The authoritative Full run passed **1,278 backend** and
**142 frontend** tests, zero failed and zero skipped. `pip check`, Ruff lint and
format check, strict mypy over 199 production files, frontend ESLint, TypeScript
checking, production build, and `git diff --check` passed. Both database
identities passed. Alembic current and sole head were
`0015_calendar_persistence`, and `alembic check` reported no new upgrade
operations.

The remediation used no real Google credential and made zero Google, OAuth, or
Calendar request. It introduced no production implementation, migration,
dependency, API, UI, Calendar write, generic provider authority, reconciliation,
browser, import, scheduling, or Agent/Automation authority. It is approved after
human review as a documentation-only architecture amendment; implementation
remains gated on commit, push, and successful exact push CI.
