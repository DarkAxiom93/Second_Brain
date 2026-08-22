# Checkpoint 75 report - Local V1.3 architecture, roadmap, and threat model

Status: **Approved and complete after human review.**

## Outcome

Checkpoint 75 is documentation and planning only. It proposes Local V1.3 as
**Local Automations & Scheduled Agents**, based on the published Local V1.2.1
release. No V1.3 production code, migration, API, frontend, test implementation,
dependency, Tool Registry version, Project export version, connector, Approval
execution, or external-write behavior was added.

The proposed end state supports durable one-time/daily/weekly Automations,
enable/pause/cancel lifecycle, deterministic IANA-timezone scheduling, durable
occurrences with fenced leases, duplicate-safe Run creation, bounded missed-run
and retry policy, local safe notifications, accessible operator history, and
fixed read-only Daily Brief and Project Watch Agents.

Automatic planning/execution is recommended only as a later, independently
reviewed V1.3 checkpoint, only for those fixed code-owned read-only Agents, and
only after trigger-only creation/recovery is proven. Automations default to
`create_only`; automatic mode is explicit opt-in. Memory Curator, arbitrary
Research goals, proposals, Approval execution, and every mutation remain out.

## Architecture summary

- **Automation -> Agent Run:** an Automation is a durable trigger/configuration;
  an Agent Run is one separately governed bounded execution. One occurrence may
  create at most one Run. A schedule never grants Tool authority or changes a
  Run, and a Run never reschedules itself.
- **Persistence:** three minimal entities are proposed: `Automation` with its
  singular schedule value, `AutomationOccurrence` with current fenced lease and
  linked Run, and append-only local `AutomationNotification`. Separate schedule
  and claim tables were rejected as unnecessary one-to-one lifecycle fragments.
- **Concurrency:** bounded deterministic `FOR UPDATE SKIP LOCKED` selection,
  unique occurrence identity, short transactions, Automation -> occurrence ->
  Run lock order, opaque lease owner plus monotonic generation, and no lock
  across provider/Tool latency.
- **Recovery/idempotency:** occurrence materialization plus next-run advancement
  is atomic; Run creation plus occurrence linking must be atomic; occurrence-
  derived Run idempotency resolves replay; expired leases are reclaimed with a
  new generation; ambiguous state fails closed for operator review.
- **Time:** UTC/database time governs due work and leases; schedules use stored
  IANA zones. Spring-forward gaps choose the first valid instant; fall-back
  ambiguity chooses the earlier fold exactly once. Recurrence advances from the
  prior scheduled local slot, not worker wake time.
- **Missed/retry:** only `skip` and `run_once`, no replay-all, with a bounded
  lookback. Scheduler retries only classified pre-Run setup failures with capped
  backoff; Agent Run retry/recovery rules remain separate. Capacity never gets
  bypassed.
- **Fixed Agents:** Daily Brief summarizes reviewed local knowledge/events.
  Project Watch inspects one exact non-null Project and an application-derived
  change window. Both are read-only, locally scoped, cited, and cannot expand
  Tool authority.

## Proposed sequence

1. 76 - Automation persistence foundation.
2. 77 - Automation API and lifecycle.
3. 78 - Scheduler materialization and claiming.
4. 79 - Restart, recovery, idempotency, and missed-run policy.
5. 80 - Automatic read-only scheduled Agent execution.
6. 81 - Automations UI and local notification inbox.
7. 82 - Daily Brief Agent.
8. 83 - Project Watch Agent.
9. 84 - Automation security and evaluation harness.
10. 85 - Local V1.3 end-to-end acceptance.
11. 86 - Local V1.3 release hardening.

Each checkpoint in `V1_3_AUTOMATION_ROADMAP.md` states its production areas,
migration/API/UI impact, transaction and concurrency invariants, security
acceptance, focused tests, rollback, and dependency. Checkpoint 75 authorizes
none of their implementation.

## Explicit deferrals

Gmail/Calendar/GitHub and all connectors; arbitrary network/external research;
external writes; proposal execution; automatic Approval; authentication and
multi-user; remote/cloud/mobile operation; arbitrary shell/Python/SQL/filesystem/
HTTP/browser/Git execution; import merge/overwrite/remap; encrypted export
redesign; credential storage; arbitrary scheduled goals; and scheduled Curator
proposal creation are deferred to separately reviewed future roadmaps.

## Instruction resolution

`docs/CHECKPOINTS.md` previously called the published V1.2.1 live-provider
hotfix "Checkpoint 75", while the explicit current request assigns Checkpoint
75 to this planning work. The repository instruction order makes the explicit
current-checkpoint request authoritative. The table now records the hotfix as an
unnumbered post-74 patch and reserves 75 for this pending planning checkpoint.
No historical commit or published release identity changed.

The older V1.2 roadmap mentioned connectors and approval-gated writes among
possible V1.3 ideas. The explicit V1.3 boundary is safer and later, so the stable
roadmap now defers them beyond V1.3. V1.2 architecture and behavior are
unchanged.

## Self-audit

- Documentation/planning only: yes.
- Migrations: none.
- Application/frontend/test implementation: none.
- Dependency changes: none.
- Registry/export-version changes: none.
- V1.2.1 production modification: none.
- Connector/external-write implementation: none.
- Proposal execution or automatic Approval authorization: none.
- Every proposed checkpoint has a distinct rollback boundary: yes.
- Roadmap is incremental and dependency ordered: yes.
- Roadmap and threat model share scope, identities, retry, time, concurrency,
  recovery, notification, and authority rules: yes.

## Verification evidence

Focused verification passed: 12 tests in `test_verification_script.py` and
`test_ci_workflow.py`, zero failures, followed by `git diff --check`.

Final `scripts/verify.ps1 -Mode Full` passed in the intended credential-free
test environment:

- pip check, Ruff lint/format, and mypy: passed;
- backend: 938 passed, zero skipped (six warnings);
- frontend: 124 passed across 11 files, zero skipped;
- ESLint, TypeScript, and production Vite build: passed;
- Alembic current/head: `0010_agent_runtime_persistence`;
- Alembic check: no new upgrade operations detected; and
- `git diff --check`: passed.

The first Full attempt exposed that the ignored maintainer `.env` supplies a
live provider key after two credential-absence tests delete only the process
variable; this produced two unrelated provider-path failures. The authoritative
rerun temporarily isolated that exact `.env` without reading or changing its
contents and restored it in `finally`. No secret was displayed or persisted.

Stable identities remain Tool Registry `agent-tools-v1` and Project export
`second-brain-project-export` version 1. Checkpoint 75 was approved by human
review after automated verification succeeded and is complete.
