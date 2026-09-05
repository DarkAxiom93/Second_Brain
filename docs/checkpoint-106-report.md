# Checkpoint 106 deterministic Calendar security/evaluation gate report

Status: **Approved and complete after human review. G01-G18 are green. CP107
has not started.**

## Preflight and scope

Preflight passed on clean synchronized `main` at exact approved CP105 commit
`4d8c0f502fb57dcc8658519cd1833efa6c3f29b5`; `HEAD` and `origin/main` matched.
Exact push CI run `33952983030` completed successfully for that SHA. Parsed and
live database identities were `127.0.0.1:5433/second_brain` and
`127.0.0.1:5433/second_brain_test`. Alembic current and sole head were
`0016_calendar_event_observations`, and `alembic check` was clean. Tool Registry
was `agent-tools-v1`; Project export was `second-brain-project-export` version
`1`.

CP106 adds test/evaluation evidence only. It changes no production code,
migration, dependency, OAuth/provider authority, API, schema, UI capability,
Calendar import, scheduling, Agent/Automation access, or Calendar write.

## Manifest and adversarial corpus

`tests/test_calendar_security_evaluation.py` owns one insertion-ordered mapping
for exactly G01-G18. It maps **37 unique node selectors**: two per threat except
G09, which has three independent recurrence/replay proofs. No node is reused
across threats. Meta-tests parse Python and UI test sources and fail for a
missing/renamed node, missing executable assertion, skip/skipif/xfail/todo,
manifest order or ID drift, duplicate node, or missing omission/fault/stable-ID
frontier.

`tests/test_calendar_security_adversarial.py` adds bounded synthetic canaries
for access/refresh/ID tokens, raw subject, state, code and verifier; exact and
hostile OAuth scopes; HTML/Markdown/script/bidi/control/instruction text;
privacy and URL-bearing provider fields; hostile nested/confusable authority
configuration; malformed/cancelled/unknown event shapes; transport/request
bounds; stable registry/export identities; and executable import/scheduling/
Agent/Automation/write omission. All behavior is fake, local, and deterministic.

## Exact G01-G18 traceability

| Threat | Exact deterministic evidence nodes | Result |
|---|---|---|
| G01 | `test_secret_canaries_have_no_calendar_persistence_or_public_field`; `test_provider_error_body_and_exception_never_escape` | PASS |
| G02 | `test_oauth_scope_catalog_is_exact_and_cannot_be_injected_via_calendar_config`; `test_transport_rejects_scope_drift_and_caches_bounded_jwks` | PASS |
| G03 | `test_forged_malformed_unknown_key_and_exact_fingerprint`; `test_reauthorization_account_substitution_preserves_prior_envelope` | PASS |
| G04 | `test_allowlist_bounds_and_exact_validation`; `test_transport_uses_exact_get_path_query_and_projection` | PASS |
| G05 | `test_exact_project_and_unassigned_are_distinct`; `test_scope_ownership_revision_replay_and_historical_scope` | PASS |
| G06 | `test_hostile_content_privacy_and_url_families_are_excluded_before_hashing`; UI `loads scoped Calendar projections explicitly and renders hostile titles inertly` | PASS |
| G07 | `test_projection_catalog_excludes_sensitive_fields`; `test_private_and_special_events_use_only_fixed_labels` | PASS |
| G08 | UI `renders hostile calendar IDs inertly with no provider-controlled links`; UI `shows accessible Calendar detail with no action or provider link` | PASS |
| G09 | `test_moved_recurring_occurrence_uses_original_start_identity`; `test_occurrence_identity_is_stable_across_current_time_changes`; `test_observation_equal_replay_stale_resurrection_and_local_browsing` | PASS |
| G10 | `test_unversioned_and_all_day_timezone_uncertainty_infer_no_stale`; `test_private_special_temporal_and_unknown_type_fail_closed` | PASS |
| G11 | `test_manual_full_refresh_persists_minimized_pages_and_safe_history`; `test_observation_uniqueness_and_cross_lineage_substitution_fail_closed` | PASS |
| G12 | `test_callback_timeout_is_bounded`; `test_unexpected_shapes_and_extreme_tokens_fail_closed_without_raw_leakage` | PASS |
| G13 | `test_stale_refresh_is_generation_fenced_with_barrier`; `test_concurrent_stale_disable_has_one_winner` | PASS |
| G14 | `test_import_and_scheduling_are_absent_from_calendar_surfaces`; UI `runs only an explicit account refresh and renders safe per-calendar status` | PASS |
| G15 | `test_zero_calendar_data_or_protected_domain_calls`; `test_calendar_model_catalog_has_no_write_import_agent_or_automation_authority` | PASS |
| G16 | `test_export_v1_excludes_calendar_and_secret_canary`; `test_stable_registry_export_and_closed_transport_identities` | PASS |
| G17 | `test_configuration_rejects_nested_confusable_and_authority_fields`; `test_create_list_read_safe_projection_and_hostile_ids` | PASS |
| G18 | `test_fingerprint_missing_credential_and_cross_account_calendar_protection`; `test_tables_safe_fields_and_one_active_sync` | PASS |

The fully qualified node selectors remain executable in the code-owned manifest;
the table uses their unique terminal names for readability.

## Verification and conclusions

The focused Calendar/OAuth/security backend set passed **102 tests**, zero
failed and zero skipped. The configured focused Calendar frontend set passed
**12 tests**, zero failed and zero skipped. The manifest/meta/adversarial-only
set passed **48 tests**, zero failed and zero skipped.

The authoritative normal-host `scripts/verify.ps1 -Mode Full` run passed
database identity, dependency integrity, Ruff lint/format, strict mypy, and
**1,339 backend tests**, zero failed and zero skipped. Alembic current/head/check
then passed. Frontend lint and typecheck passed, but Vitest stopped the verifier
at **143 passed and 2 failed** of 145; the production build was therefore not
run by that invocation.

Both failures were in the pre-existing `CalendarAccounts.test.tsx`. The
configuration test exceeded its 5-second timeout, while the revision-fenced edit
test observed the already-rendered revision-3 account after its mocked response
and could no longer find the transient `Save new configuration revision`
button. The same file passed 6/6 and the complete focused Calendar UI selection
passed 12/12 immediately before Full. Per the checkpoint instruction, no
production code or security expectation was changed and Full was not silently
retried. This is an unresolved full-suite frontend timing/state-test blocker,
not an observed Calendar production defect or G01-G18 failure.

The narrow deterministic correction changed only that test file. The first test
now applies exact controlled input values with synchronous `fireEvent.change`
instead of simulating 118 character-by-character keystrokes under full-suite
load; it still submits through the user-visible button and retains the exact
request-body, cleared-field, focus, and zero-browser-storage assertions. This
removes the timeout and prevents unfinished user interaction work from leaking
into the next test after a timeout.

The revision-fenced edit test now captures the submit button while the explicit
edit state is stable, applies the new calendar ID with a controlled change,
clicks that exact button, and awaits both the final focused success announcement
and rendered revision 3. Its exact three-request count and revision-2/calendar-
ID request-body assertions remain unchanged. It no longer depends on finding a
transient edit label after the mocked revision-3 response may already have
completed.

The two affected tests passed three consecutive targeted runs (**6 test
executions**). The complete file then passed **6/6**, and the focused Calendar
frontend selection passed **12/12**, zero skipped. The unchanged CP106 manifest
and adversarial gate passed **48/48**, zero skipped.

A fresh single authoritative normal-host Full run passed dependency integrity,
Ruff lint/format, strict mypy, **1,339/1,339 backend tests**, Alembic current/
head/check, frontend lint/typecheck, **145/145 frontend tests**, the production
Vite build, and `git diff --check`, all with zero skips. No destructive database
lifecycle was needed for this run: a read-only identity/count precheck verified
`second_brain_test` and found zero Calendar account revisions referencing a
Project.

Secret/privacy scans found zero prohibited canary occurrence. Project A,
Project B and explicit-unassigned scope remained isolated. Equal recurrence
replay, moved/all-day/DST identities and current/stale reconciliation passed.
CP104 import omission and CP105 scheduling omission are executable gate facts,
not documentation assumptions. Provider/ownership/observation/evidence faults
fail closed with atomic page behavior and ineligible inconsistent runs.

No production defect was found. There are no migration or dependency changes.
No real credential was enumerated, and no real Google/Calendar request was
made. There is zero Calendar write, import, scheduling, Agent, or Automation
Calendar authority. CP107 was not started. All paths remain unstaged and
uncommitted until final lifecycle approval. Authoritative Full is green and
CP106 is approved and complete after human review.
