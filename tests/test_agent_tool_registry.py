"""Focused Checkpoint 64 registry and pure-policy boundary tests."""

import dataclasses
import uuid
from typing import Any

import pytest
from pydantic import ValidationError

from app.agent_tools.policy import (
    PolicyRejection,
    PolicyRejectionCode,
    ResolvedToolPolicy,
    resolve_tool_policy,
)
from app.agent_tools.registry import (
    AGENT_TOOL_REGISTRY,
    MAX_CALLS_PER_RUN,
    MAX_OUTPUT_BYTES,
    MAX_TIMEOUT_SECONDS,
    REGISTRY_VERSION,
    Authority,
    IdempotencyClass,
    NetworkMode,
    ProviderMode,
    RegistryDefinitionError,
    ScopeMode,
    ToolDefinition,
    ToolRegistry,
)

EXPECTED_NAMES = (
    "maintenance.audit",
    "memory.get",
    "memory.search_explained",
    "operations.diagnostics",
    "project.get",
    "source.get",
    "source_chunk.get",
)


def _resolve(name: str = "memory.get", **changes: Any) -> Any:
    values: dict[str, Any] = {
        "name": name,
        "version": 1,
        "requested_authority": "read",
        "candidate_input": {"memory_id": uuid.uuid4()},
        "captured_registry_version": REGISTRY_VERSION,
        "captured_run_project_scope": uuid.uuid4(),
        "captured_run_tool_call_budget": 20,
        "total_calls_reserved": 0,
        "tool_calls_reserved": 0,
        "configured_provider_available": False,
    }
    values.update(changes)
    return resolve_tool_policy(**values)


def _code(result: Any) -> PolicyRejectionCode:
    assert isinstance(result, PolicyRejection)
    return result.code


def test_exact_deterministic_inventory_and_lookup() -> None:
    inventory = AGENT_TOOL_REGISTRY.inventory
    assert tuple(item.name for item in inventory) == EXPECTED_NAMES
    assert tuple((item.name, item.version) for item in inventory) == tuple(
        (name, 1) for name in EXPECTED_NAMES
    )
    assert AGENT_TOOL_REGISTRY.get_exact("memory.get", 1) is inventory[1]
    confusable = "m\u0435mory.get"
    for name in ("Memory.get", "memory.*", "memory.get*", confusable, "shell"):
        assert AGENT_TOOL_REGISTRY.get_exact(name, 1) is None
    assert AGENT_TOOL_REGISTRY.get_exact("memory.get", 2) is None


def test_registry_and_definitions_are_immutable_metadata_only() -> None:
    definition = AGENT_TOOL_REGISTRY.inventory[0]
    with pytest.raises(dataclasses.FrozenInstanceError):
        definition.timeout_seconds = 1  # type: ignore[misc]
    with pytest.raises(AttributeError):
        AGENT_TOOL_REGISTRY._inventory = ()  # type: ignore[misc]
    forbidden = {
        "handler",
        "callback",
        "callable",
        "executor",
        "repository",
        "provider",
        "import_path",
        "execute",
        "invoke",
    }
    assert forbidden.isdisjoint(ToolDefinition.__dataclass_fields__)
    for item in AGENT_TOOL_REGISTRY.inventory:
        assert item.authority is Authority.READ
        assert item.idempotency is IdempotencyClass.PURE_READ
        assert not item.approval_required


def test_construction_rejects_duplicates_and_unsafe_definitions() -> None:
    safe = AGENT_TOOL_REGISTRY.inventory[1]
    with pytest.raises(RegistryDefinitionError):
        ToolRegistry((safe, safe))
    for changed in (
        {"name": "Bad.Name"},
        {"name": "memory.*"},
        {"version": 0},
        {"authority": "execute"},
        {"approval_required": True},
        {"idempotency": "non_idempotent"},
        {"timeout_seconds": MAX_TIMEOUT_SECONDS + 1},
        {"calls_per_run": MAX_CALLS_PER_RUN + 1},
        {"max_output_bytes": MAX_OUTPUT_BYTES + 1},
        {"network_mode": "unrestricted"},
        {"redaction_policy": "raw"},
        {"input_schema": dict},
    ):
        with pytest.raises(RegistryDefinitionError):
            ToolRegistry((dataclasses.replace(safe, **changed),))


def test_all_schemas_reject_unknown_fields_and_oversized_input() -> None:
    for definition in AGENT_TOOL_REGISTRY.inventory:
        with pytest.raises(ValidationError):
            definition.input_schema.model_validate({"unexpected": True})
        with pytest.raises(ValidationError):
            definition.output_schema.model_validate({"unexpected": True})
    assert (
        _code(
            _resolve(
                candidate_input={"memory_id": uuid.uuid4(), "project_id": uuid.uuid4()}
            )
        )
        is PolicyRejectionCode.INVALID_INPUT
    )
    assert (
        _code(
            _resolve(
                "memory.search_explained",
                candidate_input={
                    "query": "x" * 501,
                    "mode": "lexical",
                    "filters": {},
                    "pagination": {"limit": 20, "offset": 0},
                },
            )
        )
        is PolicyRejectionCode.INVALID_INPUT
    )


@pytest.mark.parametrize("authority", ["propose", "execute"])
def test_authority_escalation_is_denied(authority: str) -> None:
    assert _code(_resolve(requested_authority=authority)) is (
        PolicyRejectionCode.AUTHORITY_DENIED
    )


def test_fail_closed_order_and_budget_enforcement() -> None:
    assert _code(_resolve(captured_registry_version="older")) is (
        PolicyRejectionCode.REGISTRY_VERSION_MISMATCH
    )
    assert _code(_resolve(name="unknown.tool")) is PolicyRejectionCode.UNKNOWN_TOOL
    assert _code(_resolve(version="1")) is PolicyRejectionCode.INVALID_TOOL_VERSION
    assert _code(_resolve(total_calls_reserved=20)) is (
        PolicyRejectionCode.TOTAL_BUDGET_EXHAUSTED
    )
    assert _code(_resolve(tool_calls_reserved=5)) is (
        PolicyRejectionCode.TOOL_BUDGET_EXHAUSTED
    )


def test_project_scope_matrix_and_null_is_never_unrestricted() -> None:
    project_a = uuid.uuid4()
    project_b = uuid.uuid4()
    allowed = _resolve(
        "project.get",
        candidate_input={"project_id": project_a},
        captured_run_project_scope=project_a,
    )
    assert isinstance(allowed, ResolvedToolPolicy)
    assert (
        _code(
            _resolve(
                "project.get",
                candidate_input={"project_id": project_b},
                captured_run_project_scope=project_a,
            )
        )
        is PolicyRejectionCode.SCOPE_DENIED
    )
    assert (
        _code(
            _resolve(
                "project.get",
                candidate_input={"project_id": project_a},
                captured_run_project_scope=None,
            )
        )
        is PolicyRejectionCode.SCOPE_DENIED
    )
    null_memory = _resolve(captured_run_project_scope=None)
    assert isinstance(null_memory, ResolvedToolPolicy)
    assert null_memory.run_project_scope is None
    assert null_memory.scope_mode is ScopeMode.EXACT_RUN_SCOPE


@pytest.mark.parametrize("name", ["operations.diagnostics", "maintenance.audit"])
def test_aggregate_tools_require_application_owned_permission(name: str) -> None:
    denied = _resolve(name, candidate_input={})
    assert _code(denied) is PolicyRejectionCode.OPERATOR_CAPABILITY_DENIED
    allowed = _resolve(name, candidate_input={}, operator_aggregate_allowed=True)
    assert isinstance(allowed, ResolvedToolPolicy)
    assert allowed.scope_mode is ScopeMode.OPERATOR_AGGREGATE


@pytest.mark.parametrize("mode", ["semantic", "hybrid"])
def test_provider_boundary_is_conditional_by_search_mode(mode: str) -> None:
    candidate = {
        "query": "bounded",
        "mode": mode,
        "filters": {},
        "pagination": {"limit": 20, "offset": 0},
    }
    assert (
        _code(_resolve("memory.search_explained", candidate_input=candidate))
        is PolicyRejectionCode.PROVIDER_UNAVAILABLE
    )
    resolved = _resolve(
        "memory.search_explained",
        candidate_input=candidate,
        configured_provider_available=True,
    )
    assert isinstance(resolved, ResolvedToolPolicy)
    assert resolved.network_mode is NetworkMode.CONFIGURED_PROVIDER_ONLY


def test_lexical_search_is_provider_and_network_free() -> None:
    resolved = _resolve(
        "memory.search_explained",
        candidate_input={
            "query": "bounded",
            "mode": "lexical",
            "filters": {},
            "pagination": {"limit": 20, "offset": 0},
        },
    )
    assert isinstance(resolved, ResolvedToolPolicy)
    assert resolved.provider_mode is ProviderMode.NONE
    assert resolved.network_mode is NetworkMode.NONE


def test_inventory_contains_no_forbidden_capability() -> None:
    joined = " ".join(item.name for item in AGENT_TOOL_REGISTRY.inventory)
    for token in (
        "shell",
        "python",
        "sql",
        "filesystem",
        "http",
        "browser",
        "git",
        "install",
        "environment",
        "credential",
        "write",
    ):
        assert token not in joined
