"""Checkpoint 122 joined real-route PostgreSQL Capture acceptance."""

from __future__ import annotations

import uuid
import zipfile
from collections.abc import Callable, Generator, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from app.agent_tools.registry import AGENT_TOOL_REGISTRY, REGISTRY_VERSION
from app.db.session import get_engine
from app.extraction.dependencies import get_extraction_provider
from app.extraction.provider import (
    ChunkExtraction,
    ChunkSnapshot,
    ExtractedProposal,
    ExtractionResult,
)
from app.ingestion.text import chunk_text
from app.main import create_app
from app.models import (
    AgentRun,
    Automation,
    Memory,
    MemoryEmbedding,
    MemoryExtractionRun,
    MemoryProposal,
    MemorySource,
    Project,
    Source,
)
from app.models.capture_item import CaptureItem
from app.models.source_chunk import SourceChunk
from app.models.source_document import SourceDocument
from app.project_export.models import (
    CURRENT_DATABASE_REVISION,
    FORMAT_NAME,
    FORMAT_VERSION,
)
from app.project_export.service import export_project
from app.sources.scope import LEGACY_ONLY, get_chunk_for_scope, get_document_for_scope
from tests.integration.conftest import (
    TEST_DATABASE_NAME,
    verify_connected_test_database,
)
from tests.integration.test_context_hub import _complete_rows, _runtime_tripwires

pytestmark = [
    pytest.mark.usefixtures("migrated_test_database"),
    pytest.mark.cp122_acceptance,
]

HOSTILE = (
    "<script>globalThis.cp122=true</script> [open](javascript:alert(1)) "
    "\u202eSettings\u202c\n" + "x" * 2200
)
CP122_OWNED_PREFIX = "__cp122_joined_capture_acceptance_owned_v1__:"


@dataclass
class _CP122Ownership:
    marker: str = field(default_factory=lambda: f"{CP122_OWNED_PREFIX}{uuid.uuid4()}:")
    capture_ids: set[uuid.UUID] = field(default_factory=set)
    source_ids: set[uuid.UUID] = field(default_factory=set)
    project_ids: set[uuid.UUID] = field(default_factory=set)
    proposal_ids: set[uuid.UUID] = field(default_factory=set)
    extraction_run_ids: set[uuid.UUID] = field(default_factory=set)
    memory_ids: set[uuid.UUID] = field(default_factory=set)


@dataclass(frozen=True)
class _CleanupGraph:
    project_id: uuid.UUID
    capture_id: uuid.UUID | None = None
    source_id: uuid.UUID | None = None
    document_id: uuid.UUID | None = None
    chunk_id: uuid.UUID | None = None
    extraction_run_id: uuid.UUID | None = None
    proposal_id: uuid.UUID | None = None
    memory_id: uuid.UUID | None = None
    memory_source_id: uuid.UUID | None = None


def _seed_cleanup_graph(ownership: _CP122Ownership, through: str) -> _CleanupGraph:
    stages = (
        "project",
        "capture",
        "conversion_source",
        "extraction_run",
        "proposal",
        "memory",
    )
    stop = stages.index(through)
    digest = sha256(ownership.marker.encode()).hexdigest()
    with Session(get_engine()) as session:
        project = Project(name=f"{ownership.marker}failure-{through}")
        session.add(project)
        session.flush()
        values: dict[str, uuid.UUID | None] = {
            "project_id": project.id,
            "capture_id": None,
            "source_id": None,
            "document_id": None,
            "chunk_id": None,
            "extraction_run_id": None,
            "proposal_id": None,
            "memory_id": None,
            "memory_source_id": None,
        }
        ownership.project_ids.add(project.id)
        if stop >= 1:
            capture = CaptureItem(
                project_id=project.id,
                content=f"{ownership.marker}interrupted capture",
                idempotency_key_hash=digest,
                request_fingerprint=digest,
            )
            session.add(capture)
            session.flush()
            values["capture_id"] = capture.id
            ownership.capture_ids.add(capture.id)
        if stop >= 2:
            source = Source(source_type="capture", name=f"Capture {capture.id}")
            session.add(source)
            session.flush()
            document = SourceDocument(
                source_id=source.id,
                media_type="text/plain",
                byte_size=8,
                extracted_text="evidence",
                ingestion_status="extracted",
            )
            session.add(document)
            session.flush()
            chunk = SourceChunk(
                document_id=document.id,
                chunk_index=0,
                content="evidence",
                char_start=0,
                char_end=8,
                content_hash=sha256(b"evidence").hexdigest(),
            )
            session.add(chunk)
            session.flush()
            values.update(
                source_id=source.id, document_id=document.id, chunk_id=chunk.id
            )
            ownership.source_ids.add(source.id)
            capture.state = "processed"
            capture.revision = 2
            capture.processed_at = datetime.now(UTC)
            capture.resulting_source_id = source.id
        if stop >= 3:
            run = MemoryExtractionRun(
                document_id=values["document_id"],
                project_id=project.id,
                provider="cp122-fault",
                model="cp122-fault",
                prompt_version="cp122-fault-v1",
                input_hash=digest,
                run_status="completed",
            )
            session.add(run)
            session.flush()
            values["extraction_run_id"] = run.id
            ownership.extraction_run_ids.add(run.id)
        if stop >= 5:
            memory = Memory(
                project_id=project.id,
                content="unrelated cleanup evidence",
                source="cp122-fault",
            )
            session.add(memory)
            session.flush()
            values["memory_id"] = memory.id
            ownership.memory_ids.add(memory.id)
        if stop >= 4:
            proposal = MemoryProposal(
                run_id=values["extraction_run_id"],
                source_chunk_id=values["chunk_id"],
                source_chunk_hash=sha256(b"evidence").hexdigest(),
                project_id=project.id,
                proposal_index=0,
                content="cleanup evidence",
                memory_type="semantic",
                importance=0.5,
                confidence=0.5,
                evidence_text="evidence",
                evidence_char_start=0,
                evidence_char_end=8,
                proposal_hash=digest,
                review_status="approved" if stop >= 5 else "pending",
                memory_id=values["memory_id"],
            )
            session.add(proposal)
            session.flush()
            values["proposal_id"] = proposal.id
            ownership.proposal_ids.add(proposal.id)
        if stop >= 5:
            memory_source = MemorySource(
                memory_id=values["memory_id"],
                source_id=values["source_id"],
                source_location="cp122 cleanup evidence",
            )
            session.add(memory_source)
            session.flush()
            values["memory_source_id"] = memory_source.id
        session.commit()
    return _CleanupGraph(**values)  # type: ignore[arg-type]


def _assert_graph_presence(graph: _CleanupGraph, expected: bool) -> None:
    models = (
        (Project, graph.project_id),
        (CaptureItem, graph.capture_id),
        (Source, graph.source_id),
        (SourceDocument, graph.document_id),
        (SourceChunk, graph.chunk_id),
        (MemoryExtractionRun, graph.extraction_run_id),
        (MemoryProposal, graph.proposal_id),
        (Memory, graph.memory_id),
        (MemorySource, graph.memory_source_id),
    )
    with Session(get_engine()) as session:
        for model, row_id in models:
            if row_id is not None:
                assert (session.get(model, row_id) is not None) is expected


def _snapshot_graph(graph: _CleanupGraph) -> dict[str, tuple[object, ...]]:
    models = (
        (Project, graph.project_id),
        (CaptureItem, graph.capture_id),
        (Source, graph.source_id),
        (SourceDocument, graph.document_id),
        (SourceChunk, graph.chunk_id),
        (MemoryExtractionRun, graph.extraction_run_id),
        (MemoryProposal, graph.proposal_id),
        (Memory, graph.memory_id),
        (MemorySource, graph.memory_source_id),
    )
    snapshot: dict[str, tuple[object, ...]] = {}
    with Session(get_engine()) as session:
        for model, row_id in models:
            if row_id is None:
                continue
            row = session.get(model, row_id)
            assert row is not None, f"missing {model.__tablename__} row {row_id}"
            snapshot[model.__tablename__] = tuple(
                getattr(row, column.name) for column in model.__table__.columns
            )
    return snapshot


def _cleanup_cp122_owned_rows(
    ownership: _CP122Ownership,
    test_database_url: str,
    *,
    before_delete: Callable[[str], None] | None = None,
) -> None:
    verify_connected_test_database(test_database_url)
    with Session(get_engine()) as session:
        if session.scalar(text("SELECT current_database()")) != TEST_DATABASE_NAME:
            raise pytest.UsageError(
                "CP122 cleanup refused outside the exact second_brain_test database"
            )
        capture_rows = list(
            session.execute(
                select(CaptureItem.id, CaptureItem.resulting_source_id).where(
                    CaptureItem.content.startswith(ownership.marker, autoescape=True)
                )
            )
        )
        capture_ids = ownership.capture_ids | {row.id for row in capture_rows}
        source_ids = set(ownership.source_ids)
        for row in capture_rows:
            if row.resulting_source_id is None:
                continue
            converted_source_id = session.scalar(
                select(Source.id).where(
                    Source.id == row.resulting_source_id,
                    Source.source_type == "capture",
                    Source.name == f"Capture {row.id}",
                )
            )
            if converted_source_id is not None:
                source_ids.add(converted_source_id)
        source_ids.update(
            session.scalars(
                select(Source.id).where(
                    Source.name.startswith(ownership.marker, autoescape=True)
                )
            )
        )
        project_ids = ownership.project_ids | set(
            session.scalars(
                select(Project.id).where(
                    Project.name.startswith(ownership.marker, autoescape=True)
                )
            )
        )
        document_ids = set(
            session.scalars(
                select(SourceDocument.id).where(
                    SourceDocument.source_id.in_(source_ids)
                )
            )
        )
        run_ids = ownership.extraction_run_ids | set(
            session.scalars(
                select(MemoryExtractionRun.id).where(
                    MemoryExtractionRun.document_id.in_(document_ids)
                )
            )
        )
        proposal_rows = list(
            session.execute(
                select(MemoryProposal.id, MemoryProposal.memory_id).where(
                    MemoryProposal.run_id.in_(run_ids)
                )
            )
        )
        proposal_ids = ownership.proposal_ids | {row.id for row in proposal_rows}
        memory_ids = ownership.memory_ids | {
            row.memory_id for row in proposal_rows if row.memory_id is not None
        }

        if memory_ids:
            if before_delete is not None:
                before_delete("knowledge")
            session.execute(delete(Memory).where(Memory.id.in_(memory_ids)))
        if proposal_ids:
            session.execute(
                delete(MemoryProposal).where(MemoryProposal.id.in_(proposal_ids))
            )
        if run_ids:
            session.execute(
                delete(MemoryExtractionRun).where(MemoryExtractionRun.id.in_(run_ids))
            )
        if capture_ids:
            if before_delete is not None:
                before_delete("capture")
            session.execute(delete(CaptureItem).where(CaptureItem.id.in_(capture_ids)))
        if source_ids:
            if before_delete is not None:
                before_delete("source")
            session.execute(delete(Source).where(Source.id.in_(source_ids)))
        if project_ids:
            if before_delete is not None:
                before_delete("project")
            session.execute(delete(Project).where(Project.id.in_(project_ids)))
        session.commit()


def _assert_marker_absent(marker: str) -> None:
    with Session(get_engine()) as session:
        assert (
            session.scalar(
                select(func.count(CaptureItem.id)).where(
                    CaptureItem.content.startswith(marker, autoescape=True)
                )
            )
            == 0
        )
        assert (
            session.scalar(
                select(func.count(Project.id)).where(
                    Project.name.startswith(marker, autoescape=True)
                )
            )
            == 0
        )
        assert (
            session.scalar(
                select(func.count(Source.id)).where(
                    Source.name.startswith(marker, autoescape=True)
                )
            )
            == 0
        )


@contextmanager
def _cp122_cleanup_scope(
    test_database_url: str,
    *,
    before_delete: Callable[[str], None] | None = None,
) -> Iterator[_CP122Ownership]:
    ownership = _CP122Ownership()
    try:
        yield ownership
    except BaseException as original_error:
        try:
            _cleanup_cp122_owned_rows(
                ownership, test_database_url, before_delete=before_delete
            )
        except BaseException as cleanup_error:
            raise BaseExceptionGroup(
                "CP122 acceptance and cleanup both failed",
                [original_error, cleanup_error],
            ) from None
        raise
    else:
        _cleanup_cp122_owned_rows(
            ownership, test_database_url, before_delete=before_delete
        )


@pytest.fixture(autouse=True)
def cp122_ownership(
    test_database_url: str,
) -> Generator[_CP122Ownership, None, None]:
    verify_connected_test_database(test_database_url)
    with _cp122_cleanup_scope(test_database_url) as ownership:
        yield ownership
    _assert_marker_absent(ownership.marker)


class _InjectedInterruption(RuntimeError):
    pass


@pytest.mark.parametrize(
    "stage",
    [
        "project",
        "capture",
        "conversion_source",
        "proposal",
        "extraction_run",
        "memory",
    ],
)
def test_cp122_cleanup_after_each_interrupted_creation_stage(
    stage: str, test_database_url: str
) -> None:
    sentinel_owner = _CP122Ownership()
    sentinel = _seed_cleanup_graph(sentinel_owner, "memory")
    sentinel_before = _snapshot_graph(sentinel)
    interrupted: _CP122Ownership | None = None
    interrupted_graph: _CleanupGraph | None = None
    try:
        with (
            pytest.raises(_InjectedInterruption, match=f"after {stage}"),
            _cp122_cleanup_scope(test_database_url) as ownership,
        ):
            interrupted = ownership
            interrupted_graph = _seed_cleanup_graph(ownership, stage)
            raise _InjectedInterruption(f"after {stage}")
        assert interrupted is not None and interrupted_graph is not None
        _assert_graph_presence(interrupted_graph, False)
        _assert_marker_absent(interrupted.marker)
        assert _snapshot_graph(sentinel) == sentinel_before
    finally:
        _cleanup_cp122_owned_rows(sentinel_owner, test_database_url)
        _assert_marker_absent(sentinel_owner.marker)


@pytest.mark.parametrize("delete_stage", ["knowledge", "capture", "source", "project"])
def test_cp122_cleanup_delete_failure_rolls_back_and_retries_exactly(
    delete_stage: str, test_database_url: str
) -> None:
    sentinel_owner = _CP122Ownership()
    sentinel = _seed_cleanup_graph(sentinel_owner, "memory")
    sentinel_before = _snapshot_graph(sentinel)
    failed_owner: _CP122Ownership | None = None
    failed_graph: _CleanupGraph | None = None

    def inject_failure(stage: str) -> None:
        if stage == delete_stage:
            raise RuntimeError(f"injected cleanup delete failure at {stage}")

    try:
        with (
            pytest.raises(BaseExceptionGroup) as raised,
            _cp122_cleanup_scope(
                test_database_url, before_delete=inject_failure
            ) as ownership,
        ):
            failed_owner = ownership
            failed_graph = _seed_cleanup_graph(ownership, "memory")
            raise _InjectedInterruption("original acceptance failure")
        assert [type(error) for error in raised.value.exceptions] == [
            _InjectedInterruption,
            RuntimeError,
        ]
        assert str(raised.value.exceptions[0]) == "original acceptance failure"
        assert str(raised.value.exceptions[1]) == (
            f"injected cleanup delete failure at {delete_stage}"
        )
        assert failed_owner is not None and failed_graph is not None
        _assert_graph_presence(failed_graph, True)
        assert _snapshot_graph(sentinel) == sentinel_before

        _cleanup_cp122_owned_rows(failed_owner, test_database_url)
        _assert_graph_presence(failed_graph, False)
        _assert_marker_absent(failed_owner.marker)
        _cleanup_cp122_owned_rows(failed_owner, test_database_url)
        _assert_marker_absent(failed_owner.marker)
        assert _snapshot_graph(sentinel) == sentinel_before
    finally:
        if failed_owner is not None:
            _cleanup_cp122_owned_rows(failed_owner, test_database_url)
        _cleanup_cp122_owned_rows(sentinel_owner, test_database_url)
        _assert_marker_absent(sentinel_owner.marker)


class _ReviewedProvider:
    name = "cp122-fake"
    model = "cp122-bounded"
    prompt_version = "memory_proposals_v1"

    def __init__(self) -> None:
        self.calls = 0

    def extract(
        self,
        instructions: str,
        chunks: list[ChunkSnapshot],
        max_proposals_per_chunk: int,
    ) -> ExtractionResult:
        self.calls += 1
        chunk = chunks[0]
        evidence = "script"
        start = chunk.content.index(evidence)
        return ExtractionResult(
            chunks=[
                ChunkExtraction(
                    chunk_index=chunk.chunk_index,
                    proposals=[
                        ExtractedProposal(
                            title="Reviewed capture",
                            summary=None,
                            content="Explicitly reviewed CP122 knowledge.",
                            memory_type="semantic",
                            importance=0.6,
                            confidence=0.9,
                            evidence_text=evidence,
                            evidence_start=start,
                            evidence_end=start + len(evidence),
                        )
                    ],
                )
            ]
        )


def _scope(project_id: str | None) -> dict[str, object]:
    return {"unassigned": True} if project_id is None else {"project_id": project_id}


def _create(
    client: TestClient,
    content: str,
    *,
    project_id: str | None = None,
    key: str | None = None,
) -> tuple[int, dict[str, object]]:
    body: dict[str, object] = {"content": content}
    if project_id is not None:
        body["project_id"] = project_id
    response = client.post(
        "/capture-items",
        json=body,
        headers={"Idempotency-Key": key or f"cp122-{uuid.uuid4()}"},
    )
    return response.status_code, response.json()


def _query(
    client: TestClient,
    project_id: str | None,
    state: str = "pending",
    **extra: object,
) -> dict[str, object]:
    response = client.post(
        "/capture-items/query",
        json={
            "scope": _scope(project_id),
            "states": [state],
            "page_size": 1,
            **extra,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_joined_capture_inbox_conversion_scope_restart_and_reviewed_knowledge(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    test_database_url: str,
    cp122_ownership: _CP122Ownership,
) -> None:
    verify_connected_test_database(test_database_url)
    external_calls = _runtime_tripwires(monkeypatch)
    provider = _ReviewedProvider()
    app = create_app()
    app.dependency_overrides[get_extraction_provider] = lambda: provider
    protected = (Memory, MemoryEmbedding, MemoryProposal, AgentRun, Automation)
    protected_before = _complete_rows(protected)
    with Session(get_engine()) as session:
        embedding_count_before = session.scalar(select(func.count(MemoryEmbedding.id)))

    with TestClient(app, client=("127.0.0.1", 52200)) as client:
        project_a = client.post(
            "/projects", json={"name": f"{cp122_ownership.marker}project-a"}
        ).json()
        cp122_ownership.project_ids.add(uuid.UUID(project_a["id"]))
        project_b = client.post(
            "/projects", json={"name": f"{cp122_ownership.marker}project-b"}
        ).json()
        cp122_ownership.project_ids.add(uuid.UUID(project_b["id"]))

        replay_key = f"cp122-replay-{uuid.uuid4()}"
        first_status, first_unassigned = _create(
            client, f"{cp122_ownership.marker}unassigned pagination one"
        )
        assert first_status == 201
        cp122_ownership.capture_ids.add(uuid.UUID(first_unassigned["id"]))
        omitted_status, omitted = _create(
            client,
            f"{cp122_ownership.marker}unassigned pagination lexical needle",
            key=replay_key,
        )
        cp122_ownership.capture_ids.add(uuid.UUID(omitted["id"]))
        replay_status, replay = _create(
            client,
            f"{cp122_ownership.marker}unassigned pagination lexical needle",
            key=replay_key,
        )
        owned_hostile = f"{cp122_ownership.marker}{HOSTILE}"
        _, item_a = _create(client, owned_hostile, project_id=project_a["id"])
        cp122_ownership.capture_ids.add(uuid.UUID(item_a["id"]))
        _, item_b = _create(
            client,
            f"{cp122_ownership.marker}project b isolated",
            project_id=project_b["id"],
        )
        cp122_ownership.capture_ids.add(uuid.UUID(item_b["id"]))
        assert omitted_status == 201 and replay_status == 200
        assert replay == omitted and omitted["project_id"] is None

        first_page = _query(client, None)
        assert len(first_page["items"]) == 1 and first_page["next_cursor"]
        second_page = _query(client, None, cursor=first_page["next_cursor"])
        assert len(second_page["items"]) == 1
        searched = _query(client, None, query="lexical needle")
        assert [row["id"] for row in searched["items"]] == [omitted["id"]]
        assert [row["id"] for row in _query(client, project_a["id"])["items"]] == [
            item_a["id"]
        ]
        assert [row["id"] for row in _query(client, project_b["id"])["items"]] == [
            item_b["id"]
        ]

        detail = client.post(
            f"/capture-items/{item_a['id']}/detail",
            json={"scope": _scope(project_a["id"])},
        )
        assert detail.status_code == 200 and detail.json()["content"] == owned_hostile
        edited = client.patch(
            f"/capture-items/{item_a['id']}",
            json={
                "scope": _scope(project_a["id"]),
                "revision": 1,
                "content": owned_hostile + " edited",
            },
        ).json()
        stale = client.post(
            f"/capture-items/{item_a['id']}/discard",
            json={"scope": _scope(project_a["id"]), "revision": 1},
        )
        assert stale.status_code == 409
        assert stale.json()["detail"]["item"] == edited
        assert (
            client.post(
                f"/capture-items/{item_a['id']}/detail",
                json={"scope": _scope(project_a["id"])},
            ).json()
            == edited
        )

        reassigned = client.post(
            f"/capture-items/{item_b['id']}/reassign",
            json={
                "scope": _scope(project_b["id"]),
                "target_scope": _scope(None),
                "revision": 1,
            },
        ).json()
        discarded = client.post(
            f"/capture-items/{item_b['id']}/discard",
            json={"scope": _scope(None), "revision": reassigned["revision"]},
        ).json()
        restored = client.post(
            f"/capture-items/{item_b['id']}/restore",
            json={"scope": _scope(None), "revision": discarded["revision"]},
        ).json()
        assert (
            reassigned["revision"],
            discarded["revision"],
            restored["revision"],
        ) == (
            2,
            3,
            4,
        )
        discarded = client.post(
            f"/capture-items/{item_b['id']}/discard",
            json={"scope": _scope(None), "revision": restored["revision"]},
        ).json()
        assert discarded["state"] == "discarded" and discarded["revision"] == 5

        converted_response = client.post(
            f"/capture-items/{item_a['id']}/convert-to-source",
            json={"scope": _scope(project_a["id"]), "revision": edited["revision"]},
        )
        assert converted_response.status_code == 200, converted_response.text
        converted = converted_response.json()
        capture = converted["capture"]
        source = converted["source"]
        cp122_ownership.source_ids.add(uuid.UUID(source["id"]))
        assert capture["state"] == "processed" and capture["revision"] == 3
        assert (
            capture["processed_at"] and capture["resulting_source_id"] == source["id"]
        )
        assert provider.calls == 0 and external_calls == []
        assert _complete_rows(protected) == protected_before

        replay_conversion = client.post(
            f"/capture-items/{item_a['id']}/convert-to-source",
            json={"scope": _scope(project_a["id"]), "revision": edited["revision"]},
        )
        assert replay_conversion.status_code == 200
        assert replay_conversion.json() == converted
        assert (
            client.post(
                f"/capture-items/{item_a['id']}/source",
                json={"scope": _scope(project_a["id"])},
            ).json()
            == source
        )
        assert (
            client.post(
                f"/capture-items/{item_a['id']}/source",
                json={"scope": _scope(project_b["id"])},
            ).status_code
            == 404
        )
        assert client.get(f"/sources/{source['id']}").status_code == 404

        legacy = client.post(
            "/sources",
            json={"source_type": "note", "name": f"{cp122_ownership.marker}legacy"},
        ).json()
        cp122_ownership.source_ids.add(uuid.UUID(legacy["id"]))
        legacy_document = client.put(
            f"/sources/{legacy['id']}/document/text",
            json={"text": "ordinary legacy source"},
        ).json()
        assert client.get(f"/sources/{legacy['id']}").json() == legacy
        assert client.get(f"/sources/{legacy['id']}/documents").status_code == 200

        with Session(get_engine()) as session:
            document = session.scalar(
                select(SourceDocument).where(
                    SourceDocument.source_id == uuid.UUID(source["id"])
                )
            )
            assert (
                document is not None
                and document.extracted_text == owned_hostile + " edited"
            )
            chunks = list(
                session.scalars(
                    select(SourceChunk)
                    .where(SourceChunk.document_id == document.id)
                    .order_by(SourceChunk.chunk_index)
                )
            )
            assert [row.content for row in chunks] == [
                row.content for row in chunk_text(owned_hostile + " edited", 2000, 200)
            ]
            assert get_document_for_scope(session, document.id, project_a["id"])
            assert get_document_for_scope(session, document.id, project_b["id"]) is None
            assert get_document_for_scope(session, document.id, LEGACY_ONLY) is None
            assert all(
                get_chunk_for_scope(session, row.id, project_a["id"]) for row in chunks
            )
            assert all(
                get_chunk_for_scope(session, row.id, project_b["id"]) is None
                for row in chunks
            )
            assert session.get(SourceDocument, uuid.UUID(legacy_document["id"]))

        archive = tmp_path / "cp122-export.sbexport"
        with Session(get_engine()) as session:
            export_project(
                session,
                uuid.UUID(project_a["id"]),
                archive,
                source_alembic_revision=CURRENT_DATABASE_REVISION,
            )
        with zipfile.ZipFile(archive) as exported:
            names = exported.namelist()
            payload = b"".join(exported.read(name) for name in names)
        assert FORMAT_NAME == "second-brain-project-export" and FORMAT_VERSION == 1
        assert not any("capture" in name.lower() for name in names)
        assert str(item_a["id"]).encode() not in payload
        assert REGISTRY_VERSION == "agent-tools-v1"
        assert len(AGENT_TOOL_REGISTRY.inventory) == 7

        generated = client.post(
            f"/sources/{source['id']}/memory-proposals",
            json={"project_id": project_a["id"], "chunk_limit": 1},
        )
        assert generated.status_code == 200, generated.text
        assert generated.json()["proposal_count"] == 1 and provider.calls == 1
        cp122_ownership.extraction_run_ids.add(uuid.UUID(generated.json()["id"]))
        proposals = client.get(
            "/memory-proposals",
            params={"run_id": generated.json()["id"]},
        ).json()
        assert len(proposals) == 1 and proposals[0]["project_id"] == project_a["id"]
        proposal_id = proposals[0]["id"]
        cp122_ownership.proposal_ids.add(uuid.UUID(proposal_id))
        assert (
            client.post(
                f"/memory-proposals/{proposal_id}/approve",
                json={"review_note": "CP122 explicit review"},
            ).status_code
            == 200
        )
        promoted = client.post(f"/memory-proposals/{proposal_id}/promote").json()
        cp122_ownership.memory_ids.add(uuid.UUID(promoted["memory"]["id"]))
        assert promoted["promotion_status"] == "created"
        assert promoted["memory"]["project_id"] == project_a["id"]
        with Session(get_engine()) as session:
            memory = session.get(Memory, uuid.UUID(promoted["memory"]["id"]))
            assert memory is not None
            assert {link.source_id for link in memory.source_links} == {
                uuid.UUID(source["id"])
            }
            assert (
                session.scalar(select(func.count(MemoryEmbedding.id)))
                == embedding_count_before
            )

        persisted = {
            row["id"]: (
                row["state"],
                row["revision"],
                row["project_id"],
                row["resulting_source_id"],
            )
            for row in (capture, discarded, omitted)
        }

    with TestClient(create_app(), client=("127.0.0.1", 52201)) as restarted:
        for item_id, expected in persisted.items():
            project_id = expected[2]
            state = expected[0]
            detail = restarted.post(
                f"/capture-items/{item_id}/detail", json={"scope": _scope(project_id)}
            )
            assert detail.status_code == 200
            actual = detail.json()
            assert (
                actual["state"],
                actual["revision"],
                actual["project_id"],
                actual["resulting_source_id"],
            ) == expected
            query_extra = (
                {"query": "lexical needle"} if item_id == omitted["id"] else {}
            )
            assert item_id in {
                row["id"]
                for row in _query(restarted, project_id, state, **query_extra)["items"]
            }
        reopened = restarted.post(
            f"/capture-items/{item_a['id']}/source",
            json={"scope": _scope(project_a["id"])},
        )
        assert reopened.status_code == 200 and reopened.json()["id"] == source["id"]
