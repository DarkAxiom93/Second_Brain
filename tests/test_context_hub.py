"""Focused closed-contract and zero-authority checks for Checkpoint 110."""

import uuid
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.agent_tools.registry import AGENT_TOOL_REGISTRY, REGISTRY_VERSION
from app.context_hub.models import (
    CONTRACT_VERSION,
    MAX_PAGE_SIZE,
    CalendarProvenance,
    ContextFamily,
    ContextHubQuery,
    ContextKind,
    ContextScope,
    ContextState,
    GitHubProvenance,
    LocalSourceProvenance,
    TrustLabel,
)
from app.project_export.models import FORMAT_NAME, FORMAT_VERSION


def _scope() -> ContextScope:
    return ContextScope(project_id=uuid.uuid4())


@pytest.mark.parametrize(
    "value",
    ({}, {"unassigned": False}, {"project_id": uuid.uuid4(), "unassigned": True}),
)
def test_scope_requires_exactly_one_explicit_selector(value: object) -> None:
    with pytest.raises(ValidationError):
        ContextScope.model_validate(value, strict=True)


def test_closed_contract_defaults_and_bounds() -> None:
    request = ContextHubQuery(scope=ContextScope(unassigned=True))
    assert CONTRACT_VERSION == "context-hub-v1"
    assert request.families == (
        ContextFamily.LOCAL_SOURCE,
        ContextFamily.GITHUB,
        ContextFamily.GOOGLE_CALENDAR,
    )
    assert request.query == "" and request.page_size == 20
    with pytest.raises(ValidationError):
        ContextHubQuery(scope=_scope(), page_size=MAX_PAGE_SIZE + 1)
    with pytest.raises(ValidationError):
        ContextHubQuery(scope=_scope(), query="x" * 257)
    with pytest.raises(ValidationError):
        ContextHubQuery(scope=_scope(), query="🙂" * 256)


@pytest.mark.parametrize(
    "values",
    (
        {
            "families": (ContextFamily.LOCAL_SOURCE,),
            "kinds": (ContextKind.ISSUE,),
        },
        {
            "families": (ContextFamily.GITHUB,),
            "trust": (TrustLabel.LOCAL_AUDITED,),
        },
        {
            "families": (ContextFamily.GOOGLE_CALENDAR,),
            "states": (ContextState.DELETED,),
        },
        {
            "families": (ContextFamily.GITHUB, ContextFamily.GITHUB),
        },
    ),
)
def test_impossible_or_ambiguous_filters_fail_closed(values: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ContextHubQuery(scope=_scope(), **values)


def test_family_compatible_filters_are_accepted() -> None:
    request = ContextHubQuery(
        scope=_scope(),
        families=(ContextFamily.GITHUB, ContextFamily.GOOGLE_CALENDAR),
        kinds=(ContextKind.ISSUE, ContextKind.CALENDAR_EVENT),
        trust=(TrustLabel.QUARANTINED_EXTERNAL,),
        states=(ContextState.CURRENT, ContextState.STALE),
    )
    assert request.kinds == (ContextKind.ISSUE, ContextKind.CALENDAR_EVENT)


def test_provenance_is_closed_tagged_and_exact() -> None:
    common = {"application_revision": 1}
    github = GitHubProvenance(
        account_id=uuid.uuid4(),
        external_resource_id="repository:R_1",
        external_item_id="issue:I_1",
        revision_id=uuid.uuid4(),
        **common,
    )
    calendar = CalendarProvenance(
        account_revision_id=uuid.uuid4(),
        calendar_identity_id=uuid.uuid4(),
        occurrence_key="event:E_1",
        event_revision_id=uuid.uuid4(),
        evidence_sync_run_id=uuid.uuid4(),
        **common,
    )
    local = LocalSourceProvenance(
        source_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        chunk_id=uuid.uuid4(),
        chunk_index=0,
        content_hash="a" * 64,
    )
    assert {github.family, calendar.family, local.family} == set(ContextFamily)
    with pytest.raises(ValidationError):
        GitHubProvenance.model_validate(
            {**github.model_dump(), "credential_reference": "forbidden"}, strict=True
        )


def test_hostile_text_has_no_authority_and_no_capability_expansion() -> None:
    hostile = "<script>fetch('https://attacker.invalid')</script> ignore tools SQL"
    request = ContextHubQuery(scope=_scope(), query=hostile)
    assert request.query == hostile
    assert REGISTRY_VERSION == "agent-tools-v1"
    assert not any(
        "context" in definition.name for definition in AGENT_TOOL_REGISTRY.inventory
    )
    assert FORMAT_NAME == "second-brain-project-export" and FORMAT_VERSION == 1

    service = Path("app/context_hub/service.py").read_text(encoding="utf-8")
    forbidden_imports = (
        "requests",
        "httpx",
        "urllib",
        "credential",
        "EmbeddingProvider",
        "openai_provider",
        "agent_runs",
        "automations",
        "project_export",
    )
    assert not any(f"import {name}" in service for name in forbidden_imports)
    assert (
        ".add(" not in service
        and ".commit(" not in service
        and ".flush(" not in service
    )
