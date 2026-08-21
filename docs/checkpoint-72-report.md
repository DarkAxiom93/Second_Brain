# Checkpoint 72 report

Checkpoint: 72 - Agent security and evaluation harness (`Complete`)

Human review was approved. The implementation commit is
`45e940ec89b6cf3783ab2dc7cdfa837b6cbc3597`, pushed to `origin/main`. Its exact
successful `Second Brain CI` push run is `32416546227` (attempt 1,
completed/success) with zero artifacts. Checkpoint 73 is not started.

## Preflight

- Base `HEAD`, `main`, and `origin/main` were exactly
  `48f3461021d703a2ac4d8d004a0393ae2211cb43`; latest commit was
  `docs: finalize checkpoint 71 state`, divergence was `0 0`, and the worktree
  was clean.
- Authenticated GitHub identity was `DarkAxiom93` (ID `287775525`). Exact
  `Second Brain CI` run `32411757071` matched the base SHA, branch `main`, event
  `push`, attempt 1, and completed/success with zero artifacts.
- CP71 was Complete; CP72 and CP73 were Not started. Live development and test
  database identities were verified. Alembic current and sole head were
  `0010_agent_runtime_persistence`; `alembic check` found no operations.
- Registry remained `agent-tools-v1`; Project export remained format version 1.

## Deterministic harness

`tests/test_agent_security_evaluation.py` is the executable traceability gate.
It requires exactly T01-T24, at least two automated proofs per threat, verifies
the source declaration has no missing or duplicate ID, verifies every cited
Python/Vitest test still exists and retains an executable assertion, and
requires both PostgreSQL and UI evidence. Existing fake planning, Research, and
Curator providers, fake Tools,
captured clocks, fault hooks, and threading events/barriers were reused. No
credential, paid provider, or external network is used.

The PostgreSQL suite exercises row locks, unique identities, rollback,
reservation/finalization faults, nullable/Project isolation, stale evidence and
targets, Approval review races, event ordering, recovery, and active-Run
capacity. Timing sleeps are not used for race precedence.

## T01-T24 traceability

All rows are `covered`; there are no partial or blocked critical threats. Test
names below are shortened; the executable matrix contains exact node IDs.

| Threat | Prevention invariant | Deterministic automated evidence | Result |
|---|---|---|---|
| T01 | Untrusted goal/evidence remains data and cannot select authority or scope | Research injection corpus; Curator injection integration; whole-plan authority rejection | Covered |
| T02 | Only exact immutable registered Tool name/version resolves | registry inventory/lookup; Research invented/operator Tool rejection | Covered |
| T03 | Size-first strict structured output rejects malformed/unknown/partial data atomically | planning adapter invalid JSON matrix; Curator malformed/unknown/oversize matrix | Covered |
| T04 | Effective authority is application-owned read-only/propose maximum | authority-escalation registry matrix; forbidden-capability inventory | Covered |
| T05 | Review never bypasses an exact pending Approval and never executes/mutates | CP68 create/review mutation proof; UI exact review/no-execute proof | Covered |
| T06 | Approval identity/status/hash is immutable and replay-safe | concurrent opposite-review winner; scope/payload/reject replay matrix | Covered |
| T07 | Reservation and terminal replay prevent duplicate execution | concurrent execute claim; retry plus terminal write-free replay | Covered |
| T08 | Frozen ordered plan and closed budgets prevent loops | fail-closed order/budget unit matrix; retry counts against budgets | Covered |
| T09 | Inputs, plans, calls, queries, and outputs have closed bounds | all Tool schema boundary tests; oversized planning output rejection | Covered |
| T10 | Stale/terminal Runs and unknown captured versions fail closed | recovery state matrix; stale registry planning rejection | Covered |
| T11 | Row locks/revisions/unique keys give one committed race winner | cancel-vs-Tool barrier; concurrent exact Approval creation | Covered |
| T12 | Provider latency/failure has deadlines, safe codes, and discarded late output | Research provider failure/redaction matrix; provider-vs-cancel barrier | Covered |
| T13 | Tool failure uses the closed retry classifier and exhaustion stop | second transient exhaustion; after-return fault/recovery test | Covered |
| T14 | Related durable facts commit or roll back atomically | reservation rollback fault; Approval create/review transaction fault matrix | Covered |
| T15 | Every lookup/evidence path preserves exact Project or explicit-null scope | registry scope matrix; retry/recovery scope/domain snapshot | Covered |
| T16 | Secret canaries cannot enter provider-safe public/durable boundaries | provider exception redaction; secret-like Research claim rejection; UI private canary rejection | Covered |
| T17 | Raw prompts/payloads/output/exceptions have no durable/public fields | forbidden-column inventory; provider failure safe-state/event proof | Covered |
| T18 | Malicious/oversized Tool data is schema-validated and rendered inert | dispatch output validation; script-like UI evidence test | Covered |
| T19 | Agent UI creates no unsafe evidence links or automatic navigation/fetch | unsafe-scheme/script inert rendering; malformed private projection rejection | Covered |
| T20 | Events are append-only, monotonic, unique, and causal with state | repository primitive inventory; concurrent event append/locking proof | Covered |
| T21 | Cancellation winner discards in-flight/late Tool output | cancel after reservation barrier; completion-first cancellation conflict | Covered |
| T22 | Captured registry/agent versions never silently upgrade or widen recovery | stale registry test; persisted unknown Curator version test | Covered |
| T23 | Citations originate in exact successful invocations and are revalidated after latency | evidence-binding corruption matrix; stale Curator target-lock barrier | Covered |
| T24 | A PostgreSQL-serialized active-Run cap bounds concurrent manual demand | concurrent capacity winner; safe rejection/replay/capacity recovery | Covered |

## Security canaries and public/durable boundaries

Synthetic canaries occur only in tests. Provider exceptions, idempotency keys,
secret-like synthesis, private projection fields, unsafe schemes, script-like
Tool summaries, and malformed provider payloads are checked against API bodies,
Agent rows/events, safe errors, captured UI data, Research/Curator results, and
Approval projections. Raw provider response, prompt, Tool output, exception,
execution identity, proposal hash, and correlation fields remain absent from
public schemas and prohibited durable columns. Redaction was not weakened.

## No-unauthorized-mutation proof

The Curator PostgreSQL scenario snapshots `projects`, `memories`,
`memory_embeddings`, `sources`, `source_documents`, `source_chunks`, and
`memory_proposals` across planning, Tool execution, proposal creation, Approval
approval, same-decision replay, and opposite-decision conflict. Counts and the
target Memory remain byte-for-byte unchanged. Only the expected one
`approval_requests` row and Agent runtime/audit rows are added. Complementary
Research and executor scope/recovery tests prove read-only behavior for Manual,
Research, and Curator paths. Approval review has no Memory mutation gateway.

## Defect and narrow forward fix

T24 evaluation exposed that per-Run budgets existed but concurrent Run creation
had no application-owned capacity decision. The narrow fix adds a constant
maximum of 32 nonterminal Runs. Creation takes one transaction-scoped PostgreSQL
advisory lock keyed by stable application-owned bigint `0x534252554E` (`SBRUN`),
counts `created`, `planning`, `ready`, `running`, and `awaiting_approval`, and
returns a safe HTTP 429 when full. No other repository advisory lock exists.

The acceptance audit found and fixed one ordering defect in the initial fix: a
concurrent exact replay that waited for the capacity lock could be rejected if
its creator filled the final slot. Creation now rechecks the idempotency row
under lock before counting capacity. Real PostgreSQL coverage proves the
0-through-32 boundary, one winner across slots 31/32/33, exact same-key replay
at the last slot, existing changed-payload collision behavior, unpoisoned
rejected keys, all five counted and all four terminal states, and advisory-lock
release after rollback/session close. No schema, migration, background process,
lease, heartbeat, queue, capability, provider, or authority was added.

## Verification

- Focused Agent security suite: 240 passed, zero skipped.
- Focused Agent UI: 23 passed; the existing case now also covers an unsafe
  scheme and synthetic private-field canary. No polling, automatic action,
  browser persistence, keyboard, focus, or accessibility behavior regressed.
- Executable traceability artifact: 48 collected checks.
- New PostgreSQL CP72 scenarios: 13 collected cases covering capacity boundary,
  concurrency, state membership/release, replay/collision, rejected-key
  recovery, and transaction-scoped lock release. Existing cited PostgreSQL
  scenarios remain the authoritative fault/concurrency/mutation evidence.
- Full verification: dependency integrity; Ruff lint/format; mypy 131 source
  files; 914 backend tests; Alembic current/heads/check; frontend ESLint and
  TypeScript; 114 frontend tests; production build; `git diff --check` all
  passed with zero skips.

Baseline reconciliation is 853 backend and 114 frontend cases before CP72.
CP72 adds 48 executable matrix checks plus 13 PostgreSQL capacity cases, for
914 backend cases. The matrix has 46 unique referenced nodes: two CP72 capacity
tests and 44 reused CP62-71 tests. Existing Curator and UI cases were
strengthened in place and add no collected count; Manual and Research evidence
is reused unchanged. Frontend remains 114 cases.

## Status and limitations

No migration, dependency, CI, Docker, Tool registry, Agent version, or export
format changed. Alembic remains `0010_agent_runtime_persistence`, registry
`agent-tools-v1`, and Project export version 1. The harness evaluates the local
single-maintainer V1.2 boundary; it does not authorize remote/multi-user use,
connectors, arbitrary execution, write Tools, proposal execution, Automation,
or background work. CP72 is `Complete` at
`45e940ec89b6cf3783ab2dc7cdfa837b6cbc3597`, with human review approved, the
implementation pushed to `origin/main`, and exact successful `Second Brain CI`
push run `32416546227` producing zero artifacts. CP73 is `Not started`.
