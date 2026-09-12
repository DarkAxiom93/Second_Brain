# Local V1.6 Unified Read-only Context Hub roadmap

Status: **Published as Local V1.6; Checkpoints 109-115 complete.**

This document defines the approved Local V1.6 architecture and its now-complete
implementation sequence. No post-V1.6 roadmap capability has started.

## Product decision

Local V1.6 should deliver one **Unified Read-only Context Hub** inside the
existing trusted, single-maintainer, loopback-only application. It lets the
operator find and browse already-approved context from three existing families:

1. local `Source` / `SourceDocument` / `SourceChunk` knowledge;
2. V1.4 GitHub External Context; and
3. V1.5 Google Calendar External Context.

The Hub is a federated presentation and query boundary, not a new store, trust
domain, ingestion pipeline, provider client, or Agent Tool. It preserves each
family's ownership, provenance, freshness, reconciliation, privacy, and trust
semantics instead of flattening them into a fictional universal record.

## Release invariants

- Operation remains local and loopback-only for one trusted maintainer.
- Every query selects exactly one Project or explicit unassigned scope. Omitted
  or null scope never means every Project, and a request cannot combine scopes.
- Query execution performs bounded PostgreSQL/application reads only. It makes
  no Google, GitHub, credential-store, model, embedding-provider, or other
  network request.
- Every result has a closed `family`, closed `kind`, explicit trust label,
  family-specific state/freshness, and immutable family-native provenance
  sufficient to reopen the exact underlying local record.
- Raw external content remains quarantined and non-authoritative. Displayed
  content is data, never configuration, instruction, Markdown authority, or
  executable content.
- Existing local Source/search, GitHub External Context/import, Calendar
  External Context/refresh, Agent, Automation, Tool Registry, and Project
  export contracts remain compatible and independently addressable.

## Federated read model

### Request envelope

The future contract uses one closed typed request with:

- `scope`: exactly one of `project_id` or explicit `unassigned=true`;
- bounded `query` with Unicode/control-character validation and a documented
  empty-query browse rule;
- closed sets of `families`, family-compatible `kinds`, `trust`, and `state`
  filters;
- one positive bounded `page_size`; and
- an opaque, authenticated or server-validated cursor bound to the canonical
  scope, query, filters, contract version, page size, and ordering mode.

Unknown fields, unknown enum values, impossible family/filter combinations,
both/neither scope selectors, excessive query/result bounds, and cursor/request
mismatch fail closed. Detail reads accept a typed family plus opaque/public
family-native identity and reapply the exact scope and trust boundary; UUID
shape or existence alone never grants access.

### Result envelope and provenance

The common envelope contains only a contract version, closed family and kind,
exact scope, fixed `local_audited` or `quarantined_external` trust label,
family-specific state/freshness, bounded plain-
text display fields, immutable typed provenance, and deterministic within-
family/group position. It must not claim a shared version, URL, freshness
clock, or relevance score.

Reopening resolves provenance through the authoritative repository and scope:

- local results identify the exact `Source`, `SourceDocument`, and applicable
  `SourceChunk` UUID/version/order relationships in audited ingestion;
- GitHub results identify the exact account, immutable external item identity,
  and application item revision used by existing browser/history; existing safe
  code-generated links appear only through that contract; and
- Calendar results identify the exact account/calendar/recurrence occurrence
  and immutable revision/observation evidence required by existing detail and
  history. No provider-content link is added.

CP110 must derive precise public schemas from existing repositories and stop
for architecture review if an exact immutable reopen reference cannot be
expressed without leaking a private identifier.

### Family preservation

Local Sources retain exact Project ownership and audited Source -> Document ->
Chunk provenance. Hub reads do not update access times, search state,
embeddings, documents, chunks, or Sources. Existing Source/search APIs stay
unchanged.

GitHub retains exact account, allowlist, immutable repository identity,
Project/unassigned, latest-revision, history, and complete-run reconciliation
rules. Current/stale and historical state mean only what V1.4 defines. Existing
single-current-revision import is separate and unchanged; the Hub has no import.

Calendar retains CP103 application-derived `current` / `stale` exactly. Only
eligible complete exact-window observation evidence may make an omitted
occurrence stale, and later positive observation restores current. Incomplete,
failed, partial, unversioned, cross-scope, or non-covering evidence infers
nothing. The Hub fabricates no tombstone, deleted, or cancelled event. Private/
special labels stay fixed, excluded fields stay unavailable, and there is no
provider-content link. CP102 manual refresh remains the sole request trigger.

## Search, ordering, filters, and pagination

The baseline uses **provider-family grouped results** in fixed order
`local_source`, `github`, `google_calendar`; a subset preserves relative order.
There is no cross-provider relevance rank or score.

Within each family, CP110 specifies one stable PostgreSQL-only lexical/browse
ordering using only mathematically valid family fields and immutable tie-
breakers. Any signal is labeled family-local and is not comparable across
groups. Semantic/embedding signals, provider freshness, trust, current/stale,
application status, or hidden boosts cannot enter an opaque score. Existing
Memory explained-search RRF is neither reused nor changed.

Pagination is independently bounded per family through one versioned opaque
cursor carrying each group's last ordering tuple and exhaustion state. Cursor
validation rejects modification, replay with different scope/query/filters/
page size, unknown versions, invalid tuples, and oversized input. Concurrent
changes follow a documented keyset/read-committed boundary but cannot duplicate
a tuple within one family, cross scope, reinterpret state, or substitute
provenance.

Facets are closed deterministic buckets over the exact scoped query domain.
Counts use the same PostgreSQL scope/trust/family predicates as results and are
labeled request-time observations, not snapshot guarantees. No free-form field,
sort, expression, provider query, or SQL fragment is accepted. Query UTF-8
length, filter cardinality, selected families, page size, pages, SQL work/
deadline, returned text, result count, and response bytes all have fixed caps.

## Persistence decision

The baseline directly federates existing authoritative PostgreSQL records and
adds **no table, projection, index, migration, schema, or second source of
truth**. CP109 creates no migration. CP110/111 first measure bounded direct
queries and use existing indexes only where their semantics match.

A future projection/index requires a separate reviewed decision proving direct
federation insufficient and defining owner/provenance, transactional population,
complete rebuild, failure/recovery, stale/index-drift visibility, deletion, and
verification that it never becomes authoritative or silently changes ranking.

## Privacy, export, and authority exclusions

Project export stays `second-brain-project-export` version `1`. The Hub does not
make GitHub/Calendar accounts, configuration, runs, observations, credential
references, provider identities, raw payloads, or excluded runtime state
exportable. It exposes no credentials, OAuth material, excluded Calendar
fields, arbitrary provider URLs, configuration authority, or hidden cross-
Project identifiers.

The Hub cannot import or refresh GitHub/Calendar content; create a Source,
Document, Chunk, Memory, proposal, Approval, Agent Run, Automation, or schedule;
execute a Tool; write to a provider; widen OAuth scopes; access credentials; or
become a generic network/provider executor. It is not registered in
`agent-tools-v1`, exposed to Agents/Automations, or callable through their read
tools. External text cannot become prompts, configuration, links, instructions,
filters, or authority.

## Implementation sequence after Checkpoint 109

Every checkpoint requires human approval, commit, push, and successful exact
push CI for its predecessor.

### CP110 - federated read/query contract and backend foundation

Define schemas, family adapters, immutable reopen references, family-local
ordering, scope predicates, limits, and read-only service tests using existing
persistence. Add no route, UI, provider call, Tool, Agent, or Automation access.

### CP111 - Context Hub API and typed pagination/filtering

Add loopback typed list/detail/facet routes, request-bound keyset cursors,
closed filters, bounded SQL, safe errors, and concurrency tests. Prove zero
provider/credential/model call and zero mutation. No import/refresh action.

### CP112 - accessible Unified Context Hub frontend

Add one route with explicit scope selection, grouped family/trust/state/
provenance disclosure, inert plain-text rendering, accessible keyboard/screen-
reader/reflow behavior, deterministic filters, and only existing safe links.
There is no polling or hidden refresh.

### CP113 - deterministic U01-U18 security/evaluation gate

Create the code-owned one-to-one manifest and synthetic corpus from the threat
model. Require unique deterministic backend/UI nodes, no skips/xfail/
conditional bypass, identity scans, provider tripwires, protected-domain
snapshots, and PostgreSQL concurrency/fault gates.

### CP114 - Local V1.6 end-to-end acceptance

Exercise joined local Source, fake GitHub, and fake Calendar journeys through
real routes, PostgreSQL, grouped pagination/filter/detail, reconciliation,
hostile content, restart, isolation, accessibility, and all authority/export
omissions. No real provider or credential use.

### CP115 - Local V1.6 release hardening

Run clean-install dependency/privacy/export/schema audits, Full verification,
backup/restart/recovery, release-note/runbook updates, and exact candidate
evidence. Tagging/publication remains a separate post-review action.

CP115 completed these evidence and documentation gates without product,
dependency, schema, migration, or authority changes. Local V1.6 was subsequently
published as `v1.6.0`, titled **Second Brain Local V1.6**, from exact release
commit `64c8215d142ba66f7788d2a71f3debf291cd9862`. Annotated tag object
`3d2bc5f774729459f89db7187f407db1b273c9dd` peels to that commit. GitHub Release
`387495253` was published at `2026-09-12T07:46:12Z`, is neither draft nor
prerelease, has zero assets, and is available at
<https://github.com/DarkAxiom93/Second_Brain/releases/tag/v1.6.0>. V1.6 is the
current published release and V1.5 is the preceding recovery release.
Publication introduced no production authority change.

## Rollback and compatibility

With no baseline persistence, rollback removes the additive Hub service/routes/
UI and leaves authoritative records untouched. Existing APIs/URLs remain
compatible. Forward-only recovery is unchanged because no migration is planned.
