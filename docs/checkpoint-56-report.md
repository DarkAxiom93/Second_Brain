# Checkpoint 56 report

Checkpoint: Non-authoritative GitHub Actions CI. Status: pending human review.

Files changed:

- `.github/workflows/ci.yml`
- `tests/test_ci_workflow.py`
- `scripts/verify.ps1` and `tests/test_verification_script.py` (separately
  approved exact Quick-mode portability correction and regression coverage)
- `scripts/frontend-setup.ps1` and `scripts/verify-frontend.ps1` (stale
  user-facing Node minimum text only)
- `docs/VERIFICATION.md` and `scripts/README.md`
- `docs/ARCHITECTURE.md`, `docs/V1_1_ROADMAP.md`, `docs/ROADMAP.md`,
  `docs/CHECKPOINTS.md`, `docs/CHAT_HANDOFF.md`, and this report

Behavior:

One workflow named `Second Brain CI` provides early remote feedback for pull
requests targeting `main`, pushes to `main`, and manual dispatch. Its single job
runs on `windows-2022`, has a 30-minute timeout, and configures exact Python
3.12.10 and Node.js 22.22.0. It displays only resolved Python, Node, and npm
versions.

The workflow creates repository-local `.venv`, installs `.[dev]`, runs
`.\scripts\verify.ps1 -Mode Quick -SkipDatabase`, installs the locked frontend
graph with `.\scripts\frontend-setup.ps1`, runs
`.\scripts\verify-frontend.ps1`, and runs `npm audit --audit-level=high` from
`frontend/`. Failures propagate normally without retry or `continue-on-error`.

Workflow security:

- Permissions are exactly `contents: read`.
- Immutable pins are checkout v4.2.2 at
  `11bd71901bbe5b1630ceea73d27597364c9af683`, setup-python v5.6.0 at
  `a26af69be951a213d495a4c3e4e4022e16d87065`, and setup-node v4.4.0 at
  `49933ea5288caeca8642d1e84afbd3f7d6820020`. Official repository tag refs
  were checked before implementation.
- Checkout uses `persist-credentials: false` and `fetch-depth: 1`.
- There are no secrets, explicit tokens, write permissions, OIDC, database,
  Docker, service container, artifact, deployment, publication, release,
  telemetry, coverage-service, or third-party reporting paths.

Coverage boundary:

CI does not perform PostgreSQL identity verification, integration tests,
migration lifecycle tests, Alembic current/check against a live database,
Vite-origin browser smoke, provider-backed workflows, export/import round-trip
execution, Windows development-database safety verification, or Local V1.1
release acceptance. CI is an early regression signal only. The authoritative
approval and release command remains `.\scripts\verify.ps1 -Mode Full`.

API:

Unchanged. No route, schema, request/response, authentication, CORS, provider,
or export/import behavior changed.

Database:

Unchanged. No model, migration, data, Docker, or database configuration changed.
The sole Alembic code head remains `0009_memory_expiration`.

Transactions:

No application transaction behavior changed.

Tests:

`tests/test_ci_workflow.py` is a focused standard-library text-policy test, not
a complete GitHub Actions parser. It checks approved triggers, runner,
permissions, forbidden capabilities, immutable approved actions, checkout
credential handling, exact runtimes, established commands, and the absence of
CI authority claims. Its focused run passed 4/4 tests; focused Ruff lint and
format checks passed after the test was corrected.

The exact CI-command rehearsal then exposed a confirmed pre-existing
portability defect: `.\scripts\verify.ps1 -Mode Quick -SkipDatabase` collected
450 tests and failed with 449 passed and 1 failed. The collected
`test_healthy_test_database_execution_and_optional_json` test attempts to
connect to `second_brain_test`; PostgreSQL was intentionally not running, so
the diagnostics command correctly reported that live database identity and
state could not be verified. The checkpoint requires CI to run Quick with
`-SkipDatabase` without PostgreSQL, but any behavioral verification-script or
test-scope correction requires separate human approval. Work stopped without
changing script execution behavior. Separate approval then authorized one
narrow correction: Quick passes exactly
`--deselect=tests/test_diagnostics_script.py::test_healthy_test_database_execution_and_optional_json`.
The test explicitly sets `TEST_DATABASE_URL`, invokes the healthy
`-UseTestDatabase` diagnostics path, and asserts `second_brain_test` is healthy.
No repository-wide unit/integration marker exists. Quick still collects the
containing root-level file and its other three tests; Full has no deselection
and retains the complete suite. The test source was not changed, skipped,
marked, renamed, weakened, or mocked.

Focused CI-policy and verification-script regression coverage passed 12/12.
The corrected database-free Quick run collected 453 nodes, deselected exactly
the approved live-database node, and passed all 452 selected tests with zero
skips. The containing diagnostics file ran its other three tests. A separate
collection-only check discovered the exact deselected node without executing
it. Locked frontend setup passed; ESLint, TypeScript, 9 Vitest files/78 tests,
and the Vite production build passed. `npm audit --audit-level=high` reported
zero vulnerabilities.

`.\scripts\verify.ps1 -Mode Full` passed on its single final run: `pip check`,
Ruff lint/format, strict mypy, 647/647 Python tests with zero skips, Alembic
current/heads/check, ESLint, TypeScript, 9 frontend files/78 tests, production
build, and `git diff --check`. Full executed all four tests in
`tests/test_diagnostics_script.py`, proving the live-database test remains in
the authoritative complete suite.

PostgreSQL verification:

Full verified parsed and live identities as `second_brain` and
`second_brain_test`. Alembic current and sole head were
`0009_memory_expiration`, and `alembic check` found no new upgrade operations.
No development data was changed. PostgreSQL was started only for Full and then
stopped with `scripts/dev-down.ps1`; the container and named volume were
preserved.

Smoke test:

Not required for this workflow, test, documentation, and text-only script
change. Full verification supplies the applicable script and database evidence;
Vite-origin browser smoke remains outside CI and unchanged.

API regression:

No API contract changed. All 647 Full Python tests passed.

External calls:

Official GitHub action tag refs and npm advisory metadata were queried. No paid
provider or application external call was made.

Warnings:

The first real GitHub Actions run remains pending until this checkpoint is
reviewed, committed, and pushed. No remote CI success is claimed. Two early
focused commands included broader process-helper tests without a usable unique
base temp and encountered the existing inaccessible shared-temp condition; the
formal focused run used the directly relevant modules and passed. The initial
frontend audit request was sandbox-blocked, then passed with approved registry
access. Pytest retained the existing Starlette `httpx` deprecation warning, and
Vitest retained the existing jsdom navigation notice; neither failed Full.

Git status:

Preflight was clean. `main` matched `origin/main`; the exact approved Checkpoint
55 commit was `cefdc4e2e27d2ff53eb612081b1a10973f93a997`. Local `v1.0.0`
still peeled to `a1bf40c0a27e9ee508e9bf1ab151b4665fbdba32`. Changes remain
unstaged and uncommitted.

Scope confirmation:

Only the Checkpoint 56 workflow, focused policy test, separately approved exact
Quick-mode deselection and regression coverage, necessary documentation, and
the explicitly permitted stale Node-minimum text corrections changed. No
application/frontend application code, dependency, lockfile, API, schema,
migration, database data, Docker, provider, export/import, branch protection,
tag, Release, or product behavior changed. No report-template heading was
omitted.
