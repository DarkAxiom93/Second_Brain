# Local V1.6 Unified Read-only Context Hub threat model

Status: **Approved after human review; Checkpoint 109 complete.**

This is the closed U01-U18 inventory for planned Local V1.6. CP113 must map
every identifier to at least one unique deterministic executable test node and
reject missing, duplicate-only, skipped, xfailed, or conditional coverage.
Tests use synthetic provider data and PostgreSQL only.

## Assets and boundaries

Protected assets are exact Project/unassigned ownership; audited local Source/
Document/Chunk provenance; quarantined GitHub revision/reconciliation history;
privacy-minimized Calendar revision/observation evidence; credentials and
provider identity/configuration; reviewed Memories and approvals; Agent/
Automation/Tool authority; export-v1 contents; and query availability.

The browser and query are untrusted. GitHub/Calendar content is hostile
quarantined data. Reviewed local Source text is still rendered as inert data.
Typed adapters cross into three authoritative PostgreSQL domains; the common
envelope is not a new trust domain. Provider, credential, model, Agent,
Automation, import, refresh, scheduling, export, and write services stay outside
the query path.

## Closed threat inventory

| ID | Threat | Required control | Deterministic future verification |
|---|---|---|---|
| U01 | Cross-Project or Project/unassigned leakage | Exactly one scope is mandatory on list, facet, cursor, and detail; null never means all; every family filters ownership in SQL. | Seed identical canaries in two Projects and unassigned; exhaust every surface/scope and require only the exact scope, including rejection of missing/both selectors. |
| U02 | Cross-provider identifier substitution | Detail/provenance IDs are tagged by closed family/kind and resolved only by that adapter with exact ownership; UUID existence grants nothing. | Swap real IDs among all families/kinds, including collision-shaped UUIDs; require safe not-found/rejection and zero foreign disclosure. |
| U03 | Forged detail IDs or cursors | Opaque versioned cursors bind canonical scope, query, filters, size, order, and per-family tuples; strict parsing/length caps fail closed. | Bit-flip, truncate, extend, downgrade, cross-request replay, alter tuples/exhaustion/family, and fuzz IDs; require deterministic 4xx and no widening. |
| U04 | Trust-boundary collapse | Application-owned `local_audited`/`quarantined_external` appears on every item; UI groups/labels families; no common field upgrades trust. | Assert API/UI labels for every kind/state and attempt stored/provider trust labels; only fixed application labels may appear. |
| U05 | Hostile content/instruction injection | Bounded content is inert text, never prompt/config/filter/link/command/authority; Hub is unavailable to Agents/Automations. | Seed tool/config/import/refresh instructions in every display field; assert literal rendering, zero downstream calls, and protected tables unchanged. |
| U06 | HTML, Markdown, script, bidi, or control spoofing | No raw HTML/Markdown; encode text, reject/contain controls/bidi, and permit only application-generated links. | Browser corpus with scripts, handlers, SVG/data/javascript URLs, Markdown, CSS, bidi, NUL/C0/C1/confusables; require no execution/navigation/layout escape and truthful accessible labels. |
| U07 | Privacy-field or secret leakage | Allowlisted projections exclude credentials/references, OAuth identity, raw payloads, Calendar sensitive fields, arbitrary URLs, headers, exceptions, and hidden IDs. | Place canaries in every excluded DB/provider field, errors, logs, bodies, DOM, facets, cursors, and provenance; schema/inventory scans require zero occurrence. |
| U08 | Provenance confusion/non-exact reopen | Typed immutable provenance identifies exact authoritative revision/document/chunk/observation relationships; detail revalidates them. | Use same-content revisions, changed documents, GitHub history, recurring Calendar occurrences/equal replay; each result reopens its exact record or fails closed. |
| U09 | Stale/current misrepresentation | GitHub and Calendar state uses existing eligible evidence rules; local state is native only. | Complete/incomplete/failed/partial/non-covering/cross-scope runs, replay/change/omission/resurrection; Hub must equal native APIs and fabricate no cancelled/deleted state. |
| U10 | Cross-provider ranking manipulation | Fixed group order, no cross-family score; family-local order uses closed documented SQL signals and immutable ties. | Flood one family with extreme terms/freshness/states and equal scores; group order/no-score/stable ties remain, with zero semantic/provider call. |
| U11 | Pagination/filter tampering | Closed compatible enums, canonicalization, bounded keysets, request-bound cursors, and identical scope predicates for results/facets. | Exhaust pages, mutate every cursor/filter part, use incompatible enums and concurrent changes; require no scope crossing, duplicate tuple, fabricated bucket, or unstable tie. |
| U12 | Query/resource exhaustion | Bound UTF-8 query, families, filter cardinality, page/result/response size, SQL work/deadline, returned text; avoid N+1/unbounded counts. | Boundary/over-bound Unicode, huge arrays/cursors/content, pathological terms, repeated requests, and query-count/latency budgets must reject early or remain bounded. |
| U13 | Hidden provider/network access | Dependency graph permits PostgreSQL/application reads only; no credential, HTTP, OAuth, model, or embedding resolution. | Tripwire fakes for GitHub, Google, credentials, HTTP/DNS, model, embeddings across all list/facet/detail/error paths must record zero calls. |
| U14 | Refresh/write/import/scheduling side effects | No action surface; read-only services cannot reach protected writers/provider methods. | Complete-row snapshots of Sources, Memories, imports, syncs, schedules, observations, Agents, Approvals plus SQL/provider tripwires require zero delta/calls. |
| U15 | Agent/Automation authority leakage | Hub is absent from `agent-tools-v1`, policies, fixed Agent allowlists, Automation definitions, evidence resolvers, and schedulers. | Exact registry/catalog snapshots and attempts to name Hub as Tool/evidence via manual/scheduled Runs must reject with unchanged identity. |
| U16 | Project export leakage | Export name/version/inventory remain exact; Hub is not an export source and external runtime state stays excluded. | Export all scoped canaries, inspect exact archive/schema/content, and require unchanged format/version and zero excluded canaries. |
| U17 | Configuration/registry injection | Code-owned enums contain no URL, method, SQL, field path, Tool, prompt, provider query, or executable configuration. | Unknown/nested fields, prototype keys, SQL/URL/method/header/Tool/Agent payloads, confusables and registry drift scans must reject whole requests. |
| U18 | Concurrency/reconciliation drift | Adapters derive state from authoritative rows with deterministic keysets; concurrent reconciliation cannot mix ownership/provenance or complete partial evidence. | PostgreSQL barriers interleave pages/details with GitHub reconciliation, Calendar observation commits, scope revisions, and Source updates; require valid old/new native projections only, exact provenance, zero cross-scope/write. |

## Detection, response, and residual risk

Safe diagnostics may record only code-owned error IDs, selected family, bounded
timing/counts, and a correlation value revealing no entity, scope, query,
cursor, content, provider, or credential data. They exclude raw queries,
content, cursors, provenance internals, SQL, payloads, OAuth, paths, environment,
and exceptions.

Any isolation, provenance, trust, privacy, hidden-network, side-effect,
authority, export, configuration, or reconciliation failure blocks release.
Remove/disable the Hub and preserve authoritative records; do not broaden scope,
weaken labels, refresh providers, rewrite history, or create a projection.

Residual risks are the trusted local session, sensitive existing PostgreSQL/
backup data, lexical inference from allowed text, Unicode visual ambiguity after
containment, and read-committed change between pages. They are acceptable only
with exact scope, bounded plain text, native provenance/state, deterministic
cursors, and CP113/CP114 gates.
