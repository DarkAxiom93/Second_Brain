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

## Checkpoint 6: Project API

The locally run API now supports `POST /projects` and `GET /projects`. Project
names are trimmed at their edges, must contain at least one character, and may
not exceed 200 characters. Internal whitespace and letter casing are preserved,
the description is optional, and duplicate names are allowed.

Create a Project from PowerShell:

```powershell
$body = @{
    name = "Pure Axiom"
    description = "Interactive mathematics platform"
} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/projects -ContentType application/json -Body $body
```

List Projects as a bare JSON array, optionally using the validated pagination
parameters (`limit` defaults to 50 and accepts 1 through 100; `offset` defaults
to 0 and must be nonnegative):

```powershell
Invoke-RestMethod http://127.0.0.1:8000/projects
Invoke-RestMethod 'http://127.0.0.1:8000/projects?limit=25&offset=50'
```

Repository functions use an existing SQLAlchemy session, apply pagination in
SQL, and never commit. The API owns the single write transaction for Project
creation. Database errors produce a generic HTTP 503 response without exposing
connection details.

Checkpoint 6 required no schema change or migration. Docker Compose remains
database-only and the API continues to run locally. There is no Memory API,
Project update endpoint, or Project delete endpoint yet.

## Checkpoint 7: Memory creation API

The API supports `POST /memories` for creating an unassigned Memory or one
associated with an existing Project. Content is trimmed and must not be blank.
An optional source is also trimmed, must not be blank when provided, and is
limited to 100 characters.

```powershell
$body = @{ content = "A useful fact"; source = "notes" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/memories -ContentType application/json -Body $body
```

To associate a Memory, include a Project UUID as `project_id`. Unknown projects
return HTTP 404. Database failures return a generic HTTP 503 response. The
Memory repository does not commit; the route owns its single successful commit.
There is no Memory listing, update, or deletion endpoint.

## Checkpoint 8: Memory retrieval API

The API now supports `GET /memories` and `GET /memories/{memory_id}`. Memory
listings are returned as a bare JSON array ordered by newest creation time and
then UUID. Pagination uses `limit` (default 50, range 1 through 100) and
nonnegative `offset`; an optional `project_id` UUID filters the list to assigned
memories for that Project. Unknown Project filters return an empty array.

```powershell
Invoke-RestMethod http://127.0.0.1:8000/memories
Invoke-RestMethod 'http://127.0.0.1:8000/memories?project_id=<project-uuid>&limit=25&offset=0'
Invoke-RestMethod http://127.0.0.1:8000/memories/<memory-uuid>
```

An unknown Memory UUID returns HTTP 404. Database failures return a generic HTTP
503 response. Checkpoint 8 adds no migration, search, update, or delete behavior.

## Current scope

Liveness, database readiness, Project creation/listing, and Memory creation and
retrieval are implemented. Checkpoint 9 adds normalized `sources` persistence
and association-object `memory_sources` links while retaining the legacy
`memories.source` string. Sources have no API endpoints yet. Apply the schema
with `python -m alembic upgrade head`; the current revision is `0003_sources`.
Project updates and deletion, Memory update/deletion, ingestion, search,
authentication, agent workflows, and frontend code are not implemented.
