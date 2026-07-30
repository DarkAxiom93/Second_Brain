# Contributor Guide

## Scope

- Work on one approved checkpoint at a time.
- Do not add unrequested frameworks, services, or speculative functionality.
- Do not implement Milestone 2 functionality during Milestone 1.
- Before each checkpoint, read `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`,
  `docs/CHECKPOINTS.md`, `docs/VERIFICATION.md`, `docs/SAFETY.md`,
  `docs/API_CONVENTIONS.md`, and the relevant ADRs in `docs/decisions/`.
- Resolve instructions in this order: (1) explicit current-checkpoint instructions,
  (2) this file, (3) migrations, tests, and current repository behavior,
  (4) architecture, safety, verification, API conventions, and ADRs, then
  (5) roadmap and checkpoint history. Preserve the safer existing rule if sources
  conflict, and record the resolution in the checkpoint report.

## Python workflow

- Use Python 3.12 and the project-local `.venv`.
- Install dependencies with `python -m pip install -e ".[dev]"`.
- Keep application code under `app/` and tests under `tests/`.
- Add type annotations to production code and keep configuration centralized in
  `app.core.config`.

## Verification

Run these checks before handing off changes:

```powershell
& '.\.venv\Scripts\python.exe' -m ruff check .
& '.\.venv\Scripts\python.exe' -m ruff format --check .
& '.\.venv\Scripts\python.exe' -m mypy app
& '.\.venv\Scripts\python.exe' -m pytest
```

- Run every relevant check after changes; do not silently ignore errors.
- Update the README whenever user-facing commands change.

## Repository hygiene

- Never commit secrets or local `.env` files.
- Never place secrets in source code.
- Do not commit virtual environments, caches, coverage output, or editor state.
- Do not commit or push unless explicitly requested.

## Database and later-checkpoint safety

- Never run destructive database commands without explicit approval.
- Tests must never run against the development database.
- Integration tests must use a separate PostgreSQL test database.
- Destructive cleanup must verify the test database identity first.
- The PostgreSQL development port must bind to `127.0.0.1`.
- Migration failure must prevent Uvicorn startup.
- `updated_at` must actually update and must not rely only on a creation default.
- pgvector may be enabled later, but do not add an embedding column until the
  embedding model and dimension are approved.
