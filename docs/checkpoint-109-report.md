# Checkpoint 109 report - Local V1.6 Unified Read-only Context Hub architecture

Status: **Approved and complete after human review.**

## Preflight

- Clean synchronized `main`, local HEAD, and refreshed `origin/main` were exact
  post-publication sync commit
  `81c3338fc2a212ea5c769c30b64a83a5b9034dbd`.
- Exact push CI run `33994596083` for that SHA completed successfully.
- Published annotated tag `v1.5.0` remained tag object
  `e8f281a0b805b887768e53a447fc9e3b4444e04b` and peeled to exact release commit
  `9c140dd83a84072743facefb55c2f56e91691535`.
- GitHub Release `383369546`, **Second Brain Local V1.5**, remained published,
  neither draft nor prerelease, with zero assets.
- Development Alembic current and sole head were
  `0016_calendar_event_observations`; `alembic check` found no upgrade operation.
- Tool Registry was `agent-tools-v1`; Project export was
  `second-brain-project-export` version `1`.

No preflight mismatch or architecture blocker was found.

## Decision and boundaries

Local V1.6 is the **Unified Read-only Context Hub**: one local federated find/
browse surface over local Source/Document/Chunk, V1.4 GitHub External Context,
and V1.5 Calendar External Context. It is not a source of truth and does not
pretend families share trust, provenance, freshness, state, or score semantics.

Every request selects exactly one Project or explicit unassigned scope; null
never means all. Results have a typed family/kind, exact scope, explicit
`local_audited` or `quarantined_external` trust, native state/freshness,
bounded inert text, and immutable typed provenance sufficient to reopen the
exact authoritative local record under the same scope.

The baseline uses fixed family grouping (`local_source`, `github`,
`google_calendar`) and no cross-provider score. Each family may use only a
documented deterministic PostgreSQL-local lexical/browse order and immutable
tie-breaker. Semantic/embedding, freshness, trust, and application state cannot
be mixed into an opaque score. Pagination is bounded and request-bound;
facets/filters are closed and typed.

Direct federation is sufficient. CP109 authorizes no projection, index,
persistence, migration, schema, or second source of truth. Any future projection
needs separate review of need, ownership, rebuild, recovery, drift, and non-
authoritative behavior.

Local audited provenance/ownership and search APIs remain exact. GitHub retains
account/allowlist/Project boundaries, revision/history/reconciliation, safe
generated links, quarantine, and its separate existing single-item import.
Calendar retains CP103 `current`/`stale`, no fabricated cancellation/deletion/
tombstone, fixed special/private labels, excluded fields, no content links, and
CP102 manual refresh as the sole request trigger.

Export remains `second-brain-project-export` version `1`; excluded GitHub/
Calendar runtime state, credentials, OAuth identity, raw payloads, Calendar
sensitive fields, provider authority, and hidden cross-Project IDs stay absent.
The Hub cannot refresh/import/write/schedule, mutate knowledge/workflows,
execute Tools, access provider/credential/model services, or grant Agent/
Automation authority. It is absent from `agent-tools-v1`.

## Threat model and roadmap

U01-U18 cover scope leakage, provider-ID substitution, forged IDs/cursors,
trust collapse, instruction injection, active/spoofing content, privacy leakage,
provenance confusion, stale/current errors, ranking manipulation, pagination/
filter tampering, exhaustion, hidden network, side effects, Agent/Automation
leakage, export leakage, configuration injection, and concurrency drift. Each
has a deterministic future strategy; CP113 requires unique no-skip mapping.

Proposed sequence: CP110 backend contract/foundation; CP111 typed API and
pagination/filtering; CP112 accessible frontend; CP113 U01-U18 gate; CP114 end-
to-end acceptance; CP115 release hardening. CP110 was not started.

## Verification

Focused stable-identity/export/migration/security checks: **44 passed**, zero
skipped. `git diff --check` also passed.

Full verification: **passed** after rerunning with required Windows Credential
Manager access. Backend: **1,341 passed**, zero skipped (13 warnings). Frontend:
**148 passed across 15 files**, zero skipped. `pip check`, Ruff lint, Ruff format
over 484 files, strict mypy over 203 production files, Alembic current/head/
check, frontend ESLint/TypeScript, the 88-module production Vite build, and
`git diff --check` all passed.

The initial sandboxed Full attempt reached **1,340 passed and 1 failed**, with
the sole failure reporting `credential_store_locked` in the required real
Windows adapter round-trip. It was not treated as a product result or hidden;
the authorized identical rerun with OS credential access passed all 1,341 tests.

## Exact changed paths

- `docs/ARCHITECTURE.md`
- `docs/CHECKPOINTS.md`
- `docs/ROADMAP.md`
- `docs/V1_6_CONTEXT_HUB_ROADMAP.md`
- `docs/V1_6_CONTEXT_HUB_THREAT_MODEL.md`
- `docs/checkpoint-109-report.md`

This checkpoint changes documentation only. It adds no production/test code,
dependency/lockfile, migration/schema, provider request/write/import/scheduling,
knowledge/workflow mutation, Agent/Automation capability, registry entry, or
export change. Published V1.5 is unchanged. Human review approved this
architecture and roadmap; CP109 is complete and CP110 has not started.
