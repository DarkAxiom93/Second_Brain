# Local V1.1 acceptance

Checkpoint 59 accepted the integrated behavior of the tested Local V1.1 candidate
and is committed at `42fdfc8ee211835f0725f8d8b8da73020dbe83e6`.
Checkpoint 60 has release-hardened that candidate and remains pending human
review. Local V1.1 is not tagged or published. The recovery
baseline remains `v1.0.0` at
`a1bf40c0a27e9ee508e9bf1ab151b4665fbdba32`.

## Preflight and services

- `HEAD`, `main`, and `origin/main` were the accepted candidate, divergence was
  `0 0`, the tree was clean, and the commit subject was
  `feat: add explained search frontend`.
- `Second Brain CI` run
  [30831146968](https://github.com/DarkAxiom93/Second_Brain/actions/runs/30831146968)
  was the exact `push` run for `main` and the accepted SHA. It completed with
  conclusion `success`, attempt 1, no previous attempt, and zero artifacts.
- The documented startup verified the parsed and live development and test
  database identities. Vite-origin `/api/health` returned `ok` and
  `/api/ready` returned `ready`.
- Alembic current and the sole repository head were
  `0009_memory_expiration`; `alembic check` reported no new upgrade operations.
- Diagnostics reported no provider credential. Existing development data was
  sufficient: one Project and one Memory, with no acceptance fixture created.

## Route and browser acceptance

At the normal 1280 by 593 browser viewport, direct navigation through the real
Vite origin rendered the expected level-one heading for Dashboard, Projects,
Sources, Proposals, Memories, Search, Answers, and Settings. Each retained its
requested path, rendered a non-empty `main`, and had zero horizontal overflow.
The sidebar navigated internally through all eight routes; browser Back returned
from Dashboard to Settings and Forward returned to Dashboard. A deliberately
missing path rendered `Page not found` without redirect or blank content.

All tested focusable navigation and form controls showed a 2.66667px solid
focus outline in keyboard order. At a 390 by 844 viewport the document client
and scroll widths were both 375px, so no horizontal clipping occurred. Native
headings, labels, description lists, polite status regions, alert errors,
repeated labelled explanation regions, and text channel names were present.
The stylesheet retains `prefers-reduced-motion: reduce` handling. Application-
origin pages emitted no console-breaking failure; observed console errors came
only from an unrelated installed wallet extension.

## Explained search

Editing the query remained idle until explicit submission. One lexical submit
for `Checkpoint` called the additive explained route and returned the existing
Memory in backend order with global rank 1. The results heading received focus.
The result linked successfully to Memory detail and exposed an accessible
`Why this matched` region with `Matched channels: Text`, lexical rank 1, and
six-decimal lexical signal `0.166667`. Null fields were absent and the visible
status explained that signals are ordering aids, not confidence, probability,
or certainty. An explicit unique query produced the safe empty status
`No Memories matched this search.`

With provider credentials absent, semantic and hybrid submissions each showed
only `Semantic search is not configured on this local workspace.` There was no
lexical fallback, automatic retry, or internal response detail. Deterministic
backend and frontend tests cover semantic and hybrid success, retry,
cancellation, latest-request authority, exact rank/channel rendering, and the
single-request explicit-submit contract. Lexical provider non-resolution is
covered by the live success and backend regression suite.

## Compatibility, privacy, and data integrity

Focused legacy and explained-search tests passed for the established Memory
list/search, Answer, operations, Project export/import, and retrieval contracts.
The explained projection remains confined to
`POST /memories/search/explained`; the legacy route shapes are unchanged.
Projects, Sources, ingestion, proposal review/promotion, Memory provenance,
diagnostics, and maintenance remain covered by the complete zero-skip suite.

Project `b7fc847d-21ed-4507-aacc-834297730a75` produced a 2,198-byte
`second-brain-project-export` version 1 bundle with SHA-256
`1aefa2ec426a2e0970b64aa6954d894ffef518223db84f1cc1fbd1e01978c7fd`.
Its counts were one Project and one Memory, with every other exported entity
count zero. Validation of the exact bytes through the Vite-origin API reported
valid, not importable, and the expected `project.json primary-key conflict`.
Import execution was not called. The temporary bundle was removed.

The complete aggregate map remained Memories 1, MemoryEmbeddings 0,
MemoryExtractionRuns 0, MemoryProposals 0, Projects 1, SourceChunks 0,
SourceDocuments 0, and Sources 0. The existing Project and Memory IDs, public
fields, creation times, and update times remained identical. Before and after
row digests were equal for every application table; the non-empty `memories`
and `projects` digests matched exactly, and every empty-table digest remained
the SHA-256 empty-value digest. No application row was created, updated, or
deleted.

Static and runtime review found no browser storage, service worker, polling,
scheduled request, query/result/history persistence, remote application
endpoint, or new cloud boundary. Services remain bound to loopback. Public UI
and API evidence exposed no secret, vector, raw score, distance, SQL, prompt,
provider response, database URL, environment value, filesystem path, arbitrary
payload, or raw exception. `npm audit --audit-level=high` reported zero
vulnerabilities. No paid or provider call occurred.

## Verification and shutdown

Focused backend selection: 46 passed. Focused frontend selection: 21 passed.
Full verification passed: `pip check`, Ruff lint and format, mypy over 98
source files, all 674 Python tests with zero skips, Alembic current/heads/check,
frontend lint and type checking, all 90 frontend tests, the production build,
and `git diff --check`.

After acceptance, Vite and FastAPI are stopped before PostgreSQL. PostgreSQL is
stopped with the documented `dev-down.ps1` workflow, preserving its container
and `second-brain_postgres_data` named volume. Final port and child-process
evidence is recorded in `checkpoint-59-report.md`.

## Checkpoint 60 release hardening

A clean GUID-named Python 3.12 environment installed the exact candidate with
development extras, passed `pip check`, and imported `app` from the intended
source. A committed-input-only frontend copy passed locked `npm ci`, zero-finding
audit, lint, type checking, all 90 tests, and production build with exact
`react-router` 8.3.0 and no `react-router-dom`. Both disposable directories were
removed, and the committed lockfile remained unchanged.

The release-authoritative Full run passed all 674 Python and 90 frontend tests
with zero skips, all static and dependency checks, production build, Alembic
current/sole head/check at `0009_memory_expiration`, and `git diff --check`.
Repository-relative links and stable release wording audit cleanly. Checkpoint
60 remains pending human review, and no `v1.1.0` tag or Release exists.
