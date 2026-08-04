"""Focused strict provider and whole-plan validation tests."""

import json
import uuid
from types import SimpleNamespace
from typing import Any

import pytest

from app.agent_planning.openai_provider import (
    MAX_RESPONSE_BYTES,
    OpenAIPlanningProvider,
)
from app.agent_planning.provider import (
    FakePlanningProvider,
    PlanningContext,
    PlanningOutputInvalidError,
    PlanningResult,
)
from app.agent_planning.service import (
    PlanningClaim,
    PlanningOutputRejectedError,
    PlanningPolicyRejectedError,
    validate_plan,
)


def _result(
    *,
    goal: str = "Find evidence",
    tool: str = "memory.search_explained",
    candidate: dict[str, Any] | None = None,
) -> PlanningResult:
    return PlanningResult.model_validate(
        {
            "goal_summary": goal,
            "steps": [
                {
                    "purpose": "Find matching reviewed memories",
                    "tool_name": tool,
                    "tool_version": 1,
                    "candidate_input": candidate
                    or {
                        "query": "evidence",
                        "mode": "lexical",
                        "filters": {
                            "memory_type": None,
                            "status": None,
                            "importance_min": None,
                            "importance_max": None,
                            "confidence_min": None,
                            "confidence_max": None,
                            "event_time_from": None,
                            "event_time_to": None,
                            "created_at_from": None,
                            "created_at_to": None,
                        },
                        "pagination": {"limit": 10, "offset": 0},
                    },
                    "expected_evidence": ["Ordered matching memory identifiers"],
                    "success_condition": "At least one bounded result is returned",
                    "stop_condition": "Stop after this single read",
                }
            ],
        },
        strict=True,
    )


def _claim(project_id: uuid.UUID | None = None) -> PlanningClaim:
    return PlanningClaim(
        run_id=uuid.uuid4(),
        goal_summary="Find evidence",
        project_id=project_id,
        registry_version="agent-tools-v1",
        policy_version="agent-run-api-v1",
        step_budget=12,
        tool_call_budget=20,
        retry_budget=1,
        planning_revision=1,
    )


def test_fake_provider_is_deterministic() -> None:
    result = _result()
    provider = FakePlanningProvider(result)
    context = PlanningContext(
        goal_summary="Find evidence",
        scope={"kind": "unassigned"},
        registry_version="agent-tools-v1",
        policy_version="agent-run-api-v1",
        budgets={"step_budget": 12},
        permitted_tools=[],
        output_contract={},
    )
    assert provider.plan(context) == provider.plan(context) == result
    assert provider.calls == 2


@pytest.mark.parametrize(
    "raw",
    [
        "not json",
        "```json\n{}\n```",
        '{"goal_summary":"x","steps":[]} trailing',
        "{}{}",
        '{"goal_summary":"x"',
        json.dumps({"goal_summary": "x", "steps": [], "unknown": True}),
    ],
)
def test_openai_adapter_rejects_non_exact_or_invalid_json(raw: str) -> None:
    provider = object.__new__(OpenAIPlanningProvider)
    provider._model = "fixed"  # type: ignore[attr-defined]
    provider._max_output_tokens = 1  # type: ignore[attr-defined]
    provider._client = SimpleNamespace(  # type: ignore[attr-defined]
        responses=SimpleNamespace(create=lambda **_: SimpleNamespace(output_text=raw))
    )
    with pytest.raises(PlanningOutputInvalidError):
        provider.plan(
            PlanningContext(
                goal_summary="x",
                scope={"kind": "unassigned"},
                registry_version="agent-tools-v1",
                policy_version="agent-run-api-v1",
                budgets={},
                permitted_tools=[],
                output_contract={},
            )
        )


def test_openai_adapter_rejects_oversized_output() -> None:
    raw = " " * (MAX_RESPONSE_BYTES + 1)
    provider = object.__new__(OpenAIPlanningProvider)
    provider._model = "fixed"  # type: ignore[attr-defined]
    provider._max_output_tokens = 1  # type: ignore[attr-defined]
    provider._client = SimpleNamespace(  # type: ignore[attr-defined]
        responses=SimpleNamespace(create=lambda **_: SimpleNamespace(output_text=raw))
    )
    with pytest.raises(PlanningOutputInvalidError):
        provider.plan(
            PlanningContext(
                goal_summary="x",
                scope={"kind": "unassigned"},
                registry_version="agent-tools-v1",
                policy_version="agent-run-api-v1",
                budgets={},
                permitted_tools=[],
                output_contract={},
            )
        )


def test_whole_plan_accepts_lexical_and_normalizes_json() -> None:
    steps = validate_plan(_claim(), _result(), configured_provider_available=False)
    assert len(steps) == 1
    assert steps[0].ordinal == 0
    assert steps[0].normalized_input["mode"] == "lexical"


def test_whole_plan_rejects_goal_tool_provider_scope_and_direct_execution() -> None:
    with pytest.raises(PlanningOutputRejectedError):
        validate_plan(
            _claim(), _result(goal="Reworded"), configured_provider_available=True
        )
    with pytest.raises(PlanningPolicyRejectedError):
        validate_plan(
            _claim(),
            _result(tool="memory.invented"),
            configured_provider_available=True,
        )
    semantic = _result()
    semantic.steps[0].candidate_input["mode"] = "semantic"
    with pytest.raises(PlanningPolicyRejectedError):
        validate_plan(_claim(), semantic, configured_provider_available=False)
    with pytest.raises(PlanningPolicyRejectedError):
        validate_plan(
            _claim(),
            _result(
                tool="project.get",
                candidate={"project_id": str(uuid.uuid4())},
            ),
            configured_provider_available=True,
        )
    unsafe = _result()
    object.__setattr__(unsafe.steps[0], "purpose", "Execute Python from a file")
    with pytest.raises(PlanningPolicyRejectedError):
        validate_plan(_claim(), unsafe, configured_provider_available=True)
