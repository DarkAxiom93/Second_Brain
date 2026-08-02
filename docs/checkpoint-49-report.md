# Checkpoint report

Checkpoint: 49 — Evidence-Backed Answers UI

Files changed: `frontend/src/Answers.tsx`, `frontend/src/Answers.test.tsx`, `frontend/src/App.tsx`, `frontend/src/App.test.tsx`, `frontend/src/api/client.ts`, `frontend/src/styles.css`, `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`, `docs/CHECKPOINTS.md`, `docs/CHAT_HANDOFF.md`, and this report.

Behavior: `/answers` provides a controlled, explicitly submitted Project/question/retrieval-mode/limit form. It keeps the displayed result until another explicit request succeeds, cancels obsolete submissions, guards duplicates, and provides initial, validation, loading, answer, empty-evidence, safe failure, malformed-response, and last-submission Retry states. No browser persistence, polling, automatic retry, streaming, history, or conversation behavior exists.

API: The UI reuses exactly `POST /answers` with `{query, project_id, search_mode, limit}`. Questions are trimmed and limited to 1–500 characters; Project is a nullable UUID; mode is lexical, semantic, or hybrid; limit is 1–20. The strict public response is `{answer_status, answer, search_mode, citations}`, where each returned citation has `label`, `rank`, `memory`, and nullable lexical/semantic scores. Provider/configuration details are mapped only from established safe backend detail strings; every other failure is generic.

Database: No migration, model, application row, database configuration, or CORS behavior changed. Alembic remains `0009_memory_expiration`.

Transactions: The frontend adds no persistence. The established backend answer operation remains read-only and rolls back its session.

Tests: Focused Answers and shell tests passed (19 tests). Full verification passed 630 Python tests and 68 frontend tests with zero skips. `pip check`, Ruff lint, Ruff format check, mypy, ESLint, TypeScript, non-watch Vitest, the production Vite build, Alembic current/heads/check, and `git diff --check` all passed. Pytest reported one existing Starlette/httpx deprecation warning.

PostgreSQL verification: Parsed and live development identity were verified as `second_brain`; parsed and live integration-test identity were verified as `second_brain_test`. Alembic current and sole head were `0009_memory_expiration`, and `alembic check` reported no new upgrade operations.

Smoke test: Passed through `http://127.0.0.1:5173`. PostgreSQL started with `.\scripts\dev-up.ps1`; FastAPI started with `.\scripts\start-api.ps1`; Vite started with `.\scripts\frontend-dev.ps1`. Each application readiness gate was bounded to 20 seconds. PostgreSQL became healthy on `127.0.0.1:5433`; FastAPI returned `{"status":"ok"}` from `/health` and `{"status":"ready"}` from `/ready`; the Vite proxy returned the same successful health/readiness results from `/api/health` and `/api/ready`. FastAPI and Vite remained running until exact-PID cleanup, so no successful service exited early.

Smoke readiness root cause: The previous combined launcher was the failing component. Its controller remained attached to a long-running child, its nominal 30-iteration readiness loop could consume approximately 75 seconds because each probe had a two-second timeout plus a 250 ms interval, and forced termination left Vite listening on 5173 while FastAPI was absent. Because that controller was forcibly terminated, it produced no normal process exit code. This run found the stale Vite listener by exact PID and stopped it. One diagnostic Vite start then exited early with npm/Vite exit code 1 because 5173 was occupied; its safe stderr reported only `Port 5173 is already in use`. After exact stale-listener cleanup, a fresh documented Vite start reported ready in 311 ms and passed the proxy gates. `.\scripts\dev-up.ps1` returned exit code 0. The successful FastAPI and Vite processes did not exit early, so their runtime exit code was not applicable before cleanup; their launcher cells completed with exit code 0 after the exact listener processes were intentionally stopped. `.\scripts\dev-down.ps1` returned exit code 0. PostgreSQL, FastAPI, Vite, and the Vite proxy have no Checkpoint 49 defect.

Vite-origin checks: `/answers` returned HTTP 200 and rendered the functional Answers screen. Before any submission it showed the initial answer state and all supported controls: Project UUID, question, lexical/semantic/hybrid retrieval mode, and evidence limit. Activating Submit with an empty question produced the local `Enter a question.` alert and moved focus to `#answer-question`. Editing a safe local draft left the initial answer state unchanged. `/settings` retained its existing future-screen placeholder. Safe FastAPI access logs contained only `GET /health` and `GET /ready`; no `POST /answers` occurred. No provider was resolved or called, and no answer, evidence, prompt, credential, provider configuration, or database URL was logged.

Pre/post database counts: Parsed and live identity were verified as development database `second_brain`. Counts were identical before and after smoke: projects 1, memories 1, and zero in sources, memory_sources, memory_embeddings, source_documents, source_chunks, memory_extraction_runs, and memory_proposals. No application row was created, updated, or deleted.

Provider and CORS status: No answer was submitted, no provider credential was added, and no provider call occurred. Browser traffic remained same-origin through Vite; no CORS change was needed.

Services and ports: Cleanup stopped the exact Vite and FastAPI listener PIDs before `.\scripts\dev-down.ps1` stopped PostgreSQL. Final checks confirmed ports 5173, 8000, and 5433 closed. The PostgreSQL container and named volume were preserved. Only the exact `.smoke-cp49-temp` directory created by this run was removed.

API regression: No backend route, schema, repository, prompt, provider, retrieval, ranking, evidence, usage, dependency, or migration changed. Citation order and public values are rendered without rewriting or client-created citations. Returned Memory IDs link to `/memories/{memoryId}`. The public answer response has no Source IDs, so the UI neither invents Source links nor performs prohibited N+1 detail requests.

External calls: Focused tests mock only the frontend HTTP boundary. No provider credential was added and no external provider call was made.

Warnings: Source navigation cannot be supported from the existing answer response because it returns no public Source or SourceDocument ID. This is handled without a backend change, fabrication, or follow-up lookup. Browser console noise came only from an unrelated installed Chrome extension; no application-origin console error was observed. The first Full attempt failed at database identity verification because PostgreSQL was stopped; after safely starting the existing container, the authoritative Full run passed completely.

Additional file changes: This completion pass changed only this report. No application code, test, script, configuration, dependency, migration, or other documentation file changed during the smoke investigation.

Verification evidence: The completed authoritative Full verification remains valid: 630 Python tests and 68 frontend tests passed with zero skipped, alongside pip check, Ruff, mypy, ESLint, TypeScript, production build, Alembic checks, and `git diff --check`. Because the investigation found no code defect and changed only this report, Full was not repeated.

Alembic: Current and sole head remain `0009_memory_expiration`; no migration changed.

Checkpoint 49 approval readiness: Ready for review. Implementation, Full verification, live Vite-origin smoke, no-mutation evidence, provider abstention, cleanup, and reporting are complete.

Git status: Checkpoint 48 is committed and pushed; `main` matched `origin/main` at `3c469f0` before work. No Checkpoint 49 file is staged, committed, or pushed.

Scope confirmation: Checkpoint 49 only. No backend, migration, dependency, authentication, persistence, chat, automatic provider call, PR, commit, push, or Checkpoint 50 work was added.
