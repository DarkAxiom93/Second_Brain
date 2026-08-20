# Checkpoint 70 report

Checkpoint: 70 - Read-only Research Agent (pending human review)

## Preflight

- Base SHA, `main`, and `origin/main` were exactly
  `abab3c762a1d8fbc6a2bd633d4d37e3283d48b0e`, with divergence `0 0` and a
  clean working tree before implementation.
- The base commit was `docs: finalize checkpoint 69 state`.
- Authenticated GitHub CLI identified exact `Second Brain CI` push run
  `32291257318`: branch `main`, exact base SHA, attempt `1`, completed with
  conclusion `success`, and artifact count `0`.
- Live Windows-host configuration was `127.0.0.1:5433/second_brain`; live
  identity was `second_brain`. Alembic current and sole head were
  `0010_agent_runtime_persistence`; `alembic check` found no upgrade operations.
- CP69 was Complete, CP70 was Not started, and CP71 was Not started. Registry
  was `agent-tools-v1`; Project export version was `1`.

## Delivered boundary

The immutable definition is kind `research`, version `1`, authority `read`, and
registry `agent-tools-v1`. Its exact ordered allowlist is `project.get`,
`memory.get`, `memory.search_explained`, `source.get`, and `source_chunk.get`,
all version 1. Unknown Research versions fail closed. Manual Agent behavior is
preserved. Research planning exposes and accepts only these five definitions,
keeps the exact goal as untrusted data, and preserves existing budgets, policy,
retry, deadline, cancellation, and explicit Plan/Execute rules.

Synthesis receives only application-labelled transient evidence. Each bounded
substantive claim requires supplied evidence IDs. Invented and duplicate-invalid
references fail closed. Citation order is deterministic by first claim use.
Persisted output contains only status, claims, ordered public citations, and
safe insufficiency text in an existing append-only Agent event. Each citation
binds an allowlisted type, public UUID, and current deterministic version.
Memory versions reuse the CP68 target-version helper. Exact Run, Step,
ToolInvocation, scope, existence, and version are revalidated before commit.
Prompts, reasoning, provider payloads, raw Tool output, secrets, private IDs,
and arbitrary prose are not persisted or projected.

Empty evidence deterministically returns `insufficient_evidence` without
resolving a synthesis provider. Evidence instructions to change policy, scope,
Tools, authority, approvals, Memories, browsing, or secret handling remain inert
data. Research has no propose/execute authority, creates no Approval Request,
mutates no Project/Memory/Source/Chunk, and has no external research path.

The `/agents` UI adds a clear Research choice fixed to version `1`; Manual
identity remains editable. Detail renders only bounded status, claims, citation
numbers, and safe public entity identity/version. Refresh, Plan, and Execute
remain explicit; there is no polling, automation, browser persistence, or
external-research action.

No migration, dependency, CI, Docker, registry-version, or export-format change
was made. Alembic remains `0010_agent_runtime_persistence`, registry remains
`agent-tools-v1`, and Project export remains version `1`.

Checkpoint 70 is pending human review. Checkpoint 71 remains not started.

## Final acceptance audit remediation

The final audit found and corrected four fail-closed gaps before acceptance:

- Evidence identity/version is now captured inside the exact Tool handler that
  observed each row, rather than by a later lookup. Finalization still
  revalidates exact Run/Step/Invocation ownership, scope, existence, and current
  version. An intervening PostgreSQL Memory mutation now deterministically fails
  the Run without publishing a Research result while retaining the safe observed
  invocation evidence reference.
- The synthesis boundary now rechecks the Run deadline under the locked Run row.
  A deadline or cancellation that wins during provider latency discards the late
  result; no Research event is persisted. Recovery cannot complete a Research
  Run whose read Steps succeeded but whose durable Research result is missing.
- Research Runs are denied proposal creation in the Approval service itself, and
  the Research UI exposes no Approval controls.
- Provider unavailability, timeout, request failure, malformed/unknown/oversized
  output, uncited/empty answers, invented citations, excessive citations, and
  secret-like public text now have deterministic fail-closed validation or safe
  error codes without payload leakage.

The audit also added deterministic coverage for Project/Source/SourceChunk
version-significant mutable fields (including live SourceChunk content hashing),
exact Project/unassigned planning scope, cross-Run/Step/scope/missing/stale
evidence, prompt-injection variants, repeated-result determinism, synthesis
cancellation/deadline races, provider failures, safe insufficiency rendering,
and rejection of private citation fields. These changes remain within
Checkpoint 70; Checkpoint 71 was not started.
