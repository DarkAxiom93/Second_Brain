# Checkpoint 102 architecture-gate remediation report

Status: **Both architecture remediations approved and complete after human
review; documentation only. CP102 production implementation has not started.**

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
than 90 days. The first remediation initially proposed `singleEvents=true` and
`showDeleted=true`, a
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

## Second implementation stop: cancellation/deletion shapes

Production implementation was attempted again only after the first remediation
was committed and its exact push CI succeeded. Preflight passed on clean,
synchronized `main` with `HEAD` and `origin/main` exactly
`d804f104f92bc8f126953990bda60ad1d43f16d2`; exact push CI run `33730295478`
was completed/successful for that SHA. Both live database identities passed.
Alembic current and sole head were `0015_calendar_persistence`, `alembic check`
was clean, Tool Registry was `agent-tools-v1`, and Project export remained
`second-brain-project-export` version `1`.

The current official Google `events.list` and Event resource documentation was
reviewed before coding. Google guarantees only `id`, `recurringEventId`, and
`originalStartTime` for a cancelled recurring exception, and only `id` for
other deleted/cancelled events. CP100 requires a complete normalized revision,
including non-null provider `etag`/`updated`, event type, display label, and
complete all-day or timed bounds. A first-seen minimal tombstone has neither a
safe prior projection nor the provider fields required to satisfy that schema.
Representing it would require fabricated provider data, weakened provenance, or
a schema change. Implementation therefore correctly stopped with zero changed
files, credential access, or Calendar data requests.

## Human-approved remediation: exclude tombstones

The second architecture decision narrows CP102 again. It fixes the request to
`singleEvents=true` and `showDeleted=false`; CP102 intentionally requests and
persists no cancelled/deleted tombstone. CP100's `cancelled` and `deleted`
states remain reserved schema capacity and are not manufactured. Even with the
filter, an unexpected `status=cancelled` item or any item lacking complete CP100
normalization fields fails its whole page/run closed with a code-owned safe
failure. No missing value is fabricated or borrowed, no tombstone revision is
created, prior history is preserved, no absence is inferred, and no raw body is
exposed.

The official `events.list` contract permits repeated `eventTypes` parameters
and supports exactly `birthday`, `default`, `focusTime`, `fromGmail`,
`outOfOffice`, and `workingLocation`. CP102 freezes repeated code-owned filters
for only the five CP100-approved values: `default`, `birthday`, `focusTime`,
`outOfOffice`, and `workingLocation`. `fromGmail` and any future/unknown type are
excluded. Because `singleEvents=true`, the documented deterministic
`orderBy=startTime` is compatible. The remaining inventory is fixed
`timeMin`, `timeMax`, `maxResults=250`, minimized `fields`, and a validated
ephemeral `pageToken`. `showDeleted=true`, `updatedMin`, `q`, `syncToken`, and
collection of `nextSyncToken` are prohibited.

CP102 still performs no reconciliation. CP103 may later derive only `stale`, an
application-owned observation state meaning that a previously stored projection
expected within the exact evaluated window was not observed in a fully complete
calendar/configuration/window refresh. It is not a provider tombstone or proof
of cancellation/deletion and preserves prior provider provenance. Incomplete,
partial, or failed runs infer nothing; events outside the exact window remain
unchanged; moved-outside-window ambiguity remains uncertainty/staleness. CP103
must never derive `cancelled` or `deleted` from absence.

Threat entries G09, G10, G11, and G18 now cover approved event-type filtering,
zero tombstone ingestion/fabrication, defensive cancelled/minimal-item failure,
`showDeleted=false`, ephemeral pagination with no sync-token state, and the
complete-run-only local stale boundary. G01-G08 and G12-G17 retain their prior
controls without new authority. CP106 must prove all these properties plus zero
Calendar write and zero generic-provider authority.

## Boundary and next step

CP100 and CP101 remain approved and complete. The first CP102 architecture blocker
correctly stopped production implementation, and this full-sync-only
documentation remediation is approved after human review. The second remediation
is also approved and complete after human review. Published Local V1.4, Tool
Registry `agent-tools-v1`, Project export `second-brain-project-export` version
`1`, and Alembic `0015_calendar_persistence` are unchanged. CP102 production
implementation and CP103 have not started. CP102 may resume only after this
approved amendment is committed, pushed, and its exact push CI is successful.

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
failed and zero skipped. The initial sandboxed Full attempt collected 1,278
backend tests and reported **1,277 passed, 1 failed, 0 skipped**; the sole
failure was the known environmental Windows Credential Manager lock in the
existing real-adapter round-trip test, not a product or documentation assertion.

After explicit authorization limited to that established deterministic test
path, the authoritative Full rerun passed **1,278 backend and 142 frontend
tests, zero failed and zero skipped**. Credential-store access created a fresh
random `SecondBrain/connector/v1/<UUID>` target containing only the test constant
`cp88-obviously-fake-test-secret`, read it, replaced it with the synthetic test
replacement, verified it, revoked it, verified absence, and retained `finally`
cleanup fencing. The availability probe likewise used a fresh random application
target and synthetic capability-probe bytes with cleanup. The adapter is
non-enumerating, so no unrelated target or real Google credential was read,
modified, or displayed.

`pip check`, Ruff lint/format, strict mypy over 199 production files, frontend
ESLint/typecheck/build, and `git diff --check` passed. Both database identities
passed. Alembic current and sole head were `0015_calendar_persistence`, and
`alembic check` reported no new upgrade operations. Tool Registry remained
`agent-tools-v1`; Project export remained `second-brain-project-export` version
`1`.

The remediation used no real Google credential and made zero OAuth or Calendar
API request. Official Google developer documentation was read to verify the
contract; no Calendar data endpoint was called. It introduced no production
implementation, migration, dependency, API, UI, Calendar write, generic provider
authority, reconciliation, browser, import, scheduling, or Agent/Automation
authority. Both documentation-only remediations are approved and complete after
human review. Production implementation remains gated on this commit, push, and
successful exact push CI.
