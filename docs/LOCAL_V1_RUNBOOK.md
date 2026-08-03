# Local V1 runbook

This runbook is the supported Windows maintainer path for the local Second
Brain V1. Run commands from the repository root in PowerShell. The backend is
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
`0009_memory_expiration`, and `alembic check` must report no upgrade operations.
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
Search, Answers, and Settings. Provider-backed semantic/hybrid search,
proposal generation, and successful answered responses require configured
provider credentials; deterministic automated tests cover those success paths
when credentials are absent.

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
