"""Executable CP106 G01-G18 threat-to-test release manifest."""

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

THREAT_TESTS: dict[str, tuple[str, ...]] = {
    "G01": (
        "tests/test_calendar_security_adversarial.py::test_secret_canaries_have_no_calendar_persistence_or_public_field",
        "tests/test_google_oauth.py::test_provider_error_body_and_exception_never_escape",
    ),
    "G02": (
        "tests/test_calendar_security_adversarial.py::test_oauth_scope_catalog_is_exact_and_cannot_be_injected_via_calendar_config",
        "tests/test_google_oauth.py::test_transport_rejects_scope_drift_and_caches_bounded_jwks",
    ),
    "G03": (
        "tests/test_google_oauth.py::test_forged_malformed_unknown_key_and_exact_fingerprint",
        "tests/test_google_oauth.py::test_reauthorization_account_substitution_preserves_prior_envelope",
    ),
    "G04": (
        "tests/integration/test_calendar_account_api.py::test_allowlist_bounds_and_exact_validation",
        "tests/test_calendar_sync.py::test_transport_uses_exact_get_path_query_and_projection",
    ),
    "G05": (
        "tests/integration/test_calendar_account_api.py::test_exact_project_and_unassigned_are_distinct",
        "tests/integration/test_calendar_persistence.py::test_scope_ownership_revision_replay_and_historical_scope",
    ),
    "G06": (
        "tests/test_calendar_security_adversarial.py::test_hostile_content_privacy_and_url_families_are_excluded_before_hashing",
        "frontend/src/ExternalContext.test.tsx::loads scoped Calendar projections "
        "explicitly and renders hostile titles inertly",
    ),
    "G07": (
        "tests/test_calendar_catalog.py::test_projection_catalog_excludes_sensitive_fields",
        "tests/test_calendar_security_adversarial.py::test_private_and_special_events_use_only_fixed_labels",
    ),
    "G08": (
        "frontend/src/CalendarAccounts.test.tsx::renders hostile calendar IDs "
        "inertly with no provider-controlled links",
        "frontend/src/ExternalContext.test.tsx::shows accessible Calendar detail "
        "with no action or provider link",
    ),
    "G09": (
        "tests/test_calendar_sync.py::test_moved_recurring_occurrence_uses_original_start_identity",
        "tests/test_calendar_catalog.py::test_occurrence_identity_is_stable_across_current_time_changes",
        "tests/integration/test_calendar_account_api.py::test_observation_equal_replay_stale_resurrection_and_local_browsing",
    ),
    "G10": (
        "tests/integration/test_calendar_account_api.py::test_unversioned_and_all_day_timezone_uncertainty_infer_no_stale",
        "tests/integration/test_calendar_persistence.py::test_private_special_temporal_and_unknown_type_fail_closed",
    ),
    "G11": (
        "tests/integration/test_calendar_account_api.py::test_manual_full_refresh_persists_minimized_pages_and_safe_history",
        "tests/integration/test_calendar_persistence.py::test_observation_uniqueness_and_cross_lineage_substitution_fail_closed",
    ),
    "G12": (
        "tests/test_google_oauth.py::test_callback_timeout_is_bounded",
        "tests/test_calendar_security_adversarial.py::test_unexpected_shapes_and_extreme_tokens_fail_closed_without_raw_leakage",
    ),
    "G13": (
        "tests/test_google_oauth.py::test_stale_refresh_is_generation_fenced_with_barrier",
        "tests/integration/test_calendar_account_api.py::test_concurrent_stale_disable_has_one_winner",
    ),
    "G14": (
        "tests/test_calendar_security_adversarial.py::test_import_and_scheduling_are_absent_from_calendar_surfaces",
        "frontend/src/CalendarAccounts.test.tsx::runs only an explicit account "
        "refresh and renders safe per-calendar status",
    ),
    "G15": (
        "tests/integration/test_calendar_account_api.py::test_zero_calendar_data_or_protected_domain_calls",
        "tests/test_calendar_security_adversarial.py::test_calendar_model_catalog_has_no_write_import_agent_or_automation_authority",
    ),
    "G16": (
        "tests/integration/test_calendar_persistence.py::test_export_v1_excludes_calendar_and_secret_canary",
        "tests/test_calendar_security_adversarial.py::test_stable_registry_export_and_closed_transport_identities",
    ),
    "G17": (
        "tests/test_calendar_security_adversarial.py::test_configuration_rejects_nested_confusable_and_authority_fields",
        "tests/integration/test_calendar_account_api.py::test_create_list_read_safe_projection_and_hostile_ids",
    ),
    "G18": (
        "tests/integration/test_calendar_account_api.py::test_fingerprint_missing_credential_and_cross_account_calendar_protection",
        "tests/integration/test_calendar_persistence.py::test_tables_safe_fields_and_one_active_sync",
    ),
}


def _python_tests(path: Path) -> dict[str, tuple[bool, bool]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    result: dict[str, tuple[bool, bool]] = {}
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef)
        ) and node.name.startswith("test_"):
            assertive = any(
                isinstance(child, ast.Assert)
                or (
                    isinstance(child, ast.Call)
                    and isinstance(child.func, ast.Attribute)
                    and child.func.attr == "raises"
                )
                for child in ast.walk(node)
            )
            conditional = any(
                isinstance(decorator, ast.Attribute)
                and decorator.attr in {"skip", "skipif", "xfail"}
                for decorator in node.decorator_list
            )
            result[node.name] = (assertive, conditional)
    return result


def test_manifest_is_exact_ordered_unique_g01_through_g18() -> None:
    expected = [f"G{number:02d}" for number in range(1, 19)]
    assert list(THREAT_TESTS) == expected
    nodes = [node for mapped in THREAT_TESTS.values() for node in mapped]
    assert all(mapped for mapped in THREAT_TESTS.values())
    assert len(nodes) == len(set(nodes)), (
        "a node may not silently cover unrelated threats"
    )


@pytest.mark.parametrize(
    "node_id", [node for mapped in THREAT_TESTS.values() for node in mapped]
)
def test_every_manifest_node_exists_is_assertive_and_unconditional(
    node_id: str,
) -> None:
    relative_path, test_name = node_id.split("::", 1)
    path = ROOT / relative_path
    assert path.is_file()
    source = path.read_text(encoding="utf-8")
    if path.suffix == ".py":
        tests = _python_tests(path)
        assert test_name in tests
        assert tests[test_name] == (True, False)
    else:
        marker = f'it("{test_name}"'
        assert marker in source
        body = source[source.index(marker) :].split("\n  it(", 1)[0]
        assert "expect(" in body
        assert ".skip(" not in body and ".todo(" not in body


def test_manifest_makes_omission_fault_frontier_and_stable_identities_auditable() -> (
    None
):
    evidence = "\n".join(node for mapped in THREAT_TESTS.values() for node in mapped)
    for fragment in (
        "secret_canaries",
        "exact_project_and_unassigned",
        "observation_equal_replay_stale_resurrection",
        "import_and_scheduling_are_absent",
        "export_v1_excludes_calendar",
        "configuration_rejects_nested_confusable",
        "tables_safe_fields_and_one_active_sync",
    ):
        assert fragment in evidence
