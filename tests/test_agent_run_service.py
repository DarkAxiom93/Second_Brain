"""Focused contract tests for the Agent Run lifecycle foundation."""

import uuid

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.agent_runs.service import LEGAL_TRANSITIONS, normalized_request_fingerprint
from app.main import create_app
from app.schemas.agent_run import AgentRunCreate, AgentRunRead, AgentRunState


def _request(**changes: object) -> AgentRunCreate:
    values: dict[str, object] = {
        "project_id": None,
        "agent_kind": "research-agent",
        "agent_version": "1.0.0",
        "goal_summary": "Summarize the project",
    }
    values.update(changes)
    return AgentRunCreate.model_validate(values)


def test_complete_transition_matrix_is_exact() -> None:
    expected = {
        "created": {"planning", "cancelled", "expired"},
        "planning": {"ready", "failed", "cancelled", "expired"},
        "ready": {"running", "cancelled", "expired"},
        "running": {
            "running",
            "awaiting_approval",
            "completed",
            "failed",
            "cancelled",
            "expired",
        },
        "awaiting_approval": {"running", "failed", "cancelled", "expired"},
        "completed": set(),
        "failed": set(),
        "cancelled": set(),
        "expired": set(),
    }
    assert {
        state.value: {target.value for target in targets}
        for state, targets in LEGAL_TRANSITIONS.items()
    } == expected
    for source in AgentRunState:
        for target in AgentRunState:
            assert (target in LEGAL_TRANSITIONS[source]) == (
                target.value in expected[source.value]
            )


def test_fingerprint_is_canonical_and_sensitive_to_validated_payload() -> None:
    project_id = uuid.uuid4()
    first = _request(project_id=project_id)
    reordered = AgentRunCreate.model_validate(
        {
            "goal_summary": "Summarize the project",
            "agent_version": "1.0.0",
            "agent_kind": "research-agent",
            "project_id": str(project_id),
        }
    )
    assert normalized_request_fingerprint(first) == normalized_request_fingerprint(
        reordered
    )
    assert normalized_request_fingerprint(first) != normalized_request_fingerprint(
        _request(project_id=project_id, goal_summary="Different")
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"goal_summary": ""},
        {"goal_summary": " "},
        {"goal_summary": "x" * 1001},
        {"agent_kind": "Not Stable"},
        {"agent_kind": "x" * 101},
        {"agent_version": "x" * 51},
        {"unexpected": True},
    ],
)
def test_create_schema_rejects_invalid_or_unknown_fields(
    changes: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        _request(**changes)


def test_openapi_adds_exactly_four_safe_agent_run_operations() -> None:
    schema = TestClient(create_app()).app.openapi()
    paths = schema["paths"]
    assert set(path for path in paths if path.startswith("/agent-runs")) == {
        "/agent-runs",
        "/agent-runs/{run_id}",
        "/agent-runs/{run_id}/cancel",
    }
    assert set(paths["/agent-runs"]) == {"get", "post"}
    assert set(paths["/agent-runs/{run_id}"]) == {"get"}
    assert set(paths["/agent-runs/{run_id}/cancel"]) == {"post"}
    assert not any(
        fragment in path
        for path in paths
        for fragment in (
            "agent-events",
            "agent-steps",
            "tool-invocations",
            "approval-requests",
        )
    )
    public_fields = set(AgentRunRead.model_fields)
    assert public_fields == {
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
        "safe_error_code",
        "created_at",
        "updated_at",
        "started_at",
        "finished_at",
    }
