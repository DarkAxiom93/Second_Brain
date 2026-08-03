# Checkpoint 55 report

Checkpoint: React Router 8 security remediation and baseline alignment. Status:
pending human review.

Files changed:

- `frontend/package.json` and `frontend/package-lock.json`
- Seventeen existing production/test files under `frontend/src/`, imports only
- `docs/V1_1_ROADMAP.md`, `docs/ROADMAP.md`, `docs/CHECKPOINTS.md`,
  `docs/CHAT_HANDOFF.md`, `docs/KNOWN_LIMITATIONS.md`, and this report

Behavior:

No product behavior changed. The client remains a declarative, client-only SPA.
All existing route paths, hierarchy, parameters, links, navigation labels,
layout, accessibility behavior, API calls, and catch-all 404 are unchanged.
No Framework mode, SSR, RSC, server action, loader, action, or router dev tooling
was introduced.

Dependency remediation:

- Before: direct `react-router-dom` 7.18.2 with transitive `react-router` 7.18.2.
  npm reproduced high-severity GHSA-qwww-vcr4-c8h2, affecting `react-router`
  `>=7.12.0 <8.3.0` through the direct DOM compatibility package.
- A patch-only same-major remediation was impossible. npm suggested 7.11.0 for
  the named advisory, but a trial audit exposed multiple other high-severity
  React Router advisories. That trial was fully reverted before this revision.
- `react-router-dom` 8.3.0 does not exist because React Router 8 removes that
  compatibility package. The approved v8 structure uses `react-router` directly.
- After: direct, exact `react-router` 8.3.0; `react-router-dom` is absent.
- Node engine before/after: `>=22.12.0` to `>=22.22.0`. Actual verification
  runtime: Node v24.16.0 and npm 11.13.0.
- React and React DOM remain 19.2.8; Vite remains 8.2.0. Every other direct
  dependency version is unchanged. Lockfile format remains version 3.
- npm regenerated the lockfile. It removed `react-router-dom`, `cookie`, and
  `set-cookie-parser`, upgraded `react-router`, and added its expected `cookie-es`
  dependency. No unrelated dependency family or override was added.
- Final `npm ls react-router react-router-dom` resolves only
  `react-router@8.3.0`. Final `npm audit --json` reports zero vulnerabilities:
  GHSA-qwww-vcr4-c8h2 is absent and no high or critical finding remains.

Import migration:

Normal routing APIs were migrated from `react-router-dom` to `react-router`:
`BrowserRouter`, `MemoryRouter`, `Routes`, `Route`, `Link`, `NavLink`,
`useNavigate`, and `useParams`. Neither `RouterProvider` nor `HydratedRouter` is
used, so no `react-router/dom` import was required. No package or source import
reference to `react-router-dom` remains; documentation references are historical.

API:

Unchanged. No backend routes, schemas, request/response shapes, proxy behavior,
or provider behavior changed.

Database:

Unchanged. No model, migration, data, Docker, or export/import change. Parsed and
live identities were verified as `second_brain` and `second_brain_test`. Alembic
current and sole head remain `0009_memory_expiration`; `alembic check` reports no
new upgrade operations.

Transactions:

No application transaction behavior changed. Smoke was read-only and performed
no application-data mutation.

Tests:

- Focused route/workflow suite: 8 files, 68 tests passed.
- Frontend standalone gates: ESLint passed, TypeScript passed, 9 files/78 tests
  passed, and the Vite 8.2.0 production build passed.
- `scripts/verify.ps1 -Mode Full`: passed. `pip check`, Ruff lint/format, mypy,
  640/640 pytest tests, Alembic current/heads/check, all frontend gates, build,
  and `git diff --check` passed with zero skipped tests.
- One earlier Full invocation stopped at database identity connection because a
  short command-launch timeout interrupted PostgreSQL startup. After completing
  `dev-up.ps1`, both database identities passed and the authoritative rerun
  completed successfully.

PostgreSQL verification:

PostgreSQL 16/pgvector became healthy on `127.0.0.1:5433`. Full verification used
the verified test database for integration and migration lifecycle tests. Vite
and FastAPI were stopped before `dev-down.ps1`; the database container was
stopped and the named volume preserved.

Smoke test:

Real Vite-origin browser smoke passed `/`, `/projects`, `/sources`, `/proposals`,
`/memories`, `/search`, `/answers`, `/settings`, existing Project detail
`/projects/b7fc847d-21ed-4507-aacc-834297730a75`, and unknown route
`/checkpoint-55-unknown` showing “Page not found.” Internal Projects navigation,
direct mounting, browser back/forward, shell rendering, and Vite proxy health and
readiness all passed. There was no redirect, blank shell, repeated request loop,
browser persistence, or application-origin console routing error. Captured
extension-only console noise was unrelated to the application.

API regression:

No API contract changed. Full backend verification and Vite proxy `/api/health`
and `/api/ready` both passed.

External calls:

Only npm registry dependency/audit metadata was accessed. No provider-backed,
paid, destructive, export, or import operation was called.

Warnings:

Pytest reported the existing Starlette `httpx` deprecation and inaccessible
`.pytest_cache` warnings. Vite emitted the existing jsdom “navigation to another
Document” notice. None failed verification. No npm advisory remains.

Git status:

Changes are unstaged and uncommitted. Nothing was committed, pushed, tagged, or
published. Checkpoint 55 remains pending review.

Scope confirmation:

Only the approved React Router dependency/import migration and required
Checkpoint 55 documentation changed. Backend, database, API, provider,
export/import, Docker, verification scripts, and Local V1 contracts remain
unchanged. No report-template heading was omitted.
