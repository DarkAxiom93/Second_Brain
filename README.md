# Second Brain

Second Brain is a Python 3.12 project with Foundation configuration, local
PostgreSQL infrastructure, and a minimal FastAPI liveness API.

## Prerequisites

- CPython 3.12
- Git

## Local setup on Windows

Create a project-local virtual environment with a Python 3.12 interpreter, then
install the project and development dependencies into it:

```powershell
& 'C:\path\to\Python312\python.exe' -m venv .venv
& '.\.venv\Scripts\python.exe' -m pip install --upgrade pip
& '.\.venv\Scripts\python.exe' -m pip install -e '.[dev]'
```

Copy `.env.example` to `.env` when local configuration overrides are needed.
The supported environment variables are:

- `APP_NAME`, `APP_ENV`, `APP_HOST`, `APP_PORT`, and `APP_LOG_LEVEL`
- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, and
  `POSTGRES_PORT`
- `DATABASE_URL`

No prefix is required. The checked-in values are development placeholders, not
production credentials. On Windows, commands can invoke the virtual
environment's Python executable directly without activating it.

## Quality checks

```powershell
& '.\.venv\Scripts\python.exe' -m pip check
& '.\.venv\Scripts\python.exe' -m ruff check .
& '.\.venv\Scripts\python.exe' -m ruff format --check .
& '.\.venv\Scripts\python.exe' -m mypy app
& '.\.venv\Scripts\python.exe' -m pytest
```

## Checkpoint 2: local PostgreSQL

Docker Desktop must be installed and running with Linux containers, and Docker
Compose v2 is required. `.env.example` is only a local-development template; no
real `.env` file is committed. Validate the rendered Compose configuration with:

```powershell
docker compose --env-file .env.example config
docker compose --env-file .env.example config --quiet
```

Start only PostgreSQL, inspect its health, view its logs, and stop it safely:

```powershell
docker compose --env-file .env.example up -d --wait db
docker compose --env-file .env.example ps
docker compose --env-file .env.example logs db
docker compose --env-file .env.example stop db
```

Connect with `psql` inside the database container, using its configured
environment values:

```powershell
docker compose --env-file .env.example exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

PostgreSQL is published only on `127.0.0.1`, and its data persists in the named
`postgres_data` Docker volume. The selected image includes pgvector, but the
`vector` extension is intentionally not enabled yet; a future approved migration
will enable it.

To remove stopped containers without deleting database data, use:

```powershell
docker compose --env-file .env.example down
```

Warning: the following command permanently deletes the local named database
volume and its data. Do not run it casually:

```powershell
docker compose --env-file .env.example down -v
```

## Checkpoint 3: FastAPI liveness API

The FastAPI skeleton is implemented, with `GET /health` as its only application
endpoint. It is a process liveness check and does not connect to PostgreSQL. The
database remains a separate Docker service; the API does not run in Docker.

Start the API locally on Windows:

```powershell
& '.\.venv\Scripts\python.exe' -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

While the server is running, use these URLs:

- Health: <http://127.0.0.1:8000/health>
- Interactive OpenAPI documentation: <http://127.0.0.1:8000/docs>
- OpenAPI schema: <http://127.0.0.1:8000/openapi.json>

Call the health endpoint from PowerShell:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Stop the local development server with `Ctrl+C`. Run the test and quality suite
with the commands in [Quality checks](#quality-checks).

## Checkpoint 4: database integration and readiness

The application now has a synchronous SQLAlchemy engine and request-scoped
sessions using Psycopg 3. `GET /health` remains a database-independent liveness
check, while `GET /ready` executes `SELECT 1` and reports whether PostgreSQL is
reachable. The API still runs locally rather than in Docker.

Migrations are explicit developer or deployment actions; they do not run during
application import or startup. The initial migration enables pgvector only. No
projects or memories tables exist yet.

When host port 5432 is occupied, start the database on temporary port 5433 and
set the host-accessible application URL for the current PowerShell session:

```powershell
$env:POSTGRES_PORT = "5433"
docker compose --env-file .env.example up -d --wait db
$env:DATABASE_URL = "postgresql+psycopg://second_brain:change-me@127.0.0.1:5433/second_brain"
```

Apply and inspect migrations explicitly:

```powershell
& '.\.venv\Scripts\python.exe' -m alembic upgrade head
& '.\.venv\Scripts\python.exe' -m alembic current
```

Run the normal unit suite without a test database:

```powershell
Remove-Item Env:TEST_DATABASE_URL -ErrorAction SilentlyContinue
& '.\.venv\Scripts\python.exe' -m pytest
```

Integration tests require the separate database named exactly
`second_brain_test`. Never point `TEST_DATABASE_URL` at `second_brain`,
`postgres`, or another database. `.env.test.example` contains placeholders only;
do not commit a real `.env.test` file.

```powershell
$env:TEST_DATABASE_URL = "postgresql+psycopg://second_brain:change-me@127.0.0.1:5433/second_brain_test"
& '.\.venv\Scripts\python.exe' -m pytest tests/integration
```

## Checkpoint 5: Project and Memory persistence

SQLAlchemy persistence models now define `projects` and `memories`, created by
migration file `0002_create_projects_and_memories.py` with Alembic revision
`0002_projects_memories`. Project names are not unique. A Memory may exist
without a Project, and deleting a Project preserves its memories by setting
`Memory.project_id` to `NULL`.

Both models use application-generated UUIDs, timezone-aware database timestamps,
and SQLAlchemy ORM-managed `updated_at` updates. pgvector remains installed, but
neither model has an embedding or vector column.

Apply and inspect the current migration explicitly:

```powershell
& '.\.venv\Scripts\python.exe' -m alembic upgrade head
& '.\.venv\Scripts\python.exe' -m alembic current
```

Run metadata/unit tests normally, or set the guarded test URL to run the real
PostgreSQL integration suite:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest tests/test_models.py
$env:TEST_DATABASE_URL = "postgresql+psycopg://second_brain:change-me@127.0.0.1:5433/second_brain_test"
& '.\.venv\Scripts\python.exe' -m pytest tests/integration
```

Integration tests accept only the exact database `second_brain_test`. The API
still runs locally, Docker Compose remains database-only, and there are no
Project or Memory API endpoints yet.

## Current scope

Only liveness and database readiness endpoints are implemented. Project and
Memory persistence models exist, but their API schemas, repositories, services,
and CRUD endpoints do not. Authentication, agent workflows, and frontend code
are also not implemented.
