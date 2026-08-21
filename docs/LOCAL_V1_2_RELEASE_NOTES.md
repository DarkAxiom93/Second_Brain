# Local V1.2 candidate release notes

Status: release hardening is complete at
`53d78f30c7e9ff4020179c57e286ad24980df6af` after human approval. Exact
`Second Brain CI` push run `32474664878` completed successfully on attempt 1
with zero artifacts. Local V1.2 has not been published: no `v1.2.0` tag or
GitHub Release exists, and publication requires separate explicit human
approval. Local V1.1 `v1.1.0` remains the published release and recovery point.
No V1.3 work has started.

## Candidate inventory

Local V1.2 preserves the loopback-only FastAPI, React/Vite, and PostgreSQL
topology for one trusted maintainer. It adds manually initiated Agent Runs,
strict structured plans, a private `agent-tools-v1` registry of seven read-only
Tool definitions, bounded execution through five application-owned reads,
explicit cancellation and synchronous recovery, immutable Approval Requests,
the Agent Runs and Approval review UI, a fixed read-only Research Agent, and a
fixed advisory Memory Curator Agent.

The sole Alembic head is `0010_agent_runtime_persistence`. Project export
remains `second-brain-project-export` format version `1`: source bundles from
`0009_memory_expiration` and `0010_agent_runtime_persistence` are accepted, and
the current export/import target must be `0010_agent_runtime_persistence`.
Agent, Approval, provider, execution, and private runtime state is excluded
from Project bundles and is not mutated by import.

## Safety and privacy boundary

The CP72 deterministic T01-T24 gate remains release-critical. Agent Tools are
read-only; Approval is proposal and exact human review only. There is no
proposal execution, automatic Approval or promotion, Automation, scheduler,
worker, connector, external research, external write, arbitrary execution, or
remote/multi-user trust boundary. Public and persisted surfaces exclude raw
provider or Tool payloads, secrets, hidden reasoning, private runtime state,
and execution internals.

## Installation, verification, and recovery

Use [LOCAL_V1_RUNBOOK.md](LOCAL_V1_RUNBOOK.md) for the reproducible Windows
install, loopback startup, complete verification, full-database backup,
process cleanup, and recovery procedure. Project bundles are sensitive,
unencrypted, and incomplete as database backups because Agent and Approval
state is intentionally excluded.

Rollback uses a separate checkout of published V1.1 `v1.1.0` and a verified
revision-0009 backup restored only into a separate identity-checked database.
Never downgrade the revision-0010 development database or delete its named
volume to perform rollback.

## Remaining limitations

The trusted single-maintainer and loopback-only model, provider credential
requirements, unencrypted bundles, conflict-free-only import, stateless
Answers, and all deferred capabilities are recorded in
[KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md). Concrete Checkpoint 74 evidence
is recorded in [checkpoint-74-report.md](checkpoint-74-report.md).
