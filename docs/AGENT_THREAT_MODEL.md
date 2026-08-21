# Local V1.2 agent threat model

Status: approved with Checkpoint 61 and implemented through the completed
Checkpoint 72 release gate. This threat model remains an implementation and
acceptance gate for Checkpoints 62-74.

## Scope, assets, and trust boundaries

The protected assets are reviewed Memories and provenance; Project isolation;
database integrity; exact human intent and approval; Run/Step/Invocation state;
audit integrity; credentials/configuration; local machine integrity; service
availability; and private user/provider content. The human operator and
application-owned policy/registry are trusted within the existing loopback,
single-maintainer boundary. Provider output and all content from Memories,
Sources, documents, SourceChunks, tool output, links, and future connectors are
untrusted data. The model has no authority. The database is authoritative only
for committed state, not for the truth of model-generated content.

Security invariants are fail-closed schema validation; least authority;
code-owned versioned tools; equal nullable Project scope; exact immutable
approval; short transactions and deterministic row locks; bounded time, calls,
retries, and output; safe allowlisted persistence/public projections; and
append-oriented audit events. V1.2 has no arbitrary execution, external write,
background worker, scheduler, or autonomous approval.

## Threat register

Every `Txx` identifier must map to deterministic tests before Local V1.2
acceptance. Prevention is required; detection and recovery are not substitutes.

| ID / threat | Protected asset and path | Impact | Prevention | Detection | Recovery | Required tests |
|---|---|---|---|---|---|---|
| T01 Prompt injection in Memories, Sources, documents, chunks, or tool output | Policy/authority; untrusted content says to ignore rules, call a tool, reveal data, or treat text as instructions | Scope escape, leakage, unsafe plan | Delimit content as evidence; structured plan only; code registry/policy; no instruction fields sourced from evidence; validate citations/scope | `policy_rejected` event with safe reason; injection corpus metrics | Fail Run before call; discard output; new manual Run only | Direct/indirect injection in every content channel; encoded/quoted/multilingual variants; prove no added tool/authority/cross-scope read |
| T02 Hallucinated/invented tool or version | Registry integrity; provider names absent/different tool | Arbitrary capability attempt or confused execution | Exact `(name, version)` lookup; immutable startup registry; unknown fields forbidden | Unknown-tool safe code and event; registry inventory check | Fail plan with zero invocations | Unknown name, case/Unicode confusable, version downgrade/upgrade, provider-defined schema |
| T03 Malformed structured output | State/integrity; invalid JSON, types, fields, order, encoding | Parser confusion or partial plan | Strict size-first parse and Pydantic/JSON schema validation; reject trailing prose/unknown fields; atomic whole-plan validation | Validation code plus bounded field paths, no raw payload log | Fail planning; no partial Step persistence/execution | Invalid JSON/types/enums/UUIDs, duplicate ordinals, unknown fields, trailing data, oversized/deep payload |
| T04 Authority escalation | Data integrity; model requests `propose/execute`, direct DB transaction, or a higher-authority tool | Unauthorized mutation | Effective authority is min of runtime policy and registered tool; initial executor permits `read` only; model cannot set policy | Authority-denied event and metric | Fail whole plan; operator reviews safe summary | Escalation in goal/plan/input/tool output; nested requests; assert zero write statements and unchanged protected tables |
| T05 Approval bypass | Human intent; code path executes without exact approved Request | Unauthorized mutation | One execution gateway requires locked approved, unexpired, exact hash/scope/target version and unused identity; V1.2 exposes no execute tool | Missing/mismatch approval audit event; invariant monitor | Refuse execution; flag Run failed; investigate audit | No approval, pending/rejected/expired/stale approval, wrong Run/Step/target/action/payload |
| T06 Approval replay | One-time consent; reused Request/identity or duplicate request | Duplicate mutation | Unique execution identity; atomically consume with mutation; terminal approval cannot renew/reset | Uniqueness conflict and replay event | Return original outcome if identical; otherwise reject and reconcile manually | Sequential/concurrent replay, restored request, reused key with changed payload, crash before/after consume |
| T07 Duplicate execution | Data integrity; retries/concurrency call same operation twice | Duplicate side effect/result | Canonical idempotency key; reservation uniqueness; pure-read classification; no automatic retry of ambiguous outcomes | Duplicate/reservation conflict metrics and event | Return durable original result or fail ambiguous attempt; never guess | Duplicate HTTP/provider response, concurrent executor, timeout after tool completion, database disconnect at finalize |
| T08 Infinite loop | Availability/cost; steps cycle or provider keeps requesting work | Resource exhaustion | Immutable acyclic ordered plan; maximum steps/calls/retries/wall clock; no replanning loop in initial runtime | Budget counters and deadline events | Expire/fail Run and stop reservations | Repeated same call, alternating calls, non-progress results, retry loop, clock boundary |
| T09 Unbounded calls or output | Availability/privacy; oversized plan/input/output or excessive fan-out | DoS, storage/log overflow, leakage | Per-plan/tool/input/output/time limits; bounded DB queries; truncate only after schema-safe reject/allowlist; never store arbitrary output | Limit-rejection counters and safe size metadata | Cancel/fail invocation; release resources; do not persist raw payload | Boundary±1 for every limit, compression/decompression bomb fixture, huge arrays/strings, DB row cap |
| T10 Stale or resumed Run | Human intent/state; old plan resumes after deadline/policy/data change | Wrong-scope or obsolete action | Frozen deadlines/registry/policy; terminal states nonresumable; stale detector; evidence/target versions; new Run required after expiry | Stale Run diagnostics and events | Mark `expired`/`failed`; discard late result; manual recreation | Resume every state, changed policy/registry/Project/target, late provider/tool return, terminal resume |
| T11 Concurrency races | State/approval/integrity; start/cancel/finish/review race | Invalid state, duplicate work, lost cancellation | Run row lock, revision compare-and-set, deterministic lock order, unique constraints, one captured time | Conflict/deadlock-safe codes and transition audit | Retry only safe short transaction; reconcile committed winner | Parallel starts, cancel-vs-reserve/finalize, approve-vs-expire/reject, two Steps, forced deadlock |
| T12 Provider timeout or failure | Availability/privacy; hang, transport error, invalid/partial response | Stuck Run, leakage through errors | Provider deadline, cancellation boundary, one classified transient retry, no transaction during call, safe adapter errors | Duration/status/safe code metrics; no raw exception | Retry once only if unambiguously no result; otherwise fail/expire | Timeout before/after bytes, connection failure, invalid response, late response, cancellation, secret-bearing exception |
| T13 Tool timeout or failure | Availability/state; internal read hangs/throws/returns partial result | Stuck or inconsistent Step | Registry timeout; cooperative cancellation where supported; reserve/finalize protocol; read-only DB transaction; output validation | Invocation safe status/code/duration event | Retry only pure read within budget; discard cancelled/late result | Timeout before/during/after read, exception, partial/malformed result, late return, retry exhaustion |
| T14 Database failure after partial progress | Audit/state; commit fails between reservation, outcome, event, or future mutation | Orphan/ambiguous state or audit gap | Related DB facts in one transaction; provider/tool outside transaction; uniqueness/idempotency; future mutation and approval consumption atomic | Stale reservation and invariant diagnostics | Roll back; recovery reconciles durable facts; ambiguous external effect requires manual stop | Failure injection before/after flush/commit at every boundary; connection loss; verify rollback and event consistency |
| T15 Cross-Project access | Confidentiality/isolation; input/evidence ID belongs to another Project or null scope interpreted broadly | Data disclosure/corrupt proposal | Capture scope; repository predicates and FK/application checks on every lookup; null is explicit scope, not wildcard; citation revalidation | Scope-denied event without foreign ID/content; isolation metric | Fail plan/invocation; expose no existence oracle beyond generic denial | Project A/B and null matrix for every tool/API/evidence/approval; guessed UUID; changed Project during Run |
| T16 Secret leakage | Credentials/privacy; prompt/context/output/error includes keys, URLs, environment, headers | Credential compromise | Never send unnecessary config; allowlisted inputs/output; centralized redaction; no raw prompt/provider storage; public schemas exclude internals | Canary-secret tests and log/event scanning | Fail closed, suppress value, rotate externally if real exposure; audit affected Run | Secrets in exception/content/tool output/URL/header/env-like strings; encoded values; public API/log/database snapshot scan |
| T17 Unsafe logging/raw persistence | Privacy/audit; logger or event stores prompt, raw exception/output, SQL, environment, hidden reasoning | Durable sensitive disclosure | Structured allowlisted events; bounded codes/messages; logger filters; schema lacks raw fields; no arbitrary metadata | CI schema/log lint plus canary scans; event-size diagnostics | Remove access to affected log, remediate/rotate, forward-safe redaction migration only with approval | Exception/provider/tool/database failures containing canaries; verify logs/events/public errors/backups exclude them |
| T18 Malicious or oversized tool output | Parser/UI/privacy; output contains instructions, active content, secrets, huge/deep values | Injection, XSS, DoS, leakage | Strict output schema/size; treat text as data; safe summary allowlist; escape UI; URL policy; evidence ID validation | Output-rejected event; CSP/UI test signal; size metric | Discard entire result, fail invocation, no raw persistence | HTML/script/Markdown, Unicode controls, deep JSON, secret canary, invalid citation, huge response |
| T19 Unsafe links | User safety; evidence/output presents `javascript:`, credential URL, tracking or unexpected external link | Code execution/phishing/privacy loss | Prefer internal routes by typed ID; allow only approved schemes/hosts if links are ever rendered; no auto-fetch; visible destination and safe rel attributes | Link sanitizer rejection and UI inventory | Render inert text or omit; fail malformed evidence | `javascript:`, `data:`, `file:`, UNC, userinfo, encoded scheme, redirect-like text, external target keyboard test |
| T20 Audit tampering | Accountability; update/delete/reorder/fabricate AgentEvent or mismatch state | Lost forensic trail or concealed bypass | Application append-only repository, DB grants/constraints where feasible, monotonic unique sequence, event in causal transaction, backup integrity | Sequence-gap/state-event invariant audit and immutable-field tests | Stop affected Run; preserve DB backup; operator investigation; forward repair only | Update/delete through app rejected, duplicate/gap sequence, rollback, concurrent append, state without event |
| T21 Cancellation during tool execution | Human control/state; cancellation arrives after read starts | Run advances after user stop or result leaks | Cancellation revision checked before reservation and after return; no new calls; in-flight V1.2 tools read-only; cooperative cancellation where safe | `cancellation_requested`, discarded-result, and terminal event ordering | Discard late output, finalize invocation cancelled/discarded, Run cancelled | Cancel before call, during DB query/fake tool, at return/finalize race, timeout plus cancel |
| T22 Policy/registry drift | Reproducibility; code deploy changes tool schema/limit while Run waits | Different behavior on resume | Capture registry/policy version; resolve exact installed compatible version; refuse unavailable version; no silent upgrade | Drift/unavailable-version diagnostic | Fail/expire old Run; create new Run under reviewed policy | Remove/change tool version, tighter limits, changed authority/redaction, resume after restart |
| T23 Evidence/citation fabrication | Trust; provider cites nonexistent, out-of-scope, or unsupported record | Misleading research/advice | Evidence references originate from tool results, use typed IDs/versions/ranges, are revalidated in scope; clearly label synthesis | Citation-validation failures and evaluation precision metrics | Reject result or return explicit insufficient-evidence stop | Missing/deleted/foreign/stale IDs, wrong chunk range, reordered citations, unsupported claim fixtures |
| T24 Resource exhaustion across Runs | Availability; many manual requests consume DB/provider/tool capacity | Local denial of service | Single-maintainer rate/concurrency caps, maximum active Runs, bounded queries, deadlines; no background queue | Active/stale/latency aggregate diagnostics | Reject new Runs with safe capacity code; cancel/expire stale Runs manually | Concurrent Run cap, large historical table pagination, slow reads, capacity recovery |

## Detection and operator response

Detection data is itself minimized: correlation ID, entity public ID, event
type, registry/policy version, counts/durations, safe error code, and bounded
allowlisted metadata. It excludes raw content, prompts, tool payloads, SQL,
paths, environment values, credentials, and exceptions. Diagnostics report
aggregate failed/stale/awaiting counts and bounded safe identifiers; they do not
become a general audit-data export.

On a suspected authority, approval, cross-Project, secret, or audit-integrity
failure, the runtime fails closed and stops the affected Run. The operator
preserves the database and logs, uses correlation IDs to inspect safe events,
rotates any credential outside the application if exposure is confirmed, and
uses a separately reviewed forward repair. No recovery procedure deletes the
database, rewrites audit history, silently renews approval, or resumes a
terminal/expired Run.

## Release gate

Checkpoint 72 must provide traceable deterministic tests for every register row
and the evaluation matrix in `V1_2_AGENT_ROADMAP.md`. Checkpoint 73 must confirm
the same boundaries through the real loopback API/UI with fake providers and
tools where external behavior would otherwise occur. Any unresolved critical
threat blocks Checkpoint 74 and publication. Passing tests do not authorize
V1.3 schedules, connectors, credentials, external writes, or execute authority.
