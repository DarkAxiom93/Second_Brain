# Local V1.3 Automation threat model

Status: **Implemented through approved Checkpoint 85; A01-A18 are release gates.**

This model extends, and does not replace, `AGENT_THREAT_MODEL.md`. The protected
assets remain reviewed knowledge, exact nullable Project scope, database and
audit integrity, human intent, credentials/configuration, local-machine safety,
availability, and private content. New assets are schedule intent, occurrence
identity, lease ownership, next-run correctness, notification privacy, and the
guarantee that Automation configuration grants no Agent authority.

The operator and application-owned registry/policy/schedule implementation are
trusted inside the existing loopback single-maintainer boundary. Model output,
goals, stored content, provider output, wall-clock changes, and future connector
content are untrusted. PostgreSQL committed state and database time are
authoritative for ownership; host wake timing is not.

## Security invariants

- An Automation is only a trigger/configuration; every execution is one bounded
  Agent Run with independently revalidated authority.
- One occurrence creates at most one Agent Run, and one Run links to at most one
  occurrence.
- Schedule, occurrence, lease, retry, and Run idempotency identities are
  application-derived and protected by database uniqueness.
- Stale owners cannot commit after lease loss; generation fencing is mandatory.
- No lock or transaction spans provider or Tool latency.
- Only fixed code-owned read-only Agents may execute automatically in V1.3.
- Pause, cancellation, Project deletion/change, policy drift, ambiguous state,
  and capacity exhaustion fail closed without scope or authority widening.
- Catch-up, retries, batches, recurrence frequency, history projections, and
  notifications are bounded.
- Notifications and public APIs expose safe metadata and links, never retrieved
  content, prompts, raw goals, provider/tool payloads, secrets, or exceptions.
- V1.3 has no connector, external research/write, proposal execution, automatic
  Approval, arbitrary execution, remote access, or multi-user boundary.

## Threat register

Every `Axx` item has deterministic accepted Checkpoint 84 tests and remains a
release gate.

| ID / threat | Impact | Prevention and fail-closed behavior | Detection / recovery / required tests |
|---|---|---|---|
| A01 Duplicate occurrence or Run execution | Duplicate work, cost, inconsistent history | Unique `(automation_id, schedule_revision, scheduled_at)`; occurrence-derived Run idempotency; atomic Run link; conflict returns existing durable fact. Never create a replacement Run. | Count uniqueness conflicts safely; reconcile to existing occurrence/Run. Test sequential/concurrent ticks, retries, commit disconnects, duplicate HTTP/operator starts. |
| A02 Replay of old occurrence/configuration | Obsolete intent executes after edit/pause/cancel | Capture schedule revision and definition identity; claimant revalidates lifecycle/revision before Run creation; terminal occurrences immutable. Mismatch becomes `cancelled` or `failed`, never reinterpreted. | Safe revision-mismatch notice. Test replay after every lifecycle/edit transition and restored stale request. |
| A03 Stale lease owner | Two owners commit or renew | Opaque owner plus monotonic generation and expiry; every mutation compares exact owner/generation and database time. Lost owner may observe only; it cannot link or finalize. | Lease-loss metric and safe event. Test expiry between claim/link/renew/finalize and late worker return. |
| A04 Concurrent schedulers | Duplicate materialization/claim, contention | `FOR UPDATE SKIP LOCKED`, deterministic ordering, uniqueness, bounded batches, short transactions, lease fencing. Deadlock/serialization retries are bounded. | Contention counters without payloads. PostgreSQL tests with multiple scheduler processes and forced deadlocks. |
| A05 Clock jump or host timezone change | Early/late/duplicate work, broken leases | UTC database time for due/lease decisions; injected aware clock; IANA zone stored; next slot advances from prior scheduled local slot, not wake time. Backward time never reopens terminal identity. | Detect implausible drift and pause scheduler safely. Test forward/backward jumps, sleep/wake, host-zone changes. |
| A06 DST/timezone error | Skipped or double local run | Closed schedule calculator; nonexistent time moves to first valid instant; ambiguous time uses earlier fold exactly once; capture local/offset/UTC. Invalid/unknown zones reject enable/edit. | Preview and safe calculation error. Test representative gap/fold zones, historical/future transitions, library upgrade fixtures. |
| A07 Restart during occurrence creation | Lost or duplicated scheduled slot | Occurrence insert and Automation next-run advance share one transaction. Rollback leaves neither; commit leaves both. Uniqueness resolves replay. | Startup invariant scan; fail scheduler if next-run/occurrence invariant is impossible. Failure injection before/after flush/commit. |
| A08 Restart during Run creation/execution | Orphan Run, duplicate Run, guessed outcome | Run creation and occurrence link are atomic in caller-owned session; Run idempotency resolves replay. Once linked, Agent Run recovery rules govern execution; scheduler never guesses or invokes automatic manual recovery. | Reconcile linked Run states; ambiguous invariant becomes failed/operator action. Inject crash at every link/plan/execute boundary. |
| A09 Missed schedules/downtime | Silent data loss or replay flood | Closed `skip`/`run_once`; no replay-all; seven-day maximum lookback; advance to first future slot; durable missed outcome/notice. | Show missed count/latest slot. Test short/long downtime, one-time expiry, repeated restarts. |
| A10 Runaway recurrence | Resource/cost exhaustion | No cron/seconds; minimum daily semantics; maximum active definitions; one nonterminal occurrence per Automation; bounded batch and global capacity; deterministic next-slot validation. Invalid next slot pauses/fails closed. | Rate/capacity diagnostics and operator notice. Boundary/fuzz tests for interval, overflow, non-progressing calculator. |
| A11 Retry storm | Database/provider pressure and duplicates | Scheduler retries only safe pre-link setup classes; capped attempts/backoff/jitter and retry-not-before; capacity deferral bounded separately; Agent retries remain independent. Ambiguous/validation/policy errors never retry. | Aggregate retry/exhaustion status. Test fleet-wide outage, capacity full, deterministic backoff, repeated restart. |
| A12 Schedule modification race | Work executes under neither old nor new intent | Row lock and revision CAS; schedule edit only paused/draft; captured schedule revision; claimant revalidation. Existing linked Runs remain historical and are not mutated. | HTTP conflict plus refresh. Test edit/pause/resume/cancel against materialize/claim/link. |
| A13 Deleted or changed Project scope | Cross-scope read or orphan work | Exact Project FK/scope validation at enable, claim, Run creation, and execution. Project Watch requires non-null exact Project. Deleted/missing/changed scope fails occurrence; never substitute null/all. | Safe `scope_unavailable` status without foreign content. Test deletion and reassignment at every boundary. |
| A14 Privilege expansion through configuration | Schedule grants tools, budgets, propose/execute, connector or arbitrary code | Closed configuration and fixed schedulable catalog; no tool list, prompt template, executable expression, URL, path, SQL, or authority field. Effective Run policy is application-owned and revalidated. Unknown fields reject whole request. | Policy rejection and inventory assertion. Adversarial JSON/nesting/confusables/catalog drift; prove registry and protected tables unchanged. |
| A15 Malicious goal or local evidence text | Prompt injection, leakage, unintended action | Application constructs bounded goals for fixed Agents; evidence is delimited untrusted data; strict structured output/citations and existing V1.2 policy apply. Model output cannot edit schedules or request new capability. | Safe Agent policy failure linked to occurrence. Injection corpus across labels, content, event summaries, and stored evidence. |
| A16 Capacity exhaustion | Starvation, unavailable manual Runs, unbounded database growth | Preserve 32 nonterminal Run cap; separate Automation/occurrence/claim limits; deterministic fair due order; capacity retains durable due work and never bypasses manual Run checks. No automatic deletion. | Aggregate capacity-age notice. Load tests ensure manual replay works, no dropped slot, bounded tick/storage amplification. |
| A17 Notification leakage or spoofing | Private content/secret exposure, misleading status | Code-owned closed event kinds and templates; safe status/links only; dedupe key; loopback inbox; no OS/email/webhook/push; escape UI text and never render model HTML. | Redaction tests and invariant scan. Inject secret-bearing errors/goals/results and hostile labels; verify no content in API/DOM/log. |
| A18 Accidental autonomous mutation | Reviewed data changes without explicit human action | Automatic mode admits only exact fixed `read` Agent versions and existing executable read Tools. Curator/propose, Approval execution, promotion, maintenance mutation, connectors, and all write Tools are denied. Scheduler DB writes are limited to its own metadata plus Run creation. Any policy/catalog mismatch stops the occurrence. | Protected-table before/after invariant and SQL mutation allowlist. Test malicious model/tool output, registry drift, proposed actions, direct service bypass. |

## Additional failure policy

An impossible invariant, unknown state, invalid timezone, non-progressing next
instant, lease token mismatch, missing linked Run, more than one linked Run,
or unclassified error must stop that occurrence and prevent further automatic
work for the affected Automation. The scheduler may pause the definition and
create one deduplicated safe notification; it must not repair, delete, remap,
reschedule from `now`, widen scope, or invent a Run.

Stopping the scheduler is always safe: committed definitions, occurrences,
leases, Runs, and notifications remain durable. Restart work is driven only by
committed state. Operator recovery actions must be exact, revision-aware, and
separate from pause/resume/cancel; bulk retry and replay-all are forbidden.

## Privacy, audit, and retention

Persist only typed schedule fields, captured occurrence identity, lease metadata,
safe state/error codes, fixed Agent identity, exact scope, linked public IDs,
and bounded notification templates. Never persist raw prompt/provider/tool
content in Automation metadata. Existing Agent Run redaction remains mandatory.

Automation and occurrence history is audit-sensitive and has no automatic V1.3
deletion. APIs paginate and filter in SQL with deterministic ordering. Project
export version 1 continues to exclude Agent and Automation records. Any later
export, archive, or deletion design needs a new privacy/FK/restore decision.

## Evaluation and release gates

Use fake clocks, UUIDs, scheduler owners, providers, Tools, and transaction
failure hooks. Unit tests cover schedule/DST calculation, closed schemas,
canonical identities, lifecycle, retry classification, redaction, and capacity.
PostgreSQL integration tests on verified `second_brain_test` cover locks,
uniqueness, isolation, failure injection, and concurrent schedulers. UI tests
cover every state plus keyboard, focus, live announcements, reflow, reduced
motion, and timezone clarity.

Before release, the harness must map every A01-A18 threat to named tests and
prove: no duplicate occurrence or Run; no stale-owner commit; no missed-slot
explosion; no scope widening; no automatic proposal/Approval/mutation; no raw
content in notifications; bounded retry/capacity; deterministic restart; and
zero writes to protected domain tables during automatic read-only execution.
