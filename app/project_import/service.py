"""Validate and atomically restore Project export format version 1."""

import hashlib
import json
import math
import stat
import zipfile
from collections.abc import Callable
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, cast
from uuid import UUID

from sqlalchemy import Table, UniqueConstraint, insert, select, tuple_
from sqlalchemy.orm import Session
from sqlalchemy.sql.sqltypes import String

from app.models import (
    Memory,
    MemoryEmbedding,
    MemoryExtractionRun,
    MemoryProposal,
    MemorySource,
    Project,
    Source,
    SourceChunk,
    SourceDocument,
)
from app.project_export.models import SUPPORTED_SOURCE_REVISIONS, ExportManifest
from app.project_export.service import DATA_FILES
from app.project_import.models import (
    ImportBundleError,
    ImportConflictError,
    ImportResult,
)

MAX_ARCHIVE_ENTRIES = 32
MAX_ARCHIVE_BYTES = 128 * 1024 * 1024
MAX_ENTRY_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_JSONL_ROW_BYTES = 4 * 1024 * 1024
REQUIRED_ENTRIES = frozenset(("manifest.json", *DATA_FILES))

TABLES: dict[str, Table] = {
    "project.json": cast(Table, Project.__table__),
    "memories.jsonl": cast(Table, Memory.__table__),
    "memory_embeddings.jsonl": cast(Table, MemoryEmbedding.__table__),
    "sources.jsonl": cast(Table, Source.__table__),
    "memory_sources.jsonl": cast(Table, MemorySource.__table__),
    "source_documents.jsonl": cast(Table, SourceDocument.__table__),
    "source_chunks.jsonl": cast(Table, SourceChunk.__table__),
    "memory_extraction_runs.jsonl": cast(Table, MemoryExtractionRun.__table__),
    "memory_proposals.jsonl": cast(Table, MemoryProposal.__table__),
}

INSERT_ORDER = (
    "project.json",
    "sources.jsonl",
    "source_documents.jsonl",
    "source_chunks.jsonl",
    "memories.jsonl",
    "memory_embeddings.jsonl",
    "memory_sources.jsonl",
    "memory_extraction_runs.jsonl",
    "memory_proposals.jsonl",
)


def _object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ImportBundleError("duplicate JSON object key")
        result[key] = value
    return result


def _json(data: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=_object_pairs,
            parse_constant=lambda _value: (_ for _ in ()).throw(
                ImportBundleError("non-finite JSON number")
            ),
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ImportBundleError(f"invalid JSON in {label}") from exc
    if not isinstance(value, dict):
        raise ImportBundleError(f"{label} must contain a JSON object")
    return value


def _safe_info(info: zipfile.ZipInfo) -> None:
    name = info.filename
    path = PurePosixPath(name)
    if (
        not name
        or "\\" in name
        or path.is_absolute()
        or ".." in path.parts
        or str(path) != name
    ):
        raise ImportBundleError("unsafe archive path")
    if info.flag_bits & 0x1:
        raise ImportBundleError("encrypted archive entries are unsupported")
    mode = info.external_attr >> 16
    if mode and stat.S_IFMT(mode) not in (0, stat.S_IFREG):
        raise ImportBundleError("non-regular archive entry")
    if info.file_size > MAX_ENTRY_BYTES or info.compress_size > MAX_ENTRY_BYTES:
        raise ImportBundleError("archive entry exceeds resource limit")


def _coerce_record(name: str, value: dict[str, Any]) -> dict[str, Any]:
    table = TABLES[name]
    expected = {
        column.name for column in table.columns if column.name != "search_vector"
    }
    if set(value) != expected:
        raise ImportBundleError(f"{name} has an incompatible field schema")
    result = dict(value)
    for column in table.columns:
        if column.name == "search_vector":
            continue
        item = result[column.name]
        if item is None:
            if not column.nullable:
                raise ImportBundleError(f"{name} has a null required field")
            continue
        try:
            python_type = column.type.python_type
        except NotImplementedError:
            python_type = object
        try:
            if python_type is UUID:
                if not isinstance(item, str):
                    raise ValueError
                result[column.name] = UUID(item)
            elif python_type is datetime:
                if not isinstance(item, str) or not item.endswith("Z"):
                    raise ValueError
                parsed = datetime.fromisoformat(item.replace("Z", "+00:00"))
                if parsed.utcoffset() is None:
                    raise ValueError
                result[column.name] = parsed
            elif python_type is float:
                if isinstance(item, bool) or not isinstance(item, (int, float)):
                    raise ValueError
                result[column.name] = float(item)
                if not math.isfinite(result[column.name]):
                    raise ValueError
            elif python_type is int:
                if isinstance(item, bool) or not isinstance(item, int):
                    raise ValueError
            elif python_type is str and not isinstance(item, str):
                raise ValueError
        except (TypeError, ValueError):
            raise ImportBundleError(f"{name} contains an invalid typed field") from None
        if (
            isinstance(column.type, String)
            and column.type.length is not None
            and isinstance(item, str)
            and len(item) > column.type.length
        ):
            raise ImportBundleError(f"{name} contains an overlong field")
    if name == "memory_embeddings.jsonl":
        vector = result["embedding"]
        if (
            not isinstance(vector, list)
            or result["dimensions"] != 1536
            or len(vector) != 1536
            or any(
                isinstance(number, bool)
                or not isinstance(number, (int, float))
                or not math.isfinite(float(number))
                for number in vector
            )
        ):
            raise ImportBundleError("embedding vector dimensions or values are invalid")
        result["embedding"] = [float(number) for number in vector]
    _validate_semantics(name, result)
    return result


def _validate_semantics(name: str, row: dict[str, Any]) -> None:
    hash_fields = {
        "memory_embeddings.jsonl": ("input_hash",),
        "source_chunks.jsonl": ("content_hash",),
        "memory_extraction_runs.jsonl": ("input_hash",),
        "memory_proposals.jsonl": (
            "source_chunk_hash",
            "proposal_hash",
        ),
    }
    for field in hash_fields.get(name, ()):
        value = row[field]
        if len(value) != 64 or any(
            character not in "0123456789abcdef" for character in value
        ):
            raise ImportBundleError(f"{name} contains an invalid hash")
    enums = {
        ("memories.jsonl", "memory_type"): {
            "working",
            "episodic",
            "semantic",
            "decision",
            "procedural",
            "preference",
            "temporary",
        },
        ("memories.jsonl", "status"): {
            "active",
            "superseded",
            "invalid",
            "archived",
            "expired",
        },
        ("source_documents.jsonl", "ingestion_status"): {
            "pending",
            "extracted",
            "failed",
        },
        ("memory_extraction_runs.jsonl", "run_status"): {
            "pending",
            "completed",
            "failed",
        },
        ("memory_proposals.jsonl", "memory_type"): {
            "working",
            "episodic",
            "semantic",
            "decision",
            "procedural",
            "preference",
            "temporary",
        },
        ("memory_proposals.jsonl", "review_status"): {
            "pending",
            "approved",
            "rejected",
        },
    }
    for (row_name, field), allowed in enums.items():
        if name == row_name and row[field] not in allowed:
            raise ImportBundleError(f"{name} contains an invalid state")
    for field in ("importance", "confidence"):
        if field in row and not 0.0 <= row[field] <= 1.0:
            raise ImportBundleError(f"{name} contains an out-of-range score")
    if (
        name == "source_documents.jsonl"
        and row["byte_size"] is not None
        and row["byte_size"] < 0
    ):
        raise ImportBundleError("source_documents.jsonl contains a negative byte size")
    if name == "source_chunks.jsonl" and (
        row["chunk_index"] < 0
        or row["char_start"] < 0
        or row["char_end"] <= row["char_start"]
        or not row["content"].strip()
    ):
        raise ImportBundleError("source_chunks.jsonl contains invalid bounds")
    if name == "memory_proposals.jsonl" and (
        row["proposal_index"] < 0
        or row["evidence_char_start"] < 0
        or row["evidence_char_end"] <= row["evidence_char_start"]
        or not row["content"].strip()
        or not row["evidence_text"].strip()
    ):
        raise ImportBundleError("memory_proposals.jsonl contains invalid bounds")


def _rows(payload: bytes, name: str) -> list[dict[str, Any]]:
    if name == "project.json":
        if not payload.endswith(b"\n") or payload.count(b"\n") != 1:
            raise ImportBundleError("project.json must contain exactly one row")
        return [_coerce_record(name, _json(payload[:-1], name))]
    records: list[dict[str, Any]] = []
    if payload and not payload.endswith(b"\n"):
        raise ImportBundleError(f"{name} must end with LF")
    for line in payload.splitlines():
        if len(line) > MAX_JSONL_ROW_BYTES:
            raise ImportBundleError("JSONL row exceeds resource limit")
        records.append(_coerce_record(name, _json(line, name)))
    return records


def _require_refs(data: dict[str, list[dict[str, Any]]], project_id: UUID) -> None:
    ids = {name: {row["id"] for row in rows} for name, rows in data.items()}
    if ids["project.json"] != {project_id}:
        raise ImportBundleError("Project ID is inconsistent")
    for row in data["memories.jsonl"]:
        if row["project_id"] != project_id:
            raise ImportBundleError("Memory points outside the bundle Project")
        if (
            row["supersedes_id"] is not None
            and row["supersedes_id"] not in ids["memories.jsonl"]
        ):
            raise ImportBundleError("Memory supersession points outside the bundle")
    references = (
        ("memory_embeddings.jsonl", "memory_id", "memories.jsonl", False),
        ("memory_sources.jsonl", "memory_id", "memories.jsonl", False),
        ("memory_sources.jsonl", "source_id", "sources.jsonl", False),
        ("source_documents.jsonl", "source_id", "sources.jsonl", False),
        ("source_chunks.jsonl", "document_id", "source_documents.jsonl", False),
        (
            "memory_extraction_runs.jsonl",
            "document_id",
            "source_documents.jsonl",
            False,
        ),
        ("memory_proposals.jsonl", "run_id", "memory_extraction_runs.jsonl", False),
        ("memory_proposals.jsonl", "source_chunk_id", "source_chunks.jsonl", True),
        ("memory_proposals.jsonl", "memory_id", "memories.jsonl", True),
    )
    for source_name, field, target_name, optional in references:
        for row in data[source_name]:
            value = row[field]
            if not (optional and value is None) and value not in ids[target_name]:
                raise ImportBundleError(
                    f"{source_name} reference points outside bundle"
                )
    for name in ("memory_extraction_runs.jsonl", "memory_proposals.jsonl"):
        if any(row["project_id"] != project_id for row in data[name]):
            raise ImportBundleError(f"{name} points outside the bundle Project")
    links = {
        row["id"]: row["supersedes_id"]
        for row in data["memories.jsonl"]
        if row["supersedes_id"] is not None
    }
    for start in links:
        seen: set[UUID] = set()
        current: UUID | None = start
        while current in links:
            if current in seen:
                raise ImportBundleError("Memory supersession cycle")
            assert current is not None
            seen.add(current)
            current = links[current]


def _unique_sets(table: Any) -> list[tuple[str, ...]]:
    result: list[tuple[str, ...]] = [
        (column.name,) for column in table.columns if column.unique
    ]
    result.extend(
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    )
    return result


def _check_conflicts(session: Session, data: dict[str, list[dict[str, Any]]]) -> None:
    for name, rows in data.items():
        table = TABLES[name]
        ids = [row["id"] for row in rows]
        if len(ids) != len(set(ids)):
            raise ImportBundleError(f"{name} contains duplicate IDs")
        if ids and session.scalar(
            select(table.c.id).where(table.c.id.in_(ids)).limit(1)
        ):
            raise ImportConflictError(f"{name} primary-key conflict")
        for fields in _unique_sets(table):
            values = [tuple(row[field] for field in fields) for row in rows]
            comparable = [
                value for value in values if all(item is not None for item in value)
            ]
            if len(comparable) != len(set(comparable)):
                raise ImportBundleError(f"{name} contains duplicate unique identities")
            if not comparable:
                continue
            columns = tuple(table.c[field] for field in fields)
            condition = (
                columns[0].in_([value[0] for value in comparable])
                if len(columns) == 1
                else tuple_(*columns).in_(comparable)
            )
            if session.scalar(select(table.c.id).where(condition).limit(1)):
                raise ImportConflictError(f"{name} unique-identity conflict")


def _memory_order(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    remaining = {row["id"]: row for row in rows}
    ordered: list[dict[str, Any]] = []
    inserted: set[UUID] = set()
    while remaining:
        ready = sorted(
            (
                row
                for row in remaining.values()
                if row["supersedes_id"] is None or row["supersedes_id"] in inserted
            ),
            key=lambda row: str(row["id"]),
        )
        if not ready:
            raise ImportBundleError("Memory supersession cycle")
        for row in ready:
            ordered.append(row)
            inserted.add(row["id"])
            del remaining[row["id"]]
    return ordered


def load_bundle(
    path: Path,
) -> tuple[ExportManifest, dict[str, list[dict[str, Any]]], str]:
    """Read an archive without extracting it and validate its complete graph."""

    if not path.is_file():
        raise ImportBundleError("BundlePath must be an existing regular file")
    if path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ImportBundleError("archive compressed size exceeds resource limit")
    bundle_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_ARCHIVE_ENTRIES:
                raise ImportBundleError("archive entry count exceeds resource limit")
            names = [info.filename for info in infos]
            if len(names) != len(set(names)):
                raise ImportBundleError("duplicate archive entry")
            if len({name.casefold() for name in names}) != len(names):
                raise ImportBundleError("case-colliding archive entries")
            for info in infos:
                _safe_info(info)
            if set(names) != REQUIRED_ENTRIES:
                raise ImportBundleError("archive entries do not match format version 1")
            if sum(info.file_size for info in infos) > MAX_TOTAL_BYTES:
                raise ImportBundleError("archive total size exceeds resource limit")
            if sum(info.compress_size for info in infos) > MAX_ARCHIVE_BYTES:
                raise ImportBundleError(
                    "archive compressed size exceeds resource limit"
                )
            manifest = ExportManifest.model_validate(
                _json(archive.read("manifest.json"), "manifest.json")
            )
            if manifest.source_alembic_revision not in SUPPORTED_SOURCE_REVISIONS:
                raise ImportBundleError("unsupported source Alembic revision")
            indexed = {entry.path: entry for entry in manifest.files}
            if set(indexed) != set(DATA_FILES) or len(indexed) != len(manifest.files):
                raise ImportBundleError("manifest file index is invalid")
            data: dict[str, list[dict[str, Any]]] = {}
            for name in DATA_FILES:
                payload = archive.read(name)
                entry = indexed[name]
                if (
                    len(payload) != entry.byte_length
                    or hashlib.sha256(payload).hexdigest() != entry.sha256
                ):
                    raise ImportBundleError(f"{name} length or checksum mismatch")
                rows = _rows(payload, name)
                if len(rows) != entry.row_count:
                    raise ImportBundleError(f"{name} row count mismatch")
                data[name] = rows
    except (zipfile.BadZipFile, OSError) as exc:
        raise ImportBundleError("BundlePath is not a readable ZIP bundle") from exc
    expected_counts = {
        name.removesuffix(".jsonl").removesuffix(".json"): len(rows)
        for name, rows in data.items()
    }
    if manifest.entity_counts != expected_counts:
        raise ImportBundleError("manifest entity counts mismatch")
    if data["project.json"][0]["name"] != manifest.project_name:
        raise ImportBundleError("manifest Project name mismatch")
    _require_refs(data, manifest.project_id)
    return manifest, data, bundle_hash


def import_project(
    session: Session,
    bundle_path: Path,
    *,
    execute: bool,
    expected_project_id: UUID | None = None,
    before_insert: Callable[[str], None] | None = None,
) -> ImportResult:
    """Validate a bundle and target, optionally inserting it in this transaction."""

    manifest, data, bundle_hash = load_bundle(bundle_path)
    if execute and expected_project_id != manifest.project_id:
        raise ImportBundleError("ExpectedProjectId must exactly match the manifest")
    _check_conflicts(session, data)
    if execute:
        data["memories.jsonl"] = _memory_order(data["memories.jsonl"])
        for name in INSERT_ORDER:
            if before_insert is not None:
                before_insert(name)
            if data[name]:
                session.execute(insert(TABLES[name]), data[name])
        session.flush()
    return ImportResult(
        import_status="imported" if execute else "validated",
        format_name=manifest.format_name,
        format_version=manifest.format_version,
        project_id=manifest.project_id,
        project_name=manifest.project_name,
        source_alembic_revision=manifest.source_alembic_revision,
        entity_counts=manifest.entity_counts,
        bundle_sha256=bundle_hash,
    )
