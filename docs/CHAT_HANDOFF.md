# Second Brain chat handoff

Second Brain Local V1.1 is published as `v1.1.0` from exact commit
`88dffa90ff04cde4c57dcacbe2764b8a31b0c9ce`. The annotated tag peels to that
commit, and the GitHub Release is neither draft nor prerelease. Its exact
`Second Brain CI` push run is
[30842307666](https://github.com/DarkAxiom93/Second_Brain/actions/runs/30842307666),
completed successfully at the same SHA. Checkpoint 60 is complete at that
commit. `v1.0.0` remains unchanged as the pre-V1.1 recovery point at
`a1bf40c0a27e9ee508e9bf1ab151b4665fbdba32`.

The sole live/current Alembic head remains `0009_memory_expiration`, and Project
export remains `second-brain-project-export` format version 1. The V1.1 change
set is additive: patched direct `react-router` 8.3.0 with no
`react-router-dom`; least-privilege non-authoritative CI; read-only explained
Memory search and its accessible UI; and local acceptance. Legacy search and
Answer behavior and stored data remain compatible.

Checkpoint 61 is a planning/documentation checkpoint for Local V1.2. Its
proposed architecture is in [V1_2_AGENT_ROADMAP.md](V1_2_AGENT_ROADMAP.md), and
its actionable security requirements are in
[AGENT_THREAT_MODEL.md](AGENT_THREAT_MODEL.md). Checkpoint 61 remains pending
human review, Checkpoint 62 is not started, and no V1.2 Agent functionality
exists. Do not mistake an Agent Run for an Automation: V1.2 Runs are manually
initiated; Automation is a deferred future trigger that creates a Run.

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

Do not stage, commit, push, open a PR, begin Checkpoint 62, or create another
tag/Release without explicit instruction. Checkpoint 61 changes must remain
unstaged and uncommitted pending human review.
