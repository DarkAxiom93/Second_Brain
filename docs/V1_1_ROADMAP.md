# Second Brain Local V1.1 roadmap

Status: Proposed by Checkpoint 54. Checkpoint 55 is committed and pushed;
Checkpoint 56 is implemented locally and pending human review.

## Objective and boundaries

The proposed Local V1.1 objective is to make the released local application
safer to maintain and easier to trust during retrieval: remove the known locked
frontend advisory, add a bounded non-authoritative CI signal, and add
deterministic explanations to the existing Memory search experience without
changing stored data or the V1 export/import contract.

V1.1 remains a loopback-only application for one trusted local maintainer. It
preserves explicit human review, explicit actions, deterministic local Full
verification, parsed and live database identity checks, the PostgreSQL named
volume, and the no-merge/no-overwrite import policy. The `v1.0.0` tag and
release remain the recovery baseline.

Non-goals are authentication, authorization, multi-user isolation, remote
access, cloud deployment or synchronization, background workers, autonomous
agents, scheduled or automatic maintenance, destructive deletion, import
merge/overwrite/remap, encrypted bundles, and persistent conversation history.

## Evidence base

### Confirmed repository findings

- Local V1 is released as `v1.0.0` from
  `a1bf40c0a27e9ee508e9bf1ab151b4665fbdba32`. The published release is not a
  draft or prerelease and has no uploaded assets.
- The application is a local React/Vite SPA over loopback FastAPI and
  PostgreSQL. It has no React Server Components, server actions,
  authentication, browser persistence, service worker, or cloud boundary.
- The sole Alembic head and live development revision are
  `0009_memory_expiration`; `alembic check` reports no upgrade operations.
- Local V1 acceptance covers all eight top-level UI routes. Full verification
  is the authoritative approval workflow and exercises backend, PostgreSQL,
  Alembic, frontend, and build checks with zero skips.
- The Local V1 locked frontend graph contains `react-router` and
  `react-router-dom` `7.18.2`. GitHub's reviewed `GHSA-qwww-vcr4-c8h2` advisory classifies
  `react-router` versions from `7.12.0` through versions before `8.3.0` as
  affected and `8.3.0` as patched. The vulnerable RSC action path is absent in
  this client-only SPA. Checkpoint 55 migrates the pending-review working tree
  to the official v8 package structure with direct `react-router` 8.3.0 and a
  zero-finding npm audit.
- Checkpoint 56 adds one pending-review `.github/workflows/ci.yml` early signal.
  It intentionally excludes database and release-acceptance coverage, so local
  Full verification remains authoritative. Its first remote run is pending the
  approved Checkpoint 56 commit and push.
- Existing search contracts return bare `Memory` results. PostgreSQL already
  calculates lexical rank, semantic distance, and deterministic RRF ordering;
  answer evidence already carries bounded lexical/semantic score information.
  The UI does not explain why an individual search result ranked where it did.
- Version 1 project export/import is checksummed, conflict-only, and covered by
  PostgreSQL round-trip tests. Bundles are private but unencrypted. Changing
  their format or import semantics would require separate compatibility and
  recovery planning.
- The repository contains 81 backend test files and 9 frontend test files,
  reusable Windows verification scripts, read-only diagnostics and maintenance
  auditing, and no actionable application `TODO` or `FIXME` marker that forces
  V1.1 scope.

### Planning recommendations

- Treat the React Router advisory as a dedicated first implementation
  checkpoint. A major-version dependency change deserves isolated install,
  lockfile, router compatibility, security, and regression evidence.
- Add CI in V1.1, but make it an early feedback signal only. It must not replace
  or weaken the authoritative Windows host-side `Full` workflow, database
  identity gates, or final local release evidence.
- Choose deterministic retrieval explanations as the sole user-facing V1.1
  feature. This builds on data already calculated by the repositories, improves
  trust in lexical/semantic/hybrid ordering, needs no persistence, and avoids
  authentication, remote access, background work, destructive automation, and
  new provider behavior.
- Preserve existing search endpoints and response shapes. Add a separate
  explained-search contract so `v1.0.0` clients remain compatible.
- Do not add an Alembic migration in V1.1. Any later decision to persist search
  sessions, answers, jobs, or observability must begin with a dedicated schema,
  rollback, privacy, and export-compatibility checkpoint.

### Decisions requiring human approval

- Review and approve Checkpoint 55's exact React Router 8.3.0 package/import
  migration before it is committed or later checkpoints begin.
- At Checkpoint 56, approve the CI platform and trigger policy. The recommended
  minimum is pull-request and push checks for install, dependency consistency,
  backend static/unit checks, and the locked frontend suite/build, with an
  explicit statement that local Full remains authoritative.
- Before Checkpoint 57, approve the exact additive explained-search schema,
  including which normalized score fields are public. Raw vectors, prompts,
  SQL, provider responses, and internal diagnostics must remain private.
- Approve release and tag creation only after Checkpoint 60 evidence passes.

## Prioritization

| Candidate | Priority | User value | Engineering value | Risk | Complexity | Compatibility impact | Reason |
|---|---|---|---|---|---|---|---|
| React Router advisory remediation | Must for V1.1 | Low direct, high trust | Removes known high-severity locked finding | Medium: major-version upgrade | Medium | Dependency/lockfile and possible router compatibility edits | Known reviewed advisory should be cleared before feature work. |
| Final V1.1 acceptance and release hardening | Must for V1.1 | High release confidence | Produces reproducible recovery and compatibility evidence | Medium | Medium | No intended runtime contract change | A release cannot be tagged from partial checkpoint evidence. |
| Non-authoritative CI | Should for V1.1 | Indirect | Detects pushed regressions earlier | Medium: runner differences and false confidence | Medium | New workflow only; local Full remains authoritative | The repository has strong local checks but no remote signal. |
| Deterministic retrieval explanations | Should for V1.1 | High | Reuses and clarifies existing ranking logic | Medium: contract/privacy/ranking accuracy | Medium | Additive endpoint; legacy responses unchanged | Highest bounded product value without new persistence or trust boundary. |
| Additional accessibility/usability audit | Should for V1.1 | High for keyboard and assistive-technology users | Prevents regression in the new result UI | Low | Low | None | It belongs inside the frontend and acceptance checkpoints, not as an unrelated feature. |
| Controlled manual maintenance execution | Could follow after V1.1 | Medium | Completes read-only finding workflow | High: data mutation and concurrency | High | New write APIs and safety review | It is unrelated to retrieval explanations and requires its own approval boundary. |
| Encrypted export bundles | Could follow after V1.1 | Medium | Improves data-at-rest handling outside the app | High: key management and recovery | High | Export-format compatibility and new dependencies | Valuable, but unsafe to fold into a small search-focused release. |
| Import merge/overwrite/remap | Could follow after V1.1 | Medium | More flexible restore | High: destructive conflict and identity semantics | High | Format, API, data migration, and rollback planning | Existing no-merge behavior is deliberately safe and must remain unchanged here. |
| Persistent answer/chat history | Explicitly deferred to V2 or later | Medium | Adds conversational continuity | High: privacy, schema, retention, export | High | Migration, API, export format, data rollback | Persistence expands the privacy and lifecycle boundary. |
| Authentication, multi-user isolation, cloud sync, or remote access | Explicitly deferred to V2 or later | Potentially high | Establishes a different deployment/security architecture | Critical | High | Broad schema/API/deployment/security changes | Not required by the accepted single-maintainer loopback product. |
| Scheduled jobs, background agents, or autonomous maintenance | Explicitly deferred to V2 or later | Unproven | Adds automation | Critical: hidden writes and recovery | High | New services, job state, APIs, migrations | Conflicts with explicit human review and bounded V1.1 scope. |

## Change-impact map

| Proposed change | Alembic migration | API contract | New dependency | Provider credentials | Export compatibility | Security review | Data migration/rollback |
|---|---|---|---|---|---|---|---|
| Router advisory remediation | No | No intended change | Updates existing frontend dependency | No | None | Required | Lockfile rollback to reviewed V1 baseline |
| CI signal | No | No | Workflow actions only | No provider credentials permitted | None | Required for permissions/secrets | Revert workflow |
| Explained-search backend | No | New additive response/route | No | Lexical: no; semantic/hybrid: existing embedding credential behavior only | V1 bundles unchanged | Required for public-field/privacy review | Revert additive route; no stored data |
| Explained-search frontend | No | Consumes additive route | No | Same as existing search modes | None | Accessibility and content/privacy review | Revert UI/client use; legacy endpoints remain |
| Acceptance/release | No | Verifies both legacy and additive contracts | No | Live paid calls remain optional and require separate approval | Prove V1 import/export compatibility | Required | Recover to `v1.0.0`; no data conversion |

There is no proposed V1.1 migration checkpoint. Discovery of a genuine schema
need must stop the active checkpoint and return to human scope approval; it must
not be hidden inside an API or UI checkpoint.

## Proposed checkpoint sequence

### Checkpoint 55 - React Router advisory remediation

- **Goal:** Remove `GHSA-qwww-vcr4-c8h2` from the locked frontend graph with a
  reviewed patched React Router release.
- **Justification:** The known high-severity dependency finding should be
  resolved before adding product behavior even though the current client-only
  topology does not expose the affected RSC action path.
- **Allowed scope:** removal of the v7 `react-router-dom` compatibility package,
  direct `react-router` 8.3.0, lockfile and normal-import migration; focused dependency,
  navigation, route, accessibility, build, and audit evidence; documentation of
  upstream findings.
- **Forbidden scope:** UI redesign, new routes or features, backend changes,
  schema/migration changes, broad dependency refresh, RSC/server actions.
- **Expected files or architectural areas:** `frontend/package.json`,
  `frontend/package-lock.json`, router imports/initialization only if required,
  focused frontend tests, checkpoint report, dependency limitation wording.
- **API or migration impact:** None intended; no Alembic migration.
- **Focused test strategy:** Clean locked install; dependency-tree/advisory
  inspection; all router/navigation tests; frontend lint, typecheck, Vitest,
  production build; local Full verification.
- **Acceptance criteria:** The locked graph uses a reviewed patched version;
  the named advisory is absent; all existing routes and 404 behavior remain;
  no RSC/server action path appears; manifests and lockfile are internally
  consistent; Full passes.
- **Dependencies on earlier checkpoints:** Checkpoint 54 approval.
- **Risk level:** Medium.

### Checkpoint 56 - Non-authoritative continuous integration

- **Goal:** Add a minimal CI signal for committed changes while retaining local
  Windows Full verification as the sole release-authoritative workflow.
- **Justification:** Automated remote feedback reduces maintainability risk;
  runner differences must not weaken the established local database contract.
- **Allowed scope:** One least-privilege workflow; pinned supported Python/Node
  setup; locked installs; dependency checks; backend lint/format/type/unit
  checks and frontend lint/type/Vitest/build; cache use only when safe and
  content-addressed; concise CI documentation.
- **Forbidden scope:** Deployment, publishing, secrets/provider credentials,
  write permissions, database recreation, release automation, changing local
  Full gates, or claiming CI is equivalent to Full without identical verified
  PostgreSQL/Alembic coverage.
- **Expected files or architectural areas:** `.github/workflows/`, possibly
  documentation only; existing verification scripts may be changed only if a
  separately reviewed portability defect requires it.
- **API or migration impact:** None.
- **Focused test strategy:** Workflow syntax/action-permission audit; exercise
  the exact local commands represented by CI; Full locally; verify CI failure
  propagation in the pull-request/push context after publication.
- **Acceptance criteria:** CI is least privilege, uses no application secrets,
  fails on relevant backend/frontend regressions, documents its coverage gap,
  and leaves local Full unchanged and authoritative.
- **Dependencies on earlier checkpoints:** Checkpoint 55, so CI installs the
  remediated lockfile.
- **Risk level:** Medium.

### Checkpoint 57 - Additive explained-search backend contract

- **Goal:** Return bounded, deterministic reasons for lexical, semantic, and
  hybrid Memory result ordering through a new read-only contract.
- **Justification:** Users can assess why a result matched without exposing
  vectors or changing trusted Memory data.
- **Allowed scope:** New typed request/response schemas and additive route;
  repository projections for result rank, normalized public lexical/semantic
  signals, and RRF contributions; deterministic ordering; existing filters and
  pagination; safe generic failures; contract documentation and tests.
- **Forbidden scope:** Changing existing search response shapes, persisting
  queries/results, provider changes, raw vectors/distances/SQL/prompts, ranking
  policy changes unrelated to explanation, mutations, or migrations.
- **Expected files or architectural areas:** Memory schemas, Memory route,
  retrieval repository/query projections, API documentation, unit and
  PostgreSQL integration tests.
- **API or migration impact:** Additive API contract; no migration. Lexical mode
  must not resolve a provider. Semantic/hybrid modes retain existing credential
  and safe-failure behavior.
- **Focused test strategy:** Exact schemas and validation; deterministic
  lexical/semantic/RRF calculations and tie-breaking; filtering/pagination;
  provider absence/failure; database failure; absence of private fields;
  regression tests for every legacy search contract.
- **Acceptance criteria:** Each returned explanation is reproducible from the
  ranking query, bounded to its result, and mode-appropriate; legacy endpoints
  are byte-shape compatible; no write occurs; no secret/vector/internal detail
  is public; Full passes.
- **Dependencies on earlier checkpoints:** Checkpoints 55-56.
- **Risk level:** Medium.

### Checkpoint 58 - Explained-search frontend and accessibility

- **Goal:** Show concise, accessible "why this matched" information in the
  existing Search screen for all three modes.
- **Justification:** Backend explanation data has user value only when it is
  understandable without obscuring Memory content or citation navigation.
- **Allowed scope:** Search client types/call, result explanation rendering,
  accessible labels/status, responsive layout, explicit submission and retry,
  safe error handling, focused tests and documentation.
- **Forbidden scope:** New top-level route, automatic searches/retries/polling,
  browser persistence, provider controls, exposing raw response internals,
  unrelated visual redesign, backend or schema changes.
- **Expected files or architectural areas:** `frontend/src/Search.tsx`, API
  client/types, focused Search tests, narrowly required styles, user docs.
- **API or migration impact:** Consumes Checkpoint 57 additive contract; no
  migration.
- **Focused test strategy:** Each search mode and explanation variant; explicit
  request behavior; cancellation/retry; empty/malformed/safe-failure states;
  keyboard order, focus, live regions, text alternatives, reduced motion and
  narrow viewport; legacy navigation links.
- **Acceptance criteria:** Users can distinguish lexical, semantic, and hybrid
  reasons; scores are labelled and not presented as certainty; no query occurs
  without explicit action; private data is not rendered; WCAG-oriented checks
  and Full pass.
- **Dependencies on earlier checkpoints:** Checkpoint 57.
- **Risk level:** Medium.

### Checkpoint 59 - Local V1.1 end-to-end acceptance

- **Goal:** Prove the integrated candidate against real local services and the
  V1 safety/compatibility baseline.
- **Justification:** Unit contracts do not alone prove proxy routing,
  accessibility, safe provider failure, or export/import compatibility.
- **Allowed scope:** Evidence collection, focused defect fixes within approved
  V1.1 behavior, real lexical explained search, credential-free semantic/hybrid
  failure evidence, route/accessibility/privacy/security audit, V1 bundle
  export/validation compatibility, Full verification, acceptance docs.
- **Forbidden scope:** New features, paid/provider calls without separate
  approval, import execution against conflicts, destructive cleanup, schema or
  format changes, dependency expansion.
- **Expected files or architectural areas:** Acceptance and checkpoint
  documentation; narrowly scoped defect files only if evidence finds a blocker.
- **API or migration impact:** Verification only; no migration.
- **Focused test strategy:** Real browser through Vite proxy; all top-level
  routes; explained lexical success; semantic/hybrid deterministic tests and
  safe missing-credential behavior; legacy API regression; V1 export plus
  validation-only import; Full with zero skips.
- **Acceptance criteria:** Integrated behavior matches the approved contract;
  existing V1 workflows regress neither functionally nor accessibly; a V1
  bundle remains supported without merge/overwrite; no development data is
  mutated by acceptance except separately approved exact-ID smoke data; Full
  passes.
- **Dependencies on earlier checkpoints:** Checkpoints 55-58.
- **Risk level:** Medium.

### Checkpoint 60 - V1.1 documentation and release hardening

- **Goal:** Produce a reproducible Local V1.1 release candidate and, only after
  separate human approval, make it eligible for a `v1.1.0` tag and Release.
- **Justification:** Release facts, recovery instructions, dependency state,
  and verification evidence must agree before publication.
- **Allowed scope:** Stable documentation synchronization; clean backend and
  locked frontend install rehearsals; release/security/privacy/accessibility
  audit; final Full run; exact release notes and recovery boundary; checkpoint
  report. Tag/Release creation requires an additional explicit instruction.
- **Forbidden scope:** Product changes, schema/API/format changes, unreviewed
  dependency updates, secrets, deployment, automatic publication, changing
  `v1.0.0`, or starting V1.2/V2 work.
- **Expected files or architectural areas:** README, architecture, roadmap,
  limitations, runbook, acceptance/handoff/checkpoint documents, final report.
- **API or migration impact:** None; records the accepted additive API and the
  unchanged Alembic head/export format.
- **Focused test strategy:** Repository-relative link checker; stale/future
  wording audit; clean installation rehearsals; dependency audit; route and
  schema inventories; V1 export compatibility evidence; one final local Full
  run with zero skips.
- **Acceptance criteria:** All earlier checkpoints are committed and pushed;
  `main` matches `origin/main`; the tree is clean before release; current and
  sole Alembic head remain approved with no pending operations; CI is green but
  is not substituted for local Full; clean installs and final Full pass; no
  high-severity known locked advisory remains without explicit release
  acceptance; Local V1.1 acceptance and recovery docs are complete; V1 bundles
  remain supported; no secret or development data is tracked.
- **Dependencies on earlier checkpoints:** Checkpoints 55-59.
- **Risk level:** High because it controls release eligibility.

The condition for creating `v1.1.0` is satisfaction and human review of every
Checkpoint 60 acceptance criterion, followed by a separate explicit instruction
to create the annotated tag and published Release from the exact clean commit.
Checkpoint 60 completion alone does not authorize tagging or publishing.

## Recovery and compatibility rules

- `v1.0.0` remains the stable code recovery point throughout V1.1 work.
- No proposed checkpoint changes database schema or stored application data;
  never downgrade, recreate, or reset `second_brain` during rollback.
- Existing search endpoints remain available and retain their response shapes.
- `second-brain-project-export` format version 1 remains the only approved
  format. Imports remain validation-first, conflict-only, atomic, and without
  merge, overwrite, remap, repair, or partial behavior.
- Dependency and workflow checkpoints roll back by reverting their isolated
  commits. The explained-search feature rolls back by reverting the UI and
  additive route; no data migration is required.
- Any discovered need for persistence, export-format change, new provider,
  destructive operation, or security-boundary expansion stops the active
  checkpoint and requires a revised roadmap and human approval.
