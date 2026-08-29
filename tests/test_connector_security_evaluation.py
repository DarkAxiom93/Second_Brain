"""Executable Checkpoint 95 C01-C18 threat-to-test release manifest."""

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

THREAT_TESTS: dict[str, tuple[str, ...]] = {
    "C01": (
        "tests/test_credential_operator.py::test_unexpected_nested_exception_text_is_redacted",
        "tests/test_connector_adversarial_evaluation.py::test_secret_canary_is_absent_from_public_schema_export_and_safe_failures",
    ),
    "C02": (
        "tests/test_github_transport.py::test_provider_permission_headers_are_discarded_and_cannot_define_authority",
        "tests/test_github_transport.py::test_exact_get_only_request_inventory_and_headers",
    ),
    "C03": (
        "tests/integration/test_connector_refresh_api.py::test_authenticated_identity_mismatch_fails_and_fences_account",
        "tests/integration/test_connector_persistence.py::test_cross_account_identity_and_restrictive_provenance_fks",
        "tests/integration/test_connector_refresh_api.py::test_disabled_and_stale_revision_make_zero_requests",
    ),
    "C04": (
        "tests/test_connector_adversarial_evaluation.py::test_hostile_external_content_is_only_inert_bounded_data",
        "tests/integration/test_connector_refresh_schedules.py::test_materialize_claim_link_is_deterministic_and_never_agent_or_import",
    ),
    "C05": (
        "tests/integration/test_connector_account_api.py::test_exact_project_or_explicit_unassigned_and_closed_input",
        "tests/integration/test_connector_refresh_api.py::test_external_browser_history_cursor_links_and_scope_fail_closed",
    ),
    "C06": (
        "tests/integration/test_connector_refresh_api.py::test_credential_failures_are_safe_and_make_zero_requests",
        "tests/integration/test_connector_refresh_api.py::test_authenticated_identity_mismatch_fails_and_fences_account",
        "tests/integration/test_connector_refresh_api.py::test_disabled_and_stale_revision_make_zero_requests",
    ),
    "C07": (
        "tests/integration/test_connector_persistence.py::test_equal_replay_is_write_free_and_changed_version_appends_provenance",
        "tests/integration/test_connector_refresh_api.py::test_manual_refresh_inventory_quarantine_replay_and_safe_status",
        "tests/integration/test_external_item_imports.py::test_sequential_and_concurrent_confirmation_create_exactly_one_import",
    ),
    "C08": (
        "tests/test_github_transport.py::test_redirect_is_rejected_and_retry_is_at_most_once",
        "tests/test_github_transport.py::test_request_run_byte_and_deadline_ceilings_prevent_requests",
        "tests/integration/test_connector_refresh_api.py::test_pagination_ceiling_is_incomplete_without_deletion_inference",
    ),
    "C09": (
        "tests/integration/test_connector_refresh_api.py::test_provider_failures_return_only_safe_explicit_retry_status",
        "tests/integration/test_connector_refresh_api.py::test_global_active_sync_cap_rejects_before_credential_or_network",
    ),
    "C10": (
        "tests/test_connector_adversarial_evaluation.py::test_hostile_external_content_is_only_inert_bounded_data",
        "tests/test_github_transport.py::test_non_json_and_oversized_responses_fail_closed",
        "tests/integration/test_connector_refresh_api.py::test_external_browser_history_cursor_links_and_scope_fail_closed",
    ),
    "C11": (
        "tests/integration/test_connector_refresh_api.py::test_repository_numeric_identity_change_is_rejected",
        "tests/integration/test_connector_refresh_api.py::test_authenticated_identity_mismatch_fails_and_fences_account",
        "tests/test_github_transport.py::test_redirect_is_rejected_and_retry_is_at_most_once",
    ),
    "C12": (
        "tests/integration/test_connector_refresh_api.py::test_complete_absence_stales_partial_does_not_and_replay_restores",
        "tests/integration/test_connector_refresh_api.py::test_page_failure_preserves_earlier_quarantine_and_is_not_complete",
    ),
    "C13": (
        "tests/integration/test_connector_refresh_schedules.py::test_default_draft_lifecycle_cas_and_one_per_account",
        "tests/integration/test_connector_refresh_schedules.py::test_materialize_claim_link_is_deterministic_and_never_agent_or_import",
        "tests/integration/test_connector_refresh_schedules.py::test_expired_lease_reclaims_once_and_stale_owner_is_fenced",
    ),
    "C14": (
        "tests/integration/test_connector_refresh_api.py::test_page_failure_preserves_earlier_quarantine_and_is_not_complete",
        "tests/integration/test_connector_refresh_api.py::test_provider_failures_return_only_safe_explicit_retry_status",
        "tests/integration/test_connector_refresh_schedules.py::test_expired_lease_reclaims_once_and_stale_owner_is_fenced",
    ),
    "C15": (
        "tests/test_credential_operator.py::test_unexpected_nested_exception_text_is_redacted",
        "tests/test_connector_adversarial_evaluation.py::test_secret_canary_is_absent_from_public_schema_export_and_safe_failures",
    ),
    "C16": (
        "tests/integration/test_connector_persistence.py::test_project_export_v1_excludes_all_connector_data",
        "tests/test_connector_adversarial_evaluation.py::test_database_models_have_no_plaintext_credential_field",
    ),
    "C17": (
        "tests/test_connector_adversarial_evaluation.py::test_configuration_cannot_inject_connector_authority",
        "tests/test_connector_catalog.py::test_catalog_is_exactly_github_and_cannot_express_authority",
        "tests/integration/test_connector_account_api.py::test_allowlist_bounds_canonical_validation_and_hostile_input",
    ),
    "C18": (
        "tests/test_github_transport.py::test_exact_get_only_request_inventory_and_headers",
        "tests/integration/test_connector_refresh_api.py::test_manual_refresh_inventory_quarantine_replay_and_safe_status",
        "tests/integration/test_external_item_imports.py::test_preview_is_read_only_and_exact_import_is_audited_and_inert",
        "tests/integration/test_connector_refresh_schedules.py::test_materialize_claim_link_is_deterministic_and_never_agent_or_import",
    ),
}


def _python_tests(path: Path) -> dict[str, bool]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.name: any(
            isinstance(child, ast.Assert)
            or (
                isinstance(child, ast.Call)
                and isinstance(child.func, ast.Attribute)
                and child.func.attr == "raises"
            )
            for child in ast.walk(node)
        )
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    }


def test_manifest_covers_exact_connector_threat_register() -> None:
    expected = [f"C{number:02d}" for number in range(1, 19)]
    assert list(THREAT_TESTS) == expected
    assert len(THREAT_TESTS) == len(set(THREAT_TESTS))
    assert all(tests for tests in THREAT_TESTS.values())
    assert all("::" in node_id for tests in THREAT_TESTS.values() for node_id in tests)


@pytest.mark.parametrize(
    "node_id", sorted({node_id for tests in THREAT_TESTS.values() for node_id in tests})
)
def test_every_manifest_reference_is_an_assertive_automated_test(node_id: str) -> None:
    relative_path, test_name = node_id.split("::", 1)
    path = ROOT / relative_path
    assert path.is_file()
    tests = _python_tests(path)
    assert test_name in tests
    assert tests[test_name], "referenced test has no executable prevention assertion"


def test_manifest_includes_fault_concurrency_frontier_and_mutation_proofs() -> None:
    evidence = {node_id for tests in THREAT_TESTS.values() for node_id in tests}
    required_fragments = (
        "credential_failures_are_safe",
        "concurrent_confirmation",
        "pagination_ceiling",
        "complete_absence_stales_partial_does_not",
        "stale_owner_is_fenced",
        "project_export_v1_excludes",
        "exact_get_only_request_inventory",
        "exact_import_is_audited_and_inert",
    )
    assert all(
        any(fragment in node_id for node_id in evidence)
        for fragment in required_fragments
    )
