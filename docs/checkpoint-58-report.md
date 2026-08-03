# Checkpoint report

Checkpoint: 58 — Explained Search Frontend and Accessibility. Pending human review.

Files changed:

- `frontend/src/Search.tsx`
- `frontend/src/api/client.ts`
- `frontend/src/Search.test.tsx`
- `frontend/src/api/client.search.test.ts`
- `frontend/src/styles.css`
- `docs/ARCHITECTURE.md`
- `docs/ROADMAP.md`
- `docs/V1_1_ROADMAP.md`
- `docs/CHECKPOINTS.md`
- `docs/CHAT_HANDOFF.md`
- `docs/checkpoint-58-report.md`

Behavior:

- `/search` now uses only `POST /memories/search/explained` for lexical,
  semantic, and hybrid submissions. The body is exactly `query`, `mode`,
  `filters`, and `pagination: { limit, offset: 0 }`.
- Each result preserves backend order and displays the backend-provided global
  `rank`. The Memory title, preview, project, status, type, confidence,
  importance, and detail link remain present.
- Every result has a uniquely labelled `Why this matched` section followed by a
  native description list. Visible labels are `Matched channels`, `Lexical
  rank`, `Lexical signal`, `Semantic rank`, `Semantic signal`, `Lexical RRF
  contribution`, `Semantic RRF contribution`, and `Fused RRF score`; null
  values are omitted.
- Channels are presented as `Text` and `Meaning`. Hybrid results state
  `text-only match`, `meaning-only match`, or `match through both channels` in
  text and do not rely on color. Public signal and RRF values use six decimal
  places and are not converted to percentages.
- The result status states: `Ranking signals explain backend ordering only.
  They are not confidence, probability, or certainty.`
- Explicit submit, one active request, duplicate-submit prevention,
  `AbortController` cancellation, latest-request authority, Retry from the last
  validated submission, validation focus, successful results-heading focus,
  polite loading/result status, alert errors, provider-safe messages, and
  generic malformed-response handling remain intact.
- No automatic search, debounce, polling, automatic retry, URL state,
  `localStorage`, `sessionStorage`, or browser-history persistence was added.

API:

- Added dedicated explained request, result, explanation, and matched-channel
  client types plus `searchMemoriesExplained`.
- Runtime validation requires exact result, Memory, and explanation keys;
  positive integer ranks; valid modes and ordered, duplicate-free channels;
  finite bounded signals; finite non-negative RRF values; and exact
  mode/channel nullability. Unknown and private fields fail closed and are
  never retained or rendered.
- The legacy `searchMemories` implementation is unchanged and has focused
  regression coverage for its lexical GET and semantic/hybrid POST contracts.
- Backend routes, schemas, ranking formulas, Answer contracts, and
  export/import contracts are unchanged.

Database:

- No model, migration, stored-data, dependency, lockfile, Docker, CI, provider,
  or persistence change exists.
- Development aggregate counts before and after smoke were identical:
  Memories 1, MemoryEmbeddings 0, MemoryExtractionRuns 0, MemoryProposals 0,
  Projects 1, SourceChunks 0, SourceDocuments 0, and Sources 0.

Transactions:

- Search and smoke activity was read-only. No application transaction wrote
  data.

Tests:

- Focused Search run: 19 passed. It covers explicit submission, all three exact
  request bodies, backend rank/order/link preservation, lexical explanations,
  all hybrid channel variants, six-decimal formatting, null omission,
  accessible headings/description lists, malformed/private/unknown/non-finite/
  out-of-range/nullability rejection, Retry, provider-safe errors, duplicate
  submission, cancellation, and latest-request authority.
- Full frontend run: 10 files and 90 tests passed. The two dedicated legacy API
  client regression tests are included. ESLint, TypeScript, and production Vite
  build passed.
- Full Python run: 674 tests passed with zero skipped tests. `pip check`, Ruff
  lint, Ruff format check, and mypy passed.
- `git diff --check` passed. The only warnings were the existing Starlette
  TestClient deprecation, inaccessible pytest cache warning, line-ending
  notices, and jsdom's `Not implemented: navigation to another Document` note;
  none affected an exit code.

PostgreSQL verification:

- Parsed and live identities were verified as `second_brain` and
  `second_brain_test` on `127.0.0.1:5433`.
- `alembic current`: `0009_memory_expiration (head)`.
- `alembic heads`: sole head `0009_memory_expiration (head)`.
- `alembic check`: `No new upgrade operations detected.`

Smoke test:

- The read-only browser smoke used `http://127.0.0.1:5173/search` through the
  Vite proxy and existing development data. Editing the query left the idle
  text visible and issued no automatic search. Explicit lexical submission
  reached the explained endpoint and returned one result.
- The focused results heading received focus. The result exposed backend rank
  1, an accessible `Why this matched` region, `Matched channels: Text`, lexical
  rank 1, and lexical signal `0.166667`. Its Memory detail link navigated to the
  existing detail screen successfully.
- Lexical success with no provider credentials, together with the backend
  provider-resolution tests in Full, confirms lexical mode resolves no
  provider. No semantic, hybrid, external, or paid provider call was made.
- Aggregate application-table counts were identical before and after.

API regression:

- Existing `searchMemories` remains unchanged. Its exact lexical GET and hybrid
  POST behavior passed focused frontend regression tests. All backend explained
  and legacy search tests passed in the 674-test Full run.

External calls:

- No paid or provider call occurred. The only network preflight was a read-only
  GitHub Actions API lookup.

Warnings:

- Checkpoint 57 preflight passed: `HEAD`, `main`, and `origin/main` were exactly
  `f6b9260ccf3d015e1ece38f20df62d97061bd13e`; the tree was clean; sole Alembic
  head was `0009_memory_expiration`; and `Second Brain CI` push run
  `30812460630` succeeded on attempt 1 without rerun at
  `https://github.com/DarkAxiom93/Second_Brain/actions/runs/30812460630`.
- The first Full invocation was made after smoke shutdown and failed only at
  its initial database identity connection because PostgreSQL was stopped; no
  test stage ran. PostgreSQL was restarted with the preserved volume, then one
  verification rerun completed successfully.
- The response stream disconnected after that successful `dev-up.ps1` plus
  Full command. Recovery inspection found no verification child process and
  recovered the original command cell's exact exit code 0 and complete output,
  including every successful stage. Full was therefore not rerun again.

Git status:

- All Checkpoint 58 changes are unstaged and uncommitted. Nothing was staged,
  committed, pushed, or submitted as a pull request.

Scope confirmation:

- Changed files are limited to the allowed Search/client/tests/style scope and
  Checkpoint 58 documentation listed above. No Checkpoint 59 work started.
- Final recovery inspection found no FastAPI, Vite, or verification child
  process. PostgreSQL was stopped with `docker compose ... stop db`; the
  container and named volume were preserved.

No report-template headings were omitted.
