# Verification contract

## Database topology and identity

From Windows, PostgreSQL is `127.0.0.1:5433`; `db` is valid only within the
Compose network. `DATABASE_URL` must parse to `second_brain`, and
`TEST_DATABASE_URL` to `second_brain_test`. Both parsed URL identity and live
`SELECT current_database()` identity must match before database work. Never
downgrade the development database. Migration lifecycle tests may downgrade
only the verified `second_brain_test` database.

## Required checks

Full approval requires `pip check`, Ruff lint, Ruff format check, mypy, the
complete pytest suite, `alembic current`, `alembic heads`, `alembic check`, and
`git diff --check`. No integration test may be skipped. `scripts/verify.ps1`
encodes this contract.

Quick verification is a focused development loop. Because the repository has no
reliable unit/integration marker, Quick runs tests outside `tests/integration`
and excludes the migration lifecycle file; Full remains authoritative.
`-SkipDatabase` is documentation-only preflight and is insufficient for final
approval.

Live Uvicorn smoke testing is required when startup, routing, dependency wiring,
or public behavior changes; documentation/script-only changes need safe script
behavior checks instead. Provider calls must be faked unless explicitly
approved.

Start and stop PostgreSQL with the scripts. Shutdown uses `docker compose stop
db`, preserving the container and named volume; never use `down -v`.
