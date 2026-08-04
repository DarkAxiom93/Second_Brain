"""Static persistence-boundary tests for Agent Runtime tables."""

from app.models.agent_runtime import (
    AgentEvent,
    AgentRun,
    AgentStep,
    ApprovalRequest,
    ToolInvocation,
)


def test_exact_agent_table_column_inventories() -> None:
    expected = {
        AgentRun: {
            "id",
            "project_id",
            "agent_kind",
            "agent_version",
            "goal_summary",
            "registry_version",
            "policy_version",
            "state",
            "step_budget",
            "tool_call_budget",
            "retry_budget",
            "planning_deadline",
            "run_deadline",
            "revision",
            "correlation_id",
            "idempotency_key_hash",
            "normalized_request_fingerprint",
            "safe_error_code",
            "created_at",
            "updated_at",
            "started_at",
            "finished_at",
        },
        AgentStep: {
            "id",
            "run_id",
            "ordinal",
            "purpose",
            "tool_name",
            "tool_version",
            "normalized_input",
            "expected_evidence",
            "success_condition",
            "stop_condition",
            "status",
            "created_at",
            "started_at",
            "finished_at",
        },
        ToolInvocation: {
            "id",
            "run_id",
            "step_id",
            "attempt",
            "tool_name",
            "tool_version",
            "authority",
            "validated_input_hash",
            "validated_input",
            "idempotency_key_hash",
            "status",
            "safe_result_summary",
            "evidence_references",
            "safe_error_code",
            "reserved_at",
            "started_at",
            "finished_at",
        },
        ApprovalRequest: {
            "id",
            "run_id",
            "step_id",
            "action_type",
            "target_type",
            "target_public_id",
            "target_version",
            "normalized_input",
            "proposal_hash",
            "preview",
            "evidence_references",
            "risk_classification",
            "status",
            "created_at",
            "expires_at",
            "reviewed_at",
            "reviewer_metadata",
            "execution_identity",
        },
        AgentEvent: {
            "id",
            "run_id",
            "step_id",
            "invocation_id",
            "approval_id",
            "sequence",
            "event_type",
            "event_version",
            "safe_code",
            "safe_message",
            "metadata",
            "correlation_id",
            "occurred_at",
            "recorded_at",
            "event_idempotency_hash",
        },
    }
    for model, columns in expected.items():
        assert set(model.__table__.columns.keys()) == columns


def test_forbidden_raw_persistence_fields_do_not_exist() -> None:
    forbidden = {
        "chain_of_thought",
        "hidden_reasoning",
        "raw_prompt",
        "provider_request",
        "provider_response",
        "credentials",
        "secrets",
        "environment",
        "database_url",
        "raw_exception",
        "raw_sql",
        "vector",
        "scratch_space",
        "tool_output",
        "filesystem_path",
    }
    actual = {
        column.name
        for model in (AgentRun, AgentStep, ToolInvocation, ApprovalRequest, AgentEvent)
        for column in model.__table__.columns
    }
    assert forbidden.isdisjoint(actual)


def test_agent_event_repository_has_no_update_or_delete_primitive() -> None:
    from app.repositories import agent_runtime

    names = set(dir(agent_runtime))
    assert "update_agent_event" not in names
    assert "delete_agent_event" not in names
