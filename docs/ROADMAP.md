# Roadmap

This is a capability sequence, not a schedule.

## Published releases

Local V1 is published as `v1.0.0` from
`a1bf40c0a27e9ee508e9bf1ab151b4665fbdba32` and remains the pre-V1.1 recovery
point. Local V1.1 is published as `v1.1.0` from exact commit
`88dffa90ff04cde4c57dcacbe2764b8a31b0c9ce`. Checkpoint 60 is complete at that
commit. The sole current Alembic head is `0010_agent_runtime_persistence`, and Project
export remains `second-brain-project-export` version 1.

V1.1 adds the patched frontend dependency graph, least-privilege
non-authoritative CI, deterministic explained Memory search, its accessible UI,
and integrated acceptance. It preserves legacy search/Answer contracts, stored
data, deployment topology, and export/import format. Local Full verification
remains release-authoritative.

## Local V1.2 proposal

Checkpoint 61 completed the [Local V1.2 Agent roadmap](V1_2_AGENT_ROADMAP.md) and
[threat model](AGENT_THREAT_MODEL.md) at
`850cfd0a749b5de072b910203ba9906ab5270b40`. Checkpoint 62 is complete at
`3da0cdd875dc8af7a60fd8af5b6f9878be5a769a`. Checkpoint 63 is complete at
`01832a94ae6f80bdacd0cd9301af3f294302e3e8`. Checkpoint 64 completed the private,
immutable `agent-tools-v1` seven-definition read-only registry and pure policy
resolver at `35950c60fd842a4ad022f130a3074ce8d21d9bbc`. Checkpoint 65 adds bounded
structured planning and is complete at
`1b32d91e62feb10efd5c2f2c241ee43b75b5b5e2`. Checkpoint 66 completed synchronous,
ordered execution through exactly five scoped application reads at
`d4a3533282a8ed616fa0910fcea99b07b0f1b878`. Checkpoint 67 completed one
safe-read retry, deterministic cancellation/deadline reconciliation, and
explicit synchronous operator recovery at
`7b6c6bb8c4c67f9e8a5a34c363331bc94dbb094e`. Checkpoint 68 is complete at
`1bc90b4339bd5466fda10e5d04711e3f025a0e01`. It adds immutable `memory.update` proposals and exact
human approve/reject review without target mutation or execution authority.
Checkpoint 69 completed the accessible manual Agent Runs and exact Approval
review UI at `e6324e52292e108d84666f88aeccf434c92ab39c`. Checkpoint 70 is pending
human review with one fixed, cited, read-only Research Agent. No approval execution, Automation,
connector, propose authority, or write Tool exists.

The proposed V1.2 capability is manually initiated, bounded, local Agent Runs
with structured planning, application-owned read-only tools, durable safe state,
cancellation/recovery, immutable proposed actions for exact human review, an
accessible Runs/Approvals UI, a read-only Research Agent, an advisory Memory
Curator Agent, and deterministic security/quality evaluation. An Agent Run is
not an Automation: Automation is a future trigger that creates a Run.

The independently reviewable sequence is:

1. 62 - Agent Runtime persistence foundation.
2. 63 - Agent Run state machine and API.
3. 64 - Tool Registry and policy enforcement.
4. 65 - Structured planning provider.
5. 66 - Bounded read-only executor.
6. 67 - Idempotency, cancellation, recovery, and failure injection.
7. 68 - Approval and proposed-action foundation.
8. 69 - Agent Runs and Approval UI.
9. 70 - Read-only Research Agent.
10. 71 - Advisory Memory Curator Agent.
11. 72 - Agent security and evaluation harness.
12. 73 - Local V1.2 end-to-end acceptance.
13. 74 - Local V1.2 release hardening.

V1.2 excludes scheduled/recurring Automations, background workers, external
connectors or writes, autonomous approval, execute authority in the initial
runtime, arbitrary shell/Python/SQL/filesystem/browser/network access, and
cloud, remote, multi-user, or mobile operation.

## Completed foundation

Completed capabilities include PostgreSQL persistence; normalized sources;
lexical, semantic, hybrid, and explained search; optional embeddings; TXT/PDF
ingestion; AI proposals with human review and explicit promotion; advisory
quality detection; explicit supersession, expiration, and quality refinement;
evidence-backed answers; batch embedding/re-embedding; read-only maintenance
and diagnostics; versioned Project export and controlled import; all eight
top-level local UI routes; non-authoritative CI; and V1/V1.1 acceptance.

## Deferred Local V1.3 and later

V1.3 may plan a local scheduler, one-time/recurring Automation definitions,
leases and duplicate prevention, pause/resume/retry/missed-run policy,
notifications, Daily Brief and Project Watch agents, local credentials,
read-only Calendar/Gmail/GitHub connectors, draft-only external actions, and
exact approval-gated external writes. Authentication, multi-user isolation,
remote/cloud/mobile operation, import merge/overwrite/remap, encrypted bundles,
and other expanded boundaries require their own later roadmaps. Checkpoint 61
authorizes none of this implementation.
