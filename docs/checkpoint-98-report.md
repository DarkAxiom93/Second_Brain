# Checkpoint 98 report - Local V1.5 Calendar planning

Status: **Approved and complete after human review; documentation only.**

## Outcome and selected direction

Checkpoint 98 selects **Local V1.5 - Read-only Google Calendar Context** as the
next independently reviewable release. Calendar wins over Agent/Automation UX,
export/backup evolution, and proposal/write workflows because it adds strong
daily, time-oriented context while remaining compatible with the proven
quarantine model, exact Project scope, deterministic fake-provider testing, and
the trusted single-maintainer local boundary. UX work offers less new evidence;
export v2 introduces encryption/restore compatibility risk; write workflows
introduce materially greater authority, ambiguity, and recovery complexity.

This checkpoint is planning only. It implements no V1.5 production capability.

## Preflight

- `main` was clean and synchronized with `origin/main` at
  `613335a12a259d33156c52542e202f31407afe34` after an explicit fetch.
- Post-publication documentation-sync push CI run `33331824923` for that SHA was
  completed successfully.
- `v1.4.0` was the current/latest repository tag and published non-draft,
  non-prerelease GitHub Release. Its tag resolves to exact release commit
  `c02a8ccb4b0b93a2fb73f23c112344b69eaac39a`; release-commit CI run
  `33327262569` was successful.
- Parsed and live databases were verified as `second_brain` and
  `second_brain_test` on `127.0.0.1:5433`.
- Alembic current and sole head were `0014_connector_refresh_schedules`.
- Tool Registry was `agent-tools-v1`.
- Project export was `second-brain-project-export` version `1`.

No preflight mismatch occurred. The first direct Alembic probe inherited the
container-only `db` hostname and could not resolve it from Windows; the canonical
host-side database verification then proved both parsed/live identities and the
required revision before any edit.

## Calendar, privacy, and authority boundary

The planned baseline is one explicitly authorized Google account, a non-empty
maximum-10 allowlist of exact immutable calendar IDs, one exact Project or
explicit unassigned scope, manual refresh, minimized/versioned quarantined event
snapshots, deterministic reconciliation, and accessible External Context
browsing.

Stored/public event data is limited to provider/calendar/event/recurrence
identity, provider and application revision, status/type/visibility flags,
bounded ordinary title, normalized start/end/source timezone or all-day dates,
state, first/last seen, content hash, and exact sync/scope provenance. Private
events use fixed `Busy`; working-location, focus, out-of-office, birthday, and
other reviewed special types use fixed labels and timing only.

Descriptions, locations, organizer, attendees and external guests, conference
links, attachments, reminders, extended properties, creator and type-specific
properties are excluded from requests, storage, hashes, UI, logs, exports,
prompts, and import. They are absent rather than pseudonymized. Calendar data is
still classified sensitive because local storage is not itself a privacy
control.

Explicit single-event import is omitted from the V1.5 baseline. CP104 is a
separate decision gate because the minimized time-context projection is not an
audited document and the CP93 provenance path must first be proven provider-
neutral. Scheduled refresh is likewise excluded unless CP105 separately
approves it after manual refresh. `ExternalItem` remains unavailable to every
Agent and Automation throughout V1.5; Daily Brief and Project Watch cannot use
Calendar. Tool Registry `agent-tools-v1` is unchanged.

Explicit exclusions include every Calendar write/respond action, Gmail, Drive,
Contacts, discovery outside the allowlist, arbitrary Google APIs, generic OAuth
providers, arbitrary HTTP/GraphQL, external writes, automatic/bulk import,
Memory/proposal/Approval/promotion creation, direct connector Tools, arbitrary
execution, authentication/multi-user/remote/cloud operation, and export v2.

## OAuth and credentials

The design follows Google's current official installed/desktop application
guidance: authorization code with PKCE S256, fresh state/verifier, system
browser, ephemeral `127.0.0.1` callback listener, exact callback/state handling,
and token exchange outside database transactions. The sole Calendar scope is
`https://www.googleapis.com/auth/calendar.events.readonly`; Calendar discovery,
identity, Gmail, Drive, Contacts, settings, ACL, and write scopes are not
requested.

Access tokens are short-lived and memory-only. Refresh tokens live only in a
versioned envelope behind the existing Windows per-user credential-store
abstraction. PostgreSQL may retain only an opaque reference, verified account
fingerprint, exact scope fingerprint, lifecycle, and safe timestamps. Rotation
uses fenced atomic envelope replacement. Missing, expired, revoked, rejected,
scope-changing, or identity-changing credentials stop reads and require explicit
reauthorization/review. CP99 must prove stable account verification without
silently adding identity scope; inability is a blocker.

No access/refresh token, code, client secret, PKCE material, state, cookie, or
recoverable secret may enter PostgreSQL, Project export, browser storage, logs,
diagnostics, notifications, errors, reports, crash output, prompts, or fixtures.

## Transport and reconciliation

The Calendar data inventory is only GET
`https://www.googleapis.com/calendar/v3/calendars/{allowlistedCalendarId}/events`.
Authorization uses the fixed Google authorization origin and token/revocation
endpoints required by the reviewed OAuth lifecycle; OAuth POSTs grant no
Calendar write authority. Redirects are disabled for API/token transport. There
is no arbitrary URL, query, header, batch, free/busy, CalendarList, watch,
instances endpoint, or event-content link following.

Proposed CP102 ceilings are 10 calendars; 90 days (30 past/60 future); 250 items
per page; 10 pages and 1,000 events per calendar; 5,000 events, 10 MiB, 50
Calendar requests, and 60 seconds per run; 1 MiB per response; and at most two
closed transient GET retries within the same deadline. Pagination/sync tokens
are opaque, bounded, loop-detected, and tied to the exact request fingerprint.
No lock or transaction spans OAuth, credential-store, network, browser, retry
sleep, or provider latency.

Occurrence identity is immutable account + calendar + provider event/series +
canonical `originalStartTime`; current start/end are mutable. Equal replay is
write-free. Changed validated provider identity/hash advances one application
revision. Modified and moved instances retain occurrence identity. Cancellation
creates a minimal tombstone. Whole pages validate before short commits, and a
new sync token/success commits only after all pages. Partial pages, ceilings,
timeouts, auth ambiguity, invalid sync tokens, schema/scope/revision drift, and
other incomplete runs never infer deletion. Complete same-window/filter/account
reconciliation alone may mark absence stale. All-day dates remain dates;
timezone-aware IANA conversion and provider original-start identity preserve DST
semantics.

## Threat model and implementation sequence

The dedicated register defines:

- G01 OAuth/token leakage; G02 excessive OAuth scope; G03 confused deputy/account
  substitution; G04 calendar-scope substitution;
- G05 cross-Project/unassigned leakage; G06 hostile/prompt-injection content;
  G07 attendee/privacy leakage; G08 malicious links/conference URLs;
- G09 recurring identity ambiguity; G10 deletion/reconciliation mistakes; G11
  pagination/time-window amplification; G12 rate-limit/retry abuse;
- G13 credential revocation/replacement races; G14 scheduler duplicate/restart/
  fencing; G15 import replay/revision drift; G16 export/backup leakage;
- G17 configuration authority injection; and G18 unexpected provider/network/
  fault behavior.

Each threat has prevention, fail-closed behavior, and a named deterministic
CP106 gate. The proposed independently reviewable sequence is CP99 OAuth/credential
prerequisite; CP100 inert persistence/catalog; CP101 account lifecycle/UI; CP102
bounded transport/manual sync; CP103 External Context/reconciliation; CP104
import decision gate; CP105 optional scheduling decision; CP106 G01-G18 gate;
CP107 E2E acceptance; and CP108 release hardening. Every checkpoint documents
dependency, production area, migration, API/UI, transaction/concurrency,
security/tests, and rollback/failure behavior. None authorizes its successor.

CP100 expects one additive provider-specific persistence migration after `0014`.
CP99, CP101-103, CP106-108 expect none. CP104 and CP105 add migrations only if
their separately reviewed optional capabilities require them. CP98 adds no
migration.

## Verification

Documentation-focused checks passed: `git diff --check`, changed-path review,
link/identity search, and confirmation that no application, frontend, migration,
dependency, lockfile, registry, export, CI, or Docker path changed. No new test
was necessary for a documentation-only checkpoint.

The first Full run passed pip, Ruff, formatting and mypy, then reported 1,233
passes and four failures in unchanged tests: three Agent execution tests hit the
pre-existing sub-millisecond `occurred_at <= recorded_at` database timing edge,
and the real Windows credential test was blocked by sandboxed Credential Manager
access. The exact four-test focused rerun with host credential access passed
**4/4** unchanged.

The authoritative host-access rerun of `scripts/verify.ps1 -Mode Full` passed:

- pip integrity, Ruff lint/format, and strict mypy over 182 production files;
- backend **1,237 passed**, zero skipped (12 warnings);
- Alembic current/head `0014_connector_refresh_schedules` and `alembic check`
  with no new upgrade operations;
- frontend ESLint and TypeScript;
- frontend **137 passed across 14 files**, zero skipped;
- Vite production build, 87 modules transformed;
- `git diff --check`.

## Changed paths and handoff

Changed paths are exactly:

- `docs/ARCHITECTURE.md`
- `docs/CHECKPOINTS.md`
- `docs/ROADMAP.md`
- `docs/V1_5_CALENDAR_ROADMAP.md`
- `docs/V1_5_CALENDAR_THREAT_MODEL.md`
- `docs/checkpoint-98-report.md`

Everything is left unstaged and uncommitted. No commit, push, PR, tag, release,
or Checkpoint 99 work occurred. No V1.5 production capability, migration,
dependency, lockfile, Tool Registry, export format, external request authority,
Agent/Automation authority, or V1.4 release artifact changed. Local V1.4 remains
published and unchanged at `v1.4.0` from exact release commit
`c02a8ccb4b0b93a2fb73f23c112344b69eaac39a`.

Checkpoint 98 is approved and complete after human review. Checkpoint 99 is not
started.
