"""Executable Checkpoint 84 A01-A18 threat-to-test release manifest."""

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

THREAT_TESTS: dict[str, tuple[str, ...]] = {
    "A01": (
        "tests/integration/test_automation_scheduler.py::test_concurrent_materializers_create_one_occurrence",
        "tests/integration/test_automation_scheduler.py::test_concurrent_link_and_replay_resolve_one_inert_run",
    ),
    "A02": (
        "tests/integration/test_automation_scheduler.py::test_lifecycle_and_edit_race_before_run_link",
    ),
    "A03": (
        "tests/integration/test_automation_scheduler.py::test_owner_generation_expiry_and_lifecycle_fences",
        "tests/integration/test_automation_scheduler.py::test_expired_claim_reclaims_and_fences_old_generation",
    ),
    "A04": (
        "tests/integration/test_automation_scheduler.py::test_concurrent_materializers_create_one_occurrence",
        "tests/integration/test_automation_scheduler.py::test_concurrent_claimers_claim_once",
        "tests/integration/test_automation_scheduler.py::test_serialization_and_deadlock_codes_are_bounded_retryable",
    ),
    "A05": (
        "tests/test_automation_schedule.py::test_calculation_is_host_timezone_independent",
        "tests/integration/test_automation_scheduler.py::test_backward_clock_does_not_reopen_terminal_slot",
    ),
    "A06": (
        "tests/test_automation_schedule.py::test_dst_gap_uses_first_valid_instant_and_fold_uses_fold_zero_once",
    ),
    "A07": (
        "tests/integration/test_automation_scheduler.py::test_materialization_failure_rolls_back_insert_and_advance",
    ),
    "A08": (
        "tests/integration/test_automation_scheduler.py::test_run_link_failure_rolls_back_run_and_link",
        "tests/integration/test_automation_scheduler.py::test_repeated_restart_reconciles_exact_link_without_replacement",
    ),
    "A09": (
        "tests/integration/test_automation_scheduler.py::test_missed_policy_materializes_only_latest_slot",
    ),
    "A10": (
        "tests/test_automation_schedule.py::test_invalid_closed_schedule_fields_fail",
        "tests/test_automation_schedule.py::test_preview_rejects_non_progressing_calculation",
    ),
    "A11": (
        "tests/integration/test_automation_scheduler.py::test_retry_budget_timing_and_capacity_deferral",
        "tests/integration/test_automation_scheduler.py::test_retry_exhaustion_is_terminal_and_operator_visible",
    ),
    "A12": (
        "tests/integration/test_automation_api.py::test_concurrent_pause_uses_row_lock_and_revision_cas",
        "tests/integration/test_automation_scheduler.py::test_lifecycle_and_edit_race_before_run_link",
    ),
    "A13": (
        "tests/integration/test_daily_brief_events.py::test_exact_project_and_unassigned_scope_are_isolated_and_redacted",
        "tests/integration/test_project_watch_changes.py::test_window_successful_predecessor_scope_and_version_revalidation",
    ),
    "A14": (
        "tests/test_automation_adversarial_evaluation.py::test_configuration_and_provider_output_reject_capability_injection",
        "tests/test_automation_adversarial_evaluation.py::test_automatic_inventory_is_exact_read_only_without_external_mutation",
    ),
    "A15": (
        "tests/test_automation_adversarial_evaluation.py::test_hostile_labels_and_local_evidence_cannot_alter_fixed_goal_or_authority",
        "tests/test_daily_brief_agent.py::test_forged_evidence_identifier_is_rejected",
    ),
    "A16": (
        "tests/integration/test_automation_scheduler.py::test_capacity_rejection_preserves_durable_claim",
    ),
    "A17": (
        "tests/integration/test_automation_operator_api.py::test_notification_inbox_dedup_redaction_and_idempotent_mark_read",
        "tests/integration/test_automation_operator_api.py::test_occurrence_history_is_bounded_newest_first_and_redacted",
    ),
    "A18": (
        "tests/integration/test_automation_coordinator.py::test_fixed_read_only_definition_executes_once_replays_and_mutates_no_domain",
        "tests/integration/test_automation_coordinator.py::test_unimplemented_and_non_read_definitions_fail_before_planning",
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


def test_manifest_covers_exact_automation_threat_register() -> None:
    expected = [f"A{number:02d}" for number in range(1, 19)]
    assert list(THREAT_TESTS) == expected
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


def test_manifest_includes_postgresql_fault_prompt_privacy_and_mutation_proofs() -> (
    None
):
    evidence = {node_id for tests in THREAT_TESTS.values() for node_id in tests}
    required_fragments = (
        "integration/test_automation_scheduler.py",
        "materialization_failure_rolls_back",
        "automation_adversarial_evaluation.py",
        "notification_inbox_dedup_redaction",
        "mutates_no_domain",
    )
    assert all(
        any(fragment in node_id for node_id in evidence)
        for fragment in required_fragments
    )
