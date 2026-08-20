# Checkpoint 71 report

Checkpoint: 71 - Advisory Memory Curator Agent (Pending human review)

## Preflight

- Base `HEAD`, `main`, and `origin/main` were exactly
  `f9581a5d7ab5b6595e174a5d58e1dcf1f5b7df45`; latest commit was
  `docs: finalize checkpoint 70 state`, divergence was `0 0`, and the worktree
  was clean before editing.
- Exact `Second Brain CI` push run `32405093071` matched the base SHA and `main`;
  attempt 1 was completed/success with zero artifacts.
- CP70 was Complete; CP71 and CP72 were Not started. Live Alembic current and
  sole head were `0010_agent_runtime_persistence`; `alembic check` reported no
  upgrade operations. Research and Project export remained version 1.

## Delivered boundary

- Immutable identity: kind `memory_curator`, version `1`, maximum authority
  `propose`. Unknown versions fail closed.
- Registry: unchanged `agent-tools-v1`. Exact allowlist: `memory.get` version 1
  and `memory.search_explained` version 1. Manual and Research remain compatible.
- Closed proposal catalog: exactly `memory.update`. Application code derives
  target/version, canonical hash, preview, fixed risk, expiry, one-time
  execution identity, Project scope, and initial `pending` status through CP68.
- Every finding and proposal is cited to evidence collected by the exact Run.
  Run/Step/Invocation ownership, nullable Project scope, existence, and versions
  are revalidated after provider latency. Invented, stale, uncited,
  unsupported, malformed, unsafe, or out-of-scope output fails closed.
- Duplicate proposals replay through CP68 identity; changed valid payloads are
  distinct. Existing explicit human approve/reject never executes the action.

## Safety, UI, and persistence

- Planning and Tool execution are read-only. Proposal creation occurs only in
  successful synthesis. The Curator cannot approve itself, execute, promote,
  generate embeddings, run maintenance writes, browse, or use arbitrary
  network/filesystem/shell/database capabilities.
- PostgreSQL coverage snapshots `projects`, `memories`, `memory_embeddings`,
  `sources`, and `source_chunks` across synthesis and human review; only expected
  Approval and Agent audit rows are added.
- `/agents` has a fixed Curator version 1 choice. Detail renders bounded
  findings, safe versioned evidence, proposed actions, and existing Approval
  status/review. Raw provider/Tool output, prompts, private identities, secrets,
  and hidden reasoning are not projected.
- No migration, dependency, CI, Docker, registry-version, or export-format
  change was made. Alembic remains `0010_agent_runtime_persistence`; Research
  and Project export remain version 1.

Checkpoint 71 is pending human review. Checkpoint 72 is not started.

## Verification

- Focused Curator/Approval/Research/recovery backend and PostgreSQL
  compatibility passed: 60 tests.
- Focused Curator backend files contain 27 collected cases: 8 unit/provider
  cases in `tests/test_curator_agent.py` and 19 PostgreSQL/API cases in
  `tests/integration/test_curator_agent_api.py`.
- `frontend/src/Agents.test.tsx` adds three Curator cases (fixed selection, safe
  rendering/review, and private-field rejection) and passes all 23 Agent UI
  cases.
- `scripts/verify.ps1 -Mode Full` passed: dependency integrity, Ruff lint and
  format, mypy, all 853 backend tests with zero skips, Alembic current/heads/
  check, frontend ESLint and TypeScript, all 114 frontend tests, production
  build, and `git diff --check`.

## Final acceptance audit remediation

The audit found and closed one critical stale-refresh race. Initial synthesis
revalidated observed evidence before CP68 acquired the target Memory lock; a
concurrent update in that interval could have caused proposal creation to
derive the newer version and silently refresh stale advice. Curator creation now
passes the exact observed application-owned version into a dedicated CP68-backed
entrypoint and requires equality after acquiring the target lock. A deterministic
PostgreSQL test mutates the Memory in that exact interval and proves the Run
fails with no Approval Request or Curator result.

The audit also tightened Curator-only entrypoint identity, version syntax,
secret-like proposed text, and duplicate provider proposals. Added deterministic
coverage proves: unknown and persisted-unknown versions fail closed; invented,
uncited, unsafe, unsupported-field, and duplicate synthesis rolls back; target
mutation after creation uses unchanged CP68 `superseded` review; exact replay
retains expiry/hash/execution identity; changed payloads are distinct; concurrent
exact creation yields one durable identity; cancellation/deadline winners discard
late output; provider failures expose stable safe codes; injection content stays
inert; protected domain and `memory_proposals` state does not change; and private
Curator fields are rejected by the UI projection validator.

Baseline reconciliation is 826 backend and 111 frontend cases before CP71.
Checkpoint 71 adds 27 backend cases and three frontend cases, producing final
totals of 853 and 114. Parameterized additions cover five malformed adapter
outputs, four provider failure classes, five invalid synthesis variants, and two
cancellation/deadline race winners; the remaining cases cover distinct
invariants rather than increasing counts cosmetically.
