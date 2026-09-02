# Local V1.5 read-only Google Calendar context roadmap

Status: **Checkpoint 101 approved and complete after human review.**

Checkpoint 98 defines architecture only. It implements no Calendar, OAuth,
transport, persistence, API, UI, Agent, Automation, import, scheduling, or
external-write capability. Local V1.4 remains the published recovery boundary:
`v1.4.0` at `c02a8ccb4b0b93a2fb73f23c112344b69eaac39a`, Alembic
`0015_calendar_persistence`, Tool Registry `agent-tools-v1`, and Project
export `second-brain-project-export` version `1`.

Checkpoint 99 implements only the approved exact two-scope OAuth and credential
prerequisite and is approved and complete after human review. It does not
authorize or start Checkpoint 100 or any later checkpoint.

## Decision and alternatives

Select **Local V1.5 - Read-only Google Calendar Context** as the next
independently reviewable release. It adds high daily value to the already proven
quarantined External Context model while keeping authority read-only, manual,
allowlisted, local, and separate from Agents and reviewed knowledge.

| Candidate | User value | Security and recovery | Migration/test impact | Decision |
|---|---|---|---|---|
| Read-only Google Calendar context | High, current time-oriented Project context | Sensitive, but containable through minimization, OAuth isolation, quarantine, and no writes | Additive provider persistence; deterministic fake OAuth/transport/clock tests | **Select** |
| Agent/Automation UX and observability | Useful polish, low risk | Easy rollback, but does not broaden evidence available to the operator | Mostly UI/projection work | Retain for patches, not V1.5's release theme |
| Export/backup evolution | Moderate resilience value | Encryption, key loss, compatibility, and secret/snapshot backup policy are a separate recovery boundary | Export v2 and restore matrix would be cross-cutting | Defer |
| Proposal/write workflows | Potentially high value | Confused-deputy, target drift, ambiguous external writes, and compensation are materially higher risk | New authority and recovery state machines | Defer |

The selection is the best balance of user value, bounded deterministic testing,
additive migration shape, and fit with one trusted local maintainer. It does not
justify Google-wide access, generic OAuth providers, autonomous access, writes,
or Agent access.

## Exact V1.5 boundary

The planned release contains one Google Calendar connector for one explicitly
authorized Google account. The operator supplies a non-empty allowlist of exact
immutable calendar IDs and binds the account revision to exactly one Project or
explicit unassigned scope. Initial refresh is manual. Validated snapshots are
versioned, quarantined, browseable under accessible External Context UI, and
reconciled deterministically. Null Project means unassigned and never all
Projects.

The smallest useful public/stored event projection is:

- immutable calendar ID, provider event ID, recurring series ID when present,
  and original occurrence start identity when present;
- provider `etag` and `updated` identity, application revision, status, event
  type, visibility/private redaction flag, and content hash;
- bounded summary/title for ordinary visible events only;
- normalized start and exclusive end, source timezone where supplied, all-day
  flag and calendar-local dates for all-day events;
- current/stale/cancelled/deleted state, first/last seen, exact sync run,
  account revision, calendar identity, and historical Project/unassigned scope.

Field decisions are closed:

| Google event field | V1.5 treatment |
|---|---|
| Summary/title | Store/display bounded plain text only for ordinary non-private events; private events use the fixed label `Busy` |
| Start/end/timezone | Store normalized instants plus validated IANA/source timezone; retain date-only values for all-day events |
| All-day events | Include; end date remains exclusive and no midnight instant is invented |
| Description | Exclude from requests, persistence, hashes, UI, logs, import, and prompts |
| Location | Exclude |
| Organizer | Exclude |
| Attendees/external guests | Exclude identities, counts, response states, comments, and self flags |
| Conference links/entry points | Exclude and never render as links |
| Attachments | Exclude; never follow or fetch |
| Reminders | Exclude |
| Recurrence | Store only bounded recurrence identity needed for reconciliation; do not publicly expose raw rules |
| Cancelled/deleted | Store a minimal tombstone with identity and prior safe projection; never infer from partial sync |
| Private events | Store timing/status/identity only with fixed `Busy`; never store returned private content |
| Working location, focus time, out of office, birthday and unknown event types | Store timing, safe code-owned type, and fixed label only; exclude type-specific properties; unknown types fail the page/run closed until reviewed |

No automatic import is planned. Explicit single-event import is also **omitted
from the V1.5 baseline**: the minimized projection is useful as time context but
is not a sufficient audited document, and the existing Checkpoint 93 import
path must be proven provider-neutral before reuse. Checkpoint 104 is a decision
gate only; adding import requires separate approval and, if needed, an additive
provider-neutral provenance migration. No event may create Memory, a proposal,
Approval, Agent Run, or local reviewed fact.

Scheduled refresh is also optional and excluded until Checkpoint 105 is
separately approved. Manual refresh must be accepted first.

## OAuth and credential architecture

Use Google's installed/desktop application authorization-code flow with PKCE
S256, a fresh high-entropy verifier and state per attempt, the system browser,
and an ephemeral loopback listener bound only to `127.0.0.1` on an OS-selected
port. The callback path and state are single-use, authorization expires quickly,
and the listener closes after one success/failure. No embedded browser is used.
OAuth and token requests occur outside database transactions and locks.

The exact requested OAuth scope set contains only:

- `openid`, used solely to validate the stable Google Account `sub`; and
- `https://www.googleapis.com/auth/calendar.events.readonly`, used solely for
  the later approved events-list reads.

Do not request `email`, `profile`, `calendar`, `calendar.readonly`, CalendarList,
calendar metadata, settings, ACL, Gmail, Drive, Contacts, any generic Google
scope, or any write scope. Calendar IDs are entered by the operator and
validated individually through the closed events-list surface; there is no
calendar discovery. Explicit consent text states both exact scopes, the identity-
only purpose of `openid`, account binding, local retention, excluded fields, and
revocation behavior.

The OAuth desktop client ID is non-secret configuration. If Google issues a
desktop client secret, treat it as public client identity rather than a security
boundary, but keep it out of PostgreSQL, exports, logs, browser storage, and
diagnostics; operator configuration must follow the provider's current desktop
client requirements. Access token, refresh token, authorization code, PKCE
verifier, state, cookies, and any recoverable secret exist only in bounded
memory or the existing Windows per-user credential-store abstraction. The store
holds one versioned opaque credential envelope; PostgreSQL holds only its opaque
reference, safe scope fingerprint, verified account fingerprint, lifecycle,
and timestamps.

The access token is short-lived and memory-only. Refresh occurs only immediately
before an authorized request, using the stored refresh token, with response
validation and atomic credential-envelope replacement. A newly returned refresh
token replaces the old envelope; concurrent refresh is serialized/fenced per
account revision so a stale result cannot overwrite a newer token. Missing,
expired, revoked, rejected, malformed, identity-changing, or scope-changing
credentials stop before Calendar requests, disable/fence refresh as appropriate,
preserve prior snapshots, and require explicit reauthorization. Reauthorization
must prove the same selected Google account or require disable plus explicit new
account configuration. Revocation closes future reads, attempts exact provider
revocation where supported, deletes the exact local envelope, and reports only
a safe status if either step fails.

Account identity verification requires an ID token returned by the installed-
app authorization-code flow. A supported Google OpenID Connect validation
library must validate the token against the trusted Google issuer, exact
application client audience, expiration and issued-at validity, and the fresh
authorization-attempt nonce. The application accepts only a non-empty bounded
`sub` as provider identity input and ignores and discards every other unapproved
claim. It never requests or persists email/profile data, never uses email as
identity, never persists the ID token or raw authentication response, and never
calls userinfo, Calendar metadata, or CalendarList as an identity fallback.

The application-owned stable account fingerprint is the lowercase hexadecimal
SHA-256 digest of the exact UTF-8 byte encoding of
`second-brain:google-account:v1:<sub>`, where `<sub>` is the validated Google
`sub` with no transformation or delimiter insertion beyond that fixed prefix.
The fingerprint contains no client secret, access token, refresh token, email,
or other claim. Future persistence stores only this versioned non-secret
fingerprint, preferably never raw `sub`. Reauthorization derives the same
fingerprint from a fresh, fully validated ID token and must match the exact
credential/account being replaced; a different `sub` fails closed as account
substitution while preserving the prior valid envelope.

Application code parses only the required identity claims. Unexpected ID-token
claims must not enter persistence, the credential envelope or metadata, logs,
diagnostics, reports, public schemas, browser storage, External Context, or
Calendar data. If the chosen validation library requires `email`, `profile`, a
userinfo request, or any broader authority, CP99 stops rather than widening the
boundary.

No access, refresh, or ID token; raw `sub`; raw authentication response; code;
client secret; cookie; verifier; state; or recoverable secret may enter
PostgreSQL, Project export, browser storage, URLs retained after callback, logs,
diagnostics, notifications, errors, reports, crash output, prompts, or fixtures.
Tests use unmistakably synthetic fake credential and OAuth services.

## Data and reconciliation model

Calendar uses the proven connector concepts only after a schema review; GitHub-
specific assumptions are not generalized by configuration. Proposed concepts:

- a provider-specific Calendar account/configuration revision with verified
  account fingerprint, opaque credential reference, exact immutable calendar
  allowlist, exact Project/unassigned scope, and lifecycle;
- immutable calendar identity rows, separate from mutable display metadata;
- one bounded sync run capturing account revision, date window, limits, trigger,
  completeness, safe counts/error, and sync-token generation;
- versioned normalized event snapshots keyed by account + calendar ID + provider
  event ID + occurrence identity; provider `etag`/`updated` identifies provider
  version while a monotonic application revision identifies accepted local
  change;
- a recurring occurrence identity of series/event ID plus canonical
  `originalStartTime` (date or timezone-aware instant). Current start/end are
  mutable presentation data and never the occurrence key.

Manual full sync expands occurrences only inside a fixed bounded window with
`singleEvents=true`, `showDeleted=true`, and deterministic ordering. Expansion
is provider-owned; the application does not implement arbitrary RRULE
evaluation. A modified instance retains the series plus original-start identity.
A moved/rescheduled instance updates its current times without changing that
identity. A cancelled instance records a tombstone for that occurrence. A
cancelled series or explicit deletion affects only identities explicitly
returned or covered by a fully completed reconciliation.

Deterministic rules:

- equal provider identity and normalized hash is write-free replay;
- any validated changed provider identity/hash appends/advances one application
  revision while preserving provenance used by prior local artifacts;
- older/out-of-order provider versions cannot replace a newer accepted revision;
- every accepted page is validated completely before a short transaction;
  run success and the new sync token commit only after all pages complete;
- partial page, missing page, ceiling, timeout, ambiguous 404/410, token reset,
  schema error, or scope/revision drift marks the run incomplete and never
  infers deletion;
- an invalid sync token triggers a later bounded full-resync requirement; it
  does not wipe local history or mark absence deleted;
- complete reconciliation may mark previously current in-window occurrences
  stale only when the same immutable calendar, account revision, exact window,
  filters, and successful terminal page prove coverage;
- timezone conversion uses IANA zones and timezone-aware instants. Ambiguous or
  nonexistent local times fail closed; all-day dates remain dates. DST changes
  never change occurrence identity derived from provider original start.

Scope changes require disablement, revision fencing, and a new sync. Historical
snapshots retain their captured scope and are never remapped. Removing a calendar
from the allowlist stops new reads and marks visibility/configuration state
without pretending its events were provider-deleted.

## Privacy and display

Local storage is not a privacy guarantee. Data minimization is the primary
control: attendee and organizer identities, guest lists, descriptions,
locations, meeting links, attachments, reminders, extended properties, creator,
hangout data, and type-specific metadata are not requested or stored. They are
neither hashed nor redacted into recoverable metadata; they are absent. Provider
IDs needed for reconciliation may be stored but are never presented as people.

Private and special-type events expose only fixed code-owned labels and timing.
Ordinary titles are length/Unicode/control-character bounded, escaped as inert
text, labeled external/untrusted, and never clickable or instruction-bearing.
Public projections contain exact safe provenance and stale state but no raw
provider JSON, OAuth metadata, sync/page tokens, secrets, email addresses, URLs,
or excluded fields. Export v1 excludes all Calendar account, credential,
snapshot, sync, and scheduling state. Machine/database backups remain sensitive
and are outside Project export guarantees.

## Closed request and transport inventory

The only provider hosts are `accounts.google.com` for interactive authorization,
`oauth2.googleapis.com` for token/revocation operations required by the reviewed
OAuth lifecycle, and `www.googleapis.com` for the fixed GET-only Google OpenID
Connect JWK set at `/oauth2/v3/certs` and later Calendar API reads. JWK retrieval
is code-owned, bounded, cacheable, outside database transactions, and grants no
Calendar data authority. Arbitrary OIDC discovery, issuer configuration, JWK or
certificate URL, and userinfo are prohibited. Calendar data requests are only
`GET /calendar/v3/calendars/{allowlistedCalendarId}/events`.
OAuth POSTs do not grant Calendar write authority. Redirects are disabled for
API/token calls; any required authorization redirect remains system-browser
navigation to the fixed authorization origin. Calendar IDs and page/sync tokens
are encoded as values, never accepted as hosts or paths.

CP102 must freeze exact numeric ceilings before implementation. Required maxima
are: 10 allowlisted calendars, a 90-day window (30 days past/60 future), 250
items per page, 10 pages per calendar, 1,000 accepted events per calendar and
5,000 per run, 1 MiB per response and 10 MiB per run, 50 Calendar requests per
run, and 60 seconds wall clock. Field projection requests only collection
pagination/sync metadata and the approved event fields. No `q`, CalendarList,
free/busy, batch, watch/webhook, instances endpoint, arbitrary query, or generic
URL is available.

Retries are at most two additional attempts for GET-only connect timeout, read
timeout before a complete response, 429, and selected 5xx responses, within the
same request/deadline budget. Backoff and `Retry-After` are capped. There is no
retry for auth/scope/identity/schema/redirect/limit/4xx ambiguity. Continuation
tokens are opaque, length-bounded, tied to the exact request fingerprint, loop-
detected, and accepted only from the validated response field. No database lock
or transaction spans browser, credential-store, OAuth, sleep, or network time.

## Agent, Automation, scheduling, and authority

`ExternalItem` remains unavailable to every Agent throughout V1.5.
`agent-tools-v1` does not change. Calendar cannot influence Daily Brief,
Project Watch, Research, Curator, manual Runs, proposals, Approvals, or existing
Automations. Any future use requires a dedicated checkpoint, new Tool/authority
review, privacy projection, prompt-injection gate, and deterministic evidence
rules.

If separately approved after manual refresh, Calendar scheduling must use a
Calendar-specific reviewed persistence model or prove reuse is semantically
safe; GitHub schedule rows are not assumed reusable. It is disabled by default,
explicitly enabled, revision-fenced, uniquely keyed per occurrence, bounded to
`skip` or `run_once`, and never replay-all. It creates no AgentRun, import,
credential prompt, consent, scope widening, or external write.

## Explicit exclusions

V1.5 does not authorize Calendar create/update/delete/respond, Gmail, Drive,
Contacts, arbitrary Google APIs, Calendar discovery, arbitrary HTTP/GraphQL,
generic OAuth providers, external writes, automatic or bulk event import,
Memory/proposal/Approval/promotion creation, direct connector Tools, shell,
Python, SQL, filesystem or browser execution, authentication, multi-user,
remote/cloud deployment, export v2, or access outside the selected account and
calendar allowlist.

## Implementation sequence after Checkpoint 98

Every checkpoint requires human approval of its predecessor and authorizes only
its own stated scope. Production rollback is forward repair; migration
downgrades run only on the verified test database.

### 99 - Google OAuth and credential prerequisite

- **Dependency:** approved CP98.
- **Goal/areas:** installed-app authorization-code PKCE loopback authorization;
  the exact `openid` plus `calendar.events.readonly` scope set; validated Google
  ID-token `sub`; versioned application-owned account fingerprint; OS-store
  envelope lifecycle; explicit revoke/reauthorize; OAuth service, credential
  adapter, local operator surface and safe diagnostics.
- **Persistence/migration:** none expected; no Calendar tables or secrets.
- **API/UI:** no Calendar data API/UI and no browser token persistence.
- **Transactions/concurrency:** OAuth/store/network outside SQL; single-use state
  and fenced atomic token replacement.
- **Security/tests:** synthetic OAuth server, callback/state/PKCE/account/scope,
  issuer/audience/time/nonce/`sub` validation, forged/replayed ID tokens,
  identity-changing reauthorization, claim minimization, fingerprint vectors,
  rotation/revocation/races and canary non-leakage.
- **Rollback/failure:** remove inert prerequisite and named synthetic envelopes;
  any identity/scope uncertainty blocks CP100.

### 100 - Inert Calendar persistence and closed catalog

- **Dependency:** approved CP99.
- **Goal/areas:** provider-specific inert account, calendar identity, sync and
  event revision model plus closed field/type/request catalog.
- **Persistence/migration:** one additive migration after `0014`; export v1
  explicitly excludes every new table and reference.
- **API/UI:** none.
- **Transactions/concurrency:** caller-owned sessions, uniqueness, monotonic
  revisions, one-active-sync barriers; no network.
- **Security/tests:** constraints, field exclusion, nullable-scope isolation,
  recurrence identity, migration lifecycle and export/canary exclusion.
- **Rollback/failure:** revert inert code; production uses reviewed forward
  repair and gains no capability.

### 101 - Calendar account lifecycle and safe UI

- **Dependency:** approved CP100.
- **Goal/areas:** create/list/read/disable/re-enable/revoke metadata and exact
  calendar/Project configuration; service, typed loopback routes and Settings.
- **Persistence/migration:** none expected.
- **API/UI:** metadata only; no event request or secret entry/display.
- **Transactions/concurrency:** account locks and revision CAS fence edits.
- **Security/tests:** account substitution, hostile calendar IDs, allowlist and
  scope isolation, accessibility and zero browser secret storage.
- **Rollback/failure:** disable/revoke account; no external snapshot exists.

### 102 - Bounded Calendar read transport and manual sync

- **Dependency:** approved CP101.
- **Goal/areas:** exact GET inventory, minimized projection, manual bounded full/
  incremental sync with fake transport acceptance.
- **Persistence/migration:** none expected beyond CP100.
- **API/UI:** explicit manual refresh and safe run status only.
- **Transactions/concurrency:** committed claim before credential/network work;
  validated short page commits; no locks across latency.
- **Security/tests:** hosts/methods/fields/limits/retries, token revocation,
  partial pages, 410, DST, recurrence and zero excluded-field persistence.
- **Rollback/failure:** disable transport/account; preserve prior snapshots and
  mark incomplete without deletion inference.

### 103 - Calendar External Context and reconciliation

- **Dependency:** approved CP102.
- **Goal/areas:** accessible scoped list/detail projections and deterministic
  current/stale/cancelled/deleted reconciliation.
- **Persistence/migration:** none expected.
- **API/UI:** read-only External Context, fixed private/special labels, no links.
- **Transactions/concurrency:** SQL scope/order/pagination; sync-revision fencing.
- **Security/tests:** Project A/B/unassigned isolation, XSS/injection corpus,
  equal/change/move/exception/cancel/delete/full-vs-partial matrices.
- **Rollback/failure:** hide Calendar browsing and disable refresh; history is
  preserved and no reviewed knowledge changes.

### 104 - Explicit event-import decision gate

- **Dependency:** approved CP103.
- **Goal/areas:** prove omission remains correct or separately propose a single-
  revision preview/confirm import with provider-neutral provenance.
- **Persistence/migration:** none when omitted; any schema change requires an
  explicit additive migration and approval in this checkpoint.
- **API/UI:** baseline has no import action.
- **Transactions/concurrency:** if later approved, confirmation is network-free,
  revision-exact, idempotent and creates only Source/SourceDocument.
- **Security/tests:** no automatic import, Memory, proposal, Agent or schedule;
  revision-drift/replay tests if capability is approved.
- **Rollback/failure:** omission is the default; a rejected design leaves CP103
  read-only browsing intact.

### 105 - Optional Calendar refresh scheduling decision

- **Dependency:** approved CP104 and explicit approval to include scheduling.
- **Goal/areas:** decide and, only if authorized, add disabled-by-default
  Calendar-specific bounded scheduling.
- **Persistence/migration:** additive only if reviewed representation cannot
  safely reuse existing scheduler primitives.
- **API/UI:** explicit enable/pause/history; no credential consent or import.
- **Transactions/concurrency:** unique occurrence, lease/revision fencing,
  `skip`/`run_once`, no replay-all or AgentRun.
- **Security/tests:** duplicate/restart/revocation/scope-race and zero request
  while disabled.
- **Rollback/failure:** keep disabled or omit; manual refresh remains.

### 106 - Calendar deterministic security/evaluation gate

- **Dependency:** approved implemented scope through CP105, including explicit
  omission decisions.
- **Goal/areas:** executable G01-G18 manifest, adversarial OAuth/transport/data/
  concurrency corpus and secret scanners.
- **Persistence/migration:** none.
- **API/UI:** tests only; no authority expansion.
- **Transactions/concurrency:** verified-test-database races/faults only.
- **Security/tests:** every threat maps to named zero-skip deterministic tests.
- **Rollback/failure:** unresolved critical threat blocks acceptance.

### 107 - Local V1.5 end-to-end acceptance

- **Dependency:** approved CP106.
- **Goal/areas:** joined authorize/configure/manual refresh/browse/reconcile/
  revoke journey using fake Google services.
- **Persistence/migration:** no new migration intended.
- **API/UI:** accessible recovery and privacy states.
- **Transactions/concurrency:** replay, partial sync, restart, revision and revoke
  drills on the verified test database.
- **Security/tests:** zero real credential/network/write, excluded-field leak,
  Agent access, import side effect, or cross-scope leak; Full verification.
- **Rollback/failure:** disable Calendar and preserve V1.4 recovery boundary.

### 108 - Local V1.5 release hardening

- **Dependency:** approved CP107.
- **Goal/areas:** stable docs, consent/revoke/recovery guidance, inventories,
  compatibility, dependency/privacy audit and release evidence only.
- **Persistence/migration:** verify sole approved head; no new migration.
- **API/UI:** no feature change.
- **Transactions/concurrency:** backup/restart/revocation drill without
  destructive development-database work.
- **Security/tests:** G01-G18, clean install, secret scan, export exclusion,
  Full verification and fake-provider E2E.
- **Rollback/failure:** documentation revert; `v1.4.0` remains recovery release.

## Official provider references used by CP98

- Google, *OAuth 2.0 for iOS & Desktop Apps* (installed apps, PKCE, system
  browser, redirect and token exchange):
  <https://developers.google.com/identity/protocols/oauth2/native-app>
- Google, *Choose Google Calendar API scopes* (least-privilege Calendar scopes):
  <https://developers.google.com/workspace/calendar/api/auth>
- Google, *OpenID Connect* and its API reference (ID-token validation, `sub`,
  issuer, audience, nonce and JWK metadata):
  <https://developers.google.com/identity/openid-connect/openid-connect> and
  <https://developers.google.com/identity/openid-connect/reference>
- Google, *Events: list* (GET inventory, fields, paging, sync tokens and event
  behavior): <https://developers.google.com/calendar/api/v3/reference/events/list>
- Google, *Synchronize resources efficiently* (full/incremental sync and invalid
  token behavior): <https://developers.google.com/workspace/calendar/api/guides/sync>
