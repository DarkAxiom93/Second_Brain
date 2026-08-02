# Second Brain chat handoff

Checkpoint 50 is implemented locally and awaits review. Checkpoint 49 is
committed and pushed at `3fb5b7b`; `main` matched `origin/main` and the working
tree was clean before Checkpoint 50 work began. Alembic remains
`0009_memory_expiration`.

Checkpoint 50 replaces the `/settings` placeholder with a read-only local
operations dashboard. Initial load and explicit manual Refresh request the
existing `/health` and `/ready` routes plus new aggregate-only
`GET /operations/diagnostics` and `GET /operations/maintenance-audit` routes.
There is no polling, automatic retry, browser persistence, provider resolution,
repair, migration, embedding generation, or other mutation control.

The diagnostics route reuses the established diagnostics checks inside the
existing request Session and a database-enforced read-only transaction. The
public response includes only status, capture time, warning/failure counts,
deterministically ordered checks with `check_id`, `category`, `status`, and safe
message, plus safe aggregate entity counts. It excludes the target database and
all diagnostic metadata.

The maintenance route reuses the established audit with `detail_limit=0` and
returns total/assigned/unassigned Memories, status counts, and deterministic
aggregate findings. It excludes Memory UUID samples and truncation details.
The audit service has no correct Project-scoping contract, so the API does not
offer a Project filter.

Maintenance findings are advisory and the dashboard performs no automatic
repair. Existing maintainer workflows remain available through
`scripts/export-project.ps1` and `scripts/import-project.ps1`; Export and Import
UI are deferred to Checkpoint 51.

Read `AGENTS.md` and the stable docs before further work. Use Python 3.12 from
`.venv`, use only the verified `second_brain_test` database for integration
tests, never downgrade development or delete its volume, never expose secrets,
and do not commit or push without explicit approval. Review
`docs/checkpoint-50-report.md` for final verification and smoke evidence.
