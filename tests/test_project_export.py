"""Focused format and filesystem safety tests for Project export bundles."""

import json
import shutil
import zipfile
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.models import Memory, Project
from app.project_export.models import ExportFile, ExportIntegrityError, ExportManifest
from app.project_export.serialization import canonical_json, sha256_bytes
from app.project_export.service import DATA_FILES, export_project


@pytest.fixture
def export_tmp_path() -> Generator[Path, None, None]:
    path = Path(".tmp-tests") / f"project-export-{uuid4()}"
    path.mkdir(parents=True)
    try:
        yield path
    finally:
        shutil.rmtree(path)


def test_manifest_validation_and_unsafe_paths() -> None:
    now = datetime.now(UTC)
    entry = ExportFile(
        path="memories.jsonl", byte_length=0, row_count=0, sha256="0" * 64
    )
    manifest = ExportManifest(
        exported_at=now,
        source_alembic_revision="0009_memory_expiration",
        project_id=uuid4(),
        project_name="Safe",
        entity_counts={"memories": 0},
        files=[entry],
    )
    assert manifest.format_name == "second-brain-project-export"
    for path in ("../bad", "/absolute", r"bad\name"):
        with pytest.raises(ValidationError):
            ExportFile(path=path, byte_length=0, row_count=0, sha256="0" * 64)
    with pytest.raises(ValidationError):
        ExportManifest(
            exported_at=datetime.now(),
            source_alembic_revision="head",
            project_id=uuid4(),
            project_name="Bad",
            entity_counts={},
            files=[],
        )


def test_canonical_serialization_timestamp_checksum_and_non_finite() -> None:
    identifier = UUID("00000000-0000-0000-0000-000000000001")
    timestamp = datetime(2025, 1, 2, 5, 4, 3, 12, tzinfo=UTC)
    value = canonical_json({"z": None, "id": identifier, "at": timestamp})
    assert value == (
        b'{"at":"2025-01-02T05:04:03.000012Z",'
        b'"id":"00000000-0000-0000-0000-000000000001","z":null}\n'
    )
    assert sha256_bytes(value) == sha256_bytes(value)
    with pytest.raises(ValueError, match="non-finite"):
        canonical_json({"value": float("nan")})
    with pytest.raises(ValueError, match="timezone-aware"):
        canonical_json({"at": datetime.now()})


def _project(project_id: UUID) -> Project:
    now = datetime(2025, 1, 1, tzinfo=UTC)
    return Project(
        id=project_id,
        name="Export Project",
        description=None,
        created_at=now,
        updated_at=now,
    )


def test_empty_files_and_deterministic_data_checksums(
    export_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_id = uuid4()
    monkeypatch.setattr(
        "app.repositories.project_exports.get_project",
        lambda _session, _project_id: _project(project_id),
    )
    for name in (
        "memories",
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
    checksums: list[dict[str, str]] = []
    for index in range(2):
        path = export_tmp_path / f"empty-{index}.sbexport"
        export_project(
            object(),  # type: ignore[arg-type]
            project_id,
            path,
            source_alembic_revision="0009_memory_expiration",
            exported_at=datetime(2025, 1, 1, tzinfo=UTC),
        )
        with zipfile.ZipFile(path) as archive:
            assert set(archive.namelist()) == {"manifest.json", *DATA_FILES}
            manifest = json.loads(archive.read("manifest.json"))
            assert all(archive.read(name) == b"" for name in DATA_FILES[1:])
            checksums.append(
                {item["path"]: item["sha256"] for item in manifest["files"]}
            )
    assert checksums[0] == checksums[1]


def test_reference_failure_cleans_temp_and_does_not_publish(
    export_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_id = uuid4()
    now = datetime.now(UTC)
    broken = Memory(
        id=uuid4(),
        project_id=project_id,
        content="safe",
        source=None,
        title=None,
        summary=None,
        memory_type="semantic",
        importance=0.5,
        confidence=1.0,
        status="active",
        event_time=None,
        expires_at=None,
        supersedes_id=uuid4(),
        created_at=now,
        updated_at=now + timedelta(seconds=1),
    )
    monkeypatch.setattr(
        "app.repositories.project_exports.get_project",
        lambda *_args: _project(project_id),
    )
    monkeypatch.setattr(
        "app.repositories.project_exports.memories", lambda *_args: iter((broken,))
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
    output = export_tmp_path / "broken.sbexport"
    with pytest.raises(ExportIntegrityError, match="supersession"):
        export_project(
            object(),  # type: ignore[arg-type]
            project_id,
            output,
            source_alembic_revision="0009_memory_expiration",
        )
    assert not output.exists()
    assert list(export_tmp_path.iterdir()) == []


def test_existing_output_is_never_overwritten(export_tmp_path: Path) -> None:
    output = export_tmp_path / "existing.sbexport"
    output.write_bytes(b"original")
    with pytest.raises(FileExistsError):
        export_project(
            object(),  # type: ignore[arg-type]
            uuid4(),
            output,
            source_alembic_revision="0009_memory_expiration",
        )
    assert output.read_bytes() == b"original"
