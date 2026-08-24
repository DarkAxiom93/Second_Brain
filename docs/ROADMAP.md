# Roadmap

This is a capability sequence, not a schedule.

## Published releases

Local V1 is published as `v1.0.0` from
`a1bf40c0a27e9ee508e9bf1ab151b4665fbdba32` and remains the pre-V1.1 recovery
point. Local V1.1 is published as `v1.1.0` from exact commit
`88dffa90ff04cde4c57dcacbe2764b8a31b0c9ce`. Checkpoint 60 is complete at that
commit. Local V1.2.1 is the current published V1.2 patch release, tagged
`v1.2.1` from exact commit `04e9db33dc0de7529b1599871c58cace6ed9f9e2`.
Local V1.2.0 remains intact as the preceding release from
`67e790f2f2c34b346773cddba385fa3f2db04a26`. The sole current Alembic head is
`0011_automation_persistence`, and Project export remains
`second-brain-project-export` version 1.

V1.1 adds the patched frontend dependency graph, least-privilege
non-authoritative CI, deterministic explained Memory search, its accessible UI,
and integrated acceptance. It preserves legacy search/Answer contracts, stored
data, deployment topology, and export/import format. Local Full verification
remains release-authoritative.

## Local V1.2

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
review UI at `e6324e52292e108d84666f88aeccf434c92ab39c`. Checkpoint 70 completed one
fixed, cited, read-only Research Agent at
`12a70f5e367db76cb4f0e05fb350acabc0230c3c`. Checkpoint 71 completed one fixed
advisory `memory_curator` version `1` at
`1dd8e83804c724e6790a704faa5ee13aad9dd3fe`. Checkpoint 72 completed the
T01-T24 Agent security/evaluation release gate and the 32-nonterminal-Run
capacity bound at `45e940ec89b6cf3783ab2dc7cdfa837b6cbc3597`; Checkpoint 73 local
acceptance is complete at `26c74cced438fd850907d593db5090719f6e861a`.
Checkpoint 74 release hardening is complete at
`53d78f30c7e9ff4020179c57e286ad24980df6af` after human approval and successful
push CI run `32474664878` with zero artifacts. V1.2.0 remains the preceding
published release. The unnumbered V1.2.1 live-provider and Agent reliability hardening is
published from `04e9db33dc0de7529b1599871c58cace6ed9f9e2` after successful
final pre-release CI run `32559057246`, attempt 1. Checkpoint 76 adds inert V1.3
Automation persistence only. No scheduling, approval execution, connector, or
write Tool exists.

The V1.2 capability is manually initiated, bounded, local Agent Runs
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

## Proposed Local V1.3

Checkpoint 75 completed the approved documentation-only
[Local Automations & Scheduled Agents](V1_3_AUTOMATION_ROADMAP.md) architecture
and its [V1.3 threat model](V1_3_AUTOMATION_THREAT_MODEL.md). Checkpoint 76 now
implements only the persistence foundation and is approved and complete after
human review.

The proposed scope is a local scheduler; typed one-time, daily, and weekly
Automation definitions; explicit enable/pause/cancel lifecycle; durable trigger
occurrences; fenced leases and duplicate prevention; deterministic restart,
retry, and missed-run behavior; bounded history; safe local notifications; and
fixed read-only Daily Brief and Project Watch Agents. An Automation is a durable
trigger that may create one bounded Agent Run per occurrence; it is never the
Run and grants no additional authority.

Automatic planning/execution is proposed only for explicit opt-in fixed
read-only Agents after a trigger-only scheduler and recovery foundation pass
independent review. The initial/default mode creates a Run for explicit human
execution. The independently reviewable implementation sequence is Checkpoints
76-86. Checkpoint 76 implements only the three-table persistence foundation and
is complete after human review; Checkpoint 77 has not started.

Connectors, arbitrary/external research or network access, external writes,
proposal execution, automatic Approval, credentials, authentication/multi-user,
remote/cloud/mobile operation, arbitrary execution, import merge/overwrite/
remap, and encrypted export redesign are deferred beyond V1.3 to separate
roadmaps and threat models.
