# Checkpoint 104 explicit Calendar event import decision report

Status: **Approved and complete after human review as a documentation-only
omission decision. CP105 has not started.**

## Preflight

Preflight passed on clean synchronized `main` at exact approved CP103 commit
`ce068cd321b00a4e076b4f8363fc63d0afc56ee3`; `HEAD` and `origin/main`
matched. Exact push CI run `33885223692` for that SHA completed successfully.
Development and test database parsed and live identities were verified as
`127.0.0.1:5433/second_brain` and
`127.0.0.1:5433/second_brain_test`. Alembic current and sole head were
`0016_calendar_event_observations`, and `alembic check` was clean. Tool Registry
was `agent-tools-v1`; Project export was `second-brain-project-export` version
`1`.

## Recommendation and decision

Recommend **A: keep Calendar strictly read-only External Context with no event
import**. Local V1.5 intentionally omits Calendar event import. The omission is
approved and complete after human review as a documentation-only decision.
Import is not scheduled as a V1.5 follow-up; it is omitted unless a concrete
future workflow proves the need and passes a separate architecture and
authority review beyond V1.5.

CP103 already supplies the release's intended workflow: the operator can browse
one exact Project or explicit-unassigned scope, inspect a privacy-minimized
event occurrence, and see application-derived `current` or `stale` state. No
concrete workflow was found that requires converting that context into a durable
document. Users gain accurate, bounded time context without additional action;
they lose only the convenience of searching a frozen event snapshot alongside
durable documents or reusing it as Agent evidence. That lost convenience does
not outweigh the new permanence and authority boundary.

## Architecture analysis

Calendar events are mutable temporal observations, not automatically durable
knowledge. CP103 deliberately keeps provider revisions immutable while deriving
effective state from later exact-window observation evidence. A later complete
refresh can make an occurrence locally stale, and a later positive observation
can restore it. An imported SourceDocument would not follow that state machine:
it would remain a durable local snapshot even after the provider event moved,
disappeared from the window, became stale, or ceased to exist at the provider.
That persistence could be desirable only for a demonstrated archival workflow,
which is not a Local V1.5 goal.

Recurring occurrences make permanence more ambiguous. Identity is based on the
series/event and canonical original start, while current start/end may move. A
document import would need to choose whether repeat confirmation of the same
occurrence imports the same historical revision, a new revision, or a new
document. Stale state is application evidence rather than provider deletion,
so it cannot safely answer that choice. Revision-exact preview/confirm,
fail-closed drift, and deterministic sequential/concurrent replay would all be
mandatory if import were ever proposed, but solving them would not establish
user value.

Privacy minimization also reduces document value. Private events and special
types intentionally expose fixed labels such as `Busy`; descriptions,
locations, people, conference links, and provider-content URLs are absent. A
durable document made from those labels adds little knowledge while permanently
preserving sensitive timing. Ordinary titles remain untrusted external text.
Import would need immutable provider-neutral provenance binding the exact
account/configuration revision, calendar, occurrence, event revision,
application-derived state/evidence, and exact Project or unassigned scope. The
existing CP93 `ExternalItemImport` is GitHub-specific, unique to an
`ExternalItem`, and stores a GitHub canonical URL; it cannot be reused safely by
renaming or configuration.

Project and explicit-unassigned isolation must remain exact. Historical scope
cannot be remapped after account revision changes, and null must never mean all
Projects. Omission preserves that guarantee without a second durable ownership
graph. It also avoids defining whether a later project export should include a
Calendar-derived Source while all Calendar revisions and observation evidence
remain excluded. Export stays version 1 with no Calendar data or new restore
semantics.

Creating Source, SourceDocument, and chunks would cross the quarantine boundary.
Those entities participate in existing search/retrieval, and `source.get` and
`source_chunk.get` are executable read Tools in `agent-tools-v1`. Therefore a
Calendar-derived document could become Agent-visible through existing Source
pathways even though Calendar External Context itself is unavailable to every
Agent. Later Memory extraction or proposal workflows could also consume the
generic document boundary unless separately excluded. Omission guarantees zero
Calendar-to-Source/SourceDocument/chunk and zero Calendar-to-Memory/proposal/
Approval path rather than relying on downstream negative filters.

## Closed capability statement

Local V1.5 has:

- no Calendar import endpoint or Calendar import UI action;
- no automatic import and no Agent or Automation import authority;
- no Calendar-to-Source, SourceDocument, chunk, Memory, proposal, or Approval
  path;
- no import schema, migration, dependency, or speculative production
  scaffolding;
- no Project export format or inventory change;
- no provider write, generic Google/provider transport, OAuth scope widening,
  tombstone, or incremental-sync expansion.

CP103 read-only browsing and reconciliation remain the complete Calendar-
context surface. Confirmation of this decision performed zero Calendar import
implementation, zero Calendar writes, and zero OAuth, Google, or Calendar
requests.

## Security review

No new threat ID is needed. G15 is updated to make the omission executable as a
negative authority guarantee: route/UI and durable import-path absence, zero
Calendar-derived Source/search/Agent evidence, and unchanged protected domains.
The interpretations of G01-G14 and G16-G18 do not change. Calendar content
remains untrusted; private/special labels remain minimized; Project/unassigned
isolation, no provider-content links, no Calendar write authority, no Agent or
Automation Calendar authority, the closed provider transport, exact CP99 OAuth
scopes, and the full-sync/no-tombstone model remain intact.

## Changed paths and verification

Exact changed paths:

- `docs/ARCHITECTURE.md`
- `docs/CHECKPOINTS.md`
- `docs/ROADMAP.md`
- `docs/V1_5_CALENDAR_ROADMAP.md`
- `docs/V1_5_CALENDAR_THREAT_MODEL.md`
- `docs/checkpoint-104-report.md`

No migration, dependency, backend, frontend, API, schema, database, Tool
Registry, export-format, OAuth, provider-authority, Agent, or Automation code
changed.

Focused verification passed **36 backend tests** and **6 frontend tests**, zero
failed and zero skipped. The focused backend set covered the Calendar catalog,
sync, account API, persistence/reconciliation, and existing GitHub explicit
import boundary. The frontend set covered the Calendar External Context browser.
An additional verified-test-database migration lifecycle reset passed **6
backend tests**, zero failed and zero skipped.

The first Full attempt passed database identities, dependency integrity, Ruff
lint/format, and strict mypy, then reported **1,286 passed, 1 failed, 4 setup
errors, 0 skipped**. The setup errors were test-state contamination from the
preceding focused test selection: a Calendar account revision retained a
foreign key to a test Project that a later Answers fixture tried to delete. The
independent failure was the known sandbox-host Windows Credential Manager lock.
Neither failure involved product or documentation behavior. The dedicated
migration lifecycle suite restored only the identity-verified
`second_brain_test` database; the development database was not downgraded or
cleaned.

The authoritative Full rerun in the normal Windows user context passed **1,291
backend tests** and **145 frontend tests**, zero failed and zero skipped. `pip
check`, Ruff lint/format over 472 files, strict mypy over 203 production files,
frontend ESLint/typecheck/build, and `git diff --check` passed. Development and
test database parsed/live identities passed. Alembic current and sole head were
`0016_calendar_event_observations`; `alembic check` reported no new upgrade
operations. Tool Registry remained `agent-tools-v1`; Project export remained
`second-brain-project-export` version `1`.

Verification used only existing deterministic fake/synthetic provider
boundaries. No Calendar import code was implemented, no Calendar write or real
Calendar request occurred, OAuth/provider authority was not widened, and CP105
was not started. CP104 was approved and completed after human review. The
checkpoint remained unstaged and uncommitted until this final lifecycle audit.
