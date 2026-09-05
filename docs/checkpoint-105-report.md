# Checkpoint 105 optional Calendar refresh scheduling decision report

Status: **Approved and complete after human review as a documentation-only
manual-refresh decision. CP106 has not started.**

## Preflight

Preflight passed on clean synchronized `main` at exact approved CP104 commit
`6524bd847353432d4c8dc9abeb3e04d7c9cd3b8f`; `HEAD`, `main`, and
`origin/main` matched. Exact push CI run `33889717967` for that SHA completed
successfully. Development and test database identities were verified as
`127.0.0.1:5433/second_brain` and
`127.0.0.1:5433/second_brain_test`. Alembic current and sole head were
`0016_calendar_event_observations`; `alembic check` was clean. Tool Registry was
`agent-tools-v1`; Project export was `second-brain-project-export` version `1`.

## Recommendation and concrete value

Recommend **A: keep Calendar refresh explicitly manual only**. Local V1.5 is
useful and complete with CP102 bounded manual refresh plus CP103 scoped browsing
and reconciliation. Calendar context naturally changes, and an operator can
forget to refresh, but that is a recoverable freshness risk rather than a
missing workflow: the single local maintainer can explicitly refresh before
using External Context, with the same bounded, visible run result.

Daily or weekly execution would reduce some forgotten refreshes but can also be
stale between occurrences, run when context is not needed, or fail while the
operator is absent. Because the scheduler itself remains operator-started, it
does not guarantee background freshness. No concrete V1.5 workflow was found
that manual refresh cannot reasonably serve, so this modest convenience does
not outweigh a second credential-bearing scheduler lifecycle.

## Existing scheduler architecture comparison

The V1.3 Automation scheduler owns Automation definitions and occurrences that
capture Agent identity, execution mode, scope, and an exact linked `AgentRun`.
Reusing those tables would incorrectly grant Calendar work to Agent Automation,
violate zero `AgentRun`, and blur trigger authority with provider refresh.

The V1.4 connector scheduler is structurally closer. Its code-level primitives
demonstrate safe typed cadence calculation, canonical UTC/IANA occurrences,
unique slots, revision and generation-fenced leases, bounded `skip`/`run_once`,
no replay-all, restart reconciliation, bounded retries/history/notifications,
and an explicit operator-started tick. Those concepts could inform a future
design, but its persistence owns a `ConnectorAccount` and `ConnectorSyncRun`,
and its runner is a connector refresh executor. Calendar persistence instead
owns immutable account/configuration revisions, exact calendar identities, and
CP102 `CalendarSyncRun` evidence semantics. Reusing connector rows would confuse
ownership; widening its tick would create a broader credential-backed network
executor. The existing V1.4 scheduler remains unchanged.

## Credential, lifecycle, concurrency, and recovery implications

Scheduling would require credential-store access at occurrence execution and
closed handling for missing, locked, expired, revoked, rotated, or
reauthorization-required OAuth state. Every occurrence would have to capture and
revalidate exact Calendar account, configuration revision, historical
Project/unassigned scope, and exact allowlist before credential access, before
each request/page commit, and before terminal evidence eligibility. Later
configuration or scope changes could not retrofit an old occurrence.

Manual and scheduled refreshes would need one explicit arbitration rule while
preserving CP102's one-active-run fencing. Unique occurrences, lease generations,
crash/restart idempotency, ambiguous outcomes, and duplicate prevention would be
required. Missed execution would have to remain `skip` or bounded `run_once`,
never replay-all, with deterministic DST behavior. Provider rate limits,
transient failures, capped backoff, and reauthorization states would require
bounded content-free history, notification, and operator recovery. These are
real capability costs, not reusable naming alone.

Omission introduces none of those paths. There is no scheduled credential read,
manual/scheduled race, occurrence, lease, restart recovery, missed run, provider
retry, or new notification lifecycle. CP102 request/resource limits and CP103
complete-observation evidence semantics stay exactly as implemented.

## Persistence, authority, and security

No existing non-Agent scheduler representation safely persists Calendar
scheduling. Automation tables are Agent-authority owned; connector schedule
tables are connector-account/sync owned. A justified future capability would
therefore need a separately reviewed additive Calendar-owned schedule and
occurrence representation bound to exact Calendar configuration/calendar
lineage. CP105 does not authorize that migration or any speculative scaffolding.

There is no migration, schema, dependency, backend, frontend, API, UI, or
production scheduling code change. There is no Calendar schedule persistence,
automatic/background/API-startup refresh, Calendar work through Agent
Automation tables, scheduler-triggered `AgentRun`, new credential authority,
generic provider/network executor, new OAuth scope, Calendar import, or Calendar
write. CP102 manual refresh remains the sole Calendar request trigger; CP103
browsing/reconciliation remains PostgreSQL-only and unchanged.

G01-G13 and G15-G18 require no interpretation change. G14 alone is materially
updated from a conditional scheduling placeholder to executable omission
assertions: schedule model/route/UI/runner/startup absence, unchanged connector
and Automation scheduler inventories, zero Calendar request without explicit
manual refresh, and zero `AgentRun`, import, or protected-domain mutation. The
fixed CP99 scopes, exact lineage/allowlist fencing, untrusted-content boundary,
CP102 bounds, CP103 evidence semantics, full-sync/no-tombstone behavior, export
version, Tool Registry, and all zero-authority guarantees remain intact. No new
threat ID is needed.

## Changed paths and verification

Exact changed paths:

- `docs/ARCHITECTURE.md`
- `docs/CHECKPOINTS.md`
- `docs/ROADMAP.md`
- `docs/V1_5_CALENDAR_ROADMAP.md`
- `docs/V1_5_CALENDAR_THREAT_MODEL.md`
- `docs/checkpoint-105-report.md`

Focused verification passed **66 backend tests** and **6 frontend tests**, zero
failed and zero skipped. The backend selection covered Calendar catalog, sync,
account API, persistence/reconciliation, the existing Automation scheduler, and
the existing connector refresh scheduler. The frontend selection covered the
Calendar External Context browser.

The first Full attempt passed database identities, dependency integrity, Ruff
lint/format, and strict mypy, then reported **1,286 passed, 1 failed, 4 setup
errors, 0 skipped**. The setup errors were test-state contamination from the
preceding focused Calendar selection: a retained test-only Calendar account
revision referenced a test Project that the Answers fixture later attempted to
delete. The independent failure was the known sandbox-context Windows
Credential Manager availability lock. Neither involved product or documentation
behavior.

With explicit human approval, the existing verifier immediately re-proved the
live targets as `127.0.0.1:5433/second_brain` and
`127.0.0.1:5433/second_brain_test`. A maintenance connection to only `postgres`
confirmed the exact two database names. The reset then performed these exact
actions against container `second-brain-db-1`:

1. `SELECT pg_terminate_backend(pid)` filtered exactly to
   `datname = 'second_brain_test'` (zero active rows);
2. `dropdb -U second_brain --maintenance-db=postgres --if-exists
   second_brain_test`;
3. `createdb -U second_brain --maintenance-db=postgres --owner=second_brain
   --encoding=UTF8 --template=template0 second_brain_test`; and
4. Alembic `upgrade head` with `DATABASE_URL` set exactly to
   `127.0.0.1:5433/second_brain_test`.

Post-reset parsed and live identities again passed for the exact development and
test targets. Both databases reported current and sole head
`0016_calendar_event_observations`, and `alembic check` reported no new upgrade
operations for each. The development database was never a destructive command
target and was not dropped, recreated, downgraded, migration-reset, truncated,
or otherwise modified. The PostgreSQL container was not restarted, deleted, or
recreated: exact container ID
`62904b6be659aa32b71dcda4d6e6af617426778ffd905c7809c6fc6979fac222` remained
running with start time `2026-09-03T05:13:24.059201302Z`. Named volume
`second-brain_postgres_data` remained mounted at `/var/lib/postgresql/data` and
was not deleted or recreated. `.env` was not modified.

The authoritative Full rerun in the normal Windows host context passed **1,291
backend tests** and **145 frontend tests**, zero failed and zero skipped.
Database identities, `pip check`, Ruff lint/format over 473 files, strict mypy
over 203 production files, Alembic current/head/check, frontend ESLint,
TypeScript, Vitest, production build, and `git diff --check` all passed. Tool
Registry remained `agent-tools-v1`; Project export remained
`second-brain-project-export` version `1`.

No dependency or schema change was made. No Calendar scheduling code was
implemented; zero Calendar write, import, `AgentRun`, Agent/Automation Calendar
authority, OAuth/provider authority widening, or CP106 work occurred. CP105 is
approved and complete after human review; CP106 remains not started.
