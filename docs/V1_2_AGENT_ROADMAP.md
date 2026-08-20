# Local V1.2 agent roadmap

Status: Checkpoint 61 complete at `850cfd0a749b5de072b910203ba9906ab5270b40`.
Checkpoint 62 persistence foundation is complete at
`3da0cdd875dc8af7a60fd8af5b6f9878be5a769a`; Checkpoint 63 Agent Run state
machine and API is complete at `01832a94ae6f80bdacd0cd9301af3f294302e3e8`.
Checkpoint 64 is complete at `35950c60fd842a4ad022f130a3074ce8d21d9bbc`.
Checkpoint 65 is complete at `1b32d91e62feb10efd5c2f2c241ee43b75b5b5e2`.
Checkpoint 66 completed the bounded read-only executor at
`d4a3533282a8ed616fa0910fcea99b07b0f1b878`. Checkpoint 67 completed deterministic
idempotency, cancellation, deadlines, one safe-read retry, and explicit
synchronous operator recovery at
`7b6c6bb8c4c67f9e8a5a34c363331bc94dbb094e`. Checkpoint 68 is complete at
`1bc90b4339bd5466fda10e5d04711e3f025a0e01`. Checkpoint 69 is complete at
`e6324e52292e108d84666f88aeccf434c92ab39c`; Checkpoint 70 is complete at
`12a70f5e367db76cb4f0e05fb350acabc0230c3c`, and Checkpoint 71 is not started.
The security remediation base is
`ad3c143a568be7c09a73b170f2b5be6347a27a40` with successful CI run
`31950242783`.

Local V1.1 is published as `v1.1.0` from exact commit
`88dffa90ff04cde4c57dcacbe2764b8a31b0c9ce`. `v1.0.0` remains the pre-V1.1
recovery point. The sole current Alembic head remains
`0010_agent_runtime_persistence`, and Project export remains
`second-brain-project-export` version 1.

## Product boundary

V1.2 is a loopback-only, single-maintainer system for manually initiated Agent
Runs. It may add strict structured planning, bounded internal read-only tools,
safe persisted run/audit state, cancellation and recovery, immutable proposed
actions for human review, an accessible Runs/Approvals UI, a read-only Research
Agent, and an advisory Memory Curator Agent. Deterministic fake-provider and
fake-tool evaluation is release-critical.

V1.2 excludes schedules and recurring automation, background workers, external
connectors or writes, autonomous approval, and arbitrary shell, Python, SQL,
filesystem, browser, network, Git, or package-install access. It does not add a
cloud, remote, multi-user, or mobile boundary. Those areas are V1.3 or later.

## Vocabulary and authority

- **Agent Run:** one manually created, durable, bounded attempt to satisfy one
  user goal under a captured policy/tool-registry version and nullable Project
  scope.
- **Agent Step:** one ordered, immutable planned unit within a Run. A Step may
  invoke at most one registered tool at a time, await approval, or stop.
- **Tool:** an application-owned, versioned capability with strict schemas and
  fixed policy. A model cannot define or modify a Tool.
- **Tool Invocation:** one durable attempt to call one exact Tool version with
  validated normalized input, budget reservation, result status, and safe
  summary/evidence references.
- **Approval Request:** an immutable proposal for one exact action. Human review
  changes only review status; it never changes the proposed payload.
- **Agent Event:** an append-oriented, safely redacted fact about a Run's state,
  policy decision, attempt, or recovery action.
- **Automation:** a future trigger definition that creates an Agent Run. It is
  not an Agent Run, and Automation implementation is not part of V1.2.

Authority is ordered but never inferred. `read` inspects only approved local
data and cannot mutate it. `propose` creates an immutable exact action proposal
and cannot execute it. `execute` performs an approved mutation, but the initial
V1.2 runtime is not authorized to expose it. Model output is untrusted data and
can never grant, widen, or elevate authority. Runtime policy is the only source
of effective authority; a request is rejected if any component asks for more.

## Run state machine

The API/service layer owns transactions. Every transition locks the AgentRun
row, verifies the expected state and monotonic revision, writes related state
and an AgentEvent in the same transaction, then commits once. Repositories
never commit. Provider/tool work occurs outside database transactions; intent
and budget are reserved before the call and the outcome is finalized afterward.

| State | Legal next states | Meaning, cancellation, timeout, and resume |
|---|---|---|
| `created` | `planning`, `cancelled`, `expired` | Durable request exists; no provider call. Cancel immediately. Expire if planning did not start by its deadline. Resume by claiming planning once. |
| `planning` | `ready`, `failed`, `cancelled`, `expired` | One provider planning attempt is reserved. Cancellation is checked before/after the provider call. Provider deadline yields `failed` unless the overall Run deadline yields `expired`. Crash recovery may retry only a retryable, unfinalized attempt within budget. |
| `ready` | `running`, `cancelled`, `expired` | Validated immutable plan and budgets are frozen. Starting is compare-and-set idempotent. Expire when the Run deadline passes. |
| `running` | `running`, `awaiting_approval`, `completed`, `failed`, `cancelled`, `expired` | Only the next ordered Step may advance. Self-transition records completion of one bounded invocation/step. Cancellation is honored between invocations and after an in-flight call returns; timeout prevents further calls. Recovery resumes only from durable completed outcomes or a classified safe retry. |
| `awaiting_approval` | `running`, `cancelled`, `expired`, `failed` | No tool execution occurs. Exact approval may return the Run to `running` only for proposal/review foundations; rejection produces a controlled `failed` stop code. Run or proposal expiry yields `expired`; cancellation is immediate. V1.2 has no execute-authority continuation. |
| `completed` | none | Terminal success; immutable plan/outcomes/events remain auditable. Repeated completion is a no-op only with the same idempotency identity. |
| `failed` | none | Terminal controlled failure. A new manual Run is required; terminal Runs never resume. |
| `cancelled` | none | Terminal user cancellation. In-flight non-interruptible reads are ignored on return and cannot advance the Run. |
| `expired` | none | Terminal deadline/staleness stop. It cannot be renewed or resumed; create a new Run. |

Invalid transitions return a stable conflict code and perform no write. Requests
that repeat the same idempotency key and normalized payload return the original
result; key reuse with a changed payload is rejected. Terminal states never
transition. Locks are held only for short database work, never provider/tool
latency. Concurrent start, cancel, timeout, approval, and completion operations
serialize on the Run row; dependent rows are locked in deterministic
Run/step/invocation order. Cancellation wins before new work is reserved;
already-committed completion wins over a later cancellation. Deadline checks
use one transaction-captured UTC instant.

## Persistence proposal

All entities use UUID public IDs, timezone-aware timestamps, a monotonic
revision where mutable, and an optional `project_id`. A null Project means the
explicitly selected unassigned/global-safe scope; it never means unrestricted
access. Foreign keys, policy checks, and repository predicates enforce equal
scope. Public projections are allowlists; internal correlation/idempotency
metadata remains private.

| Entity | Required shape and statuses | Immutability, indexes, ownership, retention |
|---|---|---|
| `AgentRun` | ID; nullable Project; agent kind/version; sanitized goal summary; registry/policy version; state above; budgets/deadlines; correlation and idempotency hashes; safe error code; created/updated/started/finished timestamps | Goal/scope/versions/budgets immutable after creation; state, revision, timestamps, safe error mutable. Unique requester/idempotency hash; indexes on state+deadline, Project+created, correlation. Run transition service owns writes. Retain with audit policy; deletion is an explicit future whole-Run cascade, never automatic while nonterminal or referenced by approval. |
| `AgentStep` | ID; Run; zero-based unique ordinal; structured purpose; registered tool name/version; normalized bounded input; expected evidence; success/stop conditions; status `pending/running/succeeded/failed/skipped/cancelled`; timestamps | Plan fields immutable once Run becomes `ready`; status/timestamps mutable. Unique Run+ordinal; status index. Step transition service owns. Retention follows Run. Concurrent execution requires locked Run and next ordinal. |
| `ToolInvocation` | ID; Run/Step; attempt; tool identity; authority; input hash and bounded validated input; idempotency key; status `reserved/running/succeeded/failed/timed_out/cancelled/discarded`; safe summary/evidence; safe error; timestamps | Identity/input/budget reservation immutable; outcome fields set once. Unique Step+attempt and tool/idempotency key; indexes on status+started and Run. Executor coordinator owns short reservation/finalization transactions. Never overwrite a terminal outcome; ambiguous attempts require recovery classification. |
| `ApprovalRequest` | ID; Run/Step; action type; target type/public ID/version; normalized exact input and hash; preview; evidence references; risk; status `pending/approved/rejected/expired/superseded`; created/expires/reviewed timestamps; one-time execution identity | Proposal payload, hash, risk, scope, expiry, execution identity immutable. Only review status/time/reviewer-safe metadata mutable. Unique execution identity and one active exact proposal identity; indexes on status+expiry and Project+created. Approval service owns review under row locks. Retain at least as long as Run/action audit; deletion must not erase execution evidence. |
| `AgentEvent` | ID; Run; optional Step/Invocation/Approval; monotonic sequence; event type/version; safe code/message and bounded structured metadata; correlation; occurred/recorded timestamps | Append-only to application code. Unique Run+sequence and optional event idempotency identity; indexes on Run+sequence, type+time, correlation. The transaction causing the fact owns insertion. Retain with Run; later archival/export must preserve order and integrity metadata. |

Never persist chain of thought, hidden reasoning, raw prompts, full provider
requests/responses, credentials, secrets, environment values, raw exceptions,
arbitrary tool output, vectors, raw SQL, or model scratch space. Persist only
safe structured plans, bounded schema-validated inputs, safe summaries,
allowlisted evidence references, statuses, timestamps, policy decisions, and
audit metadata. Oversized or nonconforming output is rejected before storage.

## Versioned Tool Registry

Each code-owned immutable registration contains stable name, semantic integer
version, description, strict input/output JSON schemas with unknown fields
forbidden, authority, approval requirement, timeout, per-Run invocation limit,
Project-scope rules, provider/network requirement, redaction policy, output
size limit, and idempotency classification (`pure_read`, `idempotent_write`, or
`non_idempotent`). Registry and policy versions are captured by each Run.

The initial sequence may register only internal `read` tools for Project
retrieval, Memory retrieval, explained Memory search, Source retrieval,
SourceChunk retrieval, operations diagnostics, and maintenance audit. Existing
application services/repositories are wrapped; providers cannot select private
functions or invent names. Diagnostics stay aggregate-only and database
read-only. Every lookup revalidates nullable Project scope.

Arbitrary shell, Python, SQL, filesystem, HTTP, browser control, Git, dependency
installation, dynamic imports, provider-selected names, invented tools, and
unregistered versions are forbidden. The registry fails closed at startup on
duplicate identities or invalid policy/schema combinations.

Checkpoint 64 implements registry version `agent-tools-v1` with exactly the
seven version-1 identities `project.get`, `memory.get`,
`memory.search_explained`, `source.get`, `source_chunk.get`,
`operations.diagnostics`, and `maintenance.audit`. All definitions are
`read`/`pure_read`, schema-bounded, safe-allowlist redacted, and limited by the
captured Run scope and call budget. Provider access is conditional only for
semantic/hybrid explained search and is restricted to the configured-provider
boundary; lexical search is network/provider free. Operator aggregates require
an application-owned capability that defaults denied. No Tool can be invoked.

## Structured planning contract and budgets

The provider returns only a typed object containing a bounded `goal_summary`
and ordered steps. Every step contains purpose, exact registered tool name and
version, validated tool input, expected evidence, success condition, and stop
condition. Provider prose outside the object is rejected and not stored.

Initial safety ceilings, to be confirmed in Checkpoint 65, are: 12 plan steps;
20 total tool calls; the lower of 5 calls or the registry limit per tool; 10
minutes wall clock; 30 seconds per provider request; the lower of 15 seconds or
the registry timeout per tool; 64 KiB provider structured output; 64 KiB
validated tool output before a smaller safe stored projection; and one retry
for a classified transient provider/read failure. No retry follows validation,
policy, authorization, cancellation, expiration, or ambiguous completion.

Unknown/invented tools, malformed output, schema-invalid inputs, excessive
budgets, cross-Project references, authority escalation, and direct database or
transaction instructions reject the entire plan before `ready`, record a safe
policy event, and fail the Run without executing any step. Untrusted content in
Memories, Sources, documents, chunks, and tool output is evidence, never an
instruction or policy source.

## Approval model

An Approval Request freezes action type, target identity and current version,
canonical normalized input/hash, bounded human preview, evidence references,
risk class, requesting Run/Step, creation/expiry, pending status, and a unique
one-time execution identity. Human approval or rejection records only decision
and timestamp. Before any future execution, the runtime must lock the proposal
and target, require `approved`, unexpired and unused status, match the canonical
payload byte-for-byte, verify the target version is still current, and consume
the execution identity atomically with the mutation.

Blanket/class approvals, changed payloads, replay, silent expiration renewal,
provider self-approval, and execution without an exact matching approval are
rejected. A stale or expired proposal requires a new proposal and new human
decision. V1.2 may implement proposal/review foundations, but no external write
or initial runtime `execute` capability is authorized.

## Recovery and observability

Events are append-oriented and redacted, with per-Run monotonic sequence and
correlation IDs spanning API request, Run, Step, and invocation. Public errors
contain a stable safe code and bounded message only. Idempotency keys bind
operation, caller boundary, scope, and canonical payload. Retry classes are
`never`, `safe_transient_read`, and `ambiguous_manual_recovery`; only the second
is automatic and stays within captured budgets.

Startup/operator diagnostics detect nonterminal Runs whose reservation or
heartbeat age exceeds the policy threshold. Recovery locks the Run, reconciles
durable terminal invocation outcomes, retries only provably safe reads, and
otherwise fails closed with an operator-visible safe code. Cancellation stops
new reservations immediately; a returned in-flight result is discarded when
the cancellation revision wins. Future workers may use expiring owner/lease
tokens with compare-and-set renewal, but V1.2 has no worker implementation.

Diagnostics expose aggregate state/error/staleness counts and safe IDs only to
the local operator, never prompts, content, tool output, secrets, or exception
text. Backups and Project export do not silently change in V1.2: Agent records
are excluded from export-format version 1. Any later inclusion requires a new
format/version/privacy/restore decision. Database backups must treat run and
approval records as sensitive and preserve relational/audit ordering.

## Deterministic evaluation strategy

A fake clock, UUID source, provider, registry, tools, failure injector, and
transaction hooks make every scenario reproducible with no credentials or
network. Unit tests cover schemas, state transitions, policy, budgets,
redaction, and canonical hashing. PostgreSQL integration tests use only the
verified `second_brain_test` database for locks, rollback, uniqueness, and
isolation. API/UI tests cover safe projections, keyboard/focus/status behavior,
and exact approval review. An invariant test asserts no unauthorized table
mutation.

The release harness must cover valid plan execution; unknown-tool and malformed
plan rejection; total/per-tool/step/output/time/retry budgets; loop prevention;
provider and tool timeout/failure; cancellation before, during, and after a
call; database rollback and failure after reservation/finalization; duplicate
requests; concurrent start/cancel/finish/approval; Project and nullable-scope
isolation; prompt-injection resistance; authority escalation; approval bypass,
payload change, stale target, expiration, and replay; secret/error redaction;
evidence/citation existence, ordering, scope, and correctness; recovery from
stale Runs; and proof of no unauthorized mutation.

## Checkpoints 62-74

Each checkpoint is independently reviewed and rolled back by reverting only
its migration/code/docs; database rollback means a separately approved safe
forward repair unless its checkpoint explicitly proves a test-database-only
downgrade. All depend on the previous checkpoint and Checkpoint 61 approval.

### 62 - Agent Runtime persistence foundation

- **Goal/why:** Add the five proposed entities and repository primitives so
  later behavior has durable invariants before APIs exist.
- **Allowed:** models, one migration, schemas internal to persistence, indexes,
  constraints, repository tests, export exclusion documentation.
- **Forbidden:** runtime orchestration, provider/tool calls, public API/UI,
  approvals or execution.
- **Areas/API/migration:** `app` persistence/repositories and Alembic; no API;
  one additive migration after `0009`.
- **Transactions/concurrency:** repositories never commit; prove uniqueness,
  FK/scope rules, append-only event discipline, revision/lock primitives.
- **Tests/acceptance:** migration upgrade/check on verified test DB, model and
  constraint tests, no hidden/raw fields, V1 export unchanged.
- **Dependency/risk/rollback:** C61; high; revert code and, only on verified test
  DB during lifecycle tests, migration downgrade. Production recovery is
  forward-only unless separately approved.

### 63 - Agent Run state machine and API

- **Goal/why:** Implement manual create/read/list/cancel and strict transition
  service before providers or tools.
- **Allowed:** typed APIs, transition service, safe events/errors, pagination,
  idempotent create/cancel; **forbidden:** planning/execution/tools/UI.
- **Areas/API/migration:** Agent service/routes/schemas; additive Run APIs; no
  migration expected.
- **Transactions/concurrency:** route/service transaction ownership, Run row
  locks, revisions, terminal-state and race precedence.
- **Tests/acceptance:** transition matrix, invalid transitions, duplicates,
  cancellation/expiry/concurrency, safe public fields; all transitions atomic.
- **Dependency/risk/rollback:** C62; high; revert additive routes/service.

### 64 - Tool Registry and policy enforcement

- **Goal/why:** Establish a code-owned fail-closed capability boundary.
- **Allowed:** registry metadata/schemas, policy resolver, read-tool definitions
  without invocation; **forbidden:** dynamic/model tools, arbitrary execution,
  provider planning.
- **Areas/API/migration:** runtime policy modules, perhaps private diagnostics;
  no public API or migration.
- **Transactions/concurrency:** immutable startup registry; scoped policy checks
  before any repository access.
- **Tests/acceptance:** duplicate/unknown/version/schema/authority/scope/budget
  rejection and registry inventory; only approved internal reads registered.
- **Dependency/risk/rollback:** C63; critical; revert registry modules.

### 65 - Structured planning provider

- **Goal/why:** Convert a manual goal into one strictly validated frozen plan.
- **Allowed:** provider abstraction, fake provider, planning transition, budget
  validation; **forbidden:** tool execution, raw persistence, arbitrary prose.
- **Areas/API/migration:** provider/runtime service; existing Run API may expose
  safe plan summary/status; no migration expected.
- **Transactions/concurrency:** reserve/finalize around provider call; never hold
  locks during call; single planning claimant.
- **Tests/acceptance:** valid/malformed/unknown/escalating/injected/oversized/
  timed-out plans; zero tool calls before `ready`.
- **Dependency/risk/rollback:** C64; critical; disable/revert provider path.

### 66 - Bounded read-only executor

- **Goal/why:** Execute frozen steps through only registered internal reads.
- **Allowed:** invocation coordinator and approved read wrappers; **forbidden:**
  propose/execute authority, writes, network, shell, filesystem, background work.
- **Areas/API/migration:** runtime/tool adapters and safe Run projections; no
  migration expected.
- **Transactions/concurrency:** reserve budget and attempt, release transaction,
  call, lock/revalidate, finalize; one ordered active Step.
- **Tests/acceptance:** all allowed tools, bounds, citations, scope, failures,
  malicious output, no application mutation.
- **Dependency/risk/rollback:** C65; critical; registry feature-disable/revert.

### 67 - Idempotency, cancellation, recovery, and failure injection

- **Goal/why:** Make crashes, duplicates, timeouts, and races deterministic.
- **Allowed:** retry classifier, stale detector, synchronous recovery command,
  fake clock/fault hooks; **forbidden:** worker/scheduler/lease implementation.
- **Areas/API/migration:** runtime/recovery/diagnostics; additive retry-safe API
  semantics; migration only if C62 fields prove insufficient and review stops.
- **Transactions/concurrency:** compare-and-set revision, deterministic locks,
  ambiguous outcomes fail closed.
- **Tests/acceptance:** crash at every boundary, cancellation in-flight,
  duplicate/concurrent requests, rollback; no duplicate work or resumed terminal
  Run.
- **Dependency/risk/rollback:** C66; critical; revert recovery layer.

### 68 - Approval and proposed-action foundation

Implementation is complete at
`1bc90b4339bd5466fda10e5d04711e3f025a0e01`. The exact supported proposal type is
`memory.update`; the four additive APIs provide immutable creation, bounded
read/list, and human-only approve/reject review. Expired and stale targets fail
closed as terminal Approval states. There is no proposal execution, target
mutation, write Tool, or execute authority. Checkpoint 69 is complete at
`e6324e52292e108d84666f88aeccf434c92ab39c`; Checkpoint 70 is complete at
`12a70f5e367db76cb4f0e05fb350acabc0230c3c`. Checkpoint 71 is not started.

- **Goal/why:** Persist exact immutable proposals and human decisions without
  enabling execution.
- **Allowed:** proposal creation/read/review/expiry/staleness rules and APIs;
  **forbidden:** external writes, blanket approval, runtime execute authority.
- **Areas/API/migration:** approval service/routes; migration only if reviewed
  C62 schema needs an additive constraint/field.
- **Transactions/concurrency:** lock Approval, Run, then target consistently;
  single decision; exact hash and one-time identity.
- **Tests/acceptance:** approve/reject/expire/stale/change/replay/bypass/races;
  approval cannot mutate target or cause execution.
- **Dependency/risk/rollback:** C67; critical; revert API/service, preserve audit.

### 69 - Agent Runs and Approval UI

- **Goal/why:** Provide accessible manual initiation, status/evidence,
  cancellation, and exact proposal review.
- **Allowed:** top-level/local UI, explicit refresh, keyboard/focus/live status,
  safe previews; **forbidden:** polling, automatic retries/approval/execution,
  browser persistence, redesign.
- **Areas/API/migration:** frontend and existing additive APIs; no migration.
- **Transactions/concurrency:** UI treats conflicts/stale revisions as refresh,
  never predicts success.
- **Tests/acceptance:** every state/error, responsive/reduced-motion/keyboard,
  exact confirm/reject, no secret/raw content rendering.
- **Dependency/risk/rollback:** C68; high; revert frontend route/client.

### 70 - Read-only Research Agent

- **Goal/why:** Ship one useful agent that synthesizes cited local evidence.
- **Allowed:** fixed agent definition over Project/Memory/search/Source/chunk
  reads; **forbidden:** writes, proposals, uncited claims, external research.
- **Areas/API/migration:** agent catalog/prompt contract and UI selection; no
  migration expected.
- **Transactions/concurrency:** ordinary bounded executor semantics; capture
  evidence identity/version.
- **Tests/acceptance:** deterministic scoped answers with valid ordered
  citations, injection resistance, insufficiency stop, no mutation.
- **Dependency/risk/rollback:** C69; high; unregister/revert agent.

### 71 - Advisory Memory Curator Agent

- **Goal/why:** Produce reviewable curation advice without changing Memories.
- **Allowed:** read-only quality/maintenance/retrieval tools and immutable
  proposed Memory actions; **forbidden:** Memory mutation, automatic approval or
  promotion, embeddings generation, maintenance execution.
- **Areas/API/migration:** fixed agent definition/proposal types; no migration
  unless C68 review explicitly requires one.
- **Transactions/concurrency:** target version captured; stale advice invalid;
  nullable Project isolation.
- **Tests/acceptance:** evidence-backed advice, exact proposals, stale detection,
  rejection of invented changes, no Memory writes.
- **Dependency/risk/rollback:** C70; critical; unregister/revert curator.

### 72 - Agent security and evaluation harness

- **Goal/why:** Turn this threat model into deterministic release gates.
- **Allowed:** fake providers/tools/clocks, adversarial fixtures, fault and
  concurrency harnesses; narrowly scoped defects; **forbidden:** live paid calls
  or expanded capability.
- **Areas/API/migration:** tests/evaluation documentation; no intended API or
  migration.
- **Transactions/concurrency:** exercise PostgreSQL locks/rollback only on
  verified test DB.
- **Tests/acceptance:** every threat-model required test and evaluation scenario
  passes with deterministic reports and no unauthorized mutation.
- **Dependency/risk/rollback:** C71; critical; revert harness/isolated fixes.

### 73 - Local V1.2 end-to-end acceptance

- **Goal/why:** Prove real loopback API/UI integration and safety boundaries.
- **Allowed:** manual Run through both agents, cancellation/failure/recovery/
  approval review evidence, accessibility/privacy/security audits, focused
  defects; **forbidden:** new features, paid calls, external writes.
- **Areas/API/migration:** acceptance docs plus blocker fixes only; none
  intended.
- **Transactions/concurrency:** verify live development identity before reads;
  test mutations only in isolated test DB or exact approved fixtures.
- **Tests/acceptance:** all routes/states, Vite proxy, safe failure, V1 export
  compatibility, Full zero-skip verification.
- **Dependency/risk/rollback:** C72; high; revert isolated defects.

### 74 - Local V1.2 release hardening

- **Goal/why:** Synchronize release facts, clean installs, recovery, and final
  evidence before separate publication approval.
- **Allowed:** documentation, inventories, dependency/security/privacy audit,
  final Full; **forbidden:** product/schema/API changes, tag/Release without a
  later explicit instruction, V1.3 work.
- **Areas/API/migration:** release docs only; verify approved migration head and
  unchanged export version.
- **Transactions/concurrency:** no application writes; verify backup/recovery
  guidance and stopped services.
- **Tests/acceptance:** reproducible installs, deterministic agent harness,
  accessibility, all backend/frontend/DB checks, clean release commit identity.
- **Dependency/risk/rollback:** C73; high; documentation revert; V1.1 remains the
  recovery release.

## Deferred Local V1.3 outline

V1.3 may separately plan a local scheduler; one-time and recurring Automation
definitions that trigger Agent Runs; worker leases and duplicate prevention;
pause/resume/retry/missed-run policy; a notification inbox; Daily Brief and
Project Watch agents; local credential isolation; read-only Calendar, Gmail,
and GitHub connectors; draft-only external actions; and exact approval-gated
external writes. It must define connector trust, credential storage/redaction,
network allowlists, delivery idempotency, replay prevention, revocation, audit,
and recovery before implementation. Checkpoint 61 authorizes none of it.
