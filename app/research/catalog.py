"""Immutable code-owned Agent catalog."""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

from app.agent_tools.registry import REGISTRY_VERSION

RESEARCH_KIND = "research"
RESEARCH_VERSION = "1"
RESEARCH_TOOLS = (
    ("project.get", 1),
    ("memory.get", 1),
    ("memory.search_explained", 1),
    ("source.get", 1),
    ("source_chunk.get", 1),
)


@dataclass(frozen=True, slots=True)
class AgentDefinition:
    kind: str
    version: str
    authority: Literal["read"]
    registry_version: str
    allowed_tools: tuple[tuple[str, int], ...]
    planning_contract: str
    synthesis_contract: str
    evidence_rules: str
    scope_rules: str


RESEARCH_DEFINITION = AgentDefinition(
    kind=RESEARCH_KIND,
    version=RESEARCH_VERSION,
    authority="read",
    registry_version=REGISTRY_VERSION,
    allowed_tools=RESEARCH_TOOLS,
    planning_contract="research-planning-v1",
    synthesis_contract="research-claims-v1",
    evidence_rules="exact-run-step-invocation-versioned",
    scope_rules="exact-project-or-explicitly-unassigned",
)
AGENT_CATALOG = MappingProxyType(
    {(RESEARCH_DEFINITION.kind, RESEARCH_DEFINITION.version): RESEARCH_DEFINITION}
)


def research_definition(kind: str, version: str) -> AgentDefinition | None:
    if kind != RESEARCH_KIND:
        return None
    return AGENT_CATALOG.get((kind, version))


def is_research(kind: str, version: str) -> bool:
    return (kind, version) == (RESEARCH_KIND, RESEARCH_VERSION)


def is_unknown_research(kind: str, version: str) -> bool:
    return kind == RESEARCH_KIND and not is_research(kind, version)
