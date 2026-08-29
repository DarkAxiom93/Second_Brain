# Local V1.4 read-only connectors roadmap

Status: **Approved by human review; Checkpoint 87 complete.**

This document plans Local V1.4 only. It authorizes no implementation. Local
V1.3 is the current published release as `v1.3.0` from
`f79d556cb8d99961aa081464ef151ef1037fe87a`. The current stable identities are
Alembic `0012_connector_persistence`, Tool Registry `agent-tools-v1`, and
Project export `second-brain-project-export` version `1`.

## Decision

Local V1.4 should deliver
**Local V1.4 — Read-only Connectors & External Context** inside the
existing trusted, single-maintainer, loopback-only boundary. The first release
should establish one narrow connector contract and ship one independently
reviewed GitHub implementation. Connector reads create quarantined, versioned
external snapshots with provenance. They do not create or update reviewed
Memory, grant Agent authority, or mutate an external system.

GitHub is the recommended first connector because a fine-grained personal
access token can be limited to selected repositories, read-only permissions,
and an operator-chosen expiry without introducing OAuth client-secret or token-
refresh machinery. Initial scope is repository metadata plus issues and pull
requests (including bounded comments only if separately approved in the GitHub
checkpoint). Source code, commit diffs, Actions logs/artifacts, organizations,
members, email addresses, secrets, packages, administration, webhooks, writes,
and repository discovery outside the explicit allowlist are excluded.

Google Calendar is the next candidate after the foundation because bounded
event context has strong daily value, but its OAuth client configuration,
refresh-token lifecycle, attendee privacy, recurring-event identity, and
deletion reconciliation require a separate connector review. Gmail is deferred
further: message bodies, attachments, broad mailbox search, sensitive metadata,
and phishing/prompt-injection density make its initial security and privacy
cost materially higher.

## Candidate comparison

| Candidate | User value | Dependency and migration impact | Security/credential risk | Testability and recovery | Local-boundary fit | Decision |
|---|---|---|---|---|---|---|
| Read-only connectors/context | High: brings current external work into the local review flow | OS credential-store prerequisite; additive connector metadata/snapshot persistence | High but containable with one provider, least privilege, quarantine, and no writes | Deterministic fake transport plus replay fixtures; disable/revoke leaves local snapshots explainable | Good when refresh is explicit and scope is allowlisted | **Select** |
| Safer proposal/write workflows | Medium-high, but turns reviewed intent into mutation | Requires execution state machine, target locking, compensation, and new authority | Very high confused-deputy and irreversible-write risk | External and local write ambiguity makes rollback difficult | Poorer until read-only external trust is understood | Defer |
| Multi-user/authentication | Valuable only if deployment ceases to be single-maintainer | Redesigns identity, authorization, ownership, sessions, audit, and likely every query | Critical boundary expansion and credential burden | Large cross-cutting isolation matrix; hard rollback | Conflicts with current local premise | Defer to a separate major boundary |
| Import/export/backup evolution | Moderate resilience value | Export-version, encryption/key management, FK/restore decisions | High key-loss and secret-backup risk | Testable but complex compatibility/recovery matrix | Fits locally, but less immediate product value | Defer as an independent recovery release |
| Agent/Automation UX and observability | Medium incremental value | Mostly additive UI/projections; little migration | Low-medium privacy risk | Strong deterministic testability and easy rollback | Excellent | Retain for focused patches, not the primary release |

Read-only connectors are the best value-to-risk step only under the quarantine,
least-privilege, explicit-refresh, and OS-secret-storage rules below. A generic
integration framework or multiple simultaneous providers would invalidate that
conclusion.

## Release invariants

- Operation remains loopback-only for one trusted local maintainer; there is no
  authentication, remote, cloud, or multi-user boundary.
- Connector definitions and configuration grant no Agent Tool, Agent authority,
  Automation eligibility, local write authority, or external write authority.
- The connector catalog, provider identity, resource types, scopes, limits, and
  schemas are code-owned and closed. There is no arbitrary URL, HTTP request,
  GraphQL, query language, browser action, script, path, SQL, or executable
  configuration.
- Every external API credential is least-privilege, operator-installed,
  revocable, and absent from application persistence and observability.
- External content is untrusted data, never instruction, and never silently
  becomes reviewed Memory.
- No transaction or database lock spans credential-store or network latency.
- Unknown state, scope drift, identity mismatch, ambiguous responses, and
  unclassified errors fail closed without widening reads or guessing writes.

## Credential architecture

Credentials may be stored only in the operating system's per-user credential
store behind a small application-owned interface. On the supported Windows
host this means Windows Credential Manager (or a demonstrably equivalent
DPAPI-backed per-user facility) with a non-secret opaque credential reference.
PostgreSQL may store that reference, provider, account fingerprint, selected
resource allowlist, granted-scope fingerprint, expiry/status, and safe last-
validated timestamp, but never a token, refresh token, client secret,
authorization code, cookie, password, or recoverable derivative.

Checkpoint 88 is a prerequisite and must stop if the chosen OS facility cannot
provide per-user protected storage, exact lookup/delete, non-enumerating
application use, and deterministic fake-store tests. Plaintext files,
environment persistence, frontend/browser storage, database encryption as a
substitute, and home-grown cryptography are forbidden.

The first GitHub connector uses an operator-created fine-grained token with an
expiry; it has no automatic refresh. Missing, expired, revoked, identity-
mismatched, or scope-expanded credentials disable reads and require explicit
replacement and revalidation. Replacement is an explicit local action and does
not change connector configuration or authority. Revocation deletes the exact
OS-store entry where possible, marks the local account disabled/revoked, and
prevents scheduled or manual reads; deletion failure is visible and fail-
closed. Secrets and secret-bearing headers/URLs/bodies are excluded from logs,
events, notifications, database fields, frontend state, exceptions, diagnostics,
traces, crash reports, test snapshots, exports, and application backups.
Automated tests use only fake credential handles and syntactically obvious fake
tokens that transports reject from real network use.

## External-data trust and provenance

### Exact GitHub boundary

The operator configures an explicit non-empty allowlist of canonical
`owner/repository` identities. Validation resolves and captures immutable GitHub
repository/node identities and the authenticated account fingerprint; later
name reuse or transfer cannot silently inherit trust. Permission is read-only
for repository metadata, issues, and pull requests. Initial refresh is manual
only. Scheduled refresh is a separately reviewed late checkpoint and remains
off by default.

Each refresh has fixed ceilings: repository count, resource types, items per
repository, comments per item if enabled, response bytes, pages, history
lookback, total duration, and per-host request rate. Pagination follows only
validated same-provider continuation data and stops at the ceiling. Timeouts are
short and split by connect/read/overall deadline. Retry is limited to a small
closed set of safe idempotent reads, honors bounded `Retry-After`, uses capped
backoff, and never retries ambiguous identity, authentication, authorization,
schema, pagination, or content-limit failures.

### Local records

V1.4 is expected to add three normalized concepts:

- `ConnectorAccount`: provider and immutable external account identity,
  non-secret credential reference, granted-scope fingerprint, explicit resource
  allowlist, lifecycle/revision, and safe validation/refresh summaries.
- `ConnectorSyncRun`: one operator or scheduler occurrence with captured account
  revision, bounds, trigger identity, safe counts/status/error code, and
  timestamps. It contains no credential or raw request/response payload.
- `ExternalItem`: provider/resource/repository identity, immutable provider item
  ID, canonical type, source version (`updated_at` plus provider identity where
  available), bounded untrusted title/body snapshot, content hash, state,
  first/last-seen timestamps, and exact sync provenance.

Uniqueness is provider + external account + immutable resource identity + item
identity. Equal-version/content replay is write-free. A changed item creates or
advances an application revision without destroying prior provenance required
by an already-created local SourceDocument. Items absent from a bounded partial
page are never inferred deleted. Explicit provider deletion/tombstone or a
complete bounded reconciliation marks the item stale/deleted locally; it does
not delete derived local Sources, Documents, Proposals, or Memories.

External items map to exactly one configured Project or explicit unassigned
scope captured by the account revision; null never means all Projects. Scope
cannot be edited during an in-flight sync. Changing scope requires disable,
revision change, and a new sync; existing snapshots retain historical scope and
are never remapped automatically. Every public display labels content as
external and untrusted and exposes safe provider/repository/item identity,
version, last-seen/stale state, and sync provenance.

### Review/import boundary

Connector ingestion is quarantine-only. Existing Research, Memory Curator,
Daily Brief, Project Watch, manual Agents, and all Automations remain unchanged
and cannot query `ExternalItem`. `agent-tools-v1` remains unchanged throughout
V1.4 unless a later roadmap, not this one, explicitly approves a new registry.

An operator may explicitly import one current ExternalItem revision into the
existing audited Source/SourceDocument ingestion boundary. The application
captures provider/item/version/content hash and source URL metadata, displays an
exact preview, and makes replay idempotent. Import creates no Memory: the
existing separate proposal generation, human review, and explicit promotion
rules remain mandatory. Stale/deleted upstream state is shown but never mutates
reviewed local knowledge. Bulk import, automatic import, direct Agent access,
and Automation-triggered import are excluded.

## Refresh, failure isolation, and scheduling

Manual refresh is delivered before scheduling. One sync run is serialized per
ConnectorAccount with revision compare-and-set and a database uniqueness/claim
barrier; different accounts may run concurrently within a small global cap.
The claim commits before credential lookup or network work. Bounded page results
commit in explicit short transactions only after full schema, identity, size,
scope, and provenance validation. A failure never exposes partial results as a
successful complete reconciliation. Existing snapshots remain readable with a
stale/last-success marker.

If a later checkpoint adds refresh scheduling, it reuses the existing explicit
operator-started scheduler only through a distinct closed connector occurrence
type. It does not create an Agent Run and does not grant Automation or Agent
authority. Default is disabled; enablement is explicit and revision-aware.
Credential absence/revocation, scope drift, rate limiting, outage, or ambiguous
response pauses/fails the occurrence without automatic credential prompts,
scope expansion, replay-all, or external writes.

## Export, backup, retention, and deletion

Project export `second-brain-project-export` version `1` remains unchanged and
excludes ConnectorAccount, ConnectorSyncRun, ExternalItem, credential references,
and connector-derived runtime metadata. Imported Source/SourceDocument records
continue to follow the existing version-1 rules only if already supported by
that format; the connector record itself is not exported.

OS credential-store data is outside PostgreSQL and application backup/export.
Documentation must warn that a machine backup may independently include OS
credentials and must use platform protections. Connector snapshots may contain
sensitive external content and therefore require bounded retention and an
explicit account purge action in a dedicated checkpoint. Purge is recoverable
only from an operator backup, verifies exact account ownership, never deletes
derived local knowledge, and is forbidden while sync/import work is active.
Disabling or revoking access preserves audit metadata and snapshots until that
separate explicit purge.

## Implementation sequence after Checkpoint 87

Every checkpoint depends on human approval of its predecessor. Production
database rollback is forward-only unless separately approved; migration
downgrades run only against the verified test database.

### 88 - OS credential-store prerequisite and secret boundary

- **Dependency:** approved Checkpoint 87.
- **Goal:** Prove the Windows per-user secret-store adapter, opaque references,
  exact install/replace/revoke flows, redaction, and fake test store.
- **Production areas:** credential interface/adapter, local operator command,
  configuration validation, safe diagnostics.
- **Persistence/migration:** none; no connector table and no secret in PostgreSQL.
- **API/UI:** no public API or frontend secret entry.
- **Concurrency/transactions:** no database transaction spans OS calls; exact
  replace/delete is serialized per opaque reference.
- **Security acceptance:** plaintext persistence and secret observability tests
  fail closed; unavailable secure storage blocks connector work.
- **Focused tests:** OS adapter contract, fake-store isolation, replacement,
  revocation, missing/locked store, log/error/export redaction.
- **Rollback:** remove adapter/command and delete only explicitly named test
  credentials; no database effect.

### 89 - Inert connector persistence and catalog

- **Dependency:** approved Checkpoint 88.
- **Goal:** Add closed GitHub catalog metadata and inert normalized account,
  sync-run, and external-item persistence without network behavior.
- **Production areas:** models, repositories, internal schemas, catalog.
- **Persistence/migration:** one additive migration after `0011`; export v1
  remains unchanged and excludes every connector table/reference.
- **API/UI:** none.
- **Concurrency/transactions:** caller-owned transactions, account revisions,
  item uniqueness/versioning, one-active-sync constraint.
- **Security acceptance:** catalog cannot express URL, write permission, Tool,
  authority, secret, arbitrary query, or executable configuration.
- **Focused tests:** migration lifecycle, constraints, version replay,
  cross-Project ownership, export exclusion, secret-shaped value rejection.
- **Rollback:** revert inert code; production uses reviewed forward repair.

### 90 - Connector account lifecycle and safe UI

- **Dependency:** approved Checkpoint 89.
- **Goal:** Create/list/read/disable/re-enable/revoke GitHub account metadata and
  explicit repository/scope configuration with safe validation status.
- **Production areas:** service, typed loopback routes, frontend settings flow.
- **Persistence/migration:** none expected.
- **API/UI:** additive metadata-only API/UI; credential installation remains the
  local operator command from Checkpoint 88.
- **Concurrency/transactions:** account row locks and revision compare-and-set;
  lifecycle changes fence sync claims.
- **Security acceptance:** configuration grants no Agent/Automation authority;
  APIs expose no secret/reference internals or arbitrary repositories.
- **Focused tests:** lifecycle matrix, hostile input, scope/resource allowlist,
  conflict refresh, accessibility, no browser storage.
- **Rollback:** remove routes/UI; disabled inert rows remain safe.

### 91 - Bounded GitHub read transport and manual sync

- **Dependency:** approved Checkpoint 90.
- **Goal:** Implement explicit manual read-only refresh for approved repository
  metadata and bounded issues/pull requests.
- **Production areas:** GitHub adapter, sync coordinator, schemas, routes.
- **Persistence/migration:** none expected beyond Checkpoint 89.
- **API/UI:** one explicit refresh action and safe sync status; no generic proxy.
- **Concurrency/transactions:** one active sync per account, global cap, no lock
  across credential/network latency, bounded page commits after validation.
- **Security acceptance:** exact host/account/repository/scope validation, zero
  mutation methods, closed retries/pagination, fail-closed ambiguity.
- **Focused tests:** fake transport, request inventory, timeout/rate-limit,
  pagination loops, oversized/malformed responses, revocation and scope drift.
- **Rollback:** disable connector and remove adapter/routes; snapshots remain
  marked stale and readable.

### 92 - External context browser and reconciliation

- **Dependency:** approved Checkpoint 91.
- **Goal:** Browse/filter versioned untrusted snapshots with provenance and
  reconcile updates/deletions without destructive local effects.
- **Production areas:** query service, typed routes, frontend external-context
  views.
- **Persistence/migration:** indexes only if measured and separately migrated;
  otherwise none.
- **API/UI:** bounded account/Project/type/state filters, detail/version/source
  identity display, explicit refresh; no raw HTML rendering.
- **Concurrency/transactions:** deterministic pagination and equal-version
  idempotency; complete-reconciliation marker required before absence matters.
- **Security acceptance:** cross-Project isolation, injection-safe rendering,
  stale/deleted labeling, safe link policy, no silent trust.
- **Focused tests:** update/delete/rename/transfer, partial pages, spoofed IDs,
  hostile content/links, accessibility and reflow.
- **Rollback:** remove browser/API; snapshots remain quarantined.

### 93 - Explicit single-item import into audited ingestion

- **Dependency:** approved Checkpoint 92.
- **Goal:** Import one exact current ExternalItem revision into the existing
  Source/SourceDocument boundary with preview and provenance.
- **Production areas:** import service, typed action route, UI confirmation.
- **Persistence/migration:** additive provenance link only if existing Source
  metadata cannot represent immutable provider/item/version identity; stop for
  migration review if needed.
- **API/UI:** explicit preview/confirm for one item; no bulk/automatic import.
- **Concurrency/transactions:** item revision lock/CAS, idempotency identity,
  atomic local Source/Document creation; no network call in import transaction.
- **Security acceptance:** import creates no Memory and invokes no provider;
  proposal review/promotion remains separate.
- **Focused tests:** replay, revision drift, stale/deleted item, scope mismatch,
  provenance preservation, protected-Memory snapshots.
- **Rollback:** remove action; already imported audited local records remain.

### 94 - Optional explicit connector refresh scheduling

- **Dependency:** approved Checkpoint 93 and a demonstrated user need.
- **Goal:** Add opt-in bounded GitHub refresh occurrences to the existing
  operator-started scheduler without Agent Runs.
- **Production areas:** closed scheduler catalog/coordinator, occurrence history,
  safe notifications.
- **Persistence/migration:** small additive occurrence ownership only if existing
  Automation tables cannot safely represent a non-Agent trigger; do not overload
  them merely to avoid a migration.
- **API/UI:** explicit disabled-by-default schedule and history controls.
- **Concurrency/transactions:** unique occurrence, revision fencing, bounded
  missed-run `skip`/`run_once`, no replay-all, no lock over network latency.
- **Security acceptance:** schedule grants no credential, scope, Tool, Agent, or
  import authority; revocation stops access.
- **Focused tests:** duplicate/restart/lease, scope drift, outage/rate limit,
  notification redaction, zero Agent Run and protected-domain mutation.
- **Rollback:** disable scheduling; manual refresh remains available.

### 95 - Connector security and evaluation gate

- **Dependency:** approved implemented connector scope through Checkpoint 94 (or
  an explicit decision to omit optional scheduling).
- **Goal:** Make every C01-C18 threat a deterministic release gate.
- **Production areas:** adversarial corpus, transport/request inventory,
  PostgreSQL concurrency/fault harness, secret-leak scanners.
- **Persistence/migration:** none.
- **API/UI:** exercise all exposed connector states; no capability expansion.
- **Concurrency/transactions:** verified-test-database races/faults only.
- **Security acceptance:** zero secrets, writes, scope leaks, silent trust,
  duplicate imports, or Agent/Automation authority expansion.
- **Focused tests:** complete threat manifest plus credential, injection,
  pagination, reconciliation, and protected-domain snapshots.
- **Rollback:** revert harness-only changes or isolated fixes; do not release.

### 96 - Local V1.4 end-to-end acceptance

- **Dependency:** approved Checkpoint 95.
- **Goal:** Prove credential-reference, configure, manual refresh, browse,
  reconcile, and single-item import through real loopback API/UI with fake
  GitHub and credential services.
- **Production areas:** acceptance evidence and blocker fixes only.
- **Persistence/migration:** no new migration intended.
- **API/UI:** joined accessible operator journey and recovery states.
- **Concurrency/transactions:** duplicate refresh/import and restart/failure
  drills on the verified test database.
- **Security acceptance:** no real network/credential, external write, direct
  Memory mutation, cross-Project leak, or secret-bearing artifact.
- **Focused tests:** full joined acceptance and Full zero-skip verification.
- **Rollback:** revert isolated blockers and disable connector.

### 97 - Local V1.4 release hardening

- **Dependency:** approved Checkpoint 96.
- **Goal:** Synchronize stable documentation, inventories, install/revoke/
  recovery guidance, compatibility, and release evidence.
- **Production areas:** release/runbook documentation and inventories only.
- **Persistence/migration:** verify approved sole head; no new migration.
- **API/UI:** no feature changes.
- **Concurrency/transactions:** stopped-service backup/restart/revocation drill;
  no destructive development-database operation.
- **Security acceptance:** dependency, least-privilege, secret-scanner, privacy,
  threat-manifest, and deferred-scope audit.
- **Focused tests:** complete Full verification, clean install/restart, export
  exclusion, exact credential revocation evidence.
- **Rollback:** documentation revert; `v1.3.0` remains recovery release.

Checkpoint 87 starts none of Checkpoints 88-97.

Implementation status: Checkpoint 88 is approved and complete after human
review. Checkpoint 89 is approved and complete after human review and adds only
the inert connector persistence and closed GitHub catalog described above.
Checkpoint 90 is approved and complete after human review. It adds
metadata-only, revision-aware GitHub account lifecycle/configuration APIs and
an accessible Settings flow without credential display, browser persistence,
provider calls, or new authority. Checkpoint 91 is approved and complete after
human review; it adds only the bounded explicit manual GitHub refresh described
above. Checkpoint 92 is approved and complete after human review; it adds only
the bounded external-context browser and complete-run reconciliation described
above. Checkpoints 93-97 have not started.

## Explicitly deferred beyond V1.4

Gmail; Google Calendar until its own OAuth/privacy review; every other connector;
multiple providers in one implementation checkpoint; generic HTTP/GraphQL;
source-code/diff/log/artifact ingestion; attachments; external search outside
explicit repositories; direct Agent access to external items; any Tool Registry
change; connector access for Research, Curator, Daily Brief, or Project Watch;
automatic or bulk import; automatic proposal/review/promotion; local reviewed-
knowledge mutation; external writes; OAuth client-secret/refresh-token support;
webhooks; external notifications; arbitrary shell/Python/SQL/filesystem/browser/
network execution; authentication/multi-user/remote/cloud operation; export v2,
encrypted backup, import merge/remap/overwrite, and automatic snapshot deletion.
