"""Focused contracts for the fixed Advisory Memory Curator Agent."""

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
from app.curator.provider import CuratorOutputInvalidError, CuratorProviderResult


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
