# Checkpoint 73 report

Checkpoint: 73 — Local V1.2 end-to-end acceptance. Complete.
Checkpoint 74 is not started.

Human review approved the acceptance evidence. The exact implementation and
acceptance commit is `26c74cced438fd850907d593db5090719f6e861a`; it was pushed
to `origin/main`. Its exact `Second Brain CI` push run is
`32461508843`: branch `main`, event `push`, exact acceptance SHA, attempt 1,
completed/success, with zero artifacts.

## Preflight and environment

- Base `HEAD`, `main`, and `origin/main` were exactly
  `4d9b552c62492dc781f324218e7ea17a471e6531`; the latest subject was
  `docs: finalize checkpoint 72 state`, divergence was `0 0`, and the worktree
  was clean before editing.
- Authenticated GitHub CLI identified exact `Second Brain CI` run
  `32450698498` for that SHA: branch `main`, event `push`, attempt 1,
  completed/success, with zero artifacts.
- CP72 was `Complete`; CP73 and CP74 were `Not started`. Parsed and live
  identities were verified before acceptance: development
  `127.0.0.1:5433/second_brain` and isolated test
  `127.0.0.1:5433/second_brain_test`.
- Alembic current and sole head were `0010_agent_runtime_persistence`; registry
  was `agent-tools-v1`; Project export format was version `1`.
- Mutable scenarios used only `second_brain_test`. Development-database work was
  limited to identity, migration, diagnostics, and verification reads. The
  PostgreSQL service and named volume were preserved.

## API and Agent acceptance

The focused PostgreSQL/FastAPI acceptance set exercises the real application
surface and public schemas. It covers health/readiness, Projects, Memories,
Sources/chunks, explained search, Run create/list/read, strict nullable Project
scope, planning, bounded execution, cancellation, terminal replay, Approvals,
Research, Curator, safe failure, and recovery. Exact HTTP status, revision,
terminal-state, pagination, validation, conflict, and safe-error assertions are
owned by the cited integration modules and passed in the final Full run.

| Boundary | Accepted evidence |
| --- | --- |
| Manual | Existing Manual identity remains compatible. Create, replay/collision, Project/unassigned scope, planning, bounded read execution, cancellation, terminal replay, and public projection cases passed. |
| Research `research` / `1` | Fixed `read` authority and exact five-read allowlist passed. Scoped local evidence, deterministic citations, explicit insufficient evidence, stale evidence rejection, no proposal, no mutation, no external lookup, and cancellation/deadline winners passed. |
| Memory Curator `memory_curator` / `1` | Fixed maximum `propose` authority and exact `memory.get`/`memory.search_explained` allowlist passed. Findings are cited; only immutable `memory.update` Requests may be proposed. Stale targets fail closed. Human approve/reject never mutates Memory and no proposal execution exists. |
| Approval lifecycle | Create/list/read/review, exact replay, opposite-decision conflict, expiry, stale/moved/missing target supersession, concurrency, immutable hashes/identities, and safe public projections passed. |

## Failure and recovery

Deterministic unit and PostgreSQL cases passed for provider failure, Tool
failure, timeout, cancellation during work, cancellation/deadline race winners,
stale evidence/target, duplicate/replay, the single safe-read retry and retry
exhaustion, ambiguous/manual recovery boundaries, synchronous recovery, and
active-Run capacity rejection. Terminal Runs never resume, late provider/Tool
results never overwrite a terminal winner, and recovery remains explicit with
no worker, scheduler, polling, or startup recovery.

The live test-database browser scenario created one explicitly unassigned Manual
Run. With no configured planning provider, the UI first showed a generic safe
failure; explicit refresh then showed terminal `failed`, revision `2`, and safe
code `planning_provider_unavailable`. A racing cancel produced the expected
refresh-required conflict instead of overwriting the terminal failure.

## UI, Vite proxy, and accessibility

FastAPI ran on `127.0.0.1:8000` against only `second_brain_test`; Vite ran on
`127.0.0.1:5173` and `/api/ready` successfully proxied to the backend. Real
browser acceptance exercised all nine top-level routes and rendered their page
headings: `/` Dashboard, `/projects` Projects, `/sources` Sources, `/proposals`
Proposals, `/memories` Memories, `/search` Search, `/answers` Answers, `/agents`
Agent Runs, and `/settings` Settings. The Dashboard rendered Healthy, Ready,
and `Local services are ready` through the browser-facing proxy. `/agents`
covered Run creation/detail, Manual/Research/Memory Curator selection, explicit
unassigned scope, plan/execution/Approval regions, safe errors, conflict
refresh, and explicit refresh controls. Research and Curator
result/citation/proposal and Approval-review rendering are additionally covered
by the real frontend client contract suite against representative public
projections.

Research and Curator selection fixed kind/version to `research`/`1` and
`memory_curator`/`1` with both identity fields disabled. At 390 by 844 CSS
viewport (375 CSS-pixel document width), `scrollWidth` equaled `clientWidth`, all
nine navigation links and the main region remained present, and no redesign or
horizontal overflow appeared. Keyboard Tab focused Dashboard with a visible
2.66667px solid outline. Semantic headings, fieldset/legend scope, labels, live
status/alerts, focus-after-navigation/action, normal desktop structure, and the
existing reduced-motion rule passed static and frontend regression checks.

Source/runtime inspection and UI tests confirm no interval polling, automatic
planning/retry/approval/execution, `localStorage`, `sessionStorage`, IndexedDB,
or service worker. The final audit intentionally launched the test-database API
through the project virtual-environment process (captured launcher PID `70100`,
listener PID `32820`) and Vite directly as Node PID/listener `61244`. Cleanup
targeted only listener PIDs `32820` and `61244`; both listeners, both processes,
and launcher PID `70100` were then confirmed absent. No unrelated PID was
targeted. Both exact database identities were reverified afterward. No Docker
stop/down/volume command was issued, so PostgreSQL and its named volume remained
running and preserved.

## Privacy, security, and mutation gate

The executable CP72 T01–T24 matrix remains green with 48 collected checks.
Focused Agent security/API coverage passed after the single acceptance-test fix,
and the authoritative Full run includes the same matrix with zero skips.
Script/HTML evidence remains text, unsafe schemes do not become active links,
and secret-like canaries are absent from safe responses, durable safe fields,
and application logs. Public projections exclude raw provider/Tool payloads,
private Run/Step/Invocation IDs, proposal hashes and execution identities, raw
exceptions/SQL/prompts, connection details, and hidden reasoning.

The Curator protected-domain snapshot covers `projects`, `memories`,
`memory_embeddings`, `sources`, `source_documents`, `source_chunks`, and
`memory_proposals` across execution, proposal creation, Approval review, replay,
and conflict. Those rows remain byte-for-byte unchanged; only the expected
ApprovalRequest and Agent runtime/audit rows are added. Research and Manual
read-only scenarios provide complementary no-mutation evidence. This CP73 run
performed no mutable request against the development database.

## V1 export/import compatibility

Version-1 export/import integration passed against repository-owned fixtures:
an existing V1 bundle remains readable, deterministic export validates and
round-trips without runtime state, and import preserves the existing conflict
and atomicity rules. Agent Runs, Steps, Tool Invocations, Approval Requests,
Agent Events, provider/Tool payloads, and private execution identities remain
absent from `second-brain-project-export` version `1`. No format or migration
change was made.

## Defect and forward fix

Acceptance exposed one test-determinism defect, not a product behavior defect.
`test_create_replay_projection_and_review_never_mutate_target` selected its two
Agent Events without ordering and asserted `[0, 1]`; PostgreSQL validly returned
`[1, 0]`. The smallest forward fix adds `ORDER BY agent_events.sequence` to the
test query. The exact case passed three consecutive repetitions, and the
Approval plus T01–T24 focused gate passed 57 tests afterward. No application,
schema, API, registry, export, dependency, Docker, or CI behavior changed.

Before the fix, the assertion accidentally combined two concerns: it required
the exact durable sequences `[0, 1]` but also assumed PostgreSQL heap-return
order despite having no `ORDER BY`. After the fix, it asks PostgreSQL for the
contractual durable order and retains the identical exact-list assertion. That
assertion still fails for a missing event, an extra event, a sequence gap, or a
wrong sequence; the database also enforces unique `(run_id, sequence)`. The
change therefore cannot mask a duplicate or invalid durable event sequence. It
removes only the non-contractual physical-row-order assumption and leaves all
Approval creation, replay, review, no-Memory-mutation, safe-metadata, row-count,
and event-count assertions intact.

## Final acceptance audit

The final audit found no implementation, schema, security, lifecycle, or API
defect. It corrected only the report's evidence precision by recording the nine
routes actually exercised and the exact process lifecycle above. The changed
scope remained exactly the approved eight paths. Human review subsequently
approved that evidence, and the implementation/acceptance commit was pushed and
confirmed CI-green. CP72 remains Complete, CP73 is Complete at
`26c74cced438fd850907d593db5090719f6e861a`, and CP74 remains Not started.

## Verification

- Initial broad focused backend acceptance: 234 passed and one ordering-test
  failure; Agent/App frontend acceptance: 37 passed.
- Fixed ordering case: three consecutive passes. Approval plus T01–T24 focused
  gate: 57 passed.
- Final focused backend acceptance: 187 passed. Final focused frontend
  Agent/App acceptance: 37 passed. The CP72 T01–T24 gate passed 48/48.
- Authoritative `scripts/verify.ps1 -Mode Full`: dependency integrity, Ruff
  lint and format, mypy over 131 source files, all 914 backend tests, Alembic
  current/heads/check, frontend ESLint and TypeScript, all 114 frontend tests,
  production build, and `git diff --check` passed. Backend and frontend had zero
  skips. The backend emitted six known deprecation warnings; no check failed.

## Status and limitations

CP73 is `Complete` at `26c74cced438fd850907d593db5090719f6e861a` after human
review, push to `origin/main`, and successful CI run `32461508843` with zero
artifacts. V1.2 remains a trusted, single-maintainer, loopback-only application
without authentication, remote or multi-user operation, connectors, external
research, write/execute Tools, proposal execution, automatic
Approval/promotion, Automation, or background work. CP74 is `Not started` and
no CP74 work was begun.
