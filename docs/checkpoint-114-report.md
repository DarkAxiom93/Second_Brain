# Checkpoint 114 report - Local V1.6 end-to-end acceptance

Status: **Implemented and fully verified; pending human review.** CP115 has not
started.

## Preflight and scope

CP114 began on clean synchronized `main` at exact HEAD
`cf9a05dd5d4fce99f4d66fe6c202594c35c039aa`. Local tracking and live remote
`main` matched with `origin/main...main = 0 0`; exact push run `34525995099`
was `completed` / `success` for that SHA. No production code, migration,
schema, dependency, provider scope, Tool, Agent, Automation, export format, or
CP115 behavior changed.

## Joined journey and seeded scopes

The CP114 integration gate uses real FastAPI `/context-hub/query`, `/facets`,
and `/detail` routes, real services/repositories, and PostgreSQL
`second_brain_test`. It seeds Project A, Project B, and explicit unassigned
independently. Every scope contains two audited Source -> Document -> Chunk
graphs, two persisted GitHub issues, and two persisted Calendar events with
eligible observation evidence. Collision-looking visible content and the CP113
HTML/Markdown/script/bidi/long-text corpus are present without provider
accounts, credentials, or requests.

Missing and dual scope fail with 422. Every valid walk returns only its exact
scope in fixed `local_source`, `github`, `google_calendar` group order. Page
size one forces two real pages per family; all six immutable reopen
capabilities are unique, every detail equals the listed item, and cross-scope
cursor/detail replay fails closed. Query, family, kind, trust, state, and
page-size control changes invalidate the prior cursor.

Family/kind/trust/state filters preserve only their intended two-record
universe. Facets count exactly two for the same applied scoped predicates.
Labels remain `local_audited`/`extracted` for local data and
`quarantined_external` with native current/stale state for external data.

## Native reconciliation and restart

The explicit CP114 reconciliation gate re-executes the complete real-route
native transition journey. GitHub proves current, authoritative changed
revision, incomplete omission with no stale inference, complete omission to
stale, and later presence to current. Calendar proves positive current, equal
replay, incomplete/non-covering no-stale evidence, eligible covering omission
to stale, authoritative changed revision, and later positive current. No
refresh/import occurs through the Hub and Calendar never fabricates
cancelled/deleted state.

After closing the first client and constructing a new application/client, the
stable six-record canonical family/kind/title/text/state order is unchanged.
Fresh cursors and reopen capabilities traverse and reopen all records. Runtime
tripwires remain at zero across both application instances.

## Hostile content and accessibility

Backend list/detail preserves bounded hostile visible text while excluding
credential/runtime fields. The frontend acceptance drives explicit scope,
grouped rendering, Enter-key detail opening, close-focus restoration, loading
status, and next-page traversal. Hostile HTML, Markdown, script-looking URLs,
bidi text, and long content remain React text; no executable element or
content-derived link appears. Reopen/cursor values enter neither DOM, URL,
local storage, nor session storage. Existing responsive containment, semantic
labels, textual trust/state, and live-region behavior remain unchanged.

## Authority, export, and compatibility

CP113 tripwires cover DNS/HTTP, GitHub, Google Calendar/OAuth, Windows
credentials, planning/model, research, and embeddings; the joined journey
records zero calls. Complete-row snapshots across local knowledge, connector,
Calendar, extraction/import, Automation, Agent, Tool invocation, and Approval
domains have zero Hub-read delta. Expected native reconciliation mutations are
fixture actions outside the Hub read path.

The real export service produces `second-brain-project-export` version `1`
with the exact data-file inventory. Audited local Source data remains present;
Hub runtime identity, GitHub/Calendar runtime and account data, observations,
and credential canaries are absent. Alembic remains
`0016_calendar_event_observations`; Tool Registry remains `agent-tools-v1` and
has no Context Hub Tool. Full regression verification preserves independently
addressable local Source/search, GitHub, Calendar, export, Agent, Automation,
and Tool Registry contracts.

## Verification

- Focused CP114 backend/integration: **2 passed**, zero skipped.
- Focused Context Hub frontend: **9 passed** in one file, zero skipped.
- Joined three-scope journey, pagination/filter/facet/detail, reconciliation,
  restart, hostile content, accessibility, zero-call, zero-delta, and export-v1:
  **passed**.
- Restricted-context Full attempt passed database identity, dependency
  integrity, Ruff, formatting, and mypy, then reached **1,403 passed / 1
  failed / zero skipped**. The sole failure was the known host-bound Windows
  Credential Manager probe returning `credential_store_locked`; every CP114
  node passed.
- Authoritative host-context Full verification passed: dependency integrity;
  Ruff lint/format over 498 files; strict mypy over 208 production files;
  **1,404 backend tests passed**, zero skipped (12 warnings); Alembic current
  and heads at `0016_calendar_event_observations` with no new upgrade
  operations; frontend ESLint and TypeScript; **157 frontend tests in 16
  files**, zero skipped; 89-module production build; and `git diff --check`.

## Exact changed paths

- `docs/ARCHITECTURE.md`
- `docs/CHECKPOINTS.md`
- `docs/ROADMAP.md`
- `docs/checkpoint-114-report.md`
- `frontend/src/ContextHub.test.tsx`
- `tests/integration/test_context_hub.py`

## Residual limitations

The boundary remains local and loopback-only. PostgreSQL read-committed
pagination is not a durable snapshot; concurrent inserts before a saved keyset
require a fresh walk. Provider interoperability and credentials are
intentionally absent. Transport tokens depend on the unchanged runtime secret;
CP114 validates newly issued capabilities after restart without broadening the
CP111 lifecycle contract.
