# Checkpoint 78 report - Scheduler materialization and claiming

Status: **Approved and complete after human review.**

## Outcome and command

Checkpoint 78 adds the first bounded trigger-only local scheduler foundation.
The only operator entry point is:

```powershell
.\scripts\run-automation-scheduler.ps1
```

It runs one bounded tick and stops. FastAPI startup and request handling do not
import or invoke the runner. There is no polling loop, frontend trigger,
planning, execution, provider or Tool call, Agent definition, proposal action,
Approval action, connector, or external access.

## Transactions and locking

One aware UTC instant is captured for the tick. Materialization locks at most
16 enabled due Automations in `(next_occurrence_at, id)` order with PostgreSQL
`FOR UPDATE SKIP LOCKED`. It creates one canonical captured occurrence and
advances `next_occurrence_at` from the prior scheduled local slot. Insert and
advance share the caller transaction. The existing unique
`(automation_id, schedule_revision, scheduled_at)` constraint remains the
durable race barrier; a conflict resolves the existing occurrence. A correlated
nonterminal-occurrence guard prevents a second active occurrence for one
Automation while still permitting exact same-slot resolution.

Claiming is deterministic by `(scheduled_at, id)`, bounded to 16, restricted to
exact enabled/revision-matching `create_only` occurrences, and uses
`FOR UPDATE SKIP LOCKED`. A dedicated transaction advisory lock serializes the
maximum of 32 claimed/run-created occurrences. Each claim atomically moves
`due -> claimed`, assigns an opaque UUID owner, increments lease generation,
and records claim, renewal, and expiry timestamps.

Renewal and Run linking lock Automation before occurrence and validate exact
owner, generation, unexpired lease, claimed state, Automation lifecycle and
revision, schedule revision, captured definition identity, execution mode, and
exact nullable Project scope. A stale owner cannot mutate or link work.

## Run creation and authority

The Run key is derived only from the immutable occurrence UUID and canonical
occurrence key. The existing transaction-neutral Agent Run service resolves
exact replay before its PostgreSQL-serialized 32-Run capacity check. Run
creation, sequence-zero event creation, occurrence link, and transition to
`run_created` share one caller-owned transaction. Existing unique constraints
enforce one Run per occurrence and one occurrence per Run.

Only exact schedulable catalog identities in `create_only` may link. Project
existence and exact nullable scope are revalidated. `automatic_read_only`
occurrences remain durable and unclaimed. Internally created `daily_brief` and
`project_watch` Runs remain inert in `created`; their family reservation still
blocks public creation, planning, execution, recovery, provider access, Tool
inventory, and Tool invocation.

Capacity rejection rolls back only the link transaction and leaves the claimed
occurrence durable under its lease. Retry, expired-lease reclaim, missed-run
policy, restart reconciliation, and catch-up are deliberately deferred to
Checkpoint 79.

## Failure boundaries and verification

Test-only code-owned hooks cover occurrence insert, next-slot advance, claim
state, lease generation, Run creation, and occurrence/Run link. Injected failure
rolls back the whole applicable transaction, proving no advanced schedule
without occurrence, duplicate occurrence or Run, linked occurrence without its
Run, or stale-owner commit.

Focused PostgreSQL and reservation tests passed: **32 passed, zero skipped**.
They cover lifecycle/due filtering, deterministic bounds, concurrent
materializers and claimers, `SKIP LOCKED`, uniqueness resolution, atomic
rollback, owner/generation/expiry and lifecycle fencing, automatic-mode
non-execution, Run replay/concurrency, the 32-Run cap, inert reserved Runs, zero
Steps/Tool invocations, and no API-startup side effect.

The authoritative `scripts/verify.ps1 -Mode Full` run passed:

- pip check, Ruff lint/format, and strict mypy passed;
- backend: **1003 passed, zero skipped** (12 pre-existing warnings);
- frontend: **124 passed across 11 files, zero skipped**;
- frontend ESLint, TypeScript, and production Vite build passed;
- Alembic current and sole head: `0011_automation_persistence`;
- Alembic check: no new upgrade operations detected; and
- `git diff --check`: passed.

The ignored maintainer `.env` was temporarily moved aside without being read
and restored in `finally` for authoritative provider-absence tests.

## Stable identities and deferred scope

No migration was added. Alembic remains `0011_automation_persistence`, Tool
Registry remains `agent-tools-v1`, and Project export remains
`second-brain-project-export` version 1. Checkpoint 79 has not started.
