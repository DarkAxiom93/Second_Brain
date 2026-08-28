# Checkpoint 86 report - Local V1.3 release hardening

Status: **Approved and complete after human review; subsequently published as
`v1.3.0`.**

## Base and preflight

- Exact base and approved Checkpoint 85 commit:
  `82329189dfc05dab96008c4d74187966d5b8b072`.
- Preflight branch: `main`; working tree clean; `HEAD` and `origin/main` equal;
  `origin/main...main` was `0 0`.
- Exact Checkpoint 85 push CI: **Second Brain CI** run `33104265544`, event
  `push`, completed successfully for the exact base SHA from
  `2026-08-27T18:35:50Z` to `2026-08-27T18:38:24Z`.
- Candidate identity: `v1.3.0`, title **Second Brain Local V1.3**. At Checkpoint
  86 completion, no tag, GitHub Release, PR, push, or publication action had
  been created or executed.

## Release inventory and stable identities

The production capability inventory is exactly Automation lifecycle/API/UI;
deterministic one-time/daily/weekly schedules; scheduler materialization,
claiming, and recovery; default `create_only`; explicit
`automatic_read_only`; local notification inbox; Daily Brief v1; Project Watch
v1; A01-A18 security/evaluation harness; and V1.3 E2E acceptance.

Implemented Automation Agent identities remain exactly
`("daily_brief", "1")` and `("project_watch", "1")`. Research and Memory
Curator remain unschedulable. The Tool Registry is `agent-tools-v1`. Project
export is `second-brain-project-export` version `1`.

Alembic live current and sole head are `0011_automation_persistence`.
`alembic check` reports no new upgrade operations. No migration was created.

## Clean installation and dependency security

A Git archive of the exact base SHA was expanded into a disposable clean copy.
It used no working-tree `.venv`, `node_modules`, cache directory, or untracked
file. Python 3.12.10 created a fresh virtual environment; `.[dev]` installed,
`pip check` reported no broken requirements, and `import app; import app.main`
passed. The environment bootstrap pip 25.0.1 initially reported advisories;
upgrading only disposable environment tooling to pip 26.2.1 removed them.
`pip-audit --local --skip-editable` then found no known vulnerabilities; only
the editable local project distribution was skipped, while its installed
dependencies were audited.

Node 24.16.0 and npm 11.13.0 performed fresh locked `npm ci` (210 packages),
`npm audit --audit-level=high` found zero vulnerabilities, ESLint and TypeScript
passed, and the Vite production build transformed 85 modules successfully.
No dependency or lockfile changed.

## Privacy and tracked-content audit

The 448 tracked paths contain only the intended `.env.example`,
`.env.test.example`, and `frontend/.env.example` configuration examples (plus
the ordinary Alembic module `migrations/env.py`). No sensitive filenames,
private-key markers, high-signal live API keys/tokens, database dumps,
`.sbexport` bundles, logs, temporary files, virtual environments, dependency
trees, build output, or coverage/cache output are tracked.

Public schemas and the V1 export remain closed against raw provider/Tool
payloads, hidden reasoning/private prompts, credentials, secrets, and private
runtime state. No `.env` file was printed, modified, or added.

## Project export compatibility

A real read-only export of one existing development Project at revision
`0011_automation_persistence` succeeded. The archive identity was
`second-brain-project-export` version `1` and contained exactly the ten approved
entries: manifest, Project, Memories, Memory embeddings, Sources, Memory-Source
links, Source documents/chunks, extraction runs, and Memory proposals.

Archive inspection found no Automation/occurrence/notification, Agent
Run/Step/Tool invocation/event, Approval Request, prompt, provider, secret,
reasoning, or runtime entry. Read-only validation against the separately
identity-verified `second_brain_test` target succeeded. Existing policy still
rejects unsupported revisions, malformed archives, conflicts, merge,
overwrite, reuse, remap, repair, partial import, and unvalidated execution.

## Stopped-service backup and restart drill

Ports 5173 and 8000 had no listeners before the drill. The development and
test database identities were verified both by parsed URL and live query. The
exact development database reported
`second_brain|second_brain|16.14 (Debian 16.14-1.pgdg12+1)`.

A read-only PostgreSQL custom-format backup was created with the configured
`second_brain` role. `pg_restore --list` enumerated 158 TOC entries, including
the revision table, Project/Memory data, Agent Runtime, Approval, and all three
Automation tables. No restore was executed. The container copy and local copy
were removed with the disposable audit directory.

`scripts/dev-down.ps1` stopped only PostgreSQL and preserved container
`second-brain-db-1` plus named volume `second-brain_postgres_data`.
`scripts/dev-up.ps1` restarted the same service healthy on
`127.0.0.1:5433`. Migration current/head/check remained correct. FastAPI
health returned `ok`, readiness returned `ready`, and the Vite proxy returned
the same results. The exact temporary API and Vite PIDs were stopped and ports
5173/8000 closed afterward.

The dedicated scheduler module and exact development-database guard started in
a separate process without invoking a tick. This proved command/process startup
without intentionally materializing development Automations. The scheduler is
not Uvicorn startup behavior.

The runbook backup example incorrectly used a nonexistent `postgres` role; the
drill failed safely before backup, then used the configured `second_brain` role.
The documentation-only correction is included in this checkpoint.

After the disposable clean-install directory temporarily exhausted host disk
space, Docker Desktop became unavailable and the first Full-verification attempt
stopped at database identity verification with a connection timeout. No test or
migration ran in that attempt. During the operator's Docker Desktop recovery,
the original container object disappeared but `second-brain_postgres_data`
remained. Compose recreated only the `second-brain-db-1` wrapper on that exact
named volume. Live identity then reconfirmed `second_brain`, revision `0011`,
and two retained Project rows before the successful Full rerun. No database or
volume was deleted, recreated, restored, or downgraded; the current container is
healthy. This environmental interruption is recorded rather than hidden.

## Durability, recovery, and deferred scope

Accepted CP84/CP85 evidence confirms stopping the scheduler is safe; committed
Automations, occurrences, Runs, and notifications remain durable; restart uses
only committed PostgreSQL state; there is no replay-all; stale leases are
generation-fenced; linked Runs are reused and never replaced; `create_only`
remains default; `automatic_read_only` remains opt-in; and no lock spans
provider/Tool latency.

The exact deferred inventory is authentication or multi-user isolation;
remote/cloud operation; connector integrations; Gmail/Calendar/GitHub
automation; arbitrary external/network research; arbitrary user-defined Agent
prompts; arbitrary Tools; shell/Python/SQL/filesystem/browser execution;
automatic writes to reviewed knowledge; Memory Curator scheduling; proposal
execution; automatic Approval; external notification delivery including
webhook/email/push/OS notifications; automatic history deletion; import
merge/overwrite/remap; and encrypted export/credential storage. Stable docs do
not claim these capabilities.

## Focused and Full verification

- A01-A18 manifest/adversarial focused gate: **54 passed**, zero skipped.
- CP85 joined Daily Brief/Project Watch E2E: **2 passed**, zero skipped.
- Protected-domain complete-row mutation proof: **2 parametrized cases
  passed**, zero skipped.
- Focused Automation frontend: **4 passed**, zero skipped.
- Full dependency and `pip check`: pass.
- Ruff lint/format: pass; strict mypy: pass over **157 source files**.
- Full backend: **1,092 passed**, zero skipped (10 deprecation warnings).
- Alembic current/head: `0011_automation_persistence`; check: no new upgrade
  operations.
- Full frontend: **128 passed across 12 files**, zero skipped; ESLint,
  TypeScript, and the 85-module production Vite build passed.
- `git diff --check`: pass.

## Boundary, cleanup, and recommendation

Checkpoint 86 changes documentation and release evidence only. It makes no
production, schema, migration, dependency, lockfile, CI, Docker, API, frontend,
Tool, registry, export-format, or authority change. PostgreSQL container and
volume are preserved. The development database was not downgraded, restored,
deleted, recreated, or otherwise destructively modified. No scheduler tick was
run against it.

All disposable clean-install, dependency-audit, backup, export, and log
artifacts were removed. All temporary API/frontend processes were stopped.
The exact changed paths are `README.md`, `docs/ARCHITECTURE.md`,
`docs/CHECKPOINTS.md`, `docs/KNOWN_LIMITATIONS.md`,
`docs/LOCAL_V1_RUNBOOK.md`, `docs/ROADMAP.md`,
`docs/V1_3_AUTOMATION_ROADMAP.md`,
`docs/V1_3_AUTOMATION_THREAT_MODEL.md`,
`docs/LOCAL_V1_3_RELEASE_NOTES.md`, and `docs/checkpoint-86-report.md`.
The exact documentation diff is 10 paths: eight modified files with 87
insertions and 44 deletions, plus two new files with 291 lines, for 378
insertions and 44 deletions overall.

Checkpoint 86 is approved and complete after human review. Local V1.3 was
subsequently published as `v1.3.0` with title **Second Brain Local V1.3** from
exact release commit `f79d556cb8d99961aa081464ef151ef1037fe87a`. V1.2.1
remains intact as the documented recovery release, and no V1.4 work has begun.
