"""Focused strict provider and whole-plan validation tests."""

import json
import uuid
from types import SimpleNamespace
from typing import Any

import pytest

from app.agent_planning.openai_provider import (
    MAX_RESPONSE_BYTES,
    OpenAIPlanningProvider,
    provider_planning_schema,
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
    build_context,
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
        agent_kind="research",
        agent_version="1",
    )


def _provider_context() -> PlanningContext:
    return build_context(_claim())


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
        provider.plan(_provider_context())


def test_openai_adapter_rejects_oversized_output() -> None:
    raw = " " * (MAX_RESPONSE_BYTES + 1)
    provider = object.__new__(OpenAIPlanningProvider)
    provider._model = "fixed"  # type: ignore[attr-defined]
    provider._max_output_tokens = 1  # type: ignore[attr-defined]
    provider._client = SimpleNamespace(  # type: ignore[attr-defined]
        responses=SimpleNamespace(create=lambda **_: SimpleNamespace(output_text=raw))
    )
    with pytest.raises(PlanningOutputInvalidError):
        provider.plan(_provider_context())


def _assert_all_objects_are_closed(schema: object) -> None:
    if isinstance(schema, dict):
        if schema.get("type") == "object":
            assert schema.get("additionalProperties") is False
            assert set(schema.get("required", [])) == set(schema.get("properties", {}))
        for value in schema.values():
            _assert_all_objects_are_closed(value)
    elif isinstance(schema, list):
        for value in schema:
            _assert_all_objects_are_closed(value)


def test_openai_adapter_submits_a_fully_closed_strict_schema() -> None:
    captured: dict[str, Any] = {}
    candidate = _result().steps[0].candidate_input
    raw = json.dumps(
        {
            "steps": [
                {
                    "purpose": "Find matching reviewed memories",
                    "tool_name": "memory.search_explained",
                    "tool_version": 1,
                    "candidate_input": candidate,
                    "expected_evidence": ["Ordered matching memory identifiers"],
                    "success_condition": "At least one bounded result is returned",
                    "stop_condition": "Stop after this single read",
                }
            ],
        }
    )

    def create(**kwargs: Any) -> SimpleNamespace:
        captured.update(kwargs)
        return SimpleNamespace(output_text=raw)

    provider = object.__new__(OpenAIPlanningProvider)
    provider._model = "fixed"  # type: ignore[attr-defined]
    provider._max_output_tokens = 100  # type: ignore[attr-defined]
    provider._client = SimpleNamespace(  # type: ignore[attr-defined]
        responses=SimpleNamespace(create=create)
    )
    context = _provider_context()
    result = provider.plan(context)

    submitted = captured["text"]["format"]
    assert submitted == {
        "type": "json_schema",
        "name": "agent_plan",
        "strict": True,
        "schema": provider_planning_schema(context),
    }
    _assert_all_objects_are_closed(submitted["schema"])
    assert set(submitted["schema"]["properties"]) == {"steps"}
    variants = submitted["schema"]["properties"]["steps"]["items"]["anyOf"]
    assert {
        (
            variant["properties"]["tool_name"]["const"],
            variant["properties"]["tool_version"]["const"],
        )
        for variant in variants
    } == {
        ("project.get", 1),
        ("memory.get", 1),
        ("memory.search_explained", 1),
        ("source.get", 1),
        ("source_chunk.get", 1),
    }
    search_variant = next(
        variant
        for variant in variants
        if variant["properties"]["tool_name"]["const"] == "memory.search_explained"
    )
    search_input = search_variant["properties"]["candidate_input"]
    assert set(search_input["required"]) == {
        "query",
        "mode",
        "filters",
        "pagination",
    }
    assert set(search_input["properties"]["filters"]["required"]) == set(
        search_input["properties"]["filters"]["properties"]
    )
    assert json.loads(captured["input"])["output_contract"] == submitted["schema"]
    assert result.goal_summary == context.goal_summary == "Find evidence"
    assert result.steps[0].candidate_input == candidate
    assert (
        validate_plan(_claim(), result, configured_provider_available=False)[
            0
        ].normalized_input["mode"]
        == "lexical"
    )


@pytest.mark.parametrize(
    "candidate_input",
    ["not an object", [], None, 1],
)
def test_openai_adapter_rejects_malformed_candidate_input(
    candidate_input: object,
) -> None:
    raw = json.dumps(
        {
            "steps": [
                {
                    "purpose": "Read one memory",
                    "tool_name": "memory.get",
                    "tool_version": 1,
                    "candidate_input": candidate_input,
                    "expected_evidence": ["Memory"],
                    "success_condition": "Memory is returned",
                    "stop_condition": "Stop after this read",
                }
            ],
        }
    )
    provider = object.__new__(OpenAIPlanningProvider)
    provider._model = "fixed"  # type: ignore[attr-defined]
    provider._max_output_tokens = 100  # type: ignore[attr-defined]
    provider._client = SimpleNamespace(  # type: ignore[attr-defined]
        responses=SimpleNamespace(create=lambda **_: SimpleNamespace(output_text=raw))
    )
    with pytest.raises(PlanningOutputInvalidError):
        provider.plan(_provider_context())


def test_provider_cannot_override_the_application_owned_goal() -> None:
    raw = json.dumps(
        {
            "goal_summary": "A provider-authored paraphrase",
            "steps": [
                {
                    "purpose": "Read one memory",
                    "tool_name": "memory.get",
                    "tool_version": 1,
                    "candidate_input": {"memory_id": str(uuid.uuid4())},
                    "expected_evidence": ["Memory"],
                    "success_condition": "Memory is returned",
                    "stop_condition": "Stop after this read",
                }
            ],
        }
    )
    provider = object.__new__(OpenAIPlanningProvider)
    provider._model = "fixed"  # type: ignore[attr-defined]
    provider._max_output_tokens = 100  # type: ignore[attr-defined]
    provider._client = SimpleNamespace(  # type: ignore[attr-defined]
        responses=SimpleNamespace(create=lambda **_: SimpleNamespace(output_text=raw))
    )
    with pytest.raises(PlanningOutputInvalidError):
        provider.plan(_provider_context())


def test_decoded_candidate_input_still_rejects_unknown_tool_fields() -> None:
    invalid = _result(candidate={"memory_id": str(uuid.uuid4()), "unexpected": True})
    with pytest.raises(PlanningPolicyRejectedError):
        validate_plan(_claim(), invalid, configured_provider_available=True)


def test_tool_and_candidate_input_mismatch_is_rejected_by_application_policy() -> None:
    search_candidate = _result().steps[0].candidate_input
    mismatched = _result(tool="memory.get", candidate=search_candidate)
    with pytest.raises(PlanningPolicyRejectedError):
        validate_plan(_claim(), mismatched, configured_provider_available=True)


@pytest.mark.parametrize(
    ("tool_name", "candidate_key"),
    [
        ("project.get", "project_id"),
        ("memory.get", "memory_id"),
        ("source.get", "source_id"),
        ("source_chunk.get", "source_chunk_id"),
    ],
)
def test_provider_json_represents_and_policy_validates_entity_read_inputs(
    tool_name: str, candidate_key: str
) -> None:
    entity_id = uuid.uuid4()
    project_id = entity_id if tool_name == "project.get" else None
    raw = json.dumps(
        {
            "steps": [
                {
                    "purpose": "Read bounded evidence",
                    "tool_name": tool_name,
                    "tool_version": 1,
                    "candidate_input": {candidate_key: str(entity_id)},
                    "expected_evidence": ["One application record"],
                    "success_condition": "The record is returned",
                    "stop_condition": "Stop after this read",
                }
            ],
        }
    )
    provider = object.__new__(OpenAIPlanningProvider)
    provider._model = "fixed"  # type: ignore[attr-defined]
    provider._max_output_tokens = 100  # type: ignore[attr-defined]
    provider._client = SimpleNamespace(  # type: ignore[attr-defined]
        responses=SimpleNamespace(create=lambda **_: SimpleNamespace(output_text=raw))
    )
    result = provider.plan(_provider_context())
    steps = validate_plan(
        _claim(project_id), result, configured_provider_available=True
    )
    assert steps[0].normalized_input[candidate_key] == str(entity_id)


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
