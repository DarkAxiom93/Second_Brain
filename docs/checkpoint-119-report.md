# Checkpoint 119 report

Status: **Implemented; awaiting human review.** Baseline:
`43ec6e97b1b14a5d0e57c56f5c52e5bdf2ae0828`.

## Delivered contract

`POST /capture-items/{id}/convert-to-source` requires the established exact
Capture scope and a positive observed revision. It owns one PostgreSQL
transaction, locks the exact scoped Capture, and either converts one pending
item or performs a write-free processed replay. A new conversion creates one
code-owned `source_type="capture"` Source named only from the Capture UUID, sets
no reference, hashes the exact normalized stored text with SHA-256, and reuses
the existing text-ingestion repository with `text/plain`, no filename, 2,000
character chunks, and 200 character overlap. It then records the Source,
processing instant, terminal state, one revision increment, and updated time.
Repository helpers do not commit; any route failure rolls the whole unit back.

Processed replay accepts only the original conversion revision or current
processed revision, resolves the recorded Source, and performs no ingestion or
write. `POST /capture-items/{id}/source` is a read-only exact-scope resolver and
returns only the safe existing `SourceRead`. Both bodies use closed schemas.
Conversion creates no Memory, proposal, embedding, model/provider, or network
operation. No migration was required; the sole head remains
`0017_capture_items`.

## Common capture-bound Source guard

`app.sources.scope` is the reusable reverse-binding guard. It distinguishes an
omitted/unscoped legacy-only operation from an authoritative Project UUID and
authoritative explicit-unassigned `None`. Legacy/unbound Sources preserve prior
behavior. A reverse-bound Source is admitted only when the Capture is processed,
has `processed_at`, and its immutable `project_id` exactly matches the caller
scope. Wrong, omitted, ambiguous, or invalid bindings fail closed. Document and
chunk resolution traverses the same predicate. Source gained no `project_id`.

## Complete Source-path inventory

- Public Source list omits capture-bound rows. Public Source detail, linked
  Memory listing, document listing, document detail, chunk listing, and text or
  file ingestion use legacy-only guarded lookup and safe not-found behavior.
- Memory-to-Source linking passes the loaded Memory's authoritative ownership.
  Memory-linked Source reads correlate the guard with that Memory ownership.
- Proposal generation/extraction passes its explicit Project identity. Proposal
  queue/detail/review and promotion correlate the guard with the immutable
  proposal Project before evidence is read or state is changed.
- Agent Tool `source.get` and `source_chunk.get` correlate the guard with the
  Agent Run scope. Research evidence revalidation applies the same rule.
- Context Hub `local_source` query and exact reopen correlate the guard with the
  mandatory Hub request scope.
- Project export Source, document, and chunk selection correlates the guard with
  the exact exported Project while retaining reviewed-linkage selection.
  Capture rows/bindings are not serialized; format/version remain
  `second-brain-project-export` version 1.
- Project import is unchanged. With no exported Capture binding, imported
  Sources remain legacy/unbound.
- Connector import creates new legacy/unbound Sources; its provenance reopen
  cannot encounter a capture-bound Source.
- Direct internal Source/document/chunk repository reads were inventoried.
  Public identity reads default to legacy-only; scoped subsystems use an
  existing authority and never manufacture unassigned from omission.

## Verification

The pre-commit audit found two production defects. Proposal generation had
collapsed omitted `project_id` into authoritative unassigned; the route now
uses Pydantic field presence and passes `LEGACY_ONLY` for omission, explicit
`None` for explicit-unassigned, and the UUID for exact Project authority.
Persisted run/proposal `project_id` remains backward-compatible. Connector
existing-import replay had dereferenced provenance with `Session.get`; it now
passes the exact `ExternalScope` and resolves both SourceDocument and Source
through the common capture-bound guard, rejecting inconsistent or mismatched
provenance without exposing ownership.

`tests/integration/test_capture_conversion.py` now contains 22 collected
real-PostgreSQL cases covering assigned/unassigned conversion, exact text and
fixed 2,000/200 chunks, metadata/checksum, failure matrices, both replay
revisions, resolver success/failure, proposal authority and dereferences,
unscoped Source/document/chunk/ingestion/link guards, Agent Tools, Context Hub,
research evidence, Project export selection, a barrier-controlled two-connection
race, post-document-SQL rollback, and eight statement-count paths. Connector
replay adds four-scope legacy/bound evidence in the existing integration file.
The obsolete CP118 assertion now requires both CP119 routes to exist.

The final focused-audit remediation strengthens three proofs without changing
production code. Resolver inconsistency now calls the public `/source` route
after a real processed Capture exists while narrowly substituting only the
scoped Source lookup with a not-found result, then proves a safe 404 and an
unchanged Capture/Source graph. Connector legacy, matching assigned,
matching explicit-unassigned, wrong-Project, assigned/unassigned mismatch, and
missing document/Source lookup cases now all traverse `confirm()` with the
exact request `ExternalScope`; only the two impossible-under-FK missing lookup
boundaries are narrowly injected. The conversion race now uses two explicit
SQLAlchemy Sessions that each hold and record a distinct DBAPI connection
before the barrier. Instrumentation around the real `FOR UPDATE` lookup records
the post-lock Capture state and revision observed by each worker without
replacing the lookup or changing transaction boundaries. Exactly one worker
must observe pending and enter real Source creation/ingestion, while the other
must observe processed and replay without ingestion. The final graph explicitly
asserts one SourceDocument and correlates the surviving Source and Capture
provenance to the pending observer. Resolver inconsistency evidence snapshots
and compares the complete Source, SourceDocument, and deterministically ordered
SourceChunk graph, including row counts, so the safe failure proves no graph
mutation, creation, or deletion.

The measured count assertions are unassigned/assigned conversion **7/8**,
original-revision replay **2/3**, current-revision replay **2/3**, and resolver
**2/3**; all remain within the approved conversion/replay maximum of 10 and
resolver maximum of 3. Transaction-control statements remain excluded.

The first real PostgreSQL execution collected **26 tests**: **20 passed** and
**6 failed only because the conversion and replay exact-count assertions still
contained the earlier higher inspection estimates**. All substantive
conversion, concurrency, rollback, guard, resolver, proposal, Tool, Context
Hub, research, export, and connector replay tests passed. The six expectations
now contain the measured values and passed in the subsequent Full run.

That Full run collected **1,505 backend tests** and finished with **1,504
passed, 1 failed, and 0 skipped**. The sole failure was the redundant
`test_cp119_routes_are_additive` assertion against `create_app().routes` before
FastAPI had materialized application routes. A fresh application's OpenAPI and
the established complete-route snapshot tests both contain the two CP119 paths,
confirming a test-isolation/materialization issue rather than a production
route-registration defect. The redundant assertion was removed.

The final ordinary logged-in Windows PowerShell verification is successful.
The focused CP119 PostgreSQL set finished **26 passed, 0 failed, 0 skipped**.
Real PostgreSQL evidence passed for the two-connection conversion race,
post-document-SQL rollback, the guard-bypass matrix, connector replay scope
matrix, proposal omitted/null/UUID scope distinction, and Tool, Context Hub,
research, and export guards. The measured statement counts were conversion
**7/8**, original-revision replay **2/3**, current-revision replay **2/3**, and
resolver **2/3** for unassigned/assigned scope respectively.

The final Full rerun finished **1,504 backend tests passed, 0 failed, 0
skipped**. The Windows Credential Manager test passed in the ordinary logged-in
Windows user session. Ruff, format check, mypy, pip check, and
`git diff --check` passed. Alembic current and sole head are both
`0017_capture_items`, and Alembic check reports no new upgrade operations. The
frontend finished **157 tests passed** with lint, typecheck, and production
build successful.

The Tool Registry remains `agent-tools-v1`; Project export remains
`second-brain-project-export` version `1`. No CP120/CP121 work, migration,
credential change, staging, or commit was performed.
