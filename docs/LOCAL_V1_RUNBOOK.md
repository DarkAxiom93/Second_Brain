# Local V1.3 runbook

This runbook is the supported Windows maintainer path for the Local V1.3
release candidate. Published `v1.2.1` remains the recovery release until a
separate publication approval creates `v1.3.0`.
Run commands from the repository root in PowerShell. The backend is
local FastAPI, the frontend is local Vite, and PostgreSQL 16 with pgvector runs
in Docker Compose. Nothing here deploys to a network service.

## Prerequisites and dependency setup

- CPython 3.12
- Node.js 22.12 or newer and npm 10 or newer
- Docker Desktop using Linux containers, with Docker Compose v2
- Git and Windows PowerShell 5.1 or newer

Create the repository virtual environment and install the declared backend and
development dependencies. Do not place credentials in the repository.

```powershell
& 'C:\path\to\Python312\python.exe' -m venv .venv
& '.\.venv\Scripts\python.exe' -m pip install -e '.[dev]'
& '.\.venv\Scripts\python.exe' -m pip check
.\scripts\frontend-setup.ps1
```

`frontend-setup.ps1` runs locked `npm ci` in `frontend/` and never installs a
global package. Stop Vite before running it: Windows otherwise may hold the
Rolldown native binary open and `npm ci` will fail with `EPERM ... unlink`.

## Start the database and verify migrations

```powershell
.\scripts\dev-up.ps1
.\scripts\verify-databases.ps1
& '.\.venv\Scripts\python.exe' -m alembic current
& '.\.venv\Scripts\python.exe' -m alembic heads
& '.\.venv\Scripts\python.exe' -m alembic check
```

The parsed and live development identity must both be
`127.0.0.1:5433/second_brain`; the separate test database must be
`second_brain_test`. `alembic current` and the sole head must be
`0011_automation_persistence`, and `alembic check` must report no upgrade operations.
Never downgrade the development database.

## Start FastAPI and Vite

Open two additional PowerShell terminals and run:

```powershell
.\scripts\start-api.ps1
```

```powershell
.\scripts\frontend-dev.ps1
```

Open <http://127.0.0.1:5173>. Confirm the Vite proxy reaches both services:

```powershell
Invoke-RestMethod http://127.0.0.1:5173/api/health
Invoke-RestMethod http://127.0.0.1:5173/api/ready
```

The top-level screens are Dashboard, Projects, Sources, Proposals, Memories,
Search, Answers, Agent Runs, Automations, Notifications, and Settings. Provider-backed semantic/hybrid search,
proposal generation, and successful answered responses require configured
provider credentials; deterministic automated tests cover those success paths
when credentials are absent.

Search uses the additive explained-search endpoint and displays deterministic
channel ranks and signals as ordering aids, never as confidence or certainty.
Lexical explained search requires no provider. Semantic and hybrid modes fail
safely when no provider is configured and never retry automatically.

Run one bounded scheduler tick only when due work should be processed:

```powershell
.\scripts\run-automation-scheduler.ps1
```

The scheduler is a dedicated operator process, not Uvicorn startup behavior.
Stopping it is safe: committed Automations, occurrences, Runs, and notifications
remain durable in PostgreSQL. Restart derives work only from committed state,
reclaims only expired generation-fenced leases, and reuses linked Runs. There is
no replay-all recovery. `create_only` is the default; `automatic_read_only` is
explicit opt-in. No database lock spans provider or Tool latency.

## Full verification

Keep PostgreSQL running, make sure the separate test database is reachable,
and run:

```powershell
.\scripts\verify.ps1 -Mode Full
```

Full verification checks database identities, `pip check`, Ruff lint and
format, mypy, the complete zero-skip pytest suite, Alembic current/heads/check,
frontend ESLint/TypeScript/Vitest/build, and `git diff --check`. Quick mode and
`-SkipDatabase` are not release approval.

## Diagnostics and maintenance

These commands are read-only and do not resolve providers:

```powershell
.\scripts\diagnose-system.ps1
.\scripts\diagnose-system.ps1 -ApiBaseUrl http://127.0.0.1:8000
.\scripts\audit-memory-maintenance.ps1 -DetailLimit 100
.\scripts\evaluate-retrieval.ps1 -BaselineCheck
```

Settings exposes the safe aggregate forms of diagnostics and maintenance. It
does not migrate, repair, embed, or otherwise mutate data.

## Project export and controlled import

Bundles contain private application data and are not encrypted. Store them
securely and never commit them.

```powershell
.\scripts\export-project.ps1 -ProjectId <uuid> -OutputPath C:\backup\project.sbexport
.\scripts\import-project.ps1 -BundlePath C:\backup\project.sbexport
```

Validation is read-only. Import execution is conflict-free only and requires
the exact manifest Project UUID:

```powershell
.\scripts\import-project.ps1 -BundlePath C:\backup\project.sbexport `
  -Execute -ExpectedProjectId <uuid>
```

Do not execute an import against a development database that already contains
any bundle identity. There is no merge, overwrite, remap, repair, or partial
import. See [PROJECT_EXPORT_FORMAT.md](PROJECT_EXPORT_FORMAT.md).

Format version 1 accepts source bundles produced at
`0009_memory_expiration`, `0010_agent_runtime_persistence`,
`0011_automation_persistence`, `0012_connector_persistence`,
`0013_external_item_imports`, or `0014_connector_refresh_schedules`. Current
export and import targets require `0014_connector_refresh_schedules`. Project
bundles exclude Agent Runs, Steps, Tool invocations, Agent events, Approval
Requests, connector accounts/sync runs/items/import provenance/schedules/
occurrences, credential references, provider payloads, hidden reasoning, and
other private runtime state. Imported ordinary Source/SourceDocument records
retain the existing version-1 semantics only.

## Full database backup

Project bundles are not complete backups because Agent and Approval state is
excluded. For a complete local backup, use PostgreSQL custom format and treat
the result as sensitive. Create the destination directory first:

```powershell
docker compose --env-file .env.example exec -T db `
  pg_dump -U second_brain -d second_brain -Fc -f /tmp/second-brain.dump
docker compose --env-file .env.example cp db:/tmp/second-brain.dump C:\backup\second-brain.dump
docker compose --env-file .env.example exec -T db `
  pg_restore --list /tmp/second-brain.dump
docker compose --env-file .env.example exec -T db `
  rm -f /tmp/second-brain.dump
```

Verify the database name in every command. Do not restore over the development
database, recreate it, or delete its volume during routine verification. A
restore is destructive and requires separate approval, an isolated target
database, exact target-identity verification, and `pg_restore --list` before
execution.

## Safe shutdown

Stop Vite with `Ctrl+C`, then FastAPI with `Ctrl+C`, then stop PostgreSQL:

```powershell
.\scripts\dev-down.ps1
```

Confirm ports are closed and the named volume remains:

```powershell
Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
  Where-Object LocalPort -in 5173,8000,5433
docker volume ls --format '{{.Name}}' | Select-String '^second-brain_postgres_data$'
```

`dev-down.ps1` uses `docker compose stop db`; it preserves the container and
volume. Never use `docker compose down -v`.

## Recovery

Local V1.2.1 `v1.2.1` at
`04e9db33dc0de7529b1599871c58cace6ed9f9e2` is the published recovery release.
It uses revision `0010_agent_runtime_persistence`,
but recovery still belongs in a separate checkout with a verified backup and an
identity-checked database. Never downgrade the development database. Preserve
the PostgreSQL container and `second-brain_postgres_data` named volume. Version
1 Project import remains validation-first and atomic, with no merge, overwrite,
remap, repair, or partial-import behavior.

## Troubleshooting

- Docker unavailable or unhealthy: start Docker Desktop with Linux containers,
  rerun `dev-up.ps1`, then inspect `docker compose --env-file .env.example ps`
  and `logs db`. Do not recreate the database or delete its volume.
- Port already in use: inspect the listener with
  `Get-NetTCPConnection -State Listen -LocalPort <port>` and its owning process.
  Stop only a process confirmed to belong to this repository.
- `npm ci` reports `EPERM` for a native `.node` file: stop Vite, confirm port
  5173 is closed, then rerun `frontend-setup.ps1`.
- Pytest temporary-directory access failures: use `verify.ps1`; it creates one
  GUID-named `second-brain-pytest-*` directory and cleans only that exact path.
  Do not delete shared `pytest-of-*` roots.
- A PowerShell child appears quiet: the verifier redirects and drains child
  handles deliberately. Wait for its real exit code; do not pipe verifier
  stages, inherit outer handles, sleep/retry, or suppress stderr.
- Test-database column-slot exhaustion commonly appears when repeated migration
  lifecycle runs leave PostgreSQL unable to add another column even after old
  columns were dropped; related exhaustion symptoms can also include migration
  failures, lingering sessions, or inability to create temporary schema
  objects. Verify `TEST_DATABASE_URL` and live identity are exactly
  `second_brain_test`, close stale test processes, and rerun once. Recreating or
  dropping the test database requires separate explicit human approval; never
  substitute or touch `second_brain`.
