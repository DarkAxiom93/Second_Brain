"""Closed application-owned catalog of planned schedulable Automations."""

from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True)
class SchedulableAgent:
    kind: str
    version: str
    project_required: bool


@dataclass(frozen=True, slots=True)
class AutomaticAgentDefinition:
    """Exact fixed definition allowed to cross the unattended boundary."""

    kind: str
    version: str
    authority: str
    registry_version: str
    allowed_tools: tuple[tuple[str, int], ...]
    planning_contract: str = "fixed-read-only-v1"
    synthesis_contract: str = "fixed-cited-result-v1"
    evidence_rules: str = "exact-versioned"
    scope_rules: str = "exact-project-or-explicitly-unassigned"
    max_evidence: int = 20
    max_claims: int = 5
    max_citations: int = 20
    code_owned: bool = True


RESERVED_AUTOMATION_AGENT_KINDS = frozenset({"daily_brief", "project_watch"})
DAILY_BRIEF_TOOLS = (
    ("project.get", 1),
    ("memory.get", 1),
    ("memory.search_explained", 1),
    ("source.get", 1),
    ("source_chunk.get", 1),
)
DAILY_BRIEF_DEFINITION = AutomaticAgentDefinition(
    kind="daily_brief",
    version="1",
    authority="read",
    registry_version="agent-tools-v1",
    allowed_tools=DAILY_BRIEF_TOOLS,
    planning_contract="daily-brief-planning-v1",
    synthesis_contract="daily-brief-claims-v1",
    evidence_rules="reviewed-local-exact-run-step-invocation-versioned",
    scope_rules="exact-project-or-explicitly-unassigned",
    max_evidence=20,
    max_claims=5,
    max_citations=20,
)
PROJECT_WATCH_TOOLS = DAILY_BRIEF_TOOLS
PROJECT_WATCH_DEFINITION = AutomaticAgentDefinition(
    kind="project_watch",
    version="1",
    authority="read",
    registry_version="agent-tools-v1",
    allowed_tools=PROJECT_WATCH_TOOLS,
    planning_contract="project-watch-planning-v1",
    synthesis_contract="project-watch-changes-v1",
    evidence_rules="reviewed-local-change-window-exact-versioned",
    scope_rules="exact-non-null-project",
    max_evidence=20,
    max_claims=5,
    max_citations=20,
)
IMPLEMENTED_AUTOMATION_AGENT_IDENTITIES: frozenset[tuple[str, str]] = frozenset(
    {("daily_brief", "1"), ("project_watch", "1")}
)
AUTOMATIC_AGENT_DEFINITIONS: MappingProxyType[
    tuple[str, str], AutomaticAgentDefinition
] = MappingProxyType(
    {
        ("daily_brief", "1"): DAILY_BRIEF_DEFINITION,
        ("project_watch", "1"): PROJECT_WATCH_DEFINITION,
    }
)

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


def get_automatic_agent_definition(
    kind: str, version: str
) -> AutomaticAgentDefinition | None:
    """Return an implemented definition, never a merely planned catalog row."""

    identity = (kind, version)
    if identity not in IMPLEMENTED_AUTOMATION_AGENT_IDENTITIES:
        return None
    return AUTOMATIC_AGENT_DEFINITIONS.get(identity)
