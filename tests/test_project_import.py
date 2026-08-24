"""Focused validation tests for controlled Project import."""

import json
import zipfile
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from app.models import Memory, Project
from app.project_export.models import CURRENT_DATABASE_REVISION
from app.project_export.service import export_project
from app.project_import.models import ImportBundleError
from app.project_import.service import (
    INSERT_ORDER,
    MAX_ARCHIVE_ENTRIES,
    import_project,
    load_bundle,
)


def _project(project_id: UUID) -> Project:
    now = datetime(2025, 1, 1, tzinfo=UTC)
    return Project(
        id=project_id,
        name="Import Project",
        description=None,
        created_at=now,
        updated_at=now,
    )


def _bundle(
    path: Path,
    monkeypatch: pytest.MonkeyPatch,
    memories: tuple[Memory, ...] = (),
    project_id: UUID | None = None,
    source_revision: str = "0009_memory_expiration",
) -> UUID:
    project_id = project_id or uuid4()
    monkeypatch.setattr(
        "app.repositories.project_exports.get_project",
        lambda *_args: _project(project_id),
    )
    monkeypatch.setattr(
        "app.repositories.project_exports.memories", lambda *_args: iter(memories)
    )
    for name in (
        "embeddings",
        "sources",
        "memory_sources",
        "documents",
        "chunks",
        "extraction_runs",
        "proposals",
    ):
        monkeypatch.setattr(
            f"app.repositories.project_exports.{name}", lambda *_args: iter(())
        )
    export_project(
        object(),  # type: ignore[arg-type]
        project_id,
        path,
        source_alembic_revision=source_revision,
        exported_at=datetime(2025, 1, 1, tzinfo=UTC),
    )
    return project_id


def _rewrite(path: Path, change: Callable[[str, bytes], tuple[str, bytes]]) -> None:
    with zipfile.ZipFile(path) as source:
        entries = [(info, source.read(info.filename)) for info in source.infolist()]
    with zipfile.ZipFile(path, "w") as target:
        for info, payload in entries:
            name, value = change(info.filename, payload)
            target.writestr(name, value)


def test_supported_bundle_and_validation_only_do_not_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "valid.sbexport"
    project_id = _bundle(path, monkeypatch)
    manifest, data, digest = load_bundle(path)
    assert manifest.project_id == project_id
    assert data["project.json"][0]["id"] == project_id
    assert len(digest) == 64
    session = MagicMock()
    session.scalar.return_value = None
    result = import_project(session, path, execute=False)
    assert result.import_status == "validated"
    session.execute.assert_not_called()
    session.flush.assert_not_called()
    session.commit.assert_not_called()


@pytest.mark.parametrize(
    "source_revision",
    [
        "0009_memory_expiration",
        "0010_agent_runtime_persistence",
        CURRENT_DATABASE_REVISION,
    ],
)
def test_only_proven_compatible_source_revisions_are_accepted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source_revision: str,
) -> None:
    path = tmp_path / f"{source_revision}.sbexport"
    _bundle(path, monkeypatch, source_revision=source_revision)
    manifest, _, _ = load_bundle(path)
    assert manifest.source_alembic_revision == source_revision


def test_unsupported_source_revision_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "unsupported.sbexport"
    _bundle(path, monkeypatch, source_revision="0008_memory_proposals")
    with pytest.raises(ImportBundleError, match="unsupported source"):
        load_bundle(path)


def test_checksum_count_and_unexpected_entry_rejection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "tampered.sbexport"
    _bundle(path, monkeypatch)
    _rewrite(
        path,
        lambda name, payload: (
            name,
            payload + b"x" if name == "project.json" else payload,
        ),
    )
    with pytest.raises(ImportBundleError, match="checksum"):
        load_bundle(path)
    path.unlink()
    _bundle(path, monkeypatch)
    with zipfile.ZipFile(path, "a") as archive:
        archive.writestr("unexpected.json", b"{}")
    with pytest.raises(ImportBundleError, match="entries"):
        load_bundle(path)


def test_archive_path_duplicate_and_resource_limit_rejection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "unsafe.sbexport"
    _bundle(path, monkeypatch)
    with zipfile.ZipFile(path, "a") as archive:
        archive.writestr("../bad", b"")
    with pytest.raises(ImportBundleError, match="unsafe"):
        load_bundle(path)
    path.unlink()
    _bundle(path, monkeypatch)
    with zipfile.ZipFile(path, "a") as archive:
        for index in range(MAX_ARCHIVE_ENTRIES):
            archive.writestr(f"x{index}", b"")
    with pytest.raises(ImportBundleError, match="entry count"):
        load_bundle(path)


def test_strict_duplicate_json_key_rejection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "duplicate-key.sbexport"
    _bundle(path, monkeypatch)

    def duplicate(name: str, payload: bytes) -> tuple[str, bytes]:
        if name != "manifest.json":
            return name, payload
        assert json.loads(payload)["format_name"] == "second-brain-project-export"
        return name, b'{"format_name":"x",' + payload[1:]

    _rewrite(path, duplicate)
    with pytest.raises(ImportBundleError, match="duplicate JSON"):
        load_bundle(path)


def test_supersession_cycle_and_external_reference_rejection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_id = uuid4()
    now = datetime(2025, 1, 1, tzinfo=UTC)
    first_id, second_id = uuid4(), uuid4()
    memories = (
        Memory(
            id=first_id,
            project_id=project_id,
            content="first",
            memory_type="semantic",
            importance=0.5,
            confidence=1.0,
            status="superseded",
            supersedes_id=second_id,
            created_at=now,
            updated_at=now,
        ),
        Memory(
            id=second_id,
            project_id=project_id,
            content="second",
            memory_type="semantic",
            importance=0.5,
            confidence=1.0,
            status="superseded",
            supersedes_id=first_id,
            created_at=now,
            updated_at=now,
        ),
    )
    path = tmp_path / "cycle.sbexport"
    _bundle(path, monkeypatch, memories, project_id)
    with pytest.raises(ImportBundleError, match="cycle"):
        load_bundle(path)


def test_deterministic_insertion_plan_is_dependency_safe() -> None:
    assert INSERT_ORDER.index("sources.jsonl") < INSERT_ORDER.index(
        "source_documents.jsonl"
    )
    assert INSERT_ORDER.index("memories.jsonl") < INSERT_ORDER.index(
        "memory_embeddings.jsonl"
    )
    assert INSERT_ORDER[-1] == "memory_proposals.jsonl"
