# Checkpoint 95 report - connector security and evaluation gate

Status: **Approved and complete after human review.**

## Outcome

Checkpoint 95 adds a deterministic code-owned release manifest for every V1.4
connector threat C01-C18, a bounded hostile-content/configuration corpus,
credential/export/schema leak scans, and focused frontend schedule evidence. It
reuses the production CP88-94 tests. No production defect was found and no
production code changed.

## C01-C18 release matrix

All exact pytest node IDs below passed in the authoritative Full run.
Parametrized function IDs identify their complete deterministic matrices.

| Threat | Deterministic tests | Result |
|---|---|---|
| C01 | `tests/test_credential_operator.py::test_unexpected_nested_exception_text_is_redacted`; `tests/test_connector_adversarial_evaluation.py::test_secret_canary_is_absent_from_public_schema_export_and_safe_failures` | Pass |
| C02 | `tests/test_github_transport.py::test_provider_permission_headers_are_discarded_and_cannot_define_authority`; `tests/test_github_transport.py::test_exact_get_only_request_inventory_and_headers` | Pass |
| C03 | `tests/integration/test_connector_refresh_api.py::test_authenticated_identity_mismatch_fails_and_fences_account`; `tests/integration/test_connector_persistence.py::test_cross_account_identity_and_restrictive_provenance_fks`; `tests/integration/test_connector_refresh_api.py::test_disabled_and_stale_revision_make_zero_requests` | Pass |
| C04 | `tests/test_connector_adversarial_evaluation.py::test_hostile_external_content_is_only_inert_bounded_data`; `tests/integration/test_connector_refresh_schedules.py::test_materialize_claim_link_is_deterministic_and_never_agent_or_import` | Pass |
| C05 | `tests/integration/test_connector_account_api.py::test_exact_project_or_explicit_unassigned_and_closed_input`; `tests/integration/test_connector_refresh_api.py::test_external_browser_history_cursor_links_and_scope_fail_closed` | Pass |
| C06 | `tests/integration/test_connector_refresh_api.py::test_credential_failures_are_safe_and_make_zero_requests`; `tests/integration/test_connector_refresh_api.py::test_authenticated_identity_mismatch_fails_and_fences_account`; `tests/integration/test_connector_refresh_api.py::test_disabled_and_stale_revision_make_zero_requests` | Pass |
| C07 | `tests/integration/test_connector_persistence.py::test_equal_replay_is_write_free_and_changed_version_appends_provenance`; `tests/integration/test_connector_refresh_api.py::test_manual_refresh_inventory_quarantine_replay_and_safe_status`; `tests/integration/test_external_item_imports.py::test_sequential_and_concurrent_confirmation_create_exactly_one_import` | Pass |
| C08 | `tests/test_github_transport.py::test_redirect_is_rejected_and_retry_is_at_most_once`; `tests/test_github_transport.py::test_request_run_byte_and_deadline_ceilings_prevent_requests`; `tests/integration/test_connector_refresh_api.py::test_pagination_ceiling_is_incomplete_without_deletion_inference` | Pass |
| C09 | `tests/integration/test_connector_refresh_api.py::test_provider_failures_return_only_safe_explicit_retry_status`; `tests/integration/test_connector_refresh_api.py::test_global_active_sync_cap_rejects_before_credential_or_network` | Pass |
| C10 | `tests/test_connector_adversarial_evaluation.py::test_hostile_external_content_is_only_inert_bounded_data`; `tests/test_github_transport.py::test_non_json_and_oversized_responses_fail_closed`; `tests/integration/test_connector_refresh_api.py::test_external_browser_history_cursor_links_and_scope_fail_closed` | Pass |
| C11 | `tests/integration/test_connector_refresh_api.py::test_repository_numeric_identity_change_is_rejected`; `tests/integration/test_connector_refresh_api.py::test_authenticated_identity_mismatch_fails_and_fences_account`; `tests/test_github_transport.py::test_redirect_is_rejected_and_retry_is_at_most_once` | Pass |
| C12 | `tests/integration/test_connector_refresh_api.py::test_complete_absence_stales_partial_does_not_and_replay_restores`; `tests/integration/test_connector_refresh_api.py::test_page_failure_preserves_earlier_quarantine_and_is_not_complete` | Pass |
| C13 | `tests/integration/test_connector_refresh_schedules.py::test_default_draft_lifecycle_cas_and_one_per_account`; `tests/integration/test_connector_refresh_schedules.py::test_materialize_claim_link_is_deterministic_and_never_agent_or_import`; `tests/integration/test_connector_refresh_schedules.py::test_expired_lease_reclaims_once_and_stale_owner_is_fenced` | Pass |
| C14 | `tests/integration/test_connector_refresh_api.py::test_page_failure_preserves_earlier_quarantine_and_is_not_complete`; `tests/integration/test_connector_refresh_api.py::test_provider_failures_return_only_safe_explicit_retry_status`; `tests/integration/test_connector_refresh_schedules.py::test_expired_lease_reclaims_once_and_stale_owner_is_fenced` | Pass |
| C15 | `tests/test_credential_operator.py::test_unexpected_nested_exception_text_is_redacted`; `tests/test_connector_adversarial_evaluation.py::test_secret_canary_is_absent_from_public_schema_export_and_safe_failures` | Pass |
| C16 | `tests/integration/test_connector_persistence.py::test_project_export_v1_excludes_all_connector_data`; `tests/test_connector_adversarial_evaluation.py::test_database_models_have_no_plaintext_credential_field` | Pass |
| C17 | `tests/test_connector_adversarial_evaluation.py::test_configuration_cannot_inject_connector_authority`; `tests/test_connector_catalog.py::test_catalog_is_exactly_github_and_cannot_express_authority`; `tests/integration/test_connector_account_api.py::test_allowlist_bounds_canonical_validation_and_hostile_input` | Pass |
| C18 | `tests/test_github_transport.py::test_exact_get_only_request_inventory_and_headers`; `tests/integration/test_connector_refresh_api.py::test_manual_refresh_inventory_quarantine_replay_and_safe_status`; `tests/integration/test_external_item_imports.py::test_preview_is_read_only_and_exact_import_is_audited_and_inert`; `tests/integration/test_connector_refresh_schedules.py::test_materialize_claim_link_is_deterministic_and_never_agent_or_import` | Pass |

The manifest validator proves IDs are exactly C01-C18 with no omission or
duplicate, every entry is nonempty, all 32 unique referenced nodes exist, and
every referenced Python test has an executable prevention or fail-closed
assertion. Focused and Full runs execute these surfaces; no entry is narrative.

## Security evidence

The bounded corpus has eight hostile external-content families and fourteen
configuration-injection fields. It covers Tool/Agent and secret-exfiltration
commands; scope/write/admin and import widening; shell, Python, SQL, filesystem,
and network instructions; HTML/script; Markdown links/images and dangerous
schemes; encoded text, bidi/isolate controls, ignore-prior-instruction text;
forged Project/account identity; arbitrary provider/host/URL/method/header/body/
GraphQL; and executable configuration.

Synthetic canary scans passed across public connector schemas, safe errors,
credential-operator exception handling, connector database column inventory,
Project export/archive inventory, API/database evidence, and frontend DOM and
storage cases. No real credential was used. Project A, Project B, and explicit
unassigned scope remain isolated; forged account/item/cursor and cross-account
provenance fail closed.

The fake request inventory remains exactly GET `/user`, configured repository
metadata, bounded issues, and bounded pulls on fixed `api.github.com`. Provider
permission headers cannot establish authority. Redirects fail closed. There is
no continuation-URL following, POST/PUT/PATCH/DELETE, GraphQL, or provider write.

PostgreSQL gates pass for refresh replay, equal/changed revisions, concurrent
exact import confirmation, capacity, partial-page/fault preservation,
complete-only absence reconciliation, stale replay restoration, deterministic
schedule materialization/linkage, and expired-lease generation fencing.
Protected-domain complete-row snapshots are unchanged by sync, quarantine,
browse/reconciliation, and scheduling. Explicit import permits only its exact
Source/SourceDocument/chunk/provenance rows and creates no Memory, proposal,
Approval, AgentRun, or Automation. Scheduling creates no AgentRun/import and one
occurrence links to at most one scheduled ConnectorSyncRun.

Project export remains `second-brain-project-export` version `1` and excludes
accounts, credential references, sync runs, items/import provenance, schedules,
occurrences, and notifications. Connector schema has no plaintext credential
field. OS credentials remain outside application export; machine backups may
independently contain OS-protected Credential Manager data and must retain
platform protection.

Frontend tests prove inert text, safe links, External/Untrusted labeling,
explicit import confirmation and warning, draft-first schedule warning and
explicit enable, no polling, no raw HTML/Markdown execution, no browser
credential or reference persistence, no hidden Agent/import action, and safe
status rendering.

## Verification

- New manifest/adversarial gate: **58 passed**, zero skipped.
- Focused connector backend: **144 passed**, zero skipped.
- Focused connector frontend: **7 passed across 2 files**, zero skipped.
- Full backend: **1,235 passed**, zero skipped.
- Full frontend: **136 passed across 14 files**, zero skipped.
- Pip integrity, Ruff lint/format, strict mypy over 182 production files,
  frontend ESLint/TypeScript/build, and `git diff --check`: pass.
- Alembic current/sole head: `0014_connector_refresh_schedules`; check clean.
- Tool Registry: `agent-tools-v1`.
- Project export: `second-brain-project-export` version `1`.

## Residual risk and boundaries

The approved residual risk remains: the bounded GitHub surface cannot observe
complete provider-side fine-grained-PAT grants, so an operator could grant more
than the application requests. Exact code-owned policy, fixed GET-only request
inventory, repository allowlisting, identity fencing, and no discovery/write
endpoint limit application authority. Host/OS and provider failures beyond the
deterministic hooks remain local operational residual risks.

No migration, production code, dependency, Tool Registry/export identity,
Agent/Automation connector authority, provider endpoint, transport method,
import/scheduling behavior, automatic/scheduled import, or external write was
added. No real GitHub credential/request was used. Checkpoint 96 was not
started. Every C01-C18 gate passes. Checkpoint 95 is approved and complete
after human review.
