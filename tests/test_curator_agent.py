"""Focused contracts for the fixed Advisory Memory Curator Agent."""

import json
import uuid
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.agent_planning.provider import PlanningResult
from app.agent_planning.service import (
    PlanningClaim,
    PlanningPolicyRejectedError,
    build_context,
    validate_plan,
)
from app.curator.catalog import (
    CURATOR_DEFINITION,
    CURATOR_TOOLS,
    PROPOSAL_CATALOG,
    curator_definition,
    is_unknown_curator,
)
from app.curator.openai_provider import OpenAICuratorProvider
from app.curator.provider import (
    CuratorOutputInvalidError,
    CuratorProviderRequestError,
    CuratorProviderResult,
    StrictCuratorProviderResult,
)


def _claim() -> PlanningClaim:
    return PlanningClaim(
        run_id=uuid.uuid4(),
        goal_summary="Curate safely",
        project_id=None,
        registry_version="agent-tools-v1",
        policy_version="agent-run-api-v1",
        step_budget=12,
        tool_call_budget=20,
        retry_budget=1,
        planning_revision=1,
        agent_kind="memory_curator",
        agent_version="1",
    )


def test_exact_immutable_curator_definition_and_catalog() -> None:
    assert curator_definition("memory_curator", "1") is CURATOR_DEFINITION
    assert CURATOR_DEFINITION.authority == "propose"
    assert CURATOR_DEFINITION.registry_version == "agent-tools-v1"
    assert CURATOR_TOOLS == (("memory.get", 1), ("memory.search_explained", 1))
    assert PROPOSAL_CATALOG == ("memory.update",)
    assert is_unknown_curator("memory_curator", "2")


def test_curator_planning_exposes_and_accepts_only_exact_reads() -> None:
    context = build_context(_claim())
    assert [
        (item["name"], item["version"]) for item in context.permitted_tools
    ] == list(CURATOR_TOOLS)
    invalid = PlanningResult.model_validate(
        {
            "goal_summary": "Curate safely",
            "steps": [
                {
                    "purpose": "Inspect project",
                    "tool_name": "project.get",
                    "tool_version": 1,
                    "candidate_input": {"project_id": str(uuid.uuid4())},
                    "expected_evidence": ["Project"],
                    "success_condition": "Found",
                    "stop_condition": "Absent",
                }
            ],
        },
        strict=True,
    )
    with pytest.raises(PlanningPolicyRejectedError):
        validate_plan(_claim(), invalid, configured_provider_available=False)


def test_curator_schema_rejects_unsupported_actions_and_invented_evidence() -> None:
    with pytest.raises(ValidationError):
        CuratorProviderResult.model_validate(
            {
                "findings": [],
                "proposals": [
                    {
                        "action_type": "memory.delete",
                        "target_evidence": "e1",
                        "proposed_input": {},
                        "evidence": ["e1"],
                    }
                ],
            },
            strict=True,
        )


@pytest.mark.parametrize(
    "raw",
    [
        "{",
        '{"findings":[],"proposals":[],"unknown":true}',
        '{"findings":[{"text":"uncited"}],"proposals":[]}',
        '{"findings":[],"proposals":[{"action_type":"memory.update"}]}',
        "x" * 65_537,
    ],
    ids=["malformed", "unknown-field", "uncited", "malformed-proposal", "oversized"],
)
def test_openai_curator_adapter_rejects_malformed_unknown_and_oversized_output(
    raw: str,
) -> None:
    provider = object.__new__(OpenAICuratorProvider)
    provider._model = "fake"  # type: ignore[attr-defined]
    provider._max_output_tokens = 100  # type: ignore[attr-defined]
    provider._client = SimpleNamespace(  # type: ignore[attr-defined]
        responses=SimpleNamespace(
            create=lambda **_kwargs: SimpleNamespace(output_text=raw)
        )
    )
    with pytest.raises(CuratorOutputInvalidError):
        provider.synthesize(goal="Goal", evidence=[])


def _complete_update(**changes: object) -> dict[str, object]:
    value: dict[str, object] = {
        "content": None,
        "source": None,
        "title": None,
        "summary": None,
        "memory_type": None,
        "importance": None,
        "confidence": None,
        "status": None,
        "event_time": None,
        "expires_at": None,
        "supersedes_id": None,
    }
    value.update(changes)
    return value


def _assert_strict_objects(schema: object) -> None:
    if isinstance(schema, dict):
        if schema.get("type") == "object":
            assert schema.get("additionalProperties") is False
            assert set(schema.get("required", [])) == set(schema.get("properties", {}))
        for item in schema.values():
            _assert_strict_objects(item)
    elif isinstance(schema, list):
        for item in schema:
            _assert_strict_objects(item)


def test_openai_curator_provider_uses_closed_schema_and_translates_partial_update() -> (
    None
):
    captured: dict[str, object] = {}
    raw = json.dumps(
        {
            "findings": [{"text": "The title can be clearer.", "evidence": ["e1"]}],
            "proposals": [
                {
                    "action_type": "memory.update",
                    "target_evidence": "e1",
                    "updated_fields": ["title"],
                    "proposed_input": _complete_update(title="Clearer title"),
                    "evidence": ["e1"],
                }
            ],
        }
    )

    def create(**kwargs: object) -> SimpleNamespace:
        captured.update(kwargs)
        return SimpleNamespace(output_text=raw)

    provider = object.__new__(OpenAICuratorProvider)
    provider._model = "fake"  # type: ignore[attr-defined]
    provider._max_output_tokens = 100  # type: ignore[attr-defined]
    provider._client = SimpleNamespace(  # type: ignore[attr-defined]
        responses=SimpleNamespace(create=create)
    )
    result = provider.synthesize(goal="Goal", evidence=[{"evidence_id": "e1"}])
    schema = captured["text"]["format"]["schema"]  # type: ignore[index]
    assert schema == StrictCuratorProviderResult.model_json_schema()
    _assert_strict_objects(schema)
    assert result.proposals[0].proposed_input == {"title": "Clearer title"}


def test_curator_provider_translation_rejects_duplicate_update_selection() -> None:
    raw = json.dumps(
        {
            "findings": [],
            "proposals": [
                {
                    "action_type": "memory.update",
                    "target_evidence": "e1",
                    "updated_fields": ["title", "title"],
                    "proposed_input": _complete_update(title="Clearer title"),
                    "evidence": ["e1"],
                }
            ],
        }
    )
    provider = object.__new__(OpenAICuratorProvider)
    provider._model = "fake"  # type: ignore[attr-defined]
    provider._max_output_tokens = 100  # type: ignore[attr-defined]
    provider._client = SimpleNamespace(  # type: ignore[attr-defined]
        responses=SimpleNamespace(create=lambda **_: SimpleNamespace(output_text=raw))
    )
    with pytest.raises(CuratorOutputInvalidError):
        provider.synthesize(goal="Goal", evidence=[{"evidence_id": "e1"}])


def test_curator_provider_maps_request_failure_without_payload_leakage() -> None:
    provider = object.__new__(OpenAICuratorProvider)
    provider._model = "fake"  # type: ignore[attr-defined]
    provider._max_output_tokens = 100  # type: ignore[attr-defined]

    def failed(**_: object) -> object:
        raise RuntimeError("private curator request payload")

    provider._client = SimpleNamespace(  # type: ignore[attr-defined]
        responses=SimpleNamespace(create=failed)
    )
    with pytest.raises(CuratorProviderRequestError) as caught:
        provider.synthesize(goal="Goal", evidence=[])
    assert "private curator request payload" not in str(caught.value)
