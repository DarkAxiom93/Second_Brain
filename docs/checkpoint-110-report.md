# Checkpoint 110 report - federated read/query backend foundation

Status: **Implemented; pending human review.** CP111 has not started.

## Preflight

- Clean synchronized `main` at exact HEAD
  `7e2df8fe733351ff298790c86d6a877a0c9f8e00` with `0 0` divergence.
- GitHub Actions run `34044895378` was completed/success for that exact SHA.
- Sole Alembic head `0016_calendar_event_observations`, Tool Registry
  `agent-tools-v1`, and Project export `second-brain-project-export` version `1`.

No mismatch or immutable-provenance architecture blocker was found.

## Contract and adapters

The frozen internal `context-hub-v1` contract requires exactly one `project_id`
or `unassigned=true`. Closed families are `local_source`, `github`, and
`google_calendar`; closed kinds are `source_chunk`, `repository`, `issue`,
`pull_request`, and `calendar_event`. Trust is fixed to `local_audited` or
`quarantined_external`. Native states are local `extracted`, GitHub
`current`/`stale`/`deleted`, and Calendar CP103-derived `current`/`stale`.
Duplicate, unknown, incompatible, both, and neither inputs fail closed.

Limits are 256 query characters/768 UTF-8 bytes, three families, five kinds,
two trust labels, four states, positive per-family page size through 50, 500
title characters, 4,000 text characters, and 200 Calendar candidates for
post-evidence state filtering. There are no free-form fields, sorts, SQL,
provider queries, expressions, URLs, methods, headers, Tools, or authority.

Local ownership reuses the exact `MemorySource -> Memory.project_id` boundary
and returns extracted document chunks only. GitHub selects the latest revision
per immutable account/resource/item identity and retains native history/state.
Calendar reuses CP103 eligible positive/covering-omission evidence and exposes
the exact evidence-run lineage; it fabricates no cancelled/deleted state.

Groups have fixed order `local_source`, `github`, `google_calendar`. Local order
is Source `created_at DESC`, Source UUID `ASC`, chunk index `ASC`, chunk UUID
`ASC`; GitHub and Calendar use application revision `DESC`, immutable revision
UUID `DESC`. There is no universal score, semantic/embedding signal, hidden
boost, provider freshness mixing, or Memory RRF reuse.

## Immutable reopen references

- Local: exact Source, SourceDocument, SourceChunk, chunk index, and content hash.
- GitHub: connector account, resource/item identity, exact revision row, and
  application revision; exact historical revisions remain reopenable.
- Calendar: account revision, calendar identity, occurrence key, exact event
  revision/application revision, eligible evidence run, and evidence version.

Every relationship and exact Project/unassigned scope is revalidated. The
contract excludes credentials/references, OAuth data, raw payloads, arbitrary
provider URLs, and excluded Calendar fields.

## Authority and persistence

The dependency graph contains SQLAlchemy reads and pure projection only: zero
provider, credential-store, HTTP/network, model, embedding, refresh, import,
scheduler, Tool, Agent, Automation, approval, export, or mutation capability.
External text remains bounded inert strings. No route, frontend, table,
projection, index, migration, schema, dependency, or second source of truth was
added, and existing migrations were not edited.

## Verification

Focused contract tests: **11 passed**, zero skipped. Focused PostgreSQL Context
Hub tests: **2 passed**, zero skipped. Coverage includes all-family Project and
explicit-unassigned isolation, both/neither rejection, grouping, filter
compatibility, bounds, exact reopen, cross-scope forgery rejection, inert text,
and stable registry/export boundaries.

The first restricted Full run reached **1,351 passed / 3 failed**. Two new-test
fixture defects were corrected; the remaining failure was the documented
restricted-context `credential_store_locked` boundary. Final elevated Full
verification then passed: `pip check`; Ruff lint and format over 490 files;
strict mypy over 206 production files; **1,354 backend tests passed**, zero
skipped (14 warnings); Alembic current/head/check at
`0016_calendar_event_observations` with no upgrade operations; frontend ESLint,
TypeScript, **148 tests across 15 files**, and the 88-module production build;
and `git diff --check`. The Credential Manager result was green outside the
restricted sandbox and required no production weakening or mock.

## Exact changed paths

- `app/calendar/query.py`
- `app/context_hub/__init__.py`
- `app/context_hub/models.py`
- `app/context_hub/service.py`
- `tests/test_context_hub.py`
- `tests/integration/test_context_hub.py`
- `docs/ARCHITECTURE.md`
- `docs/CHECKPOINTS.md`
- `docs/ROADMAP.md`
- `docs/checkpoint-110-report.md`

## Residual risk

CP110 intentionally has only conservative first-page exhaustion metadata and no
public cursor/facet/detail API; those remain CP111. Read-committed changes remain
visible between queries. Direct bounded `ILIKE` filtering and the Calendar work
cap should be measured before any separately reviewed index/projection decision.
