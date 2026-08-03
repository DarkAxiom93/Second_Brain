# Local V1 acceptance

Checkpoint 52 accepted the Local V1 capability set in release tree
`a1bf40c0a27e9ee508e9bf1ab151b4665fbdba32`. The released acceptance baseline
is `v1.0.0`, and the working tree was clean when it was published. Alembic
remains `0009_memory_expiration`. All eight top-level UI routes are functional.
The authoritative final command is `.\scripts\verify.ps1 -Mode Full`; see
`checkpoint-52-report.md` for the recorded
result and environmental limitations.

## Capability evidence

| Capability | Acceptance evidence |
|---|---|
| Dashboard health/readiness | Real Chrome at the Vite origin reported Healthy/Ready; `/api/health` and `/api/ready` returned through the proxy. |
| Projects | Real UI loaded the existing paginated list and detail link; creation, validation, safe failure, and pagination are covered by `Projects.test.tsx` and backend route/integration tests. |
| Sources and documents | Real top-level Sources route loaded its labelled creation form and empty state. JSON/TXT/PDF ingestion, Source detail, document metadata, chunks, validation, and missing/failure states are covered by `Sources.test.tsx`, `Documents.test.tsx`, and ingestion/source integration tests. |
| Proposals | Real review-queue route loaded. Generation, detail/evidence, approve, reject, promote, concurrency, and provider failures are covered by `Proposals.test.tsx` and proposal route/integration tests with fake providers. |
| Memories | Real UI listed the existing Memory, opened its detail, displayed provenance, refinement, supersede/expire controls, and similarity/contradiction advisories. Lifecycle success is covered by focused frontend and PostgreSQL tests. No destructive action was submitted. |
| Search | Real lexical search returned the existing Memory in backend order. Semantic and hybrid success and safe provider failure are covered by frontend, route, repository, and PostgreSQL tests. |
| Answers | Real labelled stateless form loaded. Evidence-backed success, citation order, empty evidence, validation, and provider failure are covered by `Answers.test.tsx` and answer tests; no provider call was submitted during acceptance. |
| Settings and maintenance | Real UI displayed health, safe diagnostics, aggregate counts, advisory maintenance findings, embedding coverage, and explicit export/import controls. There is no polling, retry loop, repair, migration, or embedding control. |
| Export/import | A real existing Project produced a non-empty 2,198-byte V1 bundle through the Vite proxy. The same bytes validated as valid but non-importable with one existing-Project conflict; execution remained unavailable and aggregate counts stayed at 1 Project/1 Memory. PostgreSQL round-trip integration tests provide successful import fidelity evidence. |
| Missing and safe failure states | The real catch-all route rendered a 404. Component and API tests cover missing entities, empty collections, validation, timeouts, malformed responses, generic provider/database failures, cancellation, and manual retry. |

## Release audits

- Clean backend rehearsal: a GUID-named virtual environment under `C:\tmp` was
  created with Python 3.12, installed from `.[dev]`, passed `pip check`, imported
  `app.main:app`, and was removed by exact verified path.
- Clean frontend rehearsal: `npm ci` left `package.json` and
  `package-lock.json` unchanged; ESLint, TypeScript, 78 Vitest tests, and the
  production build passed. No global install occurred.
- Accessibility/UX: keyboard Tab order traversed all navigation and available
  Settings controls with visible focus outlines; forms have accessible labels,
  validation focuses the first invalid field, live regions announce work and
  completion, statuses include text, long content wraps, and reduced-motion CSS
  is present. A confirmed 390px horizontal-overflow defect was fixed and a real
  browser recheck measured equal document client/scroll widths.
- Privacy/security: tracked/untracked artifact inspection found no real `.env`,
  bundle, database dump, volume data, or generated development data. Static and
  test audits found no browser persistence, service worker, unsafe CORS, raw
  vectors/bundle bytes/provider errors, prompt/reasoning exposure, or complete
  authenticated database URL in public UI contracts. Operation routes retain
  direct-loopback and distinct exact-header protection plus `no-store`.
- Request behavior: source review plus deterministic component tests confirm
  explicit requests, abort-on-unmount/replacement, no polling, no automatic
  retry, and bounded detail requests. Returned nested data and separate bounded
  relationship/advisory requests avoid accidental per-row N+1 behavior.

Provider-backed live success was deliberately not attempted because diagnostics
reported missing credentials and paid/external calls require explicit approval.
The Chrome extension lacked optional local-file upload permission; service-level
validation used the same exact exported bundle, and the UI bundle flow remains
covered by deterministic tests. Neither limitation changes application data.
