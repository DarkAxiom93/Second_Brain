# Local V1.7 Capture & Triage Inbox threat model

Status: **Proposed for human review; Checkpoint 116 documentation only.**

This is the closed deterministic CAP01-CAP18 inventory. CP121 must map every ID
to at least one unique executable test node and reject missing, duplicate-only,
skipped, xfailed, or conditional coverage. CP122 proves the joined boundary.

## Assets and boundaries

Protected assets are exact Project/unassigned ownership, capture content and
history, immutable identity, state/revision, idempotency material, exact
CaptureItem-to-Source provenance, audited Source ingestion, reviewed knowledge,
Agent/Automation/Tool authority, provider/network isolation, export-v1 content,
database/backup confidentiality, and availability.

The browser, identifiers, headers, cursors, and captured text are untrusted.
FastAPI validation and exact-scope services cross into caller-transaction-owned
PostgreSQL repositories. Only explicit conversion crosses into the existing
audited text Source ingestion repositories. Memory/search/Answers, Context Hub,
models/embeddings/providers, Agents, Tools, Automations, export, and external
systems remain outside the Capture boundary.

## Closed threat inventory

| ID | Threat | Required invariant/control | Planned deterministic evaluation |
|---|---|---|---|
| CAP01 | Cross-Project or Project/unassigned leakage | Every non-create Capture read/action requires exactly one scope; SQL filters ID/query and ownership together. A capture-bound Source derives immutable scope from its processed CaptureItem reverse binding; every Source/document/chunk/downstream path uses the common guard, while unbound Sources retain legacy contracts. | Seed identical canaries in two Projects and unassigned; exhaust Capture surfaces and direct/legacy Source list/detail/document/chunk/ingestion/link/proposal/Tool/Hub/export paths; attempt unscoped and wrong-scope access with real/forged IDs; require rejection/omission, exact matching-scope access only, and unchanged legacy-Source behavior. |
| CAP02 | Forged or substituted identifiers | UUID existence grants nothing; Capture and Project are revalidated in exact scope; resulting Source comes only from locked persisted provenance. | Fuzz IDs; swap real IDs among scopes/types; submit nonexistent Projects and caller-selected Source IDs; require safe 4xx/not-found, zero disclosure/write. |
| CAP03 | Duplicate or replayed creation | Required bounded idempotency key is hashed, unique, and bound to canonical normalized content/scope fingerprint. | Same-key same-request sequential/concurrent replay returns one UUID/row; same key with changed content/scope conflicts; malformed keys reject; no key/hash/fingerprint leaks. |
| CAP04 | Invalid state transition | Closed actions alone implement pending/discarded restore and pending/processed conversion; processed is terminal; no generic setter/delete. | Attempt every state/action matrix and malformed enum/body; only allowed edges succeed, terminal mutations fail, row/source counts remain exact. |
| CAP05 | Partial conversion | Source, document, chunks, provenance, processed time/state/revision commit in one route transaction; any failure rolls all back. | Inject faults after each write/flush and at commit; require pending unchanged Capture and zero new Source/document/chunk, then clean retry succeeds once. |
| CAP06 | Concurrent double conversion | Lock/revalidate Capture; unique resulting Source; processed replay returns recorded Source without ingestion. | PostgreSQL barriers race conversions and ambiguous-response replay; require one Source/document/chunk set, transition, provenance ID, and identical reopen. |
| CAP07 | Stale/lost update | All mutations compare revision under row lock, increment once, update `updated_at`, and conflict without overwrite; `id`/`created_at` never change. | Interleave edit/edit, edit/discard, reassign/convert, restore/reassign, delayed requests; require one winner, no lost/mixed state, immutable identity/creation time, and exactly one updated-time advance per successful mutation. |
| CAP08 | Hostile instruction text | Content is data only and absent from prompts, evidence, configuration, actions, automatic routing. | Store direct/indirect/multilingual/encoded instructions naming Tools, Agents, providers, projects, transitions; require literal display and zero downstream call/delta. |
| CAP09 | HTML/Markdown/script/bidi/control spoofing | Normalize/reject forbidden controls; React text only; no content-derived link; bidi isolate and overflow/accessibility containment. | Browser corpus of tags, handlers, SVG/data/javascript URLs, Markdown, NUL/C0/C1, bidi overrides/isolates, confusables, long text; require no execution/navigation/layout escape. |
| CAP10 | Privacy leakage | Allowlisted schemas/logging exclude idempotency/fingerprint, prompts, SQL/errors, hidden IDs, and content from logs/diagnostics; detail is scoped. | Plant canaries in content/private fields/errors; inspect API variants, headers, logs, diagnostics, DOM outside exact detail, cursors, reports; require zero unintended occurrence. |
| CAP11 | Oversized/resource-exhaustion input | Exact normalized content/query/key/state/cursor/page/result bounds; closed indexed query shapes; keyset only; no offset, count, facets, semantic/embedding query, unbounded iteration, or retry loop. Normal-path SQL ceilings are create 3, query 2, detail 2, edit 3, reassign 4, discard/restore 3, convert/replay 10, and scoped Source resolver 3. No wall-clock or examined-row guarantee is claimed. | Test exact and +1 input/page/cursor boundaries with ASCII/multibyte values and require immediate over-limit rejection; instrument SQL and enforce each endpoint ceiling; inspect executed query shapes and migration indexes; require no OFFSET/count/facet/semantic query or unbounded application iteration and at most 50 returned items. |
| CAP12 | Hidden model/provider/network access | Capture actions use validation/PostgreSQL only; conversion uses local ingestion only; no provider/credential/HTTP/DNS resolution. | Tripwire model, embedding, HTTP/DNS, credential, GitHub, Google boundaries across success/error/replay; require zero calls and embedding rows. |
| CAP13 | Agent/Automation/Tool/Context-Hub authority leakage | Capture is absent from registry, policies, fixed-agent evidence, Automation/scheduler, Hub families, Brief, Watch, Curator. | Snapshot inventories and attempt Capture through Runs, Tools, Hub reopen/filter, Brief/Watch/Curator evidence; all reject/omit with zero delta. |
| CAP14 | Export leakage | Export remains exact `second-brain-project-export` v1; export/import does not know CaptureItems. | Export Projects with assigned/unassigned canaries; inspect archive names/schema/bytes/version and round-trip; require no canary/Capture row or drift. |
| CAP15 | Backup exposure | Docs treat backups as containing sensitive captures; no secondary copies, Capture export, browser storage, telemetry. | Backup/restore synthetic DB and prove Capture recovery; scan output/temp/browser stores; only protected DB backup may contain canary. |
| CAP16 | Reassignment race | Pending reassignment locks current exact scope/revision and validates the target. Conversion reads and freezes ownership inside the same locked transaction; processed scope is immutable. | Race reassignment with old/new detail/query/edit/discard/convert and Project removal; require one winner and only complete old/new ownership. If conversion wins, every scoped Source/downstream path must accept only the frozen processed scope; never both/mixed or unassigned fallback. |
| CAP17 | Destructive data loss | No Capture purge/delete; Project and resulting Source FKs restrict deletion; processed terminal; rollback/recovery preserves rows. | Route/OpenAPI scans prove no delete; attempt ORM/SQL Project/Source deletion and fault/restart/restore; require restriction and exact recoverable state. |
| CAP18 | Source provenance/lifecycle confusion | Processed iff one immutable unique Source FK and write-once `processed_at` exist; processed Capture scope is the authoritative reverse Source binding; deletion is restricted; replay/scoped resolver returns the same Source; no Memory. | Convert equal-content captures and replay one; race reassignment/conversion; mutate/delete related objects; attempt the resulting ID through every legacy Source/document/chunk/ingestion/link/proposal/Tool/Hub/export path without scope and with wrong scope. Require distinct stable mappings, one write-once processing time, exact frozen-scope enforcement, matching text/chunks, no bypass/orphan/replacement, and zero automatic Memory/proposal/embedding. |

## Detection, response, and residual risk

Safe diagnostics may record only code-owned error IDs, operation kind, bounded
timing/counts, and a content-free correlation value. They exclude content,
query, cursor, Project/Capture/Source UUIDs, idempotency material, SQL, raw
exceptions, environment, paths, provider/configuration, and secrets.

Any isolation, duplicate, transition, atomicity, concurrency, privacy,
hidden-call, authority, export, destructive-loss, or provenance failure blocks
release. Disable additive route/UI capability while preserving PostgreSQL rows;
do not purge captures, weaken FKs, widen scope, create replacement Sources, or
run automatic repair. Migration rollback is allowed only on the verified test
database; production recovery is forward-only.

Residual risks are the trusted unauthenticated local session, sensitive text in
PostgreSQL/backups, shoulder-surfing, Unicode ambiguity after containment,
lexical inference from displayed text, and read-committed changes between
pages. They are accepted only with loopback operation, exact scope, bounded
inert text, revision/locking, protected backups, and CP121/CP122 gates.
