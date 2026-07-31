"""Streaming archive writer for project export format version 1."""

import os
import tempfile
import zipfile
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.project_export.models import (
    ExportFile,
    ExportIntegrityError,
    ExportManifest,
    ExportResult,
    ProjectNotFoundError,
)
from app.project_export.serialization import canonical_json, validate_archive_path
from app.repositories import project_exports

DATA_FILES = (
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


def _record(row: Any) -> dict[str, Any]:
    return {
        column.key: getattr(row, column.key)
        for column in inspect(type(row)).columns
        if column.key != "search_vector"
    }


def _zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(validate_archive_path(name), (1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o600 << 16
    return info


def _write_rows(
    archive: zipfile.ZipFile,
    name: str,
    rows: Iterator[Any],
    reference_fields: tuple[str, ...],
) -> tuple[ExportFile, set[UUID], list[dict[str, Any]]]:
    digest = sha256()
    count = 0
    length = 0
    ids: set[UUID] = set()
    references: list[dict[str, Any]] = []
    with archive.open(_zip_info(name), "w") as output:
        for row in rows:
            record = _record(row)
            data = canonical_json(record)
            output.write(data)
            digest.update(data)
            length += len(data)
            count += 1
            if "id" in record:
                ids.add(record["id"])
            references.append({field: record[field] for field in reference_fields})
    return (
        ExportFile(
            path=name, byte_length=length, row_count=count, sha256=digest.hexdigest()
        ),
        ids,
        references,
    )


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ExportIntegrityError(message)


def export_project(
    session: Session,
    project_id: UUID,
    output_path: Path,
    *,
    source_alembic_revision: str,
    exported_at: datetime | None = None,
) -> ExportResult:
    """Create a validated bundle and atomically publish it to a new path."""

    output_path = output_path.resolve()
    if output_path.exists():
        raise FileExistsError("output path already exists")
    if not output_path.parent.is_dir():
        raise FileNotFoundError("output parent directory does not exist")
    project = project_exports.get_project(session, project_id)
    if project is None:
        raise ProjectNotFoundError("Project does not exist")
    captured_at = exported_at or datetime.now(UTC)
    temp_fd, temp_name = tempfile.mkstemp(
        prefix=f".{output_path.name}.", suffix=".tmp", dir=output_path.parent
    )
    os.close(temp_fd)
    temp_path = Path(temp_name)
    try:
        files: list[ExportFile] = []
        ids: dict[str, set[UUID]] = {}
        refs: dict[str, list[dict[str, Any]]] = {}
        providers: tuple[
            tuple[str, Callable[[Session, UUID], Iterator[Any]], tuple[str, ...]], ...
        ] = (
            ("memories.jsonl", project_exports.memories, ("supersedes_id",)),
            ("memory_embeddings.jsonl", project_exports.embeddings, ("memory_id",)),
            ("sources.jsonl", project_exports.sources, ()),
            (
                "memory_sources.jsonl",
                project_exports.memory_sources,
                ("memory_id", "source_id"),
            ),
            ("source_documents.jsonl", project_exports.documents, ("source_id",)),
            ("source_chunks.jsonl", project_exports.chunks, ("document_id",)),
            (
                "memory_extraction_runs.jsonl",
                project_exports.extraction_runs,
                ("document_id",),
            ),
            (
                "memory_proposals.jsonl",
                project_exports.proposals,
                ("run_id", "memory_id", "source_chunk_id"),
            ),
        )
        with zipfile.ZipFile(temp_path, "w") as archive:
            project_data = canonical_json(_record(project))
            archive.writestr(_zip_info("project.json"), project_data)
            files.append(
                ExportFile(
                    path="project.json",
                    byte_length=len(project_data),
                    row_count=1,
                    sha256=sha256(project_data).hexdigest(),
                )
            )
            ids["project.json"] = {project.id}
            refs["project.json"] = [_record(project)]
            for name, provider, reference_fields in providers:
                entry, row_ids, row_refs = _write_rows(
                    archive, name, provider(session, project_id), reference_fields
                )
                files.append(entry)
                ids[name] = row_ids
                refs[name] = row_refs

            for row in refs["memory_embeddings.jsonl"]:
                _require(
                    row["memory_id"] in ids["memories.jsonl"],
                    "embedding references a Memory outside the export",
                )
            for row in refs["memory_sources.jsonl"]:
                _require(
                    row["memory_id"] in ids["memories.jsonl"]
                    and row["source_id"] in ids["sources.jsonl"],
                    "MemorySource reference is outside the export",
                )
            for row in refs["source_documents.jsonl"]:
                _require(
                    row["source_id"] in ids["sources.jsonl"],
                    "document references a Source outside the export",
                )
            for row in refs["source_chunks.jsonl"]:
                _require(
                    row["document_id"] in ids["source_documents.jsonl"],
                    "chunk references a document outside the export",
                )
            for row in refs["memory_extraction_runs.jsonl"]:
                _require(
                    row["document_id"] in ids["source_documents.jsonl"],
                    "extraction run references a document outside the export",
                )
            for row in refs["memory_proposals.jsonl"]:
                _require(
                    row["run_id"] in ids["memory_extraction_runs.jsonl"],
                    "proposal references a run outside the export",
                )
                _require(
                    row["memory_id"] is None
                    or row["memory_id"] in ids["memories.jsonl"],
                    "proposal references a Memory outside the export",
                )
                _require(
                    row["source_chunk_id"] is None
                    or row["source_chunk_id"] in ids["source_chunks.jsonl"],
                    "proposal references a chunk outside the export",
                )
            for row in refs["memories.jsonl"]:
                _require(
                    row["supersedes_id"] is None
                    or row["supersedes_id"] in ids["memories.jsonl"],
                    "Memory supersession reference is outside the export",
                )

            counts = {
                entry.path.removesuffix(".jsonl").removesuffix(".json"): entry.row_count
                for entry in files
            }
            manifest = ExportManifest(
                exported_at=captured_at,
                source_alembic_revision=source_alembic_revision,
                project_id=project.id,
                project_name=project.name,
                entity_counts=counts,
                files=files,
            )
            archive.writestr(
                _zip_info("manifest.json"),
                canonical_json(manifest.model_dump(mode="python")),
            )
        temp_path.rename(output_path)
        package_bytes = output_path.read_bytes()
        return ExportResult(
            output_path=str(output_path),
            project_id=project.id,
            project_name=project.name,
            entity_counts=counts,
            package_byte_size=len(package_bytes),
            package_sha256=sha256(package_bytes).hexdigest(),
            source_alembic_revision=source_alembic_revision,
        )
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
