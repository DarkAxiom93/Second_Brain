"""Immutable, fail-closed Agent Tool Registry containing metadata only."""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from pydantic import BaseModel

from app.agent_tools import schemas

REGISTRY_VERSION = "agent-tools-v1"
MAX_TIMEOUT_SECONDS = 15
MAX_CALLS_PER_RUN = 5
MAX_OUTPUT_BYTES = 65_536
_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:[._][a-z0-9]+)*$", re.ASCII)


class Authority(StrEnum):
    READ = "read"


class ScopeMode(StrEnum):
    EXACT_RUN_SCOPE = "exact_run_scope"
    OPERATOR_AGGREGATE = "operator_aggregate"


class ProviderMode(StrEnum):
    NONE = "none"
    CONDITIONAL = "conditional"


class NetworkMode(StrEnum):
    NONE = "none"
    CONFIGURED_PROVIDER_ONLY = "configured_provider_only"


class IdempotencyClass(StrEnum):
    PURE_READ = "pure_read"


class RegistryDefinitionError(ValueError):
    code = "invalid_registry_definition"


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    name: str
    version: int
    description: str
    input_schema: type[BaseModel]
    output_schema: type[BaseModel]
    authority: Authority
    approval_required: bool
    timeout_seconds: int
    calls_per_run: int
    scope_mode: ScopeMode
    provider_mode: ProviderMode
    network_mode: NetworkMode
    redaction_policy: str
    max_output_bytes: int
    idempotency: IdempotencyClass


class ToolRegistry:
    __slots__ = ("_definitions", "_inventory")
    _definitions: Mapping[tuple[str, int], ToolDefinition]
    _inventory: tuple[ToolDefinition, ...]

    def __init__(self, definitions: tuple[ToolDefinition, ...]) -> None:
        validated: dict[tuple[str, int], ToolDefinition] = {}
        for definition in definitions:
            self._validate(definition)
            identity = (definition.name, definition.version)
            if identity in validated:
                raise RegistryDefinitionError
            validated[identity] = definition
        object.__setattr__(
            self,
            "_definitions",
            MappingProxyType(validated.copy()),
        )
        object.__setattr__(
            self,
            "_inventory",
            tuple(
                sorted(validated.values(), key=lambda item: (item.name, item.version))
            ),
        )

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("ToolRegistry is immutable")

    @staticmethod
    def _validate(definition: ToolDefinition) -> None:
        if not isinstance(definition, ToolDefinition):
            raise RegistryDefinitionError
        if not _NAME_PATTERN.fullmatch(definition.name) or definition.version < 1:
            raise RegistryDefinitionError
        if not (1 <= len(definition.description) <= 500):
            raise RegistryDefinitionError
        for schema_type in (definition.input_schema, definition.output_schema):
            if not isinstance(schema_type, type) or not issubclass(
                schema_type, BaseModel
            ):
                raise RegistryDefinitionError
            config = schema_type.model_config
            if config.get("extra") != "forbid" or not config.get("strict"):
                raise RegistryDefinitionError
        if definition.authority is not Authority.READ or definition.approval_required:
            raise RegistryDefinitionError
        if definition.idempotency is not IdempotencyClass.PURE_READ:
            raise RegistryDefinitionError
        if not 1 <= definition.timeout_seconds <= MAX_TIMEOUT_SECONDS:
            raise RegistryDefinitionError
        if not 1 <= definition.calls_per_run <= MAX_CALLS_PER_RUN:
            raise RegistryDefinitionError
        if not 1 <= definition.max_output_bytes <= MAX_OUTPUT_BYTES:
            raise RegistryDefinitionError
        if definition.redaction_policy != "safe_allowlist":
            raise RegistryDefinitionError
        if not isinstance(definition.scope_mode, ScopeMode):
            raise RegistryDefinitionError
        if not isinstance(definition.provider_mode, ProviderMode):
            raise RegistryDefinitionError
        if not isinstance(definition.network_mode, NetworkMode):
            raise RegistryDefinitionError
        if (
            definition.provider_mode is ProviderMode.NONE
            and definition.network_mode is not NetworkMode.NONE
        ):
            raise RegistryDefinitionError

    @property
    def inventory(self) -> tuple[ToolDefinition, ...]:
        return self._inventory

    def get_exact(self, name: str, version: int) -> ToolDefinition | None:
        if not isinstance(name, str) or not _NAME_PATTERN.fullmatch(name):
            return None
        if not isinstance(version, int) or isinstance(version, bool) or version < 1:
            return None
        return self._definitions.get((name, version))


def _definition(
    name: str,
    input_schema: type[BaseModel],
    output_schema: type[BaseModel],
    *,
    scope: ScopeMode = ScopeMode.EXACT_RUN_SCOPE,
    provider: ProviderMode = ProviderMode.NONE,
    network: NetworkMode = NetworkMode.NONE,
) -> ToolDefinition:
    return ToolDefinition(
        name=name,
        version=1,
        description=f"Bounded read-only metadata contract for {name}.",
        input_schema=input_schema,
        output_schema=output_schema,
        authority=Authority.READ,
        approval_required=False,
        timeout_seconds=10,
        calls_per_run=5,
        scope_mode=scope,
        provider_mode=provider,
        network_mode=network,
        redaction_policy="safe_allowlist",
        max_output_bytes=65_536,
        idempotency=IdempotencyClass.PURE_READ,
    )


AGENT_TOOL_REGISTRY = ToolRegistry(
    (
        _definition("project.get", schemas.ProjectGetInput, schemas.ProjectGetOutput),
        _definition("memory.get", schemas.MemoryGetInput, schemas.MemoryGetOutput),
        _definition(
            "memory.search_explained",
            schemas.MemorySearchExplainedInput,
            schemas.MemorySearchExplainedOutput,
            provider=ProviderMode.CONDITIONAL,
            network=NetworkMode.CONFIGURED_PROVIDER_ONLY,
        ),
        _definition("source.get", schemas.SourceGetInput, schemas.SourceGetOutput),
        _definition(
            "source_chunk.get",
            schemas.SourceChunkGetInput,
            schemas.SourceChunkGetOutput,
        ),
        _definition(
            "operations.diagnostics",
            schemas.EmptyInput,
            schemas.AggregateOutput,
            scope=ScopeMode.OPERATOR_AGGREGATE,
        ),
        _definition(
            "maintenance.audit",
            schemas.EmptyInput,
            schemas.AggregateOutput,
            scope=ScopeMode.OPERATOR_AGGREGATE,
        ),
    )
)
