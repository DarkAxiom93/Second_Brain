# Checkpoint 113 report - Context Hub security and evaluation gate

Status: **Implemented and fully verified; pending human review.** CP114 has not
started.

## Audit history and database gate

CP113 began from synchronized `main` at
`e1740a0dcb3bd64db738ecab98e44c0a7b5d273e` with
`origin/main...main = 0 0`. The first pre-commit audit rejected broad static and
partial mappings. The second rejected remaining gaps in deterministic U09 and
U18 behavior, incomplete U12/U14 evidence, and a database fixture whose normal
environment skip could hide mapped PostgreSQL nodes. No commit was made after
either audit.

The remediation added only the `cp113_security` pytest marker declaration and
a collection-scoped signal. Unrelated integration selections retain the prior
missing-`TEST_DATABASE_URL` skip. A selection containing a marked CP113 node
instead fails with the exact required-database message. Existing parsed and
live checks still require `second_brain_test`; there is no fallback to
`DATABASE_URL` or `second_brain`, and destructive permissions were not
broadened. Only intentionally mapped nodes carry the marker.

## Closed executable manifest

`tests/test_context_hub_security_evaluation.py` owns one ordered U01-U18
manifest with **25 unique executable nodes**. Its reusable validator rejects
missing/extra IDs, empty or duplicate mappings, missing files/nodes,
non-assertive nodes, Python skip/skipif/xfail calls or decorators, Vitest
skip/todo, and recursively discovered fixture/environment skips. Marked
PostgreSQL nodes are accepted only with the exact fail-closed database fixture.

| ID | Executable node(s) |
|---|---|
| U01 | `tests/integration/test_context_hub.py::test_u01_all_surfaces_exhaust_exact_three_scope_canaries` |
| U02 | `tests/integration/test_context_hub.py::test_u02_all_family_kind_reopen_substitutions_fail_closed` |
| U03 | `tests/test_context_hub.py::test_cursor_is_opaque_bound_and_strictly_validated` |
| U04 | `frontend/src/ContextHub.test.tsx::renders fixed family order and visible kind, trust, state, scope, provenance, and exact facets` |
| U05 | `tests/integration/test_context_hub.py::test_u05_hostile_instructions_execute_no_authority_or_mutation`; `frontend/src/ContextHub.test.tsx::keeps hostile content inert and reopens detail in-page without exposing or persisting the token` |
| U06 | `frontend/src/ContextHub.test.tsx::contains the complete hostile rendering corpus without execution navigation or label spoofing` |
| U07 | `tests/integration/test_context_hub.py::test_u07_excluded_canaries_never_reach_hub_surfaces_or_errors`; `frontend/src/ContextHub.test.tsx::keeps excluded privacy and capability canaries out of the DOM` |
| U08 | `tests/integration/test_context_hub.py::test_exact_scope_grouping_inert_text_and_reopen` |
| U09 | `tests/integration/test_context_hub.py::test_u09_native_github_and_calendar_state_is_preserved` |
| U10 | `tests/integration/test_context_hub.py::test_u10_family_flood_keeps_fixed_groups_stable_ties_and_no_scores` |
| U11 | `tests/integration/test_context_hub.py::test_context_hub_api_paginates_reopens_facets_and_rejects_replay`; `frontend/src/ContextHub.test.tsx::paginates with the canonical applied snapshot and invalidates the cursor when controls change` |
| U12 | `tests/integration/test_context_hub.py::test_u12_boundaries_overbounds_repetition_and_sql_work_are_bounded` |
| U13 | `tests/integration/test_context_hub.py::test_u13_runtime_tripwires_stay_zero_across_success_and_error_paths` |
| U14 | `tests/integration/test_context_hub.py::test_u14_query_facets_and_detail_mutate_no_protected_domain` |
| U15 | `tests/test_context_hub_security_adversarial.py::test_u15_registry_agent_automation_and_evidence_catalogs_have_no_hub_authority`; `tests/integration/test_context_hub.py::test_u15_agent_automation_and_tool_interfaces_reject_context_hub` |
| U16 | `tests/integration/test_connector_persistence.py::test_project_export_v1_excludes_all_connector_data`; `tests/integration/test_calendar_persistence.py::test_export_v1_excludes_calendar_and_secret_canary` |
| U17 | `tests/test_context_hub_security_adversarial.py::test_u17_unknown_nested_configuration_and_confusable_injection_rejects` |
| U18 | `tests/integration/test_context_hub.py::test_u18_postgresql_event_barriers_preserve_scope_provenance_and_keysets`; `tests/integration/test_context_hub.py::test_u18_github_commit_between_hub_pages_is_old_or_new_not_mixed`; `tests/integration/test_context_hub.py::test_u18_calendar_and_scope_commits_make_detail_exact_or_fail_closed` |

## Final evidence inventory

U09 executes real `/context-hub/query` and `/context-hub/detail` requests after
native persistence transitions. GitHub covers current, changed revision,
incomplete/non-reconciling omission, complete omission to stale, and later
presence to current. Calendar covers positive current evidence, equal replay,
non-covering complete evidence, covering omission to stale, changed revision,
and later positive current evidence. Responses retain exact scope and
immutable provenance and never fabricate cancelled/deleted state.

U18 uses `threading.Event` barriers only, with no sleeps. Three nodes cover a
local Source/Chunk commit between reads, a GitHub revision commit between Hub
pages plus old-detail reopen, and a Calendar revision/evidence commit combined
with an exact scope ownership move and old-detail reopen. Assertions admit only
valid old/new projections, prohibit cross-scope leakage and duplicate reopen
identities, preserve provenance, and require exact reopen or safe 404.

U12 executes character/UTF-8 query limits, page limits, overlong cursor/reopen
limits, nested/unknown request rejection, stored title/text projection limits,
response and per-family ceilings, repeated reads, and a SQL-statement ceiling.
U14 compares complete rows across knowledge, connector, Calendar,
extraction/import, refresh, Automation, Agent, Tool invocation, and Approval
domains on success and failure paths; domain-writer and provider/runtime
tripwires stay zero. U16 executes project-export-v1, inspects both ZIP archives,
and excludes connector, Calendar, credential, sync/runtime, and external Hub
canaries.

The bounded code-owned hostile corpus contains synthetic values only. Runtime
tripwires cover DNS, sync/async HTTP, GitHub, Calendar, Google OAuth, Windows
credentials, planning, research/model, and embeddings; all recorded zero.

## Stable boundaries

Alembic remains `0016_calendar_event_observations`. Tool Registry remains
`agent-tools-v1` with seven definitions. Project export remains
`second-brain-project-export` version `1`. There are no production-code,
migration, schema, table, index, dependency, provider-scope, Tool, Agent,
Automation, import, refresh, scheduling, write-authority, or CP114 changes.

## Verification

- Manifest/adversarial suite: **29 passed**.
- CP113 PostgreSQL gate: **17 passed, 1,385 deselected, zero skipped**.
- Focused U09/U18 suite: **3 passed**; expanded U09/U12/U14/U18: **6 passed**.
- Context Hub frontend file: **8 passed**.
- Full attempt 1: **1,397 passed, four setup errors from pre-run database
  residue, and one unrelated Windows credential-store failure**. The verifier
  restored the database; a direct audit found no remaining `hub-*` rows.
- Clean Full attempt 2: pip integrity, Ruff lint/format over 497 files, and mypy
  over 208 production files passed; backend was **1,401 passed, one failed,
  zero skipped**. The only failure was
  `tests/test_credentials.py::test_windows_adapter_real_round_trip_or_explicit_unsupported`
  because the OS returned `credential_store_locked`; isolation reproduced it.
  Alembic and frontend stages did not run, so final Full success is not claimed.
- Execution-context classification identified the failing shell as the
  restricted `HR85029\CodexSandboxOffline` identity. The normal authorized,
  interactive Windows host identity `HR85029\KushKush` required no elevation;
  Windows Credential Manager was available there and the exact isolated node
  passed: **1 passed**.
- Final authoritative Full run from that same host context: dependency
  integrity passed; Ruff lint and format passed over 497 files; strict mypy
  passed over 208 production files; **1,402 backend tests passed, zero
  skipped**; Alembic current and heads were
  `0016_calendar_event_observations`, and Alembic check found no new upgrade
  operations; frontend ESLint and TypeScript passed; **156 frontend tests in
  16 files passed** with no skips reported; the 89-module production build
  passed; and `git diff --check` passed.

All work remains unstaged and uncommitted. Nothing was pushed, no PR was
created, and CP114 was not started.

## Exact changed paths

- `docs/ARCHITECTURE.md`
- `docs/CHECKPOINTS.md`
- `docs/ROADMAP.md`
- `docs/checkpoint-113-report.md`
- `frontend/src/ContextHub.test.tsx`
- `pyproject.toml`
- `tests/integration/conftest.py`
- `tests/integration/test_calendar_persistence.py`
- `tests/integration/test_connector_persistence.py`
- `tests/integration/test_context_hub.py`
- `tests/test_context_hub_security_adversarial.py`
- `tests/test_context_hub_security_evaluation.py`
