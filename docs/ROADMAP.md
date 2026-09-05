# Roadmap

This is a capability sequence, not a schedule.

## Published releases

Local V1 is published as `v1.0.0` from
`a1bf40c0a27e9ee508e9bf1ab151b4665fbdba32` and remains the pre-V1.1 recovery
point. Local V1.1 is published as `v1.1.0` from exact commit
`88dffa90ff04cde4c57dcacbe2764b8a31b0c9ce`. Checkpoint 60 is complete at that
commit. Local V1.2.1 is the current published V1.2 patch release, tagged
`v1.2.1` from exact commit `04e9db33dc0de7529b1599871c58cace6ed9f9e2`.
Local V1.2.0 remains intact as the preceding release from
`67e790f2f2c34b346773cddba385fa3f2db04a26`. Local V1.4 is the current
published release, tagged `v1.4.0` with title **Second Brain Local V1.4** from
exact commit `c02a8ccb4b0b93a2fb73f23c112344b69eaac39a`. Local V1.3.0 remains
the preceding documented recovery release from
`f79d556cb8d99961aa081464ef151ef1037fe87a`. The sole current Alembic head is
`0016_calendar_event_observations`, Tool Registry remains `agent-tools-v1`, and
Project export remains `second-brain-project-export` version `1`.

V1.1 adds the patched frontend dependency graph, least-privilege
non-authoritative CI, deterministic explained Memory search, its accessible UI,
and integrated acceptance. It preserves legacy search/Answer contracts, stored
data, deployment topology, and export/import format. Local Full verification
remains release-authoritative.

## Local V1.2

Checkpoint 61 completed the [Local V1.2 Agent roadmap](V1_2_AGENT_ROADMAP.md) and
[threat model](AGENT_THREAT_MODEL.md) at
`850cfd0a749b5de072b910203ba9906ab5270b40`. Checkpoint 62 is complete at
`3da0cdd875dc8af7a60fd8af5b6f9878be5a769a`. Checkpoint 63 is complete at
`01832a94ae6f80bdacd0cd9301af3f294302e3e8`. Checkpoint 64 completed the private,
immutable `agent-tools-v1` seven-definition read-only registry and pure policy
resolver at `35950c60fd842a4ad022f130a3074ce8d21d9bbc`. Checkpoint 65 adds bounded
structured planning and is complete at
`1b32d91e62feb10efd5c2f2c241ee43b75b5b5e2`. Checkpoint 66 completed synchronous,
ordered execution through exactly five scoped application reads at
`d4a3533282a8ed616fa0910fcea99b07b0f1b878`. Checkpoint 67 completed one
safe-read retry, deterministic cancellation/deadline reconciliation, and
explicit synchronous operator recovery at
`7b6c6bb8c4c67f9e8a5a34c363331bc94dbb094e`. Checkpoint 68 is complete at
`1bc90b4339bd5466fda10e5d04711e3f025a0e01`. It adds immutable `memory.update` proposals and exact
human approve/reject review without target mutation or execution authority.
Checkpoint 69 completed the accessible manual Agent Runs and exact Approval
review UI at `e6324e52292e108d84666f88aeccf434c92ab39c`. Checkpoint 70 completed one
fixed, cited, read-only Research Agent at
`12a70f5e367db76cb4f0e05fb350acabc0230c3c`. Checkpoint 71 completed one fixed
advisory `memory_curator` version `1` at
`1dd8e83804c724e6790a704faa5ee13aad9dd3fe`. Checkpoint 72 completed the
T01-T24 Agent security/evaluation release gate and the 32-nonterminal-Run
capacity bound at `45e940ec89b6cf3783ab2dc7cdfa837b6cbc3597`; Checkpoint 73 local
acceptance is complete at `26c74cced438fd850907d593db5090719f6e861a`.
Checkpoint 74 release hardening is complete at
`53d78f30c7e9ff4020179c57e286ad24980df6af` after human approval and successful
push CI run `32474664878` with zero artifacts. V1.2.0 remains the preceding
published release. The unnumbered V1.2.1 live-provider and Agent reliability hardening is
published from `04e9db33dc0de7529b1599871c58cace6ed9f9e2` after successful
final pre-release CI run `32559057246`, attempt 1. Checkpoint 76 adds inert V1.3
Automation persistence only. No scheduling, approval execution, connector, or
write Tool exists.

The V1.2 capability is manually initiated, bounded, local Agent Runs
with structured planning, application-owned read-only tools, durable safe state,
cancellation/recovery, immutable proposed actions for exact human review, an
accessible Runs/Approvals UI, a read-only Research Agent, an advisory Memory
Curator Agent, and deterministic security/quality evaluation. An Agent Run is
not an Automation: Automation is a future trigger that creates a Run.

The independently reviewable sequence is:

1. 62 - Agent Runtime persistence foundation.
2. 63 - Agent Run state machine and API.
3. 64 - Tool Registry and policy enforcement.
4. 65 - Structured planning provider.
5. 66 - Bounded read-only executor.
6. 67 - Idempotency, cancellation, recovery, and failure injection.
7. 68 - Approval and proposed-action foundation.
8. 69 - Agent Runs and Approval UI.
9. 70 - Read-only Research Agent.
10. 71 - Advisory Memory Curator Agent.
11. 72 - Agent security and evaluation harness.
12. 73 - Local V1.2 end-to-end acceptance.
13. 74 - Local V1.2 release hardening.

V1.2 excludes scheduled/recurring Automations, background workers, external
connectors or writes, autonomous approval, execute authority in the initial
runtime, arbitrary shell/Python/SQL/filesystem/browser/network access, and
cloud, remote, multi-user, or mobile operation.

## Completed foundation

Completed capabilities include PostgreSQL persistence; normalized sources;
lexical, semantic, hybrid, and explained search; optional embeddings; TXT/PDF
ingestion; AI proposals with human review and explicit promotion; advisory
quality detection; explicit supersession, expiration, and quality refinement;
evidence-backed answers; batch embedding/re-embedding; read-only maintenance
and diagnostics; versioned Project export and controlled import; all eight
top-level local UI routes; non-authoritative CI; and V1/V1.1 acceptance.

## Local V1.3 release candidate

Checkpoint 75 completed the approved documentation-only
[Local Automations & Scheduled Agents](V1_3_AUTOMATION_ROADMAP.md) architecture
and its [V1.3 threat model](V1_3_AUTOMATION_THREAT_MODEL.md). Checkpoints 76 and
77 are approved and complete. Checkpoint 78 implements the explicit trigger-only
scheduler foundation and is approved and complete after human review;
Checkpoint 79 is approved and complete after human review. Checkpoint 80 is
approved and complete after human review; production automatic eligibility
remains empty until the dedicated fixed-Agent checkpoints.

Checkpoint 81 is approved and complete after human review. Its additive safe
history/inbox APIs and explicit-refresh Automations UI do not install either
reserved fixed Agent, enable automatic execution, or begin Checkpoint 82.

Checkpoint 82 implements only the fixed scheduled-only Daily Brief v1 identity
and is approved and complete after human review. Checkpoint 83 implements fixed
scheduled-only Project Watch v1 for one exact non-null Project, with
application-derived successful-occurrence watermarks, bounded versioned
Project/Memory change evidence, cited changes/no-change results, automatic
read-only execution, redacted completion notifications, and UI activation.
Checkpoint 83 is approved and complete after human review. Checkpoint 84's
A01-A18 deterministic security/evaluation harness and Checkpoint 85's joined
V1.3 end-to-end acceptance are approved and complete. Checkpoint 86 performs
documentation-and-evidence-only release hardening; publication remains a
separate approval.

The proposed scope is a local scheduler; typed one-time, daily, and weekly
Automation definitions; explicit enable/pause/cancel lifecycle; durable trigger
occurrences; fenced leases and duplicate prevention; deterministic restart,
retry, and missed-run behavior; bounded history; safe local notifications; and
fixed read-only Daily Brief and Project Watch Agents. An Automation is a durable
trigger that may create one bounded Agent Run per occurrence; it is never the
Run and grants no additional authority.

Automatic planning/execution exists only for explicit opt-in fixed read-only
Daily Brief v1 and Project Watch v1. The default `create_only` mode creates a
Run for explicit human execution. The independently reviewed implementation
sequence is Checkpoints 76-85; Checkpoint 86 changes only release documentation
and evidence.

Connectors, arbitrary/external research or network access, external writes,
proposal execution, automatic Approval, credentials, authentication/multi-user,
remote/cloud/mobile operation, arbitrary execution, import merge/overwrite/
remap, and encrypted export redesign are deferred beyond V1.3 to separate
roadmaps and threat models.

## Approved Local V1.4 direction

Checkpoint 87 is approved and complete after human review. It defines
[Local V1.4 — Read-only Connectors & External Context](V1_4_ROADMAP.md)
and its [threat model](V1_4_THREAT_MODEL.md). The recommended narrow release is
one connector foundation plus an independently reviewed GitHub read-only
implementation using OS-protected credentials, explicit repository allowlists,
bounded refresh, quarantined versioned external snapshots, and explicit single-
item import into the existing audited ingestion/review flow.

The proposal preserves the loopback single-maintainer boundary, keeps all
existing Agents and Automations unchanged, adds no connector Tool to
`agent-tools-v1`, and leaves Project export version 1 unchanged. Checkpoint 89
is approved and complete after human review with inert connector persistence
and the closed GitHub catalog. Checkpoints 90-94 are approved and complete
after human review. Checkpoints 95-96 are approved and complete after human
review. Checkpoint 97 release hardening is approved and complete after human
review. After that approval, Local V1.4 was published as `v1.4.0`, titled
**Second Brain Local V1.4**, from exact release commit
`c02a8ccb4b0b93a2fb73f23c112344b69eaac39a`.
Checkpoint 88 completed the Windows per-user OS credential-store prerequisite
after human review.
Calendar and Gmail, direct Agent
connector access, external writes, automatic import/review/promotion,
authentication/multi-user, generic network execution, and export redesign
remain deferred.

## Planned Local V1.5 direction

Checkpoint 98 is approved and complete after human review. It selects **Local
V1.5 - Read-only Google Calendar Context**. The dedicated
[roadmap](V1_5_CALENDAR_ROADMAP.md) and
[G01-G18 threat model](V1_5_CALENDAR_THREAT_MODEL.md) compare the alternatives
and define a manual-first, one-account, exact-calendar-allowlist release with a
privacy-minimized event projection. Import and scheduling remain separate
decision gates; Agents and Automations remain unable to access Calendar data.

Checkpoint 99 is approved and complete after human review. It implements only
the approved OAuth/credential prerequisite. Its exact two-scope installed-app
PKCE flow, signed ID-token identity gate, versioned OS-store envelope, fenced refresh,
reauthorization and revocation introduce no Calendar data request or schema.
Email/profile, userinfo, broader scopes, Calendar persistence/API/UI/sync/import,
scheduling and Agent/Automation access remain absent. Tool Registry, Project
export and Alembic identities remained unchanged through CP99.
Checkpoint 100 is approved and complete after human review. It implements only
the inert provider-specific Calendar persistence
foundation and closed catalogs at `0015_calendar_persistence`. It adds no
Calendar network request, API/UI, executor, reconciliation, import, scheduling,
or Agent/Automation authority. Checkpoint 101 is approved and complete after
human review. It implements only revision-fenced
Calendar account configuration and lifecycle metadata plus its safe Settings
UI. Calendar data access and Checkpoint 102 remain not started.
The documentation-only CP102 architecture-gate remediation resolves the CP100
schema mismatch by intentionally narrowing V1.5 to independent bounded manual
full syncs. V1.5 has no incremental sync, persisted provider continuation,
`syncToken`, `nextSyncToken`, incremental request fingerprint, or captured
credential generation. Ephemeral `nextPageToken` pagination remains bounded and
loop-detected for one active refresh. This amendment is approved after human
review. A second documentation-only gate records that first-seen Google
cancelled/deleted tombstones may contain only identity fields and cannot be
represented by CP100's complete revision schema without fabrication. The
approved second remediation further narrows CP102 to `singleEvents=true`,
`showDeleted=false`, and repeated filters for the five CP100-approved event
types; unexpected cancelled or incomplete items fail the page/run closed.
CP103 may later infer only local `stale` observation state from absence in a
fully complete exact-window refresh, never provider cancellation or deletion.
CP102 production implementation is approved and complete after human review. It adds
only explicit account-level refresh, the fixed GET-only `events.list`
transport, minimized append-only event revisions, and safe per-calendar run
history. Claims and page writes use short fenced transactions; credential,
OAuth, retry sleep, and provider latency remain outside SQL. The CP103
architecture gate correctly stopped before implementation because an equal
CP102 replay reuses its historical event revision: a new successful run retains
only aggregate counts and has no durable exact observed-occurrence set. The
documentation-only remediation, approved after human review, authorizes future
additive migration
`0016_calendar_event_observations`, but does not create it. That future schema
will separate immutable provider/content revision history from provider-
content-free per-run observation evidence, require an explicit nullable closed
evidence-version manifest (including zero-item runs), and leave every historical
CP102 run unmarked without backfill. Effective `current`/`stale` will be derived
only from later fully complete, versioned, internally complete, exact-lineage,
exact-window evidence; absence never derives `cancelled` or `deleted`. CP103
production implementation is approved and complete after human review at
`ce068cd321b00a4e076b4f8363fc63d0afc56ee3`.

Checkpoint 104 is approved and complete after human review as a documentation-
only omission decision. Local V1.5 intentionally has no Calendar event import.
CP103 scoped read-only
External Context browsing adequately serves the release goal without turning
mutable temporal context, stale projections, recurring/moved occurrences, or
privacy-minimized fixed labels into durable searchable documents. There is no
Calendar import API/UI, Source/SourceDocument/chunk or Memory/proposal/Approval
path, automatic import, Agent/Automation authority, migration, export-v1
change, provider write, or OAuth widening. Import is omitted unless a concrete
future workflow proves the need in a separate beyond-V1.5 architecture review.
Checkpoint 105 is approved and complete after human review as a documentation-
only decision keeping Calendar refresh explicitly manual. CP102 manual bounded
refresh remains the sole trigger; CP103 browsing/reconciliation is unchanged.
There is no Calendar schedule persistence/API/UI, background or API-startup
refresh, scheduler-triggered `AgentRun`, new credential authority, migration,
schema, dependency, import, or write change. The V1.3 Agent Automation scheduler
is authority-incompatible, while the V1.4 connector scheduler's reusable
code-level cadence/occurrence/lease concepts remain connector-owned and
unchanged. No concrete single-maintainer V1.5 workflow justifies adding a
Calendar-owned lifecycle for credential, revision/allowlist, concurrency,
restart, missed-run, provider-backoff, and notification recovery. Future
Calendar scheduling requires a separate reviewed capability beyond V1.5.
CP106 has not started. Both preceding CP102 architecture remediations remain
approved and complete after human review.
