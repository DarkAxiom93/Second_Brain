# Local V1.4 read-only connector threat model

Status: **Approved by human review; Checkpoint 87 complete.**

This model extends, and does not replace, `AGENT_THREAT_MODEL.md` and
`V1_3_AUTOMATION_THREAT_MODEL.md`. Protected assets include reviewed knowledge,
exact nullable Project scope, credentials, external account/resource identity,
snapshot provenance, database/audit integrity, local-machine safety, privacy,
availability, human intent, and the guarantees of no external writes and no
authority expansion through connector configuration.

The trusted boundary contains the local operator, application-owned closed
connector catalog/policy, OS per-user credential store, and validated committed
PostgreSQL state. External APIs, external content, provider metadata, pagination
links/tokens, rate-limit responses, wall clock, network outcomes, model output,
and future connector content are untrusted. GitHub is the only proposed V1.4
provider. Tests use fake transports and fake credentials; no release test needs
a real secret or external call.

## Security invariants

- Credentials are never plaintext in PostgreSQL, files, browser storage, logs,
  exports, reports, notifications, exceptions, prompts, or test artifacts.
- Connector permissions, hosts, resource types, repositories, page/history
  limits, retries, and methods are closed and application-owned.
- Only safe idempotent external reads exist. No connector code path can issue an
  external mutation.
- Configuration and schedules grant no Tool, Agent, Automation, import, proposal,
  Approval, promotion, or mutation authority.
- External snapshots are quarantined untrusted input with exact scope, identity,
  version, hash, and sync provenance.
- External content never silently becomes Memory. One explicit operator import
  enters the existing audited ingestion pipeline; review and promotion remain
  separate.
- No lock or database transaction spans OS credential-store or network latency.
- Scope, identity, credential, schema, provenance, or outcome ambiguity fails
  closed without widening, guessing, retrying writes, or deleting local facts.

## Threat register

Every row requires deterministic prevention, fail-closed behavior, and named
tests in Checkpoint 95.

| ID / threat | Impact | Prevention | Fail-closed behavior | Required deterministic tests |
|---|---|---|---|---|
| C01 Credential/token leakage | External account compromise and private-data exposure | OS per-user protected store; opaque references only; authorization header created at final transport boundary; structural redaction everywhere; secret fields prohibited by schema | Abort install/lookup/sync; persist only safe code; disable account on suspected exposure and require explicit replacement | Canary token through config, DB, logs, exception, HTTP errors, UI/DOM, notifications, exports/backups, test reports, crash serialization, and prompt inputs; assert zero occurrence |
| C02 Excessive API scopes | Reads data beyond operator intent | Fine-grained expiring token selected by the operator; exact application-owned read-policy fingerprint; fixed GET-only endpoints and selected repositories revalidated before every sync. GitHub does not expose a complete fine-grained-PAT grant inventory through this bounded surface; `X-Accepted-GitHub-Permissions` is endpoint-required metadata, not token-grant proof | Reject/fence any application policy, account, repository, or configuration drift the application can verify; never derive authority from provider headers. Additional PAT repository/permission grants remain residual operator-managed risk and are not represented as verified | Closed policy rejects write/admin/org/user/email names; hostile permission headers cannot alter the fingerprint; configured-repository drift is fenced; document that provider-side grant expansion may be undetectable without forbidden discovery |
| C03 Confused deputy | External content/config causes broader reads or local actions | Code-owned provider/resource catalog; immutable external IDs; exact account/repository/Project binding; no generic request/tool/import field | Stop sync/import on identity or revision mismatch; no fallback account/repository/scope | Cross-account token, transferred/renamed repository, foreign item ID, stale UI request, crafted nested authority/import fields |
| C04 Prompt injection from external content | Model follows malicious instructions or leaks data | No V1.4 Agent access; label as untrusted; delimiter/escaping rules retained for later explicit import/proposal stages | Render inert text; reject unsafe structure; imported content receives no extra authority | Injection corpus in titles/bodies/comments/URLs including tool requests, secret requests, encoded instructions, HTML/Markdown and Unicode controls; prove zero Agent/Tool calls |
| C05 Cross-Project leakage | External content appears in the wrong Project or unassigned/all scope | Exact nullable scope captured with account and item revision; SQL ownership predicates; scope edits require disabled revision and never remap history | Return not found/scope conflict; never widen null to all or substitute another Project | Project A/B/unassigned list/detail/import, concurrent scope edit and sync, deleted Project, forged IDs and pagination cursors |
| C06 Stale/revoked/expired credential | Unauthorized attempts, confusing stale data, repeated failures | Validate exact reference, credential usability, authenticated account identity, closed application policy, and configured repository access/identity; explicit replacement/revocation; no automatic refresh. Complete provider-side PAT grants are not observable through the approved surface | Disable/pause reads on identity/access failures, preserve prior snapshots, and require operator action; transient store/provider failure does not fabricate a token-grant state | Missing/locked store, server revocation, local delete failure, replacement race, identity-changing token, and replacement with undetectably broader provider grants documented as residual risk |
| C07 Duplicate ingestion/import | Storage amplification or duplicate local Sources/Documents | Unique external identity/version/content hash; one active sync per account; deterministic import idempotency key and target revision CAS | Resolve exact replay write-free; conflict on different request fingerprint; never create replacement local record | Sequential/concurrent refresh/import, retry after commit disconnect, duplicate pages/items, changed content with same/different version, idempotency collision |
| C08 Pagination/retry amplification | Unbounded calls, memory/storage use, cost, denial of service | Fixed pages/items/bytes/deadline/rate ceilings; validated same-host continuation; loop detection; closed read-only retry classes and capped backoff | Stop at first violated ceiling/token/identity; mark run incomplete, so absence cannot imply deletion | Cyclic/branching pagination, huge token, hostile Link URL, endless pages, duplicate pages, timeout, 429/Retry-After extremes, retry budget and restart |
| C09 Rate-limit exhaustion | Connector or account unavailable; unrelated work starved | Per-account/global rate and concurrency caps; honor bounded provider reset/retry; manual-first refresh; no busy polling | Persist safe rate-limited state and next eligible instant; no immediate automatic retry or account switching | Primary/secondary limit responses, malformed reset, fleet cap, concurrent accounts, clock jumps, operator retry before eligibility |
| C10 Malicious external content | XSS, unsafe links, oversized payload, parser/resource attack | Byte/field/count limits before persistence; strict JSON schema; escape text; approved HTTPS GitHub links from canonical identities only; no raw HTML/attachments | Reject offending item/page or whole run according to atomic page policy; retain prior safe snapshot | Script/HTML/Markdown, dangerous/encoded schemes, redirects, userinfo, bidi/control chars, decompression/JSON depth, oversized UTF-8, invalid encoding |
| C11 Connector identity spoofing | Data attributed to the wrong provider/account/repository/item | TLS through maintained client; fixed `api.github.com` host; no redirects to other hosts; capture authenticated account and immutable repository/item node IDs; validate every page | Reject response and disable/revalidate account on identity drift; never trust display names alone | DNS/host/redirect attempts in fake transport, renamed/transferred/recreated repo, mismatched node/database IDs, wrong authenticated user, forged API URLs |
| C12 Deletion/update reconciliation | Data loss, stale truth presented as current, provenance break | Version/hash history; last-seen and complete-run markers; only explicit tombstone or complete bounded reconciliation marks stale/deleted; derived local facts immutable | Partial/failed run makes no deletion inference; ambiguous version remains prior plus safe stale status | Update ordering, clock skew, same timestamp changed hash, tombstone, 404 authorization ambiguity, partial page, repository removal, resurrection/recreation |
| C13 Scheduler-triggered external access | Unexpected network/credential use or replay flood | Scheduling is late, optional, disabled by default, separate from Agent Runs; exact account revision/credential/scope revalidation; `skip`/`run_once`, no replay-all | Revocation/pause/revision drift prevents request; failed occurrence awaits explicit action | Enable confirmation, pause/revoke race, restart/duplicate occurrence/lease, long downtime, capacity full; prove zero request when disabled and zero Agent Run |
| C14 External outage or ambiguous response | Duplicate work, corrupted snapshots, misleading completeness | Classify DNS/connect/timeout/status/schema outcomes; validate whole page before short commit; sync completeness explicit; reads only | Preserve prior snapshots, mark run incomplete/failed, never infer deletion or automatically import | Failure before/after request/page validation/page commit/finalization, disconnect, 5xx, malformed success, truncated JSON, unknown status, retry boundaries |
| C15 Logging/notification leakage | Secrets or private content escapes quarantine | Allowlisted safe fields/codes/counts only; no request/response bodies, headers, query strings, titles, repository names where not necessary, or exception text | Drop unsafe diagnostic field/event; fail the affected operation if safe reporting cannot be guaranteed | Secret/private canaries across each logger/event/notification/API error/telemetry path, hostile exception strings, structured-log serialization |
| C16 Export/backup secret leakage | Portable compromise or unexpected sensitive archive | Export v1 excludes all connector tables/references; credentials never enter PostgreSQL; documented OS-backup caveat; connector snapshot backup classified sensitive | Export fails if connector entries appear in manifest/archive; no fallback serialization | Exact archive inventory, string/canary scan, DB dump field inventory, restore compatibility, OS credential-store exclusion documentation check |
| C17 Privilege expansion through configuration | Read connector becomes generic network/execution/write capability | Closed schemas/catalog; reject unknown fields; fixed provider host/methods/resources; no URL/query/tool/agent/schedule-import/authority field | Reject whole configuration and leave prior revision unchanged; unknown catalog version disables sync | Adversarial JSON/nesting/confusables, arbitrary URL/header/method/GraphQL, write resource, Tool/Agent/Automation/import fields, catalog drift and downgrade |
| C18 Accidental external or reviewed-local mutation | External system or trusted Memory changes without exact human workflow | Transport request inventory permits GET only (and narrowly justified HEAD if approved); no mutation SDK methods; DB protected-domain snapshots; explicit import creates only Source/Document, then existing proposal/review/promotion | Any non-read request construction or protected-table delta stops release/operation; rollback local transaction | Fake server records every method/path/body; malicious response/model/config; direct service bypass; full protected-table before/after snapshots for sync/browse/import/schedule; prove no Memory/Proposal/Approval mutation from sync |

## Detection and operator response

Detection is content-minimized: correlation ID, public local account/sync ID,
provider code, captured revision, safe state/error code, bounded counts/durations,
and credential/scope validity booleans. It excludes credentials/references,
authorization/query data, repository or item content, provider payloads,
prompts, URLs with parameters, paths, environment values, SQL, and exceptions.

On suspected credential, scope, identity, cross-Project, external-write, silent-
trust, or audit failure, stop and disable the affected connector, revoke the
credential outside the application when necessary, preserve database/log
evidence without copying secrets, and use a separately reviewed forward repair.
Never broaden scope, replace an identity silently, delete reviewed knowledge,
rewrite provenance, retry an ambiguous mutation, or auto-refresh a credential.

## Residual risk and release gate

The OS credential store protects data at rest but cannot protect a token from a
compromised operator session or process. A read-only token can still expose
sensitive repository content within its approved scope. External providers can
change APIs, rate limits, identities, and retention semantics. Quarantined
snapshots and machine backups remain sensitive. These risks are accepted only
inside the existing trusted local-machine boundary with least privilege,
expiry, explicit revocation, and bounded reads.

GitHub's approved bounded endpoints do not provide a complete inventory of a
fine-grained PAT's repository grants and permissions. Successful access proves
only usability for the exact configured repositories; it cannot prove absence
of additional grants. `X-Accepted-GitHub-Permissions` states what an endpoint
accepts and is never treated as token-grant metadata. Residual provider-token
least privilege therefore depends on operator creation, expiry, review, and
revocation, while application authority remains independently constrained to
the fixed GET-only allowlisted surface.

Checkpoint 95 must map C01-C18 to named deterministic tests. Checkpoint 96 must
prove the complete loopback flow with fake credential and GitHub services and
zero skips. Any unresolved critical threat blocks Checkpoint 97 and publication.
Passing these gates does not authorize Gmail, Calendar, direct Agent connector
Tools, external writes, automatic import, multi-user operation, or export v2.

Implementation status: Checkpoints 95 and 96 are approved and complete. The
Checkpoint 97 release audit reconfirmed the complete C01-C18 manifest, fixed
GET-only inventory, export exclusion, credential cleanup, and the provider-side
PAT over-grant observability residual risk. Passing release hardening does not
expand connector authority.
