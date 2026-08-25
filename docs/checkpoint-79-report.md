# Checkpoint 79 report - Restart and recovery

Status: **Approved and complete after human review.**

## Outcome

Checkpoint 79 extends the explicit one-tick trigger-only scheduler with bounded
restart reconciliation. PostgreSQL transaction time is authoritative in normal
operation. The tick reconciles durable linked Runs, reclaims only expired
claims, applies the missed-run policy, claims eligible work, and creates or
resolves the exact occurrence-derived Run. FastAPI startup remains inert and
the scheduler never calls Agent planning, execution, provider, Tool, or the
explicit manual Agent recovery operation.

## Restart, fencing, and linked Runs

Expired `claimed` occurrences are selected in stable lease-expiry/UUID order
with `FOR UPDATE SKIP LOCKED`. Reclamation changes the opaque owner, increments
the monotonic generation, and establishes a new bounded lease. An unexpired
lease is never reclaimed; the previous owner/generation cannot renew or link
after reclamation.

Linked occurrences resolve only their exact durable `agent_run_id`. A missing
linked Run becomes `linked_run_missing` with an operator-visible content-free
failure. Nonterminal Runs remain `run_created` and are not recovered or
advanced. Terminal Runs project only a safe completed/failed occurrence
summary. Exact replay and repeated restart never create a replacement Run.
Reserved `daily_brief` and `project_watch` Runs remain inert in `created`.

Run creation and occurrence linking retain the Checkpoint 78 atomic caller
transaction. A failed commit acknowledgement is checked in a fresh transaction:
an exact durable link is accepted; otherwise the same occurrence becomes
`ambiguous_commit_outcome` and is never automatically retried.

## Missed-run and lookback policy

Materialization advances exclusively from canonical scheduled points. It
calculates the latest overdue point and first future point while writing at most
one occurrence, regardless of downtime length.

- `skip` writes one terminal `missed` occurrence for the latest overdue slot,
  creates no Run, and advances to the first future slot.
- `run_once` writes one `due` occurrence for the latest overdue slot and allows
  that same occurrence through the existing `create_only` flow.
- Slots older than the approved seven-day maximum lookback use the bounded safe
  disposition `missed_lookback_bounded`; there is no replay-all or historical
  row expansion. One-time schedules use the same configured policy.

## Retry and capacity policy

The retry classifier is closed to pre-link SQLAlchemy database operational
failures and PostgreSQL serialization/deadlock SQLSTATEs. Validation, scope,
lifecycle, catalog/policy, cancellation, integrity/uniqueness, provider/Tool,
Agent, and ambiguous outcomes are never scheduler-retried.

Failure attempts are bounded by the Automation's approved limit and an absolute
maximum of three. Retry uses the same occurrence, a capped exponential delay,
stable occurrence-derived jitter, and persisted `retry_not_before`. Exhaustion
becomes `setup_retry_exhausted` plus one deduplicated safe notification.
Exact Agent Run capacity rejection returns the same occurrence to durable due
work with a delay and does not increment `attempt_count`. The existing 32-Run,
16-row tick, one-nonterminal-occurrence-per-Automation, and 32 claimed/run-created
occurrence bounds remain intact.

## Verification and failure injection

Focused PostgreSQL verification passed **28 tests, zero skipped**. It covers
Checkpoint 78 transaction rollbacks plus expired/unexpired lease boundaries,
generation fencing, concurrent recovery, bounded `skip` and `run_once`,
seven-day diagnostics, no replay-all, exact Run replay, terminal/nonterminal
linked reconciliation, repeated restart idempotency, retry timing/classification,
capacity deferral, retry exhaustion, forward downtime and backward-clock
behavior, and continued absence of startup scheduling, Steps, and Tool
invocations.

The authoritative `scripts/verify.ps1 -Mode Full` run passed on the final tree:

- pip check, Ruff lint/format, and strict mypy passed;
- backend: **1013 passed, zero skipped** (12 warnings);
- frontend: **124 passed across 11 files, zero skipped**;
- frontend ESLint, TypeScript, Vitest, and production Vite build passed;
- Alembic current and sole head: `0011_automation_persistence`;
- Alembic check: no new upgrade operations detected; and
- `git diff --check`: passed.

Two provider-absence unit tests were made independent of repository-local dotenv
state by running from pytest-owned temporary directories. No `.env` file was
read, exposed, moved, or modified.

Repeated historical migration lifecycle tests had exhausted PostgreSQL dropped-
column slots in the disposable `second_brain_test` database. With explicit human
approval, parsed/live identity and UTF-8 owner metadata were verified, only
`second_brain_test` was force-disconnected, dropped, and recreated, and all
migrations from base through `0011_automation_persistence` succeeded. The
development `second_brain` database, PostgreSQL container, named volume, and
configuration were preserved.

## Stable identities and scope

No migration was added. Alembic remains `0011_automation_persistence`, Tool
Registry remains `agent-tools-v1`, and Project export remains
`second-brain-project-export` version `1`. Checkpoint 80 was not started. All
changes remain unstaged and uncommitted.
