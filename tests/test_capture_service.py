"""Focused unit coverage for the internal Capture domain contract."""

import dataclasses
import logging
import uuid

import pytest

from app.agent_tools.registry import AGENT_TOOL_REGISTRY, REGISTRY_VERSION
from app.captures.service import (
    CaptureCreate,
    CaptureItemProjection,
    CaptureValidationError,
    hash_idempotency_key,
    normalize_capture_content,
    request_fingerprint,
    validate_idempotency_key,
)
from app.context_hub.models import ContextFamily, ContextKind
from app.project_export.models import FORMAT_NAME, FORMAT_VERSION, ExportManifest
from app.project_export.service import DATA_FILES
from app.project_import.service import INSERT_ORDER, REQUIRED_ENTRIES, TABLES


def test_content_normalization_preserves_meaningful_whitespace() -> None:
    assert normalize_capture_content("  first\r\nsecond\r  ") == "  first\nsecond\n  "


@pytest.mark.parametrize("value", ["", " \t\r\n ", "a\x00b", "\ud800"])
def test_invalid_content_is_rejected(value: str) -> None:
    with pytest.raises(CaptureValidationError):
        normalize_capture_content(value)


def test_character_and_utf8_boundaries() -> None:
    assert len(normalize_capture_content("a" * 8_000)) == 8_000
    with pytest.raises(CaptureValidationError):
        normalize_capture_content("a" * 8_001)
    assert len(normalize_capture_content("😀" * 8_000).encode()) == 32_000
    with pytest.raises(CaptureValidationError):
        normalize_capture_content("😀" * 8_000 + "a")


@pytest.mark.parametrize(
    "value",
    [
        "x" * 7,
        "x" * 129,
        "has space",
        "has\ttab",
        "line\nfeed",
        "x" * 8 + "\x7f",
        "café-key",
    ],
)
def test_invalid_idempotency_keys(value: str) -> None:
    with pytest.raises(CaptureValidationError):
        validate_idempotency_key(value)


@pytest.mark.parametrize(
    "value",
    ["x" * 8, "x" * 128, "!#$%&'()*+,-./:;<=>?@[\\]^_`{|}~"],
)
def test_valid_idempotency_key_boundaries_and_punctuation(value: str) -> None:
    assert validate_idempotency_key(value) == value


def test_key_hash_and_fingerprint_are_deterministic_and_scope_bound() -> None:
    project_id = uuid.uuid4()
    assert hash_idempotency_key("visible-key") == hash_idempotency_key("visible-key")
    unassigned = request_fingerprint("text", None)
    assigned = request_fingerprint("text", project_id)
    assert unassigned != assigned
    assert assigned != request_fingerprint("changed", project_id)
    assert len(unassigned) == 64


def test_safe_projection_has_no_private_idempotency_material() -> None:
    assert {
        field.name for field in dataclasses.fields(CaptureItemProjection)
    }.isdisjoint({"idempotency_key_hash", "request_fingerprint"})
    assert CaptureCreate("text", "visible-key").project_id is None


def test_capture_is_absent_from_authority_and_export_inventories() -> None:
    assert REGISTRY_VERSION == "agent-tools-v1"
    assert tuple(item.name for item in AGENT_TOOL_REGISTRY.inventory) == (
        "maintenance.audit",
        "memory.get",
        "memory.search_explained",
        "operations.diagnostics",
        "project.get",
        "source.get",
        "source_chunk.get",
    )
    assert tuple(ContextFamily) == (
        ContextFamily.LOCAL_SOURCE,
        ContextFamily.GITHUB,
        ContextFamily.GOOGLE_CALENDAR,
    )
    assert tuple(ContextKind) == (
        ContextKind.SOURCE_CHUNK,
        ContextKind.REPOSITORY,
        ContextKind.ISSUE,
        ContextKind.PULL_REQUEST,
        ContextKind.CALENDAR_EVENT,
    )
    expected_files = (
        "project.json",
        "memories.jsonl",
        "memory_embeddings.jsonl",
        "sources.jsonl",
        "memory_sources.jsonl",
        "source_documents.jsonl",
        "source_chunks.jsonl",
        "memory_extraction_runs.jsonl",
        "memory_proposals.jsonl",
    )
    assert FORMAT_NAME == "second-brain-project-export"
    assert FORMAT_VERSION == 1
    assert expected_files == DATA_FILES
    assert frozenset(("manifest.json", *expected_files)) == REQUIRED_ENTRIES
    assert set(TABLES) == set(expected_files)
    assert set(INSERT_ORDER) == set(expected_files)
    assert all("capture" not in value for value in expected_files)
    assert all("capture" not in table.name for table in TABLES.values())
    assert set(ExportManifest.model_fields) == {
        "format_name",
        "format_version",
        "exported_at",
        "source_alembic_revision",
        "project_id",
        "project_name",
        "entity_counts",
        "export_options",
        "files",
    }


def test_raw_key_is_absent_from_projection_and_logs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    raw_key = "visible-private-key-!"
    with caplog.at_level(logging.DEBUG):
        digest = hash_idempotency_key(raw_key)
        projection_fields = {
            field.name for field in dataclasses.fields(CaptureItemProjection)
        }
    assert raw_key not in caplog.text
    assert raw_key != digest and len(digest) == 64
    assert projection_fields.isdisjoint(
        {"idempotency_key", "idempotency_key_hash", "request_fingerprint"}
    )
