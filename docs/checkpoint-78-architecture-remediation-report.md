# Pre-Checkpoint 78 architecture remediation report

Status: **Implemented and pending human review. Checkpoint 78 is not implemented.**

## Blocker and resolution

Checkpoint 78's fail-closed gate found that `daily_brief` and `project_watch`
were valid Automation configuration identities but had no implemented fixed
Agent definitions. The generic manual Run path accepts other stable Agent kinds,
and an unrecognized kind would otherwise receive the generic planning Tool
inventory. Persisting either future Automation identity without a reservation
gate could therefore grant unintended later planning authority.

The code-owned Automation catalog now distinguishes three facts:

- the complete reserved Agent-kind families, covering every version;
- the exact identities valid only for planned Automation configuration; and
- the exact implemented Automation Agent identities, currently an empty set.

Public manual Run creation rejects every still-reserved family/version with the
safe `agent definition unsupported` response. Unrelated generic manual kinds,
Research version 1, and Memory Curator version 1 retain their existing behavior.
The transaction-neutral Run creation service remains unchanged, so a future
Checkpoint 78 scheduler can create and atomically link an exact catalog identity
inside its caller-owned transaction.

Planning checks the persisted identity immediately after locking the Run and
before replay handling, state/revision mutation, Tool inventory construction,
or provider work. Execution applies the same check before terminal/replay,
state, plan, Tool, or provider handling. Explicit recovery and the per-step
reservation boundary repeat the check as defense in depth. A scheduler-created
Run therefore remains inert in `created`.

An exact version may become plannable only through a later approved Agent
checkpoint that adds it explicitly to the implemented-identity set and supplies
its dedicated code-owned definition and Tool allowlist. Adding a catalog entry
alone does not grant authority, and unknown family versions remain reserved.

## Boundary

This remediation adds no scheduler, worker, occurrence materialization, lease,
Agent definition, Tool, authority, provider behavior, automatic action,
connector, migration, or export change. Alembic remains
`0011_automation_persistence`, Tool Registry remains `agent-tools-v1`, Project
export remains `second-brain-project-export` version 1, and Checkpoints 78 and
79 remain unimplemented.

## Verification evidence

Focused catalog and PostgreSQL/API tests passed: **14 passed, zero skipped**.
The authoritative `scripts/verify.ps1 -Mode Full` run then passed with the
ignored maintainer `.env` temporarily moved aside and restored in `finally`:

- pip check, Ruff lint/format, and strict mypy passed;
- backend: **985 passed, zero skipped** (11 pre-existing deprecation/schema
  warnings);
- frontend: **124 passed across 11 files, zero skipped**;
- frontend ESLint, TypeScript, and production Vite build passed;
- Alembic current and sole head: `0011_automation_persistence`;
- Alembic check: no new upgrade operations detected; and
- `git diff --check`: passed.

The Tool Registry identity remains `agent-tools-v1`, and Project export remains
`second-brain-project-export` version 1. No migration was added.
