# Second Brain

Second Brain is a Python 3.12 project. This repository currently contains only
the Checkpoint 1 foundation: project metadata, a typed settings module, and the
quality-tooling baseline.

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
production credentials. On Windows, all commands can invoke the virtual
environment's Python executable directly without activating it.

## Quality checks

```powershell
& '.\.venv\Scripts\python.exe' -m ruff check .
& '.\.venv\Scripts\python.exe' -m ruff format --check .
& '.\.venv\Scripts\python.exe' -m mypy app
& '.\.venv\Scripts\python.exe' -m pytest
```

## Current scope

There is intentionally no runnable application or API implementation in
Checkpoint 1. Docker, database integration, agent workflows, and frontend code
are also not implemented.
