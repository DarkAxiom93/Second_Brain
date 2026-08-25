"""Closed application-owned catalog of planned schedulable Automations."""

from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True)
class SchedulableAgent:
    kind: str
    version: str
    project_required: bool


RESERVED_AUTOMATION_AGENT_KINDS = frozenset({"daily_brief", "project_watch"})
IMPLEMENTED_AUTOMATION_AGENT_IDENTITIES: frozenset[tuple[str, str]] = frozenset()

CATALOG = MappingProxyType(
    {
        ("daily_brief", "1"): SchedulableAgent("daily_brief", "1", False),
        ("project_watch", "1"): SchedulableAgent("project_watch", "1", True),
    }
)


def is_reserved_automation_agent_kind(kind: str) -> bool:
    """Return whether every version of this future Agent family is inert."""

    return kind in RESERVED_AUTOMATION_AGENT_KINDS


def is_reserved_automation_agent_identity(kind: str, version: str) -> bool:
    """Keep future families inert unless an exact implementation is installed."""

    identity = (kind, version)
    return (
        is_reserved_automation_agent_kind(kind)
        and identity not in IMPLEMENTED_AUTOMATION_AGENT_IDENTITIES
    )


def is_planned_schedulable_identity(kind: str, version: str) -> bool:
    """Return whether this exact identity is valid Automation configuration."""

    return (kind, version) in CATALOG


def get_schedulable_agent(kind: str, version: str) -> SchedulableAgent | None:
    """Return only an exact code-owned planned identity.

    Catalog membership describes configuration validity only. It grants no Run,
    Tool, provider, planning, or execution authority.
    """

    return CATALOG.get((kind, version))
