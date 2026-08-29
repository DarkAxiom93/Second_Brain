"""Closed-catalog and pure validation tests for Checkpoint 89."""

import ast
import dataclasses
from pathlib import Path

import pytest

from app.connectors.catalog import CATALOG, GITHUB_CONNECTOR, get_connector
from app.connectors.validation import (
    granted_scope_fingerprint,
    snapshot_content_hash,
    validate_account_values,
)


def test_catalog_is_exactly_github_and_cannot_express_authority() -> None:
    assert tuple(CATALOG) == ("github",)
    assert get_connector("GitHub") is None
    assert get_connector("gmail") is None
    assert GITHUB_CONNECTOR.resources == (
        dataclasses.replace(GITHUB_CONNECTOR.resources[0]),
        dataclasses.replace(GITHUB_CONNECTOR.resources[1]),
        dataclasses.replace(GITHUB_CONNECTOR.resources[2]),
        dataclasses.replace(GITHUB_CONNECTOR.resources[3]),
    )
    assert [(item.kind, item.enabled) for item in GITHUB_CONNECTOR.resources] == [
        ("repository", True),
        ("issue", True),
        ("pull_request", True),
        ("comment", False),
    ]
    assert not GITHUB_CONNECTOR.discovery
    assert not GITHUB_CONNECTOR.external_writes
    assert not GITHUB_CONNECTOR.agent_access
    assert not GITHUB_CONNECTOR.automation_access
    assert not GITHUB_CONNECTOR.import_access
    assert not {
        "url",
        "host",
        "method",
        "query",
        "graphql",
        "tool",
        "agent",
        "executable",
    } & {field.name for field in dataclasses.fields(GITHUB_CONNECTOR)}


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("provider", "gitlab"),
        ("external_account_id", "ghp_fake_secret"),
        ("external_account_id", "authorization"),
        ("credential_reference", "ghp_fake_secret"),
        ("credential_reference", "sbcred:v1:not-a-uuid"),
        ("resource_allowlist", ["owner/github_pat_fake"]),
        ("granted_scope_fingerprint", "access_token"),
    ],
)
def test_secret_shaped_and_open_account_metadata_reject(
    field: str, value: object
) -> None:
    values: dict[str, object] = {
        "provider": "github",
        "external_account_id": "account:123",
        "external_account_fingerprint": "a" * 64,
        "credential_reference": "sbcred:v1:12345678-1234-4123-8123-123456789abc",
        "resource_allowlist": ["owner/repository"],
        "granted_scope_fingerprint": "b" * 64,
    }
    values[field] = value
    with pytest.raises(ValueError):
        validate_account_values(**values)  # type: ignore[arg-type]


def test_content_hash_is_deterministic_and_unambiguous() -> None:
    assert snapshot_content_hash("ab", "c") == snapshot_content_hash("ab", "c")
    assert snapshot_content_hash("ab", "c") != snapshot_content_hash("a", "bc")


def test_scope_fingerprint_uses_only_canonical_permission_names() -> None:
    assert granted_scope_fingerprint(("issues_read", "metadata_read")) == (
        granted_scope_fingerprint(("metadata_read", "issues_read"))
    )
    with pytest.raises(ValueError):
        granted_scope_fingerprint(("github_pat_fake",))


def test_inert_connector_modules_import_no_network_or_credential_adapter() -> None:
    roots = (
        Path("app/connectors/catalog.py"),
        Path("app/connectors/validation.py"),
        Path("app/repositories/connectors.py"),
    )
    forbidden = {
        "httpx",
        "requests",
        "socket",
        "urllib",
        "app.credentials.windows",
        "app.credentials.fake",
    }
    imports: set[str] = set()
    paths = [
        path
        for root in roots
        for path in ([root] if root.is_file() else root.glob("*.py"))
    ]
    for path in paths:
        tree = ast.parse(path.read_bytes(), filename=str(path))
        imports.update(
            node.module or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        )
        imports.update(
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        )
    assert not forbidden & imports
