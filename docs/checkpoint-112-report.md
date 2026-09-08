# Checkpoint 112 report - Accessible Unified Context Hub frontend

Status: **Implemented; pending human review.** CP113 has not started.

## Preflight

- Clean synchronized `main` at exact HEAD
  `9b1304282a070c7552b2f5281c834a70af551d58` with zero divergence.
- CP111 remediation push CI run `34266502099` was `completed` / `success` for
  that exact SHA.
- Sole Alembic head `0016_calendar_event_observations`, Tool Registry
  `agent-tools-v1`, and Project export `second-brain-project-export` version `1`
  were unchanged.

## Route and explicit scope

The existing primary navigation now includes `Context Hub`, backed by exactly
one frontend route, `/context-hub`. Page initialization calls only the existing
Project-list API. The initial scope control has no selected value and no Hub
read occurs until the operator explicitly selects one Project or `Explicit
unassigned` and activates `Search context`.

The bounded optional query, family, kind, trust, state, and page-size controls
use closed CP111 values. Each submit creates one canonical in-memory applied
request snapshot. Any later control change aborts an active read, removes the
results, facets, detail, and cursor, and requires another explicit submit.
Pagination therefore sends the opaque cursor only with the exact applied
request that produced it.

## Grouped disclosure, facets, and detail

Results are rendered in fixed `local_source`, `github`, `google_calendar`
order. Every item and exact detail visibly labels family, kind, trust, native
state, exact selected scope, and code-owned family meaning: audited Source to
Document to Chunk; exact GitHub immutable item revision/history; or exact
Calendar occurrence/revision with application observation evidence.

Facets are fetched from `/context-hub/facets` for the same applied request and
display family, kind, trust, and state counts plus the request-time observation
timestamp. HTTP 422 is shown as `Counts unavailable for this request` without
partial/fabricated counts or filter changes.

Exact detail uses only the item's opaque `reopen_id` as the body capability for
`POST /context-hub/detail`. It remains inside `/context-hub`, is never rendered,
decoded, linked, or persisted, and receives a generic safe failure. Closing
detail restores focus to the exact result button that opened it.

## Hostile text, accessibility, and reflow

All Hub title/text fields use ordinary React text nodes. The page contains no
HTML/Markdown renderer, `dangerouslySetInnerHTML`, content-derived link, or
content-derived route/request/filter. Explicit `white-space`, anywhere-wrap,
word-break, max-width, overflow, and `unicode-bidi: isolate` containment keeps
long, control, and bidi-bearing text inside its item. No provider link is
invented because CP111 exposes none.

The route uses a main landmark, ordered headings, labeled selects and inputs,
fieldset/legend filter groups, native keyboard controls, existing visible-focus
styles, `aria-busy`, polite status updates, alerts, textual (not color-only)
trust/state labels, and meaningful action names. Responsive grid sizing and the
existing narrow breakpoint keep ordinary UI within the viewport.

## Changed paths

- `frontend/src/api/client.ts`
- `frontend/src/ContextHub.tsx`
- `frontend/src/ContextHub.test.tsx`
- `frontend/src/App.tsx`
- `frontend/src/App.test.tsx`
- `frontend/src/styles.css`
- `docs/ARCHITECTURE.md`
- `docs/CHECKPOINTS.md`
- `docs/ROADMAP.md`
- `docs/checkpoint-112-report.md`

No backend contract, migration, persistence, dependency, provider access,
refresh/import/write/scheduling surface, Agent/Automation authority, Tool
Registry, or export identity changed. No CP113 U01-U18 manifest or gate was
created.

## Verification

Focused Context Hub and application-shell frontend tests: **20 passed** across
2 files. Evidence covers navigation/route, explicit Project and unassigned
scope, no early Hub read, deterministic payloads, fixed grouping/disclosure,
facets and work-limit failure, exact-request cursor pagination and reset,
in-page reopen/token secrecy, hostile HTML/Markdown/script/URL/bidi text,
content-derived navigation absence, empty/status states, accessible groups and
landmarks, focus restoration, and absence of refresh/import/write/scheduling
controls.

The first Full run passed pip integrity, Ruff, formatting, and strict mypy,
then reached **1,359 passed / 1 failed** backend tests. The only failure was the
known restricted-context Windows Credential Manager probe returning
`credential_store_locked`; it was unrelated to CP112 and no product code was
changed for it.

The authoritative host-context rerun of `./scripts/verify.ps1 -Mode Full`
passed: dependency integrity; Ruff lint and format over 494 files; strict mypy
over 208 production files; **1,360 backend tests passed**, zero skipped (13
warnings); Alembic current/head/check at
`0016_calendar_event_observations` with no upgrade operations; frontend ESLint
and TypeScript; **154 tests across 16 files**; the 89-module production build;
and `git diff --check`.
