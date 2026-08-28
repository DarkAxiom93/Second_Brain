"""Closed application-owned connector catalog with no transport behavior."""

from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class ConnectorResource:
    """One inert resource identity; membership grants no runtime authority."""

    kind: str
    enabled: bool
    content: bool


@dataclass(frozen=True, slots=True)
class ConnectorDefinition:
    """A provider definition that cannot express requests or execution."""

    provider: str
    version: str
    resources: tuple[ConnectorResource, ...]
    discovery: bool = False
    external_writes: bool = False
    agent_access: bool = False
    automation_access: bool = False
    import_access: bool = False


GITHUB_CONNECTOR = ConnectorDefinition(
    provider="github",
    version="1",
    resources=(
        ConnectorResource("repository", True, False),
        ConnectorResource("issue", True, True),
        ConnectorResource("pull_request", True, True),
        ConnectorResource("comment", False, True),
    ),
)

CATALOG: MappingProxyType[str, ConnectorDefinition] = MappingProxyType(
    {GITHUB_CONNECTOR.provider: GITHUB_CONNECTOR}
)


def get_connector(provider: str) -> ConnectorDefinition | None:
    """Return only an exact code-owned provider definition."""

    return CATALOG.get(provider)


def supports_resource(provider: str, resource_kind: str) -> bool:
    """Return whether one exact persistence resource is currently enabled."""

    connector = get_connector(provider)
    return connector is not None and any(
        resource.kind == resource_kind and resource.enabled
        for resource in connector.resources
    )
