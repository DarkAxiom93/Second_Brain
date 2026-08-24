# Checkpoint 76 report - Automation persistence foundation

Status: **Approved and complete after human review.**

## Outcome

Checkpoint 76 adds only the inert Local V1.3 Automation persistence foundation.
The additive `0011_automation_persistence` revision follows
`0010_agent_runtime_persistence` and creates `automations`,
`automation_occurrences`, and `automation_notifications`. No Automation API,
lifecycle service, schedule calculator, scheduler, worker, UI, Agent execution,
provider call, Tool behavior, or authority change was added. Checkpoint 77 was
not started.

## Persistence contract

- `Automation` stores a bounded label; fixed Automation and Agent identities;
  exact nullable Project scope; closed lifecycle, execution mode, schedule kind,
  DST, and missed-run values; typed local schedule fields; bounded retry,
  capacity, and recurrence configuration; monotonic revisions; UTC next
  occurrence; and lifecycle timestamps.
- `AutomationOccurrence` stores the immutable schedule slot and local/UTC
  identity, captured definition and exact nullable scope identity, closed state,
  monotonic revision/counters, optional single Agent Run, safe disposition/error
  codes, retry timing, lifecycle timestamps, and fenced lease fields.
- `AutomationNotification` stores only bounded safe local-inbox metadata, closed
  event/severity values, optional occurrence/Run links, read/creation times, and
  a unique deduplication key.

The schema contains no cron, prompt template, Tool list, URL, path, SQL,
executable expression, arbitrary configuration object, or authority field.

## Constraints, indexes, and deletion

Database checks close enum values, require nonnegative revisions, generations,
and counters, bound retry/capacity/recurrence values, enforce schedule-owned
field shapes, pair lifecycle and terminal timestamps, pair lease owner/expiry,
and bound safe text. The primary duplicate barrier is
`UNIQUE (automation_id, schedule_revision, scheduled_at)`. Canonical occurrence
keys, linked Agent Runs, and notification deduplication keys are also unique.
A composite notification FK prevents an occurrence from being referenced under
another Automation.

Indexes cover deterministic due Automation selection, Project/history lookup,
due/retry occurrence selection, expired-lease lookup, and unread/history inbox
queries. Project, Automation, occurrence, and Agent Run FKs use `RESTRICT` so
audit-sensitive Automation state is not cascaded away. Nullable Project scope
continues to mean exact unassigned scope, never all Projects.

## Repository and export behavior

The new repository exposes create/get and deterministic occurrence/notification
insert/list primitives. It flushes for durable identities but never commits or
rolls back; callers own the complete transaction. Focused rollback coverage
proves no partial persistence remains. The repositories perform no provider,
Tool, Agent, scheduling, or lifecycle side effect.

Project export identity remains `second-brain-project-export` version `1`.
Its file set and entity contract are unchanged and explicitly exclude all
Automation, occurrence, notification, and Agent Runtime state. Import remains
compatible with version-1 bundles from `0009_memory_expiration`,
`0010_agent_runtime_persistence`, and the new current target revision.
Tool Registry identity remains `agent-tools-v1` and its inventory is unchanged.

## Verification evidence

The authoritative credential-free `scripts/verify.ps1 -Mode Full` run passed:

- pip check, Ruff lint/format, and mypy passed;
- backend: 953 passed, zero skipped (six pre-existing deprecation warnings);
- frontend: 124 passed across 11 files, zero skipped;
- ESLint, TypeScript, and the Vite production build passed;
- Alembic current and sole head: `0011_automation_persistence`;
- Alembic check: no new upgrade operations detected; and
- `git diff --check`: passed.

The verified `second_brain_test` suite exercised upgrade, test-only downgrade
to `0010`, re-upgrade to `0011`, all three tables and relationships, closed
checks, counters, timestamps, indexes, FK behavior, occurrence uniqueness,
notification deduplication, caller-owned rollback, and export exclusion. The
development database received only the requested additive upgrade to `0011`;
no development downgrade or destructive database command ran.

As in Checkpoint 75, the ignored maintainer `.env` activates live provider paths
in two credential-absence tests. The authoritative run temporarily moved that
exact file aside without reading or changing it and restored it in `finally`.
No secret was displayed or persisted.

## Security acceptance

The persistence foundation addresses A01-A03, A07-A08, A12-A14, and A17-A18
through unique occurrence identity, captured revisions/definition/scope,
lease-generation fields, atomic caller-owned transactions, strict FKs and
closed safe metadata. It implements none of the later scheduler behaviors.
There is no new Agent authority, automatic planning/execution, scheduled
Curator, proposal execution, automatic Approval, connector, external research
or write, or arbitrary shell/Python/SQL/filesystem/browser/network authority.

Checkpoint 76 was approved by human review and is complete.
