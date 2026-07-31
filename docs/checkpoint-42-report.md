# Checkpoint report

Checkpoint: 42 — Local Web UI Foundation.

Files changed: Added the locked React/TypeScript/Vite workspace under
`frontend/`, the application shell, dashboard, typed API boundary, CSS, Vitest
tests, PowerShell setup/development/verification scripts, focused Python script
checks, Full verification integration, ignore rules, and the required
architecture/workflow/history/handoff documentation.

Behavior: The responsive shell exposes deterministic routes for `/`,
`/projects`, `/sources`, `/proposals`, `/memories`, `/search`, `/answers`, and
`/settings`. The root dashboard alone is functional. It makes one health and one
readiness request on load, provides loading/success/generic failure states and a
manual Retry, and never polls. Future routes are concise placeholders. Unknown
routes render a local Not Found page without a backend request.

API: One configurable, same-origin API base defaults to `/api`. Requests use a
five-second timeout, AbortController cancellation, same-origin credentials,
strict exact payload validation for `{"status":"ok"}` and
`{"status":"ready"}`, and generic safe errors. There are no automatic retries,
logs, persistent browser storage, hard-coded database details, CORS changes, or
backend contract changes. Vite rewrites `/api/health` and `/api/ready` to the
existing backend `/health` and `/ready`.

Database: No model, schema, migration, Docker service, or database behavior
changed. The dashboard and smoke use GET requests only and create, update, or
delete no application data. Alembic current and sole head remain
`0009_memory_expiration`; `alembic check` reports no new upgrade operations.

Transactions: No frontend transaction or persistence behavior exists. Backend
transaction ownership is unchanged.

Tests: Node.js `v24.16.0` and npm `11.13.0` were used. `package.json` and
`package-lock.json` are present and synchronized; dependencies install locally
only. Fourteen Vitest tests cover shell/navigation, dashboard requests and
loading, safe success/failure, Retry, malformed responses, no polling, no
sensitive output, every placeholder, and local Not Found behavior. Seven Python
checks cover Windows PowerShell 5.1 parsing, missing runtimes/dependencies,
`npm ci`, no global install, isolated execution, failure propagation, and Full
verification integration. Frontend ESLint, TypeScript checking, all tests, and
the Vite production build pass.

PostgreSQL verification: Parsed and live development/test identities passed.
The final approval-tree Full run passed pip check, Ruff lint/format, strict
mypy, all 610 Python tests with zero skips, Alembic current/heads/check,
frontend lint/type check/14 tests/build, and `git diff --check`. Earlier Full
attempts were environment-only failures: the sandbox user temp root was
inaccessible, and unchanged-tree attempts also encountered the previously
documented Windows subprocess `WinError 6`. The unchanged authoritative reruns
used the verified repository-local ignored temporary directory and passed. The
final approval run followed the `frontend/*.tsbuildinfo` ignore correction and
therefore covers the complete candidate tree.

Smoke test: PostgreSQL, FastAPI, and Vite ran separately on their documented
loopback ports. Headless Chrome rendered the dashboard success state, a Projects
placeholder, and the client Not Found page. Health and readiness returned `ok`
and `ready` through the browser-facing Vite origin. No CORS change, application
write, provider call, or persistent output occurred. Frontend and backend were
stopped by exact process ID; PostgreSQL was then stopped with its Docker volume
preserved. Final checks confirmed ports 5173, 8000, and 5433 were closed.

API regression: All 610 Python tests pass. Backend application code, public
routes, schemas, Python dependencies, database behavior, authentication
behavior, and health/readiness responses are unchanged.

External calls: npm registry queries and local dependency download were used to
select and lock current mutually compatible packages. No provider was resolved
or called. No application telemetry, analytics, CDN, external font, or runtime
network dependency was added.

Warnings: npm audit reports two high-severity advisories through React Router
7.18.2. The advisory is for React Server Components action handling; this
client-only Vite application does not enable RSC, server rendering, or actions.
Downgrading exposed a broader set of Router advisories, so the current release
was retained. Vite-exposed environment values are public client configuration
and must never contain secrets. Authentication and application write workflows
remain deferred.

Git status: Work remains unstaged/untracked on `main` as required. No stage,
commit, push, PR, or next-checkpoint work was performed.

Scope confirmation: Checkpoint 42 only. No Project, Source, Proposal, Memory,
Search, or Answer workflow; authentication; backend code; API contract; Python
dependency; database model; migration; Docker service; provider call; commit;
push; PR; or later-checkpoint functionality was added.

Omitted headings: None.
