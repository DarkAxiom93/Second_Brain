# Second Brain chat handoff

Second Brain Local V1 is released as `v1.0.0`. The annotated tag still points to
`a1bf40c0a27e9ee508e9bf1ab151b4665fbdba32`. Alembic remains at the sole code
head `0009_memory_expiration`.

Checkpoint 55 is complete at
`cefdc4e2e27d2ff53eb612081b1a10973f93a997`, is pushed, and `main` matched
`origin/main` before Checkpoint 56 began. It installs exact `react-router`
8.3.0, contains no `react-router-dom`, and has a zero-finding npm audit.

Checkpoint 56 is complete at
`2c4ed449c2471d4c4729164714e551979028d0f8` and pushed. It adds one
least-privilege workflow at `.github/workflows/ci.yml`, triggered only by pull
requests targeting `main`, pushes to `main`, and manual dispatch. Its one
`windows-2022` job uses Python 3.12.10 and Node.js 22.22.0. It creates the local
`.venv`, installs `.[dev]`, runs Quick with `-SkipDatabase`, installs the exact
frontend lockfile, runs the established frontend verification, and runs npm
audit at high severity. The only actions are immutable pins of checkout v4.2.2,
setup-python v5.6.0, and setup-node v4.4.0. Permissions are `contents: read`.

CI has no secrets, explicit token, write access, OIDC, PostgreSQL, Docker,
artifact, deployment, publication, provider, export/import, or release path.
It does not perform PostgreSQL identity verification, integration or migration
lifecycle tests, live Alembic checks, Vite-origin browser smoke, provider-backed
workflows, export/import round trips, development-database safety verification,
or Local V1.1 acceptance. `.\scripts\verify.ps1 -Mode Full` remains the sole
release-authoritative command. The first exact push run completed successfully
without rerun or artifact: run ID `30806886319`,
`https://github.com/DarkAxiom93/Second_Brain/actions/runs/30806886319`.

A real database-free Quick rehearsal initially failed because the root-level
live diagnostics test was collected. A separately approved correction now
deselects exactly
`tests/test_diagnostics_script.py::test_healthy_test_database_execution_and_optional_json`
only in Quick; the file's other three tests remain included, and Full retains
the complete suite. Corrected Quick passed 452 selected tests with exactly one
deselection. Final Full passed all 647 Python tests and all 78 frontend tests
with zero skips; the live diagnostics test executed successfully. Alembic
remained `0009_memory_expiration`. PostgreSQL was stopped afterward and its
named volume was preserved.

Checkpoint 57 is complete at
`f6b9260ccf3d015e1ece38f20df62d97061bd13e`. Its exact push CI run
`30812460630` succeeded on attempt 1 without rerun:
`https://github.com/DarkAxiom93/Second_Brain/actions/runs/30812460630`. It adds only
`POST /memories/search/explained`, with strict typed lexical, semantic, and
hybrid explanations; six-decimal bounded signals; RRF `k=60`; SQL-side ranking
and pagination; lazy provider resolution that never runs for lexical mode; and
no persistence. Legacy search and Answer contracts remain unchanged.
Checkpoint 58 is complete at
`ccef163469c021c53e0bf5889babc838de58c9c7`. `/search` now
uses only the additive explained endpoint, preserves explicit submission,
cancellation, retry, focus, links, backend order, safe errors, and no browser
persistence, and renders accessible channel explanations with six-decimal
public ranking values and an ordering-aid disclaimer. No backend, migration,
dependency, lockfile, or stored-data change was made.

Checkpoint 59 acceptance is implemented locally and pending human review. It
adds evidence and documentation only; no product, migration, dependency,
provider, CI, Docker, or stored-data behavior changed. Read `AGENTS.md`,
`docs/V1_1_ROADMAP.md`, `docs/VERIFICATION.md`, `docs/SAFETY.md`, and
`docs/checkpoint-59-report.md` before further work. Use
Python 3.12 from `.venv`; use only verified `second_brain_test` for integration
tests; never recreate a database or delete the PostgreSQL volume. Do not stage,
commit, push, open a PR, or begin Checkpoint 60 without explicit instruction.
