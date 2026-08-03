# Second Brain chat handoff

Second Brain Local V1.1 is a release-hardened candidate pending human review.
It is not tagged or published. `v1.0.0` remains the stable release and recovery
point at `a1bf40c0a27e9ee508e9bf1ab151b4665fbdba32`. The sole Alembic head remains
`0009_memory_expiration`, and Project export remains
`second-brain-project-export` format version 1.

Checkpoints 55 through 59 are committed and pushed. The Checkpoint 59 commit is
`42fdfc8ee211835f0725f8d8b8da73020dbe83e6` (`docs: record local v1.1
acceptance`). Its exact `Second Brain CI` push run is
[30833738044](https://github.com/DarkAxiom93/Second_Brain/actions/runs/30833738044):
`main`, exact head SHA, completed `success`, attempt 1, zero artifacts.

The V1.1 change set is additive: patched direct `react-router` 8.3.0 with no
`react-router-dom`; least-privilege non-authoritative CI; the read-only
`POST /memories/search/explained` contract; its accessible Search UI; and local
acceptance. Legacy lexical, semantic, and hybrid search shapes and Answer
behavior are unchanged. There is no V1.1 migration or export-format change.

Checkpoint 60 changes documentation only. Its clean Python 3.12 installation,
locked frontend installation, zero-finding npm audit, inventory, security,
privacy, accessibility, compatibility, recovery, and final Full evidence are in
[checkpoint-60-report.md](checkpoint-60-report.md). Release-facing guidance is
in [LOCAL_V1_1_RELEASE_NOTES.md](LOCAL_V1_1_RELEASE_NOTES.md). Checkpoint 60
remains pending human review; its changes must remain unstaged and uncommitted.

Read `AGENTS.md`, [V1_1_ROADMAP.md](V1_1_ROADMAP.md),
[LOCAL_V1_RUNBOOK.md](LOCAL_V1_RUNBOOK.md), [VERIFICATION.md](VERIFICATION.md),
and [SAFETY.md](SAFETY.md) before further work. Use Python 3.12 from `.venv` and
only the verified `second_brain_test` database for integration tests. Never
downgrade or recreate `second_brain`, and never delete the PostgreSQL volume.

Do not stage, commit, push, open a PR, create a tag or Release, or begin another
checkpoint without explicit instruction. Publication of `v1.1.0` requires
separate approval after Checkpoint 60 human review.
