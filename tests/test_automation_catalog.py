"""Code-owned reservation boundaries for future Automation Agents."""

import pytest

from app.automations.catalog import (
    IMPLEMENTED_AUTOMATION_AGENT_IDENTITIES,
    get_automatic_agent_definition,
    get_schedulable_agent,
    is_planned_schedulable_identity,
    is_reserved_automation_agent_identity,
    is_reserved_automation_agent_kind,
)


def test_production_automatic_agent_set_contains_only_daily_brief_v1() -> None:
    assert frozenset({("daily_brief", "1")}) == IMPLEMENTED_AUTOMATION_AGENT_IDENTITIES
    definition = get_automatic_agent_definition("daily_brief", "1")
    assert definition is not None
    assert definition.authority == "read"
    assert definition.registry_version == "agent-tools-v1"
    assert definition.max_evidence == 20
    assert get_automatic_agent_definition("project_watch", "1") is None


@pytest.mark.parametrize("kind", ["daily_brief", "project_watch"])
def test_reserved_family_covers_unimplemented_versions(kind: str) -> None:
    assert is_reserved_automation_agent_kind(kind)
    assert is_reserved_automation_agent_identity(kind, "1") is (kind == "project_watch")
    assert is_reserved_automation_agent_identity(kind, "unknown")
    assert is_planned_schedulable_identity(kind, "1")
    assert not is_planned_schedulable_identity(kind, "2")
    assert get_schedulable_agent(kind, "1") is not None
    assert get_schedulable_agent(kind, "2") is None


def test_unrelated_generic_family_is_not_reserved_or_schedulable() -> None:
    assert not is_reserved_automation_agent_kind("research-agent")
    assert not is_reserved_automation_agent_identity("research-agent", "1.0.0")
    assert not is_planned_schedulable_identity("research-agent", "1.0.0")
