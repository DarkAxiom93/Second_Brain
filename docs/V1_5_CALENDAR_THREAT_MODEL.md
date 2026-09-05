# Local V1.5 Google Calendar threat model

Status: **CP99-CP105 are approved and complete after human review. Checkpoint
105 is a documentation-only manual-refresh decision.
CP106 has not started.**

This register extends rather than replaces the Agent, Automation, and V1.4
connector threat models. Calendar content, Google/OAuth responses, browser
navigation, wall clock, network outcomes, event identities, pagination and sync
tokens are untrusted. The trusted boundary is the local operator, closed
application policy, OS per-user credential store, validated PostgreSQL state,
and deterministic code-owned projections. Passing this plan authorizes no
implementation.

## Security invariants

- Only one explicitly authorized account and exact immutable calendar allowlist
  may be read, through the fixed GET-only Calendar inventory.
- OAuth requests contain exactly `openid` and
  `https://www.googleapis.com/auth/calendar.events.readonly`; `openid` is used
  only to validate the ID-token `sub`, and no email/profile/userinfo authority
  or data is accepted.
- Secrets never enter PostgreSQL, exports, browser storage, observability,
  errors, reports, prompts, or fixtures.
- The stored event projection excludes attendees, organizer, description,
  location, conference links, attachments, reminders, extended properties, and
  private content.
- Calendar content is quarantined untrusted data and unavailable to Agents and
  Automations; it creates no import, Memory, proposal, Approval, or write.
- Project and unassigned scopes are exact. Null never means unrestricted.
- Partial, failed, ambiguous, or mismatched sync never infers deletion.
- Only a closed-version, internally complete observation manifest can make a
  succeeded/complete run reconciliation evidence. Historical unversioned runs
  and zero observation rows without a manifest infer nothing.
- No database transaction or lock spans OAuth, credential-store, network,
  browser, backoff, or provider latency.

## G01-G18 register

The future named gate is Checkpoint 106. Each row defines its prevention,
fail-closed response, and minimum deterministic gate.

| ID / threat | Prevention and fail-closed behavior | CP106 deterministic gate |
|---|---|---|
| G01 OAuth/token leakage | PKCE/state/nonce, ephemeral loopback callback, memory-only access and ID tokens, OS-store refresh envelope, structural redaction and prohibited raw token/identity fields. Parse only required ID-token claims and discard all others. Any unsafe serialization aborts; suspected leakage disables the account and requires replacement. | Synthetic access/refresh/ID-token, raw-`sub`, code/state/verifier and unexpected-claim canaries across callback URL/history, credential metadata, DB, logs, API/UI, DOM/storage, errors, diagnostics, notifications, exports, backups, prompts, reports and crash serialization; zero occurrence. |
| G02 Excessive OAuth scope | Request and fingerprint exactly the set `{openid, https://www.googleapis.com/auth/calendar.events.readonly}`; `openid` is identity-only. Reject every extra, missing or changed grant and never request `email`, `profile`, userinfo, Calendar metadata/discovery, write, or generic Google scopes. | Fake consent/token responses with missing `openid`, missing Calendar scope, email, profile, write, CalendarList/metadata, Gmail, Drive, userinfo and unknown scopes; assert no credential install or Calendar call. |
| G03 Confused deputy/account substitution | Require a Google ID token and validate trusted issuer, exact client audience, expiration/issued-at, attempt nonce and non-empty bounded `sub`. Derive lowercase SHA-256 over UTF-8 `second-brain:google-account:v1:<sub>` as the sole stable fingerprint; bind it to the credential envelope/account revision/allowlist. Reauthorization must match exactly; no email, userinfo, Calendar metadata or CalendarList fallback. | Valid and wrong signed-in account, deterministic fingerprint vectors, wrong `sub` reauthorization, swapped/malformed/forged/replayed ID token, issuer/audience/time/nonce failures, stale callback/state, unexpected claims and identity-changing refresh; no replacement/snapshot, prior envelope preserved and account fenced. |
| G04 Calendar-scope substitution | Immutable validated calendar IDs, non-empty maximum-10 allowlist, no discovery, and per-request account/revision binding. | `primary`, crafted IDs, encoding/path traversal, calendar rename/reuse, foreign calendar response, allowlist edit during sync and hostile continuation; no widened request. |
| G05 Cross-Project/unassigned leakage | Exact captured nullable scope, SQL ownership predicates and historical scope preservation; null is unassigned only. Future observation ownership derives scope through the immutable account/configuration revision and exact run, never a caller-substitutable scope. Reconciliation cannot cross calendar, account/configuration revision, or historical scope. | Project A/B/unassigned list/detail/sync/observation/reconciliation, forged IDs/cursors/observation foreign keys, scope edit/delete races and prior-revision history; stale history never crosses a later scope revision. |
| G06 Hostile/prompt-injection event content | Minimized bounded plain-text projection, escaping/control filtering, external/untrusted labels, and no Agent/Tool access. Reject malformed/oversized content or render inert. | HTML/Markdown/script, bidi/control, encoded instructions, tool/secret requests and Unicode corpus; zero execution, link, prompt, Agent or protected-domain delta. |
| G07 Attendee/privacy leakage | Do not request/store/hash/display attendees, organizer, guests, description, location, links, attachments, reminders or extended properties; private/special events use fixed labels. | Canary in every excluded field and raw payload/exception; scan DB, hashes, APIs, UI, logs, exports and reports for zero occurrence. |
| G08 Malicious links/conference URLs | URL-bearing fields are excluded; UI creates no provider-content hyperlink and transport never follows event links/attachments. | `javascript:`, `data:`, userinfo, redirect, encoded host, meeting and attachment URL corpus; zero navigation/request/rendered anchor. |
| G09 Recurring-event identity ambiguity | Occurrence key is immutable calendar + provider event/series + canonical original start; current times are mutable. The request filters to the five approved event types. Unknown type/time/identity and unexpected cancelled/incomplete occurrences fail the page/run without tombstone fabrication. Every accepted identity in an observation-aware page must atomically gain one exact run observation even when its content revision is reused. | Equal replay without duplicate content revision but with exact new observation, expanded series, moved occurrence, modified exception, duplicate run-occurrence rejection, duplicate original start, all-day recurrence, DST fold/gap, identity collision, `fromGmail`/unknown exclusion and minimal cancelled exceptions. |
| G10 Deletion/reconciliation mistakes | CP102 fixes `showDeleted=false`, intentionally ingests no tombstone and never produces `cancelled`/`deleted` revisions. CP103 must not copy provider fields into a fabricated stale revision. It derives effective application-owned `current`/`stale` only from the latest applicable positive or negative evidence: positive eligible observation is current; omission by a later closed-version, internally complete, exact-lineage run is stale only when the prior projection satisfies the exact reviewed coverage predicate; later positive evidence restores current. Partial, failed, incomplete, unversioned, non-covering, or mismatched runs infer nothing. | Exact query asserts `showDeleted=false`; first-seen tombstones create no revision; complete/versioned/manifest-valid versus partial/unversioned matrices; timed and all-day boundary tests; moved-outside-window ambiguity; resurrection and idempotency; zero fabricated stale revision and zero absence-derived `cancelled`/`deleted`. |
| G11 Pagination/time-window amplification | Every refresh is an independent full sync with fixed calendar/window/page/item/byte/request/deadline limits, `singleEvents=true`, `showDeleted=false`, and only the five repeated approved `eventTypes`. `nextPageToken` is bounded, loop-detected, tied only in memory to the exact current request, and discarded at termination. `syncToken` is never requested and `nextSyncToken` is never collected or persisted. Future observation-aware page commits atomically persist every accepted occurrence observation; terminal eligibility requires the exact distinct observation count to equal accepted-item accounting, including an explicit versioned zero-item manifest. | Exact query inventory, endless/cyclic/branching/oversized page tokens, huge pages/events, fixed boundaries, shifting pages, cross-page duplicate identity, count/manifest mismatch and zero-item manifest assertions; scan for zero tombstone/sync-token/provider content in observation state. |
| G12 Rate-limit/retry abuse | GET-only closed transient classes, at most two retries, capped backoff/Retry-After within run deadline, no busy polling or account switch. | 429/5xx/timeouts before/after response, malformed/extreme Retry-After, retry exhaustion, concurrent accounts and clock jumps. |
| G13 Credential revocation/replacement races | Serialize/fence CP99 envelope rotation and the exact current account revision; install/reauthorize only after complete two-scope and ID-token identity validation. CP102 persists no credential generation because no continuation survives a refresh, but rechecks current eligibility before page writes and terminal success. Observation insertion and manifest eligibility use that same exact account/configuration/calendar fence; drift cannot produce eligible evidence. Revoke blocks before requests and deletes the exact envelope. | Revoke vs refresh/request/page observation/terminal manifest, two refreshes, token rotation, concurrent reauthorization with different `sub`, failed replacement preserving the prior envelope, missing/locked store, disabled/revoked/configuration drift and stale worker result; no mismatched eligible evidence. |
| G14 Scheduler duplicate/restart/fencing | CP105 intentionally omits Calendar scheduling from Local V1.5. CP102 explicit manual refresh is the sole trigger. There is no Calendar schedule persistence/API/UI, background/API-startup work, connector- or Automation-table reuse, scheduler-triggered `AgentRun`, or new credential authority. The V1.4 connector scheduler remains unchanged. Any future Calendar schedule is beyond V1.5 and requires a separate reviewed Calendar-owned capability. | Assert schedule model/route/UI/runner/startup-hook absence; connector and Automation scheduler inventories unchanged; zero Calendar request without explicit CP102 refresh; zero `AgentRun`, import, or protected-domain delta. |
| G15 Import replay/revision drift | CP104 intentionally omits Calendar import from Local V1.5. There is no endpoint, UI action, Calendar-to-Source/SourceDocument/chunk or Memory/proposal/Approval path, automatic import, or Agent/Automation import authority. This avoids freezing a mutable current/stale or moved recurring occurrence—and privacy-minimized fixed labels—as a durable searchable document. Any future import is beyond V1.5 and requires a separate architecture review; no speculative provenance schema is authorized. | Assert route/UI absence, zero Calendar provenance/import rows or Calendar-derived Source/SourceDocument/chunk rows, unchanged protected tables, no Calendar data in Source/Memory search or Agent evidence, and no provider request during browsing. |
| G16 Export/backup leakage | Export v1 excludes all Calendar/OAuth tables and references; credentials, ID tokens, raw `sub`, raw identity payloads and unapproved claims never enter PostgreSQL; docs classify database/machine backup as sensitive. Export fails on inventory drift. | Exact archive inventory and access/refresh/ID-token/raw-identity/unexpected-claim canary scans, format/version compatibility, schema field inventory and OS-store exclusion documentation. |
| G17 Configuration authority injection | Closed typed catalog has no URL/method/query/header/scope/tool/agent/import/write/executable fields; unknown fields/types reject the whole revision. | Adversarial nested JSON, confusables, arbitrary hosts/methods/scopes/fields, GraphQL, Tool/Agent/Automation/import authority and catalog downgrade/drift. |
| G18 Unexpected provider/network/fault behavior | TLS fixed hosts, redirects off, strict schemas/content types/encodings, whole-page validation and safe error taxonomy. Unexpected provider 4xx, `status=cancelled`, deletion/minimal shapes, or missing normalization fields fail closed with no raw body, fabricated values, tombstone, or retry. Observation-aware page persistence is atomic; any revision/observation/ownership failure leaves the run ineligible. Reconciliation is local PostgreSQL-only and introduces no Google request or Calendar write. OpenID key retrieval remains fixed and bounded; arbitrary discovery, userinfo, sync-token reset, and 410 recovery are absent. | Existing network/provider fault corpus plus disconnect at every revision/observation/manifest boundary, cross-owner substitution, aggregate/observation mismatch, unversioned historical and zero-item runs; zero provider content in observations, zero CP102/103 `cancelled`/`deleted` revision, zero reconciliation Google request, Calendar write, or generic-provider authority. |

## Detection, response, and residual risk

Detection records only safe local IDs, provider code, account revision, state,
bounded counts/duration, and code-owned error identifiers. It excludes content,
calendar names/IDs where unnecessary, people, URLs, OAuth fields, tokens,
headers, payloads, paths, environment values, SQL and exceptions.

On credential, scope, identity, privacy, cross-Project, external-write, or audit
failure, disable the affected account, revoke/replace authorization when needed,
preserve safe evidence, and use reviewed forward repair. Never broaden scope,
silently substitute identity, delete history, retry ambiguous mutation, or turn
Calendar content into instruction.

The OS credential store cannot protect an authorized token from a compromised
operator session or process. Read-only Calendar access can still expose highly
sensitive facts. Google may change APIs, quotas, OAuth behavior, recurrence,
retention, and identity semantics. Local database and machine backups may contain
minimized Calendar snapshots. These residual risks are acceptable only within
the existing trusted single-maintainer loopback boundary, least privilege,
minimization, explicit revocation, bounded reads, and the CP106/107 gates.
