"""Executable CP72 threat-to-test traceability release gate."""

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

THREAT_TESTS: dict[str, tuple[str, ...]] = {
    "T01": (
        "tests/test_research_agent.py::test_prompt_injection_variants_remain_plain_evidence",
        "tests/integration/test_curator_agent_api.py::test_injection_content_is_inert_and_cannot_widen_curator_authority",
        "tests/test_agent_planning.py::test_whole_plan_rejects_goal_tool_provider_scope_and_direct_execution",
    ),
    "T02": (
        "tests/test_agent_tool_registry.py::test_exact_deterministic_inventory_and_lookup",
        "tests/test_research_agent.py::test_research_planner_cannot_select_operator_or_invented_tool",
    ),
    "T03": (
        "tests/test_agent_planning.py::test_openai_adapter_rejects_non_exact_or_invalid_json",
        "tests/test_curator_agent.py::test_openai_curator_adapter_rejects_malformed_unknown_and_oversized_output",
    ),
    "T04": (
        "tests/test_agent_tool_registry.py::test_authority_escalation_is_denied",
        "tests/test_agent_tool_registry.py::test_inventory_contains_no_forbidden_capability",
    ),
    "T05": (
        "tests/integration/test_agent_approval_api.py::test_create_replay_projection_and_review_never_mutate_target",
        "frontend/src/Agents.test.tsx::confirms and approves one exact pending "
        "proposal without executing",
    ),
    "T06": (
        "tests/integration/test_agent_approval_api.py::test_concurrent_opposite_review_has_one_winner_and_one_event",
        "tests/integration/test_agent_approval_api.py::test_scope_matrix_changed_payload_and_reject_replay_are_exact",
    ),
    "T07": (
        "tests/integration/test_agent_execution_api.py::test_only_one_execution_claims_and_run_lock_is_free_during_tool_latency",
        "tests/integration/test_agent_execution_api.py::test_transient_read_retries_once_and_terminal_replay_writes_nothing",
    ),
    "T08": (
        "tests/test_agent_tool_registry.py::test_fail_closed_order_and_budget_enforcement",
        "tests/integration/test_agent_execution_api.py::test_retry_counts_against_total_and_per_tool_budgets",
    ),
    "T09": (
        "tests/test_agent_tool_registry.py::test_all_schemas_reject_unknown_fields_and_oversized_input",
        "tests/test_agent_planning.py::test_openai_adapter_rejects_oversized_output",
    ),
    "T10": (
        "tests/integration/test_agent_execution_api.py::test_recovery_state_rules_expire_overdue_but_never_start_valid_ready",
        "tests/integration/test_agent_planning_api.py::test_stale_registry_and_missing_plan_never_call_provider",
    ),
    "T11": (
        "tests/integration/test_agent_execution_api.py::test_cancellation_during_tool_latency_discards_late_result_and_wins",
        "tests/integration/test_agent_approval_api.py::test_concurrent_duplicate_creation_has_one_row_event_and_frozen_fields",
    ),
    "T12": (
        "tests/integration/test_research_agent_api.py::test_synthesis_provider_failures_are_stable_and_redacted",
        "tests/integration/test_agent_planning_api.py::test_cancellation_during_provider_latency_wins_and_discards_result",
    ),
    "T13": (
        "tests/integration/test_agent_execution_api.py::test_second_transient_failure_never_creates_attempt_two",
        "tests/integration/test_agent_execution_api.py::test_fault_after_tool_return_is_not_translated_and_stale_recovery_retries",
    ),
    "T14": (
        "tests/integration/test_agent_execution_api.py::test_fault_after_reservation_rolls_back_invocation_atomically",
        "tests/integration/test_agent_approval_api.py::test_create_and_review_failures_roll_back_every_partial_fact",
    ),
    "T15": (
        "tests/test_agent_tool_registry.py::test_project_scope_matrix_and_null_is_never_unrestricted",
        "tests/integration/test_agent_execution_api.py::test_retry_and_recovery_preserve_project_and_unassigned_scope_and_domain_rows",
    ),
    "T16": (
        "tests/integration/test_research_agent_api.py::test_synthesis_provider_failures_are_stable_and_redacted",
        "tests/test_research_agent.py::test_secret_like_provider_claim_is_not_persistable_public_text",
    ),
    "T17": (
        "tests/test_agent_runtime_models.py::test_forbidden_raw_persistence_fields_do_not_exist",
        "tests/integration/test_agent_planning_api.py::test_provider_failure_has_no_steps_and_safe_failed_state",
    ),
    "T18": (
        "tests/test_agent_tool_dispatch.py::test_strict_input_and_output_validation",
        "frontend/src/Agents.test.tsx::renders ordered plans and bounded evidence "
        "as inert text",
    ),
    "T19": (
        "frontend/src/Agents.test.tsx::renders ordered plans and bounded evidence "
        "as inert text",
        "frontend/src/Agents.test.tsx::rejects malformed projections containing "
        "private fields",
    ),
    "T20": (
        "tests/test_agent_runtime_models.py::test_agent_event_repository_has_no_update_or_delete_primitive",
        "tests/integration/test_agent_runtime_persistence.py::test_concurrent_event_append_is_unique_monotonic_and_run_lock_serializes",
        "tests/integration/test_agent_approval_api.py::test_create_and_review_failures_roll_back_every_partial_fact",
    ),
    "T21": (
        "tests/integration/test_agent_execution_api.py::test_cancellation_after_reservation_before_tool_call_discards_result",
        "tests/integration/test_agent_execution_api.py::test_completion_first_rejects_later_cancellation",
    ),
    "T22": (
        "tests/integration/test_agent_planning_api.py::test_stale_registry_and_missing_plan_never_call_provider",
        "tests/integration/test_curator_agent_api.py::test_persisted_unknown_curator_version_fails_closed_in_planning",
    ),
    "T23": (
        "tests/test_research_agent.py::test_evidence_binding_corruption_fails_closed",
        "tests/integration/test_curator_agent_api.py::test_intervening_mutation_at_target_lock_fails_without_silent_refresh",
    ),
    "T24": (
        "tests/integration/test_agent_run_api.py::test_concurrent_creators_at_slots_31_32_33_never_exceed_capacity",
        "tests/integration/test_agent_run_api.py::test_capacity_boundary_replay_collision_and_rejected_key_recovery",
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


def _declared_threat_ids() -> list[str]:
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    for node in tree.body:
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "THREAT_TESTS"
            and isinstance(node.value, ast.Dict)
        ):
            return [
                key.value
                for key in node.value.keys
                if isinstance(key, ast.Constant) and isinstance(key.value, str)
            ]
    raise AssertionError("THREAT_TESTS dictionary declaration not found")


def test_matrix_covers_exact_threat_register_with_multiple_automated_proofs() -> None:
    expected = [f"T{number:02d}" for number in range(1, 25)]
    assert _declared_threat_ids() == expected
    assert list(THREAT_TESTS) == expected
    assert all(len(set(node_ids)) >= 2 for node_ids in THREAT_TESTS.values())
    assert all("::" in node_id for tests in THREAT_TESTS.values() for node_id in tests)


@pytest.mark.parametrize(
    "node_id",
    sorted({node_id for tests in THREAT_TESTS.values() for node_id in tests}),
)
def test_every_matrix_reference_names_an_existing_automated_test(node_id: str) -> None:
    relative_path, test_name = node_id.split("::", 1)
    path = ROOT / relative_path
    assert path.is_file()
    if path.suffix == ".py":
        tests = _python_tests(path)
        assert test_name in tests
        assert tests[test_name], (
            "referenced test has no executable prevention assertion"
        )
    else:
        source = path.read_text(encoding="utf-8")
        marker = f'it("{test_name}"'
        assert marker in source
        body = source[source.index(marker) :].split("\n  it(", 1)[0]
        assert "expect(" in body, "referenced UI test has no prevention assertion"


def test_matrix_uses_postgresql_and_frontend_evidence() -> None:
    evidence = {node_id for tests in THREAT_TESTS.values() for node_id in tests}
    assert any(node_id.startswith("tests/integration/") for node_id in evidence)
    assert any(node_id.startswith("frontend/") for node_id in evidence)
