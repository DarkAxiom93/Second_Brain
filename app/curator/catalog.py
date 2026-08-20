"""Immutable code-owned Memory Curator definition."""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

from app.agent_tools.registry import REGISTRY_VERSION

CURATOR_KIND = "memory_curator"
CURATOR_VERSION = "1"
CURATOR_TOOLS = (("memory.get", 1), ("memory.search_explained", 1))
PROPOSAL_CATALOG = ("memory.update",)


@dataclass(frozen=True, slots=True)
class CuratorDefinition:
    kind: str
    version: str
    authority: Literal["propose"]
    registry_version: str
    allowed_tools: tuple[tuple[str, int], ...]
    proposal_catalog: tuple[str, ...]


CURATOR_DEFINITION = CuratorDefinition(
    kind=CURATOR_KIND,
    version=CURATOR_VERSION,
    authority="propose",
    registry_version=REGISTRY_VERSION,
    allowed_tools=CURATOR_TOOLS,
    proposal_catalog=PROPOSAL_CATALOG,
)
CURATOR_CATALOG = MappingProxyType(
    {(CURATOR_KIND, CURATOR_VERSION): CURATOR_DEFINITION}
)


def curator_definition(kind: str, version: str) -> CuratorDefinition | None:
    return CURATOR_CATALOG.get((kind, version)) if kind == CURATOR_KIND else None


def is_curator(kind: str, version: str) -> bool:
    return (kind, version) == (CURATOR_KIND, CURATOR_VERSION)


def is_unknown_curator(kind: str, version: str) -> bool:
    return kind == CURATOR_KIND and not is_curator(kind, version)
