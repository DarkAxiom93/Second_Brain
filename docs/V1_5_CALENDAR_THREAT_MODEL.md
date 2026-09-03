# Local V1.5 Google Calendar threat model

Status: **Checkpoint 98 and both CP102 architecture remediations are approved
and complete after human review. CP102 production implementation has not
started.**

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
| G05 Cross-Project/unassigned leakage | Exact captured nullable scope, SQL ownership predicates and historical scope preservation; null is unassigned only. | Project A/B/unassigned list/detail/sync, forged IDs/cursors, scope edit/delete races and prior-revision history. |
| G06 Hostile/prompt-injection event content | Minimized bounded plain-text projection, escaping/control filtering, external/untrusted labels, and no Agent/Tool access. Reject malformed/oversized content or render inert. | HTML/Markdown/script, bidi/control, encoded instructions, tool/secret requests and Unicode corpus; zero execution, link, prompt, Agent or protected-domain delta. |
| G07 Attendee/privacy leakage | Do not request/store/hash/display attendees, organizer, guests, description, location, links, attachments, reminders or extended properties; private/special events use fixed labels. | Canary in every excluded field and raw payload/exception; scan DB, hashes, APIs, UI, logs, exports and reports for zero occurrence. |
| G08 Malicious links/conference URLs | URL-bearing fields are excluded; UI creates no provider-content hyperlink and transport never follows event links/attachments. | `javascript:`, `data:`, userinfo, redirect, encoded host, meeting and attachment URL corpus; zero navigation/request/rendered anchor. |
| G09 Recurring-event identity ambiguity | Occurrence key is immutable calendar + provider event/series + canonical original start; current times are mutable. The request filters to the five approved event types. Unknown type/time/identity and unexpected cancelled/incomplete occurrences fail the page/run without tombstone fabrication. | Equal replay, expanded series, moved occurrence, modified exception, duplicate original start, all-day recurrence, DST fold/gap, identity collision, `fromGmail`/unknown exclusion and minimal cancelled exceptions. |
| G10 Deletion/reconciliation mistakes | CP102 fixes `showDeleted=false`, intentionally ingests no tombstone and never produces `cancelled`/`deleted` revisions. Unexpected cancelled or incomplete items fail the page/run closed and preserve history. CP103 may derive only application-owned `stale` when an expected in-window projection is absent from a fully complete exact-calendar/configuration/window run; stale is uncertainty, preserves provider provenance, and is never proof of provider cancellation/deletion. Partial runs infer nothing and outside-window events remain unchanged. | Exact query asserts `showDeleted=false`; first-seen ID-only and recurring minimal tombstones create no revision; complete versus partial evidence, rolling-window and moved-outside-window ambiguity; assert no absence-derived `cancelled`/`deleted`. |
| G11 Pagination/time-window amplification | Every refresh is an independent full sync with fixed calendar/window/page/item/byte/request/deadline limits, `singleEvents=true`, `showDeleted=false`, and only the five repeated approved `eventTypes`. `nextPageToken` is bounded, loop-detected, tied only in memory to the exact current request, and discarded at termination. `syncToken` is never requested and `nextSyncToken` is never collected or persisted. | Exact query inventory, endless/cyclic/branching/oversized page tokens, huge pages/events, fixed 30-day-past/60-day-future boundaries, shifting pages, duplicate tokens and ceiling assertions; scan request/schema/storage surfaces for zero tombstone and sync-token state. |
| G12 Rate-limit/retry abuse | GET-only closed transient classes, at most two retries, capped backoff/Retry-After within run deadline, no busy polling or account switch. | 429/5xx/timeouts before/after response, malformed/extreme Retry-After, retry exhaustion, concurrent accounts and clock jumps. |
| G13 Credential revocation/replacement races | Serialize/fence CP99 envelope rotation and the exact current account revision; install/reauthorize only after complete two-scope and ID-token identity validation. CP102 persists no credential generation because no continuation survives a refresh, but rechecks current eligibility before page writes and terminal success. Revoke blocks before requests and deletes the exact envelope. | Revoke vs refresh/request, two refreshes, token rotation, concurrent reauthorization with different `sub`, failed replacement preserving the prior envelope, missing/locked store, disabled/revoked/configuration drift and stale worker result. |
| G14 Scheduler duplicate/restart/fencing | Scheduling absent by default; if approved, unique occurrence, lease/revision fencing, `skip`/`run_once`, no replay-all/AgentRun/import. | Omission assertion or enable confirmation, duplicate/restart/lease loss, long downtime, revoke/scope race and zero request while disabled. |
| G15 Import replay/revision drift | V1.5 baseline omits import. If CP104 approves it, exact preview/revision/hash, network-free confirm and unique provenance are mandatory; never Memory/proposal/Agent. | Baseline route/UI absence and zero import rows; if approved, sequential/concurrent replay, changed revision, disconnect-after-commit and protected-table snapshots. |
| G16 Export/backup leakage | Export v1 excludes all Calendar/OAuth tables and references; credentials, ID tokens, raw `sub`, raw identity payloads and unapproved claims never enter PostgreSQL; docs classify database/machine backup as sensitive. Export fails on inventory drift. | Exact archive inventory and access/refresh/ID-token/raw-identity/unexpected-claim canary scans, format/version compatibility, schema field inventory and OS-store exclusion documentation. |
| G17 Configuration authority injection | Closed typed catalog has no URL/method/query/header/scope/tool/agent/import/write/executable fields; unknown fields/types reject the whole revision. | Adversarial nested JSON, confusables, arbitrary hosts/methods/scopes/fields, GraphQL, Tool/Agent/Automation/import authority and catalog downgrade/drift. |
| G18 Unexpected provider/network/fault behavior | TLS fixed hosts, redirects off, strict schemas/content types/encodings, whole-page validation and safe error taxonomy. Unexpected provider 4xx, `status=cancelled`, deletion/minimal shapes, or missing normalization fields fail closed with no raw body, fabricated values, tombstone, or retry; there is no sync-token reset/410 workflow. OpenID key retrieval is fixed GET-only Google JWK access with bounded cache/size/time outside transactions; arbitrary discovery, issuer/JWK configuration and userinfo are absent. Ambiguity preserves prior state. | DNS/connect/TLS/redirect, forged/unknown-key/signature/algorithm ID tokens, malformed JWK/cache rotation, arbitrary discovery/userinfo absence, malformed/truncated/deep JSON, compression/byte bombs, unexpected 4xx/status/type/cancelled/minimal item, disconnect at every transaction boundary and provider clock/version anomalies; zero CP102 `cancelled`/`deleted` revision, Calendar write or generic-provider authority. |

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
