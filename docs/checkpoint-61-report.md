# Checkpoint report

Checkpoint: 61 - V1.2 Agent roadmap and threat model. Status remains pending
human review. Checkpoint 62 is not started.

Files changed: `README.md`; `docs/ARCHITECTURE.md`; `docs/ROADMAP.md`;
`docs/CHECKPOINTS.md`; `docs/CHAT_HANDOFF.md`;
`docs/KNOWN_LIMITATIONS.md`; new `docs/V1_2_AGENT_ROADMAP.md`; new
`docs/AGENT_THREAT_MODEL.md`; and this report.

Behavior: Documentation and planning only. No Agent Runtime, database model,
migration, API, frontend screen, scheduler, connector, provider, tool,
automation, or application behavior was implemented.

Preflight:

- `HEAD`, `main`, and `origin/main` were exactly
  `88dffa90ff04cde4c57dcacbe2764b8a31b0c9ce`; divergence was `0 0`, and the
  working tree was clean before editing.
- `Second Brain CI` run
  [30842307666](https://github.com/DarkAxiom93/Second_Brain/actions/runs/30842307666)
  was event `push`, workflow `Second Brain CI`, exact head SHA, status
  `completed`, and conclusion `success`.
- Annotated tag `v1.1.0` existed and peeled exactly to the required commit. The
  published [v1.1.0 Release](https://github.com/DarkAxiom93/Second_Brain/releases/tag/v1.1.0)
  existed and was neither draft nor prerelease.
- Annotated `v1.0.0` remained unchanged and peeled to
  `a1bf40c0a27e9ee508e9bf1ab151b4665fbdba32`; its published Release remained
  neither draft nor prerelease.
- After safely starting only the existing PostgreSQL service, the live current
  and sole Alembic head were both `0009_memory_expiration`; the named volume was
  preserved.
- The application constants and format documentation still identify
  `second-brain-project-export` version 1.

Architecture: The roadmap separately defines Agent Run, Agent Step, Tool, Tool
Invocation, Approval Request, Agent Event, and future Automation. It defines
strict `read`, `propose`, and `execute` authority while withholding execute
authority from the initial runtime and denying model authority. It specifies
the state machine, persistence/privacy boundary, versioned Tool Registry,
structured plan contract and budgets, immutable exact approvals, recovery,
observability, deterministic evaluation, Checkpoints 62-74, and deferred V1.3.

Threat model: The actionable register covers prompt injection, invented tools,
malformed output, authority/approval attacks, replay/duplicates, loops/bounds,
stale state and races, provider/tool/database failures, Project isolation,
secrets/logging/output/links, audit integrity, cancellation, policy drift,
citation fabrication, and capacity. Each entry records asset/path, impact,
prevention, detection, recovery, and required tests.

API: No API change. Later API impacts are proposals only and require their own
checkpoint reviews.

Database: No database, model, migration, stored-data, Docker, or export-format
change. Live current and sole head remain `0009_memory_expiration`; export
remains `second-brain-project-export` version 1.

Transactions: No application transaction was added or changed. The roadmap
proposes service/route ownership, repository non-commit behavior, short
row-locked transition transactions, provider/tool calls outside transactions,
and atomic audit/idempotency facts for later review.

Tests: The focused changed-document relative-link audit passed, and the focused
`git diff --check` passed. Release-authoritative
`.\scripts\verify.ps1 -Mode Full` passed in 147.3 seconds: `pip check`; Ruff
lint and format over 257 files; mypy over 98 source files; all 674 backend tests;
Alembic current, heads, and check; frontend lint and type checking; all 90
frontend tests in 10 files; production build; and final `git diff --check`.
There were zero test failures or skips.

PostgreSQL verification: Full verified parsed/live development identity as
`127.0.0.1:5433/second_brain` and test identity as the separate
`second_brain_test`. Alembic current and sole head were
`0009_memory_expiration`; `alembic check` reported no new upgrade operations.
After verification, `dev-down.ps1` stopped only the database service; its
container and named volume were preserved.

Smoke test: No live UI/API smoke is required because this checkpoint changes
documentation only and implements no behavior.

API regression: The complete 674-test backend and 90-test frontend suites passed
with no API or application change.

External calls: Read-only GitHub API calls verified the required CI and Release
facts. No application provider or paid call occurred.

Warnings: The first sandboxed GitHub request was denied network access and was
repeated with approved read-only access. The first Alembic command inherited
the Compose-only `db` host and could not resolve it; the documented Windows URL
was then used after safely starting the existing database service. Neither
attempt changed application data. Pytest emitted the existing Starlette
TestClient deprecation warning and a cache warning because sandbox permissions
prevented `.pytest_cache` creation; verification still passed and its isolated
temporary test directory was used. The frontend test environment emitted its
existing `Not implemented: navigation to another Document` diagnostic. Git
reported expected LF-to-CRLF working-copy notices for updated tracked Markdown.

Git status: Exactly six tracked documentation files are modified and three new
documentation files are untracked. All nine are unstaged and uncommitted.

Scope confirmation: Checkpoint 61 only. No application, API, migration,
dependency, lockfile, CI, Docker, database, provider, tag, Release, stage,
commit, push, PR, or Checkpoint 62 work.
