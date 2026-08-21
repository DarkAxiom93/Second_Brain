# Second Brain chat handoff

Second Brain Local V1.1 is published as `v1.1.0` from exact commit
`88dffa90ff04cde4c57dcacbe2764b8a31b0c9ce`. The annotated tag peels to that
commit, and the GitHub Release is neither draft nor prerelease. Its exact
`Second Brain CI` push run is
[30842307666](https://github.com/DarkAxiom93/Second_Brain/actions/runs/30842307666),
completed successfully at the same SHA. Checkpoint 60 is complete at that
commit. `v1.0.0` remains unchanged as the pre-V1.1 recovery point at
`a1bf40c0a27e9ee508e9bf1ab151b4665fbdba32`.

The sole live/current Alembic head is `0010_agent_runtime_persistence`, and Project
export remains `second-brain-project-export` format version 1. The V1.1 change
set is additive: patched direct `react-router` 8.3.0 with no
`react-router-dom`; least-privilege non-authoritative CI; read-only explained
Memory search and its accessible UI; and local acceptance. Legacy search and
Answer behavior and stored data remain compatible.

Checkpoint 61 is complete at `850cfd0a749b5de072b910203ba9906ab5270b40`. Its
proposed architecture is in [V1_2_AGENT_ROADMAP.md](V1_2_AGENT_ROADMAP.md), and
its actionable security requirements are in
[AGENT_THREAT_MODEL.md](AGENT_THREAT_MODEL.md). Checkpoint 62 is complete at
`3da0cdd875dc8af7a60fd8af5b6f9878be5a769a`. Checkpoint 63 is complete at
`01832a94ae6f80bdacd0cd9301af3f294302e3e8`. Checkpoint 64 completed the private,
immutable `agent-tools-v1` registry with exactly seven version-1 `read`/
`pure_read` definitions and a pure fail-closed policy resolver at
`35950c60fd842a4ad022f130a3074ce8d21d9bbc`. New Runs capture this version and
replayed older Runs retain their original value. Checkpoint 65 completed strict,
durable frozen planning at `1b32d91e62feb10efd5c2f2c241ee43b75b5b5e2`.
Checkpoint 66 completed bounded read-only execution at
`d4a3533282a8ed616fa0910fcea99b07b0f1b878`, with successful CI run
`31959234267`. Checkpoint 67 completed idempotency, one global classified safe-read
retry, cancellation/deadline reconciliation, stale detection, and explicit
synchronous single-Run operator recovery at
`7b6c6bb8c4c67f9e8a5a34c363331bc94dbb094e`; its exact successful `Second Brain
CI` push run is `32025350296` (attempt 1, completed/success, zero artifacts).
Checkpoint 68 is complete at
`1bc90b4339bd5466fda10e5d04711e3f025a0e01`; its exact successful `Second Brain
CI` push run is `32219122039` (attempt 1, completed/success, zero artifacts). It adds exactly four
Approval APIs and one proposal-only `memory.update` definition with human-only
review, expiry, and stale-target handling. Approval cannot mutate a Memory or
execute an action. Checkpoint 69 is complete at
`e6324e52292e108d84666f88aeccf434c92ab39c`; its exact successful `Second Brain
CI` push run is `32273491445` (attempt 1, completed/success, zero artifacts).
It adds the accessible `/agents` and `/agents/:runId` UI with explicit Run
creation, planning, bounded read-only execution, cancellation, refresh, and
exact Approval review. There is no approval execution, Automation, connector,
or external behavior. Do not mistake an Agent Run
for an Automation: V1.2 Runs are manually
initiated; Automation is a deferred future trigger that creates a Run.

Checkpoint 70 is complete at
`12a70f5e367db76cb4f0e05fb350acabc0230c3c`; its exact successful `Second Brain
CI` push run is `32401692854` (attempt 1, completed/success, zero artifacts).
It adds the immutable `research` version `1` Agent with `read` authority and the
exact five-Tool allowlist `project.get`, `memory.get`,
`memory.search_explained`, `source.get`, and `source_chunk.get`. Its substantive
answered claims require deterministic versioned citations; stale or intervening
evidence fails closed, and empty evidence returns explicit insufficiency. It
cannot mutate domain state, create Approvals or proposals, perform external
research, poll, retry automatically, or persist browser state.

The proposed initial runtime is bounded and read-only. Code-owned versioned
tools, strict structured plans, nullable Project isolation, exact immutable
human approval foundations, safe audit state, cancellation/recovery, and
deterministic fake-provider/tool evaluation are required. Model output cannot
grant authority. Initial execute authority, scheduled/recurring automation,
workers, connectors, external writes, arbitrary execution/network access, and
cloud/remote/multi-user/mobile operation are excluded.

Before further work, read `AGENTS.md`, [ARCHITECTURE.md](ARCHITECTURE.md),
[ROADMAP.md](ROADMAP.md), [CHECKPOINTS.md](CHECKPOINTS.md),
[VERIFICATION.md](VERIFICATION.md), [SAFETY.md](SAFETY.md),
[API_CONVENTIONS.md](API_CONVENTIONS.md), the V1.2 roadmap/threat model, and the
relevant ADRs. Use Python 3.12 from `.venv` and only the verified
`second_brain_test` database for integration tests. Never downgrade or recreate
`second_brain`, and never delete the PostgreSQL volume.

Checkpoint 71 is complete at
`1dd8e83804c724e6790a704faa5ee13aad9dd3fe`; its exact successful `Second Brain
CI` push run is `32410053222` (attempt 1, completed/success, zero artifacts). It
adds immutable `memory_curator` version `1` with `propose` maximum authority,
exactly `memory.get` and `memory.search_explained`, bounded cited advice, and
only immutable `memory.update` Approval Requests. No proposal execution or
domain mutation exists.

Checkpoint 72 is complete at
`45e940ec89b6cf3783ab2dc7cdfa837b6cbc3597`; its exact successful `Second Brain
CI` push run is `32416546227` (attempt 1, completed/success, zero artifacts).
Its executable release gate covers T01-T24 with 48 matrix checks, 240 focused
Agent security tests, 23 focused Agent UI tests, 914 backend tests, and 114
frontend tests, all with zero skips. T24 adds a PostgreSQL-serialized maximum of
32 nonterminal Runs while preserving exact replay at capacity and safe rejection
of new distinct Runs. Checkpoint 73 local acceptance is complete at
`26c74cced438fd850907d593db5090719f6e861a`; its exact successful `Second Brain
CI` push run is `32461508843` (attempt 1, completed/success, zero artifacts).
Checkpoint 74 release hardening is complete at
`53d78f30c7e9ff4020179c57e286ad24980df6af` after human approval. Its exact
successful `Second Brain CI` push run is `32474664878` (attempt 1,
completed/success, zero artifacts), and its evidence is in
`checkpoint-74-report.md`. Local V1.2 is not published; no `v1.2.0` tag or
GitHub Release exists. Publication requires separate explicit human approval,
and no V1.3 work has started.
