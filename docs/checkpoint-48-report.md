# Checkpoint report

Checkpoint: 48 — Lexical, Semantic, and Hybrid Search UI

Files changed: `frontend/src/Search.tsx`, `frontend/src/Search.test.tsx`, `frontend/src/App.tsx`, `frontend/src/App.test.tsx`, `frontend/src/api/client.ts`, `frontend/src/styles.css`, `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`, `docs/CHECKPOINTS.md`, `docs/CHAT_HANDOFF.md`, and this report.

Behavior: `/search` provides one controlled, explicitly submitted form for lexical, semantic, and hybrid Memory retrieval. Editing does not search. The submit button is disabled while active, duplicate submissions are guarded, a newer run aborts the previous controller, and Retry repeats only the last explicit submission. Validation focuses the first invalid query, Project, or limit control. Loading, populated, empty, provider/configuration, malformed-response, and generic failures render safely.

API: Lexical uses only `GET /memories` with trimmed `query`, established structured query parameters, `limit`, and `offset=0`. Semantic and hybrid use only `POST /memories/search` with `{query, mode, filters, pagination:{limit, offset:0}}`. Query length is 1–500 and limit is 1–100. Supported UI filters are `project_id`, `memory_type`, `status`, `importance_min`, `importance_max`, `confidence_min`, and `confidence_max`. Responses are strictly validated bare `MemoryRead[]`; no second HTTP layer or automatic retry exists.

Database: No migration, model, data, or database behavior changed. Parsed and live identities were verified as development `second_brain` and test `second_brain_test` without printing complete URLs.

Transactions: Search remained read-only. Safe aggregates immediately before and after the final lexical smoke request were identical: projects 1, memories 1, and zero in sources, memory_sources, memory_embeddings, source_documents, source_chunks, memory_extraction_runs, and memory_proposals.

Tests: Focused Search: 9 passed. Full verification: 630 Python tests passed and 62 frontend tests passed, with zero skipped tests. `pip check`, Ruff lint, Ruff format check, strict mypy, ESLint, TypeScript, production Vite build, Alembic current/heads/check, and `git diff --check` all passed. Pytest reported two existing warnings: one Starlette/httpx deprecation and one Pydantic field-attribute warning.

PostgreSQL verification: `scripts/dev-up.ps1` started the existing container healthy on loopback port 5433. Parsed/live identities passed. Alembic current and sole head were `0009_memory_expiration`; `alembic check` reported no new upgrade operations. The single Full run passed.

Smoke test: Passed through `http://127.0.0.1:5173`. `/search` loaded with no automatic result request; invalid empty input was rejected locally and focus moved to `#search-query`. Editing left the results region unchanged. One explicit lexical search returned one result in backend order with a `/memories/{memoryId}` link. A forced safe API-unavailable state exposed Retry; Retry repeated the last lexical submission and retained the safe generic failure. Semantic and Hybrid (RRF) controls rendered but were not submitted. `/answers` remained the unchanged placeholder. A final lexical request through the Vite origin returned HTTP 200. No Memory content, evidence, vector, credential, configuration value, or complete database URL is recorded here.

API regression: No backend route, schema, repository, ranking, retrieval, embedding, provider, answer, or CORS behavior changed. Browser results use only `MemoryRead`; no N+1 detail requests occur.

External calls: No provider call occurred. Semantic and hybrid were not submitted during live smoke. Whitelisted 502/503 embedding failures map to fixed safe UI messages; all other failures use a generic safe error without rendering response bodies.

Warnings: Public search responses expose no lexical, semantic, RRF, or component scores. The UI displays the one-based backend result position as rank, states that scores are not exposed, preserves array order, and never normalizes, fuses, recomputes, compares, or reranks results.

Git status: `main` matches `origin/main` at Checkpoint 47. No file is staged. Only intended Checkpoint 48 files are modified or untracked. Checkpoint 48 is not committed or pushed.

Scope confirmation: Checkpoint 48 only. No dependency, migration, backend, authentication, browser persistence, polling, search history, automatic retry, reranking, query expansion, provider fallback, PR, commit, push, or Checkpoint 49 work was added.

Service cleanup: Chrome smoke tab finalized. Vite, FastAPI, and PostgreSQL stopped in order. Ports 5173, 8000, and 5433 have no listeners. Exact temporary smoke logs were removed. Docker named volumes `second-brain-lab-postgres-data` and `second-brain_postgres_data` remain preserved.
