"""Pure, fail-closed resolution of registered Agent Tool policy."""

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from pydantic import ValidationError

from app.agent_tools.registry import (
    AGENT_TOOL_REGISTRY,
    MAX_OUTPUT_BYTES,
    MAX_TIMEOUT_SECONDS,
    REGISTRY_VERSION,
    NetworkMode,
    ProviderMode,
    ScopeMode,
    ToolRegistry,
)


class PolicyRejectionCode(StrEnum):
    REGISTRY_VERSION_MISMATCH = "registry_version_mismatch"
    UNKNOWN_TOOL = "unknown_tool"
    INVALID_TOOL_VERSION = "invalid_tool_version"
    INVALID_INPUT = "invalid_input"
    AUTHORITY_DENIED = "authority_denied"
    SCOPE_DENIED = "scope_denied"
    OPERATOR_CAPABILITY_DENIED = "operator_capability_denied"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    NETWORK_DENIED = "network_denied"
    TOTAL_BUDGET_EXHAUSTED = "total_budget_exhausted"
    TOOL_BUDGET_EXHAUSTED = "tool_budget_exhausted"
    INVALID_REGISTRY_DEFINITION = "invalid_registry_definition"


@dataclass(frozen=True, slots=True)
class PolicyRejection:
    code: PolicyRejectionCode


@dataclass(frozen=True, slots=True)
class ResolvedToolPolicy:
    name: str
    version: int
    authority: str
    normalized_input: Mapping[str, Any]
    run_project_scope: uuid.UUID | None
    scope_mode: ScopeMode
    provider_mode: ProviderMode
    network_mode: NetworkMode
    timeout_seconds: int
    max_output_bytes: int
    remaining_run_calls: int
    remaining_tool_calls: int


def _reject(code: PolicyRejectionCode) -> PolicyRejection:
    return PolicyRejection(code)


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def resolve_tool_policy(
    *,
    name: str,
    version: object,
    requested_authority: str,
    candidate_input: object,
    captured_registry_version: str,
    captured_run_project_scope: uuid.UUID | None,
    captured_run_tool_call_budget: int,
    total_calls_reserved: int,
    tool_calls_reserved: int,
    configured_provider_available: bool,
    operator_aggregate_allowed: bool = False,
    registry: ToolRegistry = AGENT_TOOL_REGISTRY,
) -> ResolvedToolPolicy | PolicyRejection:
    if captured_registry_version != REGISTRY_VERSION:
        return _reject(PolicyRejectionCode.REGISTRY_VERSION_MISMATCH)
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        return _reject(PolicyRejectionCode.INVALID_TOOL_VERSION)
    definition = registry.get_exact(name, version)
    if definition is None:
        return _reject(PolicyRejectionCode.UNKNOWN_TOOL)
    if requested_authority != "read":
        return _reject(PolicyRejectionCode.AUTHORITY_DENIED)
    try:
        validated = definition.input_schema.model_validate(candidate_input, strict=True)
    except (ValidationError, TypeError, ValueError):
        return _reject(PolicyRejectionCode.INVALID_INPUT)

    normalized = validated.model_dump(mode="json", exclude_none=False)
    if definition.name == "project.get":
        if captured_run_project_scope is None:
            return _reject(PolicyRejectionCode.SCOPE_DENIED)
        if getattr(validated, "project_id", None) != captured_run_project_scope:
            return _reject(PolicyRejectionCode.SCOPE_DENIED)
    if definition.scope_mode is ScopeMode.OPERATOR_AGGREGATE:
        if not operator_aggregate_allowed:
            return _reject(PolicyRejectionCode.OPERATOR_CAPABILITY_DENIED)
    elif definition.scope_mode is not ScopeMode.EXACT_RUN_SCOPE:
        return _reject(PolicyRejectionCode.SCOPE_DENIED)

    provider_mode = definition.provider_mode
    network_mode = definition.network_mode
    if (
        definition.name == "memory.search_explained"
        and getattr(validated, "mode", None) == "lexical"
    ):
        provider_mode = ProviderMode.NONE
        network_mode = NetworkMode.NONE
    if provider_mode is ProviderMode.CONDITIONAL and not configured_provider_available:
        return _reject(PolicyRejectionCode.PROVIDER_UNAVAILABLE)
    if network_mode not in {NetworkMode.NONE, NetworkMode.CONFIGURED_PROVIDER_ONLY}:
        return _reject(PolicyRejectionCode.NETWORK_DENIED)
    if captured_run_tool_call_budget < 0 or total_calls_reserved < 0:
        return _reject(PolicyRejectionCode.TOTAL_BUDGET_EXHAUSTED)
    if total_calls_reserved >= captured_run_tool_call_budget:
        return _reject(PolicyRejectionCode.TOTAL_BUDGET_EXHAUSTED)
    if tool_calls_reserved < 0 or tool_calls_reserved >= definition.calls_per_run:
        return _reject(PolicyRejectionCode.TOOL_BUDGET_EXHAUSTED)
    if (
        definition.timeout_seconds > MAX_TIMEOUT_SECONDS
        or definition.max_output_bytes > MAX_OUTPUT_BYTES
    ):
        return _reject(PolicyRejectionCode.INVALID_REGISTRY_DEFINITION)
    return ResolvedToolPolicy(
        name=definition.name,
        version=definition.version,
        authority=definition.authority.value,
        normalized_input=_freeze(normalized),
        run_project_scope=captured_run_project_scope,
        scope_mode=definition.scope_mode,
        provider_mode=provider_mode,
        network_mode=network_mode,
        timeout_seconds=definition.timeout_seconds,
        max_output_bytes=definition.max_output_bytes,
        remaining_run_calls=captured_run_tool_call_budget - total_calls_reserved - 1,
        remaining_tool_calls=definition.calls_per_run - tool_calls_reserved - 1,
    )
