"""Real-PostgreSQL evidence for Checkpoint 119 conversion and Source guards."""

import threading
import uuid
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from hashlib import sha256
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, event, func, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.agent_tools.dispatch import (
    ToolCallContext,
    ToolControlledFailure,
    dispatch_exact,
)
from app.captures import service as capture_service
from app.context_hub.models import ContextFamily, ContextHubQuery, ContextScope
from app.context_hub.service import ContextNotFoundError, query_context, reopen_context
from app.db.session import get_engine, get_session_factory
from app.extraction.dependencies import get_extraction_provider
from app.extraction.provider import (
    ChunkExtraction,
    ChunkSnapshot,
    ExtractedProposal,
    ExtractionResult,
)
from app.ingestion.text import chunk_text
from app.main import create_app
from app.models.capture_item import CaptureItem
from app.models.memory import Memory
from app.models.memory_embedding import MemoryEmbedding
from app.models.memory_proposal import MemoryProposal
from app.models.memory_source import MemorySource
from app.models.project import Project
from app.models.source import Source
from app.models.source_chunk import SourceChunk
from app.models.source_document import SourceDocument
from app.repositories import (
    memory_proposal_promotions,
    memory_proposals,
    project_exports,
)
from app.research.service import _in_scope
from app.schemas.capture import CaptureScope
from app.schemas.memory_proposal import MemoryProposalFilters
from app.sources.scope import get_source_for_scope
from tests.integration.conftest import verify_connected_test_database

pytestmark = pytest.mark.usefixtures("migrated_test_database")


@pytest.fixture(autouse=True)
def clean_conversion_rows(test_database_url: str) -> Generator[None, None, None]:
    verify_connected_test_database(test_database_url)
    with Session(get_engine()) as session:
        session.execute(delete(CaptureItem))
        session.execute(delete(SourceChunk))
        session.execute(delete(SourceDocument))
        session.execute(delete(Source).where(Source.source_type == "capture"))
        session.commit()
    yield
    verify_connected_test_database(test_database_url)
    with Session(get_engine()) as session:
        session.execute(delete(CaptureItem))
        session.execute(delete(SourceChunk))
        session.execute(delete(SourceDocument))
        session.execute(delete(Source).where(Source.source_type == "capture"))
        session.commit()


def _client() -> TestClient:
    return TestClient(create_app(), client=("127.0.0.1", 52119))


def _project() -> uuid.UUID:
    with Session(get_engine(), expire_on_commit=False) as session:
        project = Project(name=f"cp119-{uuid.uuid4()}")
        session.add(project)
        session.commit()
        return project.id


def _scope(project_id: uuid.UUID | None) -> dict[str, object]:
    return (
        {"unassigned": True} if project_id is None else {"project_id": str(project_id)}
    )


def _create(
    client: TestClient, text: str, project_id: uuid.UUID | None = None
) -> dict[str, Any]:
    body: dict[str, object] = {"content": text}
    body.update(_scope(project_id))
    response = client.post(
        "/capture-items",
        json=body,
        headers={"Idempotency-Key": f"cp119-{uuid.uuid4()}"},
    )
    assert response.status_code == 201
    return response.json()


def _convert(
    client: TestClient,
    item: dict[str, Any],
    project_id: uuid.UUID | None,
    revision: int | None = None,
) -> Any:
    return client.post(
        f"/capture-items/{item['id']}/convert-to-source",
        json={
            "scope": _scope(project_id),
            "revision": item["revision"] if revision is None else revision,
        },
    )


class EmptyProvider:
    name = "openai"
    model = "cp119-fake"
    prompt_version = "memory_proposals_v1"

    def extract(
        self,
        instructions: str,
        chunks: list[ChunkSnapshot],
        max_proposals_per_chunk: int,
    ) -> ExtractionResult:
        return ExtractionResult(
            chunks=[
                ChunkExtraction(chunk_index=chunk.chunk_index, proposals=[])
                for chunk in chunks
            ]
        )


class OneProposalProvider(EmptyProvider):
    model = "cp119-one-proposal"

    def extract(
        self,
        instructions: str,
        chunks: list[ChunkSnapshot],
        max_proposals_per_chunk: int,
    ) -> ExtractionResult:
        return ExtractionResult(
            chunks=[
                ChunkExtraction(
                    chunk_index=chunk.chunk_index,
                    proposals=[
                        ExtractedProposal(
                            title="Evidence",
                            summary=None,
                            content="PostgreSQL evidence",
                            memory_type="semantic",
                            importance=0.5,
                            confidence=0.9,
                            evidence_text="PostgreSQL",
                            evidence_start=chunk.content.index("PostgreSQL"),
                            evidence_end=chunk.content.index("PostgreSQL") + 10,
                        )
                    ],
                )
                for chunk in chunks
            ]
        )


def _seed_source(project_id: object) -> uuid.UUID:
    """Create a legacy Source, or a capture-bound Source for UUID/None scope."""
    text = "PostgreSQL evidence"
    now = datetime.now(UTC)
    with Session(get_engine(), expire_on_commit=False) as session:
        source = Source(
            source_type="note" if project_id is _LEGACY else "capture",
            name=f"cp119-source-{uuid.uuid4()}",
            checksum=sha256(text.encode()).hexdigest(),
        )
        session.add(source)
        session.flush()
        document = SourceDocument(
            source_id=source.id,
            media_type="text/plain",
            original_filename=None,
            byte_size=len(text.encode()),
            extracted_text=text,
            ingestion_status="extracted",
            extracted_at=now,
        )
        document.chunks = [
            SourceChunk(**chunk.__dict__) for chunk in chunk_text(text, 2000, 200)
        ]
        session.add(document)
        session.flush()
        if project_id is not _LEGACY:
            identity = uuid.uuid4()
            session.add(
                CaptureItem(
                    id=identity,
                    project_id=project_id,
                    content=text,
                    state="processed",
                    revision=2,
                    created_at=now,
                    updated_at=now,
                    processed_at=now,
                    resulting_source_id=source.id,
                    idempotency_key_hash=sha256(f"key:{identity}".encode()).hexdigest(),
                    request_fingerprint=sha256(
                        f"request:{identity}".encode()
                    ).hexdigest(),
                )
            )
        session.commit()
        return source.id


_LEGACY = object()


@pytest.mark.cp121_security
def test_proposal_generation_distinguishes_omitted_null_and_project_scope() -> None:
    project_id = _project()
    other_id = _project()
    legacy_id = _seed_source(_LEGACY)
    unassigned_id = _seed_source(None)
    assigned_id = _seed_source(project_id)
    app = create_app()
    app.dependency_overrides[get_extraction_provider] = EmptyProvider
    client = TestClient(app)

    def generate(source_id: uuid.UUID, body: dict[str, object]) -> int:
        response = client.post(f"/sources/{source_id}/memory-proposals", json=body)
        return response.status_code

    assert [
        generate(legacy_id, {}),
        generate(legacy_id, {"project_id": None}),
        generate(legacy_id, {"project_id": str(project_id)}),
    ] == [200, 200, 200]
    assert [
        generate(unassigned_id, {}),
        generate(unassigned_id, {"project_id": None}),
        generate(unassigned_id, {"project_id": str(project_id)}),
    ] == [404, 200, 404]
    assert [
        generate(assigned_id, {}),
        generate(assigned_id, {"project_id": None}),
        generate(assigned_id, {"project_id": str(other_id)}),
        generate(assigned_id, {"project_id": str(project_id)}),
    ] == [404, 404, 404, 200]


@pytest.mark.cp121_security
def test_proposal_read_review_and_promotion_fail_after_binding_scope_mismatch() -> None:
    project_id, wrong_id = _project(), _project()
    source_id = _seed_source(project_id)
    app = create_app()
    app.dependency_overrides[get_extraction_provider] = OneProposalProvider
    client = TestClient(app)
    generated = client.post(
        f"/sources/{source_id}/memory-proposals",
        json={"project_id": str(project_id)},
    )
    assert generated.status_code == 200 and generated.json()["proposal_count"] == 1
    with Session(get_engine()) as session:
        proposal = memory_proposals.list_proposals(
            session, MemoryProposalFilters(project_id=project_id)
        )[0]
        proposal_id = proposal.id
        capture = session.scalar(
            select(CaptureItem).where(CaptureItem.resulting_source_id == source_id)
        )
        assert capture is not None
        capture.project_id = wrong_id
        session.commit()

    with Session(get_engine()) as session:
        assert memory_proposals.get_proposal(session, proposal_id) is None
        assert (
            memory_proposals.list_proposals(
                session, MemoryProposalFilters(project_id=project_id)
            )
            == []
        )
        with pytest.raises(memory_proposals.ProposalNotFoundError):
            memory_proposals.review_proposal(session, proposal_id, "approved", None)
        with pytest.raises(memory_proposal_promotions.ProposalNotFoundError):
            memory_proposal_promotions.promote_proposal(session, proposal_id)


@pytest.mark.parametrize("assigned", [False, True])
@pytest.mark.cp121_security
def test_conversion_persists_exact_text_metadata_chunks_and_capture(
    assigned: bool,
) -> None:
    client = _client()
    project_id = _project() if assigned else None
    text = "A" * 1999 + "\r\n" + "B" * 2201
    item = _create(client, text, project_id)
    response = _convert(client, item, project_id)
    assert response.status_code == 200
    payload = response.json()
    source_id = uuid.UUID(payload["source"]["id"])
    capture = payload["capture"]
    assert payload["source"]["source_type"] == "capture"
    assert payload["source"]["name"] == f"Capture {item['id']}"
    assert item["content"] not in payload["source"]["name"]
    assert len(payload["source"]["name"]) <= 255
    assert payload["source"]["reference"] is None
    assert (
        payload["source"]["checksum"]
        == sha256(item["content"].encode("utf-8")).hexdigest()
    )
    assert capture["state"] == "processed"
    assert capture["revision"] == item["revision"] + 1
    assert capture["processed_at"] is not None
    assert capture["updated_at"] > item["updated_at"]
    assert capture["resulting_source_id"] == str(source_id)

    expected = chunk_text(item["content"], 2000, 200)
    with Session(get_engine()) as session:
        stored = session.get(CaptureItem, uuid.UUID(item["id"]))
        documents = session.scalars(
            select(SourceDocument).where(SourceDocument.source_id == source_id)
        ).all()
        assert stored is not None and stored.resulting_source_id == source_id
        assert len(documents) == 1
        document = documents[0]
        assert document.extracted_text == item["content"]
        assert document.media_type == "text/plain"
        assert document.original_filename is None
        chunks = session.scalars(
            select(SourceChunk)
            .where(SourceChunk.document_id == document.id)
            .order_by(SourceChunk.chunk_index)
        ).all()
        assert [
            (
                row.chunk_index,
                row.content,
                row.char_start,
                row.char_end,
                row.content_hash,
            )
            for row in chunks
        ] == [
            (
                row.chunk_index,
                row.content,
                row.char_start,
                row.char_end,
                row.content_hash,
            )
            for row in expected
        ]


@pytest.mark.cp121_security
def test_conversion_scope_state_identity_and_stale_fail_without_writes() -> None:
    client = _client()
    project_id, other_id = _project(), _project()
    assigned = _create(client, "assigned", project_id)
    unassigned = _create(client, "unassigned")
    discarded = _create(client, "discarded")
    assert (
        client.post(
            f"/capture-items/{discarded['id']}/discard",
            json={"scope": _scope(None), "revision": discarded["revision"]},
        ).status_code
        == 200
    )
    attempts = (
        _convert(client, assigned, other_id),
        _convert(client, assigned, None),
        _convert(client, unassigned, project_id),
        _convert(client, assigned, project_id, 99),
        _convert(client, discarded, None),
        client.post(
            f"/capture-items/{uuid.uuid4()}/convert-to-source",
            json={"scope": _scope(None), "revision": 1},
        ),
    )
    assert [value.status_code for value in attempts] == [404, 404, 404, 409, 409, 404]
    with Session(get_engine()) as session:
        assert (
            session.scalar(
                select(func.count(Source.id)).where(Source.source_type == "capture")
            )
            == 0
        )
        rows = session.scalars(
            select(CaptureItem).where(
                CaptureItem.id.in_(
                    [
                        uuid.UUID(assigned["id"]),
                        uuid.UUID(unassigned["id"]),
                        uuid.UUID(discarded["id"]),
                    ]
                )
            )
        ).all()
        assert sorted((row.state, row.revision) for row in rows) == [
            ("discarded", 2),
            ("pending", 1),
            ("pending", 1),
        ]


@pytest.mark.parametrize("assigned", [False, True])
@pytest.mark.cp121_security
def test_processed_replay_accepts_only_original_and_current_revision(
    assigned: bool,
) -> None:
    client = _client()
    project_id = _project() if assigned else None
    item = _create(client, "replay text", project_id)
    first = _convert(client, item, project_id)
    assert first.status_code == 200
    capture = first.json()["capture"]
    source_id = first.json()["source"]["id"]
    with Session(get_engine()) as session:
        before = (
            session.get(CaptureItem, uuid.UUID(item["id"])).updated_at,
            session.scalar(select(func.count(Source.id))),
            session.scalar(select(func.count(SourceDocument.id))),
            session.scalar(select(func.count(SourceChunk.id))),
        )
    for revision in (item["revision"], capture["revision"]):
        replay = _convert(client, item, project_id, revision)
        assert replay.status_code == 200
        assert replay.json()["source"]["id"] == source_id
        assert replay.json()["capture"] == capture
    stale = _convert(client, item, project_id, capture["revision"] + 1)
    assert stale.status_code == 409
    with Session(get_engine()) as session:
        after = (
            session.get(CaptureItem, uuid.UUID(item["id"])).updated_at,
            session.scalar(select(func.count(Source.id))),
            session.scalar(select(func.count(SourceDocument.id))),
            session.scalar(select(func.count(SourceChunk.id))),
        )
    assert after == before


@pytest.mark.parametrize("assigned", [False, True])
@pytest.mark.cp121_security
def test_source_resolver_is_scoped_safe_and_read_only(assigned: bool) -> None:
    client = _client()
    project_id = _project() if assigned else None
    item = _create(client, "resolver", project_id)
    converted = _convert(client, item, project_id).json()
    before = converted["capture"]
    resolved = client.post(
        f"/capture-items/{item['id']}/source", json={"scope": _scope(project_id)}
    )
    assert resolved.status_code == 200
    assert resolved.json() == converted["source"]
    wrong_scope = None if assigned else _project()
    assert (
        client.post(
            f"/capture-items/{item['id']}/source", json={"scope": _scope(wrong_scope)}
        ).status_code
        == 404
    )
    detail = client.post(
        f"/capture-items/{item['id']}/detail", json={"scope": _scope(project_id)}
    )
    assert detail.json() == before


@pytest.mark.cp121_security
def test_source_resolver_rejects_pending_discarded_missing_and_broken_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client()
    pending = _create(client, "pending")
    discarded = _create(client, "discarded")
    client.post(
        f"/capture-items/{discarded['id']}/discard",
        json={"scope": _scope(None), "revision": 1},
    )
    for item in (pending, discarded):
        assert (
            client.post(
                f"/capture-items/{item['id']}/source", json={"scope": _scope(None)}
            ).status_code
            == 409
        )
    assert (
        client.post(
            f"/capture-items/{uuid.uuid4()}/source", json={"scope": _scope(None)}
        ).status_code
        == 404
    )
    converted = _convert(client, pending, None).json()
    source_id = uuid.UUID(converted["source"]["id"])
    with Session(get_engine()) as session:
        before = session.get(CaptureItem, uuid.UUID(pending["id"]))
        assert before is not None
        capture_snapshot = (
            before.id,
            before.project_id,
            before.content,
            before.state,
            before.revision,
            before.created_at,
            before.updated_at,
            before.processed_at,
            before.resulting_source_id,
            before.idempotency_key_hash,
            before.request_fingerprint,
            before.search_vector,
        )
        source = session.get(Source, source_id)
        assert source is not None
        source_snapshot = (
            source.id,
            source.source_type,
            source.name,
            source.reference,
            source.checksum,
            source.created_at,
            source.updated_at,
        )
        document = session.scalar(
            select(SourceDocument).where(SourceDocument.source_id == source_id)
        )
        assert document is not None
        document_snapshot = (
            document.id,
            document.source_id,
            document.media_type,
            document.original_filename,
            document.byte_size,
            document.extracted_text,
            document.ingestion_status,
            document.error_code,
            document.extracted_at,
            document.created_at,
            document.updated_at,
        )
        chunk_snapshots = [
            (
                chunk.id,
                chunk.document_id,
                chunk.chunk_index,
                chunk.content,
                chunk.char_start,
                chunk.char_end,
                chunk.content_hash,
                chunk.locator,
                chunk.created_at,
            )
            for chunk in session.scalars(
                select(SourceChunk)
                .where(SourceChunk.document_id == document.id)
                .order_by(SourceChunk.chunk_index, SourceChunk.id)
            ).all()
        ]
        graph_counts = (
            session.scalar(select(func.count(CaptureItem.id))),
            session.scalar(select(func.count(Source.id))),
            session.scalar(select(func.count(SourceDocument.id))),
            session.scalar(select(func.count(SourceChunk.id))),
        )

    monkeypatch.setattr(capture_service, "get_source_for_scope", lambda *_: None)
    inconsistent = client.post(
        f"/capture-items/{pending['id']}/source", json={"scope": _scope(None)}
    )
    assert inconsistent.status_code == 404
    with Session(get_engine()) as session:
        after = session.get(CaptureItem, uuid.UUID(pending["id"]))
        assert after is not None
        assert (
            after.id,
            after.project_id,
            after.content,
            after.state,
            after.revision,
            after.created_at,
            after.updated_at,
            after.processed_at,
            after.resulting_source_id,
            after.idempotency_key_hash,
            after.request_fingerprint,
            after.search_vector,
        ) == capture_snapshot
        source = session.get(Source, source_id)
        assert source is not None
        assert (
            source.id,
            source.source_type,
            source.name,
            source.reference,
            source.checksum,
            source.created_at,
            source.updated_at,
        ) == source_snapshot
        document = session.scalar(
            select(SourceDocument).where(SourceDocument.source_id == source_id)
        )
        assert document is not None
        assert (
            document.id,
            document.source_id,
            document.media_type,
            document.original_filename,
            document.byte_size,
            document.extracted_text,
            document.ingestion_status,
            document.error_code,
            document.extracted_at,
            document.created_at,
            document.updated_at,
        ) == document_snapshot
        assert [
            (
                chunk.id,
                chunk.document_id,
                chunk.chunk_index,
                chunk.content,
                chunk.char_start,
                chunk.char_end,
                chunk.content_hash,
                chunk.locator,
                chunk.created_at,
            )
            for chunk in session.scalars(
                select(SourceChunk)
                .where(SourceChunk.document_id == document.id)
                .order_by(SourceChunk.chunk_index, SourceChunk.id)
            ).all()
        ] == chunk_snapshots
        assert (
            session.scalar(select(func.count(CaptureItem.id))),
            session.scalar(select(func.count(Source.id))),
            session.scalar(select(func.count(SourceDocument.id))),
            session.scalar(select(func.count(SourceChunk.id))),
        ) == graph_counts


@pytest.mark.cp121_security
def test_unscoped_source_document_ingestion_and_link_boundaries_fail_closed() -> None:
    client = _client()
    project_id, wrong_id = _project(), _project()
    item = _create(client, "guarded source text", project_id)
    converted = _convert(client, item, project_id).json()
    source_id = converted["source"]["id"]
    with Session(get_engine(), expire_on_commit=False) as session:
        document = session.scalar(
            select(SourceDocument).where(
                SourceDocument.source_id == uuid.UUID(source_id)
            )
        )
        assert document is not None
        chunk = session.scalar(
            select(SourceChunk).where(SourceChunk.document_id == document.id)
        )
        assert chunk is not None
        matching_memory = Memory(content="matching", project_id=project_id)
        wrong_memory = Memory(content="wrong", project_id=wrong_id)
        session.add_all([matching_memory, wrong_memory])
        legacy_capture_type = Source(
            source_type="capture", name=f"imported-capture-{uuid.uuid4()}"
        )
        session.add(legacy_capture_type)
        session.commit()

    listed = client.get("/sources").json()
    assert source_id not in {row["id"] for row in listed}
    assert client.get(f"/sources/{source_id}").status_code == 404
    assert client.get(f"/sources/{source_id}/documents").status_code == 404
    assert client.get(f"/source-documents/{document.id}").status_code == 404
    assert client.get(f"/source-documents/{document.id}/chunks").status_code == 404
    assert (
        client.put(
            f"/sources/{source_id}/document/text", json={"text": "overwrite"}
        ).status_code
        == 404
    )
    assert (
        client.put(
            f"/sources/{source_id}/document/file",
            files={"file": ("a.txt", b"overwrite", "text/plain")},
        ).status_code
        == 404
    )
    assert client.get(f"/sources/{source_id}/memories").status_code == 404
    assert (
        client.post(
            f"/memories/{wrong_memory.id}/sources", json={"source_id": source_id}
        ).status_code
        == 404
    )
    linked = client.post(
        f"/memories/{matching_memory.id}/sources", json={"source_id": source_id}
    )
    assert linked.status_code == 201
    matching_sources = client.get(f"/memories/{matching_memory.id}/sources")
    assert matching_sources.status_code == 200
    assert [row["source_id"] for row in matching_sources.json()] == [source_id]
    legacy = client.get(f"/sources/{legacy_capture_type.id}")
    assert legacy.status_code == 200


@pytest.mark.cp121_security
def test_tools_hub_research_and_export_use_their_authoritative_project_scope() -> None:
    client = _client()
    project_id, wrong_id = _project(), _project()
    item = _create(client, "federated capture evidence", project_id)
    converted = _convert(client, item, project_id).json()
    source_id = uuid.UUID(converted["source"]["id"])
    with Session(get_engine()) as session:
        document = session.scalar(
            select(SourceDocument).where(SourceDocument.source_id == source_id)
        )
        assert document is not None
        chunk = session.scalar(
            select(SourceChunk).where(SourceChunk.document_id == document.id)
        )
        assert chunk is not None
        memory = Memory(content="reviewed linkage", project_id=project_id)
        session.add(memory)
        session.flush()
        session.add(MemorySource(memory_id=memory.id, source_id=source_id))
        session.commit()

        source_output = dispatch_exact(
            name="source.get",
            version=1,
            normalized_input={"source_id": source_id},
            context=ToolCallContext(session, project_id),
        )
        assert source_output.id == source_id  # type: ignore[attr-defined]
        chunk_output = dispatch_exact(
            name="source_chunk.get",
            version=1,
            normalized_input={"source_chunk_id": chunk.id},
            context=ToolCallContext(session, project_id),
        )
        assert chunk_output.id == chunk.id  # type: ignore[attr-defined]
        for name, key, value in (
            ("source.get", "source_id", source_id),
            ("source_chunk.get", "source_chunk_id", chunk.id),
        ):
            with pytest.raises(ToolControlledFailure):
                dispatch_exact(
                    name=name,
                    version=1,
                    normalized_input={key: value},
                    context=ToolCallContext(session, wrong_id),
                )

        request = ContextHubQuery(
            scope=ContextScope(project_id=project_id),
            families=(ContextFamily.LOCAL_SOURCE,),
        )
        result = query_context(session, request)
        local_items = result.groups[0].items
        assert len(local_items) == 1
        reopened = reopen_context(session, request.scope, local_items[0].provenance)
        assert reopened.provenance == local_items[0].provenance
        wrong_scope = ContextScope(project_id=wrong_id)
        assert (
            query_context(
                session,
                request.model_copy(update={"scope": wrong_scope}),
            )
            .groups[0]
            .items
            == ()
        )
        with pytest.raises(ContextNotFoundError):
            reopen_context(session, wrong_scope, local_items[0].provenance)

        run = SimpleNamespace(project_id=project_id)
        wrong_run = SimpleNamespace(project_id=wrong_id)
        assert _in_scope(session, run, "source", source_id)  # type: ignore[arg-type]
        assert _in_scope(session, run, "source_chunk", chunk.id)  # type: ignore[arg-type]
        assert not _in_scope(session, wrong_run, "source", source_id)  # type: ignore[arg-type]
        assert not _in_scope(  # type: ignore[arg-type]
            session, wrong_run, "source_chunk", chunk.id
        )

        assert [row.id for row in project_exports.sources(session, project_id)] == [
            source_id
        ]
        assert list(project_exports.sources(session, wrong_id)) == []


@pytest.mark.cp121_security
def test_concurrent_conversion_serializes_to_one_graph(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client()
    item = _create(client, "X" * 4100)
    barrier = threading.Barrier(2)
    worker_context = threading.local()
    ingestion_workers: list[int] = []
    locked_observations: dict[int, tuple[str, int]] = {}
    real_create = capture_service.source_repository.create_source
    real_get_scoped_capture = capture_service.repository.get_scoped_capture

    def observed_locked_capture(*args: Any, **kwargs: Any) -> CaptureItem | None:
        capture = real_get_scoped_capture(*args, **kwargs)
        if kwargs.get("lock") and capture is not None:
            locked_observations[worker_context.identity] = (
                capture.state,
                capture.revision,
            )
        return capture

    def observed_create(*args: Any, **kwargs: Any) -> Source:
        ingestion_workers.append(worker_context.identity)
        return real_create(*args, **kwargs)

    monkeypatch.setattr(
        capture_service.source_repository, "create_source", observed_create
    )
    monkeypatch.setattr(
        capture_service.repository, "get_scoped_capture", observed_locked_capture
    )

    def worker(identity: int) -> dict[str, object]:
        worker_context.identity = identity
        with get_session_factory()() as session:
            connection = session.connection()
            physical = connection.connection.dbapi_connection
            session_id = id(session)
            connection_id = id(physical)
            barrier.wait(timeout=10)
            result = capture_service.convert_capture(
                session,
                uuid.UUID(item["id"]),
                CaptureScope(unassigned=True),
                item["revision"],
            )
            source_id = result.source.id
            projection = result.item
            session.commit()
            return {
                "worker": identity,
                "session_id": session_id,
                "connection_id": connection_id,
                "observed_state": locked_observations[identity][0],
                "observed_revision": locked_observations[identity][1],
                "entered_ingestion": identity in ingestion_workers,
                "source_id": source_id,
                "revision": projection.revision,
                "state": projection.state,
            }

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(worker, range(2)))
    assert len({result["session_id"] for result in results}) == 2
    assert len({result["connection_id"] for result in results}) == 2
    assert len(ingestion_workers) == 1
    pending_observers = [
        result for result in results if result["observed_state"] == "pending"
    ]
    processed_observers = [
        result for result in results if result["observed_state"] == "processed"
    ]
    assert len(pending_observers) == len(processed_observers) == 1
    creator = pending_observers[0]
    replay = processed_observers[0]
    assert creator["observed_revision"] == item["revision"]
    assert replay["observed_revision"] == item["revision"] + 1
    assert creator["worker"] == ingestion_workers[0]
    assert creator["entered_ingestion"] is True
    assert replay["entered_ingestion"] is False
    assert creator["worker"] != replay["worker"]
    assert creator["revision"] == replay["revision"] == 2
    assert creator["state"] == replay["state"] == "processed"
    ids = {result["source_id"] for result in results}
    assert len(ids) == 1
    source_id = ids.pop()
    assert isinstance(source_id, uuid.UUID)
    assert creator["source_id"] == replay["source_id"] == source_id
    with Session(get_engine()) as session:
        capture = session.get(CaptureItem, uuid.UUID(item["id"]))
        documents = session.scalars(
            select(SourceDocument).where(SourceDocument.source_id == source_id)
        ).all()
        assert capture is not None and capture.state == "processed"
        assert capture.revision == item["revision"] + 1
        assert capture.resulting_source_id == source_id
        assert capture.resulting_source_id == creator["source_id"]
        assert (
            session.scalar(
                select(func.count(Source.id)).where(Source.source_type == "capture")
            )
            == 1
        )
        assert len(documents) == 1
        document = documents[0]
        assert session.scalar(
            select(func.count(SourceChunk.id)).where(
                SourceChunk.document_id == document.id
            )
        ) == len(chunk_text(item["content"], 2000, 200))


@pytest.mark.cp121_security
def test_cap16_reassignment_conversion_race_freezes_one_complete_scope() -> None:
    from app.captures.service import (
        CaptureNotFoundError,
        CaptureRevisionConflictError,
        convert_capture,
        reassign_capture,
    )

    project_a, project_b = _project(), _project()
    client = _client()
    item = _create(client, "race frozen scope", project_a)
    barrier = threading.Barrier(2)

    def move() -> str:
        with get_session_factory()() as session:
            barrier.wait(timeout=10)
            try:
                reassign_capture(
                    session,
                    uuid.UUID(item["id"]),
                    CaptureScope(project_id=project_a),
                    CaptureScope(project_id=project_b),
                    1,
                )
                session.commit()
                return "moved"
            except (CaptureNotFoundError, CaptureRevisionConflictError):
                session.rollback()
                return "lost"

    def convert() -> str:
        with get_session_factory()() as session:
            barrier.wait(timeout=10)
            try:
                convert_capture(
                    session,
                    uuid.UUID(item["id"]),
                    CaptureScope(project_id=project_a),
                    1,
                )
                session.commit()
                return "converted"
            except (CaptureNotFoundError, CaptureRevisionConflictError):
                session.rollback()
                return "lost"

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(move), pool.submit(convert)]
        results = [future.result() for future in futures]
    assert results.count("lost") == 1
    with Session(get_engine()) as session:
        capture = session.get(CaptureItem, uuid.UUID(item["id"]))
        assert capture is not None and capture.revision == 2
        assert capture.project_id in {project_a, project_b}
        if "converted" in results:
            assert capture.state == "processed" and capture.project_id == project_a
            assert capture.resulting_source_id is not None
            assert get_source_for_scope(session, capture.resulting_source_id, project_a)
            assert (
                get_source_for_scope(session, capture.resulting_source_id, project_b)
                is None
            )
        else:
            assert capture.state == "pending" and capture.project_id == project_b
            assert capture.resulting_source_id is None


@pytest.mark.cp121_security
def test_cap16_conversion_win_closes_old_new_visibility_and_downstream_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.captures.service import (
        CaptureNotFoundError,
        CaptureRevisionConflictError,
        convert_capture,
        reassign_capture,
    )

    project_a, project_b = _project(), _project()
    item = _create(_client(), "deterministic frozen path", project_a)
    conversion_locked = threading.Event()
    reassignment_entered = threading.Event()
    real_get = capture_service.repository.get_scoped_capture
    worker_context = threading.local()

    def hold_conversion_lock(*args: Any, **kwargs: Any) -> CaptureItem | None:
        capture = real_get(*args, **kwargs)
        if getattr(worker_context, "operation", None) == "convert" and kwargs.get(
            "lock"
        ):
            conversion_locked.set()
            assert reassignment_entered.wait(timeout=10)
        return capture

    monkeypatch.setattr(
        capture_service.repository, "get_scoped_capture", hold_conversion_lock
    )

    def convert_worker() -> str:
        worker_context.operation = "convert"
        with get_session_factory()() as session:
            convert_capture(
                session,
                uuid.UUID(item["id"]),
                CaptureScope(project_id=project_a),
                1,
            )
            session.commit()
        return "converted"

    def reassign_worker() -> str:
        assert conversion_locked.wait(timeout=10)
        worker_context.operation = "reassign"
        with get_session_factory()() as session:
            reassignment_entered.set()
            try:
                reassign_capture(
                    session,
                    uuid.UUID(item["id"]),
                    CaptureScope(project_id=project_a),
                    CaptureScope(project_id=project_b),
                    1,
                )
                session.commit()
                return "moved"
            except (CaptureNotFoundError, CaptureRevisionConflictError):
                session.rollback()
                return "lost"

    with ThreadPoolExecutor(max_workers=2) as pool:
        converted = pool.submit(convert_worker)
        reassigned = pool.submit(reassign_worker)
        assert converted.result() == "converted"
        assert reassigned.result() == "lost"

    client = _client()
    old_scope = _scope(project_a)
    new_scope = _scope(project_b)
    detail = client.post(
        f"/capture-items/{item['id']}/detail", json={"scope": old_scope}
    )
    assert detail.status_code == 200
    assert detail.json()["state"] == "processed"
    source_id = uuid.UUID(detail.json()["resulting_source_id"])
    assert (
        client.post(
            f"/capture-items/{item['id']}/detail", json={"scope": new_scope}
        ).status_code
        == 404
    )
    old_query = client.post(
        "/capture-items/query", json={"scope": old_scope, "states": ["processed"]}
    )
    new_query = client.post(
        "/capture-items/query", json={"scope": new_scope, "states": ["processed"]}
    )
    assert [row["id"] for row in old_query.json()["items"]] == [item["id"]]
    assert new_query.json()["items"] == []
    for method, path, payload, expected in (
        ("patch", "", {"content": "secondary"}, 409),
        ("post", "/discard", {}, 409),
    ):
        assert (
            getattr(client, method)(
                f"/capture-items/{item['id']}{path}",
                json={"scope": old_scope, "revision": 2, **payload},
            ).status_code
            == expected
        )
        assert (
            getattr(client, method)(
                f"/capture-items/{item['id']}{path}",
                json={"scope": new_scope, "revision": 2, **payload},
            ).status_code
            == 404
        )
    assert (
        client.post(
            f"/capture-items/{item['id']}/source", json={"scope": old_scope}
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/capture-items/{item['id']}/source", json={"scope": new_scope}
        ).status_code
        == 404
    )

    with Session(get_engine()) as session:
        document = session.scalar(
            select(SourceDocument).where(SourceDocument.source_id == source_id)
        )
        assert document is not None
        chunks = session.scalars(
            select(SourceChunk).where(SourceChunk.document_id == document.id)
        ).all()
        assert chunks
        memory = Memory(content="explicit downstream link", project_id=project_a)
        session.add(memory)
        session.flush()
        session.add(MemorySource(memory_id=memory.id, source_id=source_id))
        session.commit()
        request = ContextHubQuery(
            scope=ContextScope(project_id=project_a),
            families=(ContextFamily.LOCAL_SOURCE,),
            query="deterministic frozen path",
        )
        local_items = query_context(session, request).groups[0].items
        assert local_items
        assert {row.provenance.document_id for row in local_items} == {document.id}
        assert {row.provenance.chunk_id for row in local_items}.issubset(
            {chunk.id for chunk in chunks}
        )
        for row in local_items:
            assert (
                reopen_context(session, request.scope, row.provenance).text == row.text
            )
            with pytest.raises(ContextNotFoundError):
                reopen_context(
                    session, ContextScope(project_id=project_b), row.provenance
                )
        with pytest.raises(IntegrityError):
            session.execute(delete(Project).where(Project.id == project_a))
            session.commit()
        session.rollback()
        persisted = session.get(CaptureItem, uuid.UUID(item["id"]))
        assert persisted is not None
        assert persisted.project_id == project_a
        assert persisted.resulting_source_id == source_id


@pytest.mark.cp121_security
def test_cap18_equal_content_has_distinct_stable_write_once_provenance() -> None:
    with Session(get_engine()) as session:
        protected_before = (
            session.scalar(select(func.count(Memory.id))),
            session.scalar(select(func.count(MemoryProposal.id))),
            session.scalar(select(func.count(MemoryEmbedding.id))),
        )
    client = _client()
    project_id, wrong_id = _project(), _project()
    content = "equal provenance content " + "x" * 2200
    first = _create(client, content, project_id)
    second = _create(client, content, project_id)
    first_result = _convert(client, first, project_id).json()
    second_result = _convert(client, second, project_id).json()
    assert first["id"] != second["id"]
    assert first_result["source"]["id"] != second_result["source"]["id"]
    first_time = first_result["capture"]["processed_at"]
    replay = _convert(client, first, project_id).json()
    assert replay["source"]["id"] == first_result["source"]["id"]
    assert replay["capture"]["processed_at"] == first_time
    with Session(get_engine()) as session:
        captures = session.scalars(
            select(CaptureItem).where(
                CaptureItem.id.in_((uuid.UUID(first["id"]), uuid.UUID(second["id"])))
            )
        ).all()
        assert len(captures) == 2
        assert len({row.resulting_source_id for row in captures}) == 2
        for row in captures:
            assert row.state == "processed" and row.project_id == project_id
            document = session.scalar(
                select(SourceDocument).where(
                    SourceDocument.source_id == row.resulting_source_id
                )
            )
            assert document is not None and document.extracted_text == content
            chunks = session.scalars(
                select(SourceChunk)
                .where(SourceChunk.document_id == document.id)
                .order_by(SourceChunk.chunk_index)
            ).all()
            assert [chunk.content for chunk in chunks] == [
                chunk.content for chunk in chunk_text(content, 2000, 200)
            ]
        assert (
            session.scalar(select(func.count(Memory.id))),
            session.scalar(select(func.count(MemoryProposal.id))),
            session.scalar(select(func.count(MemoryEmbedding.id))),
        ) == protected_before

        for source_id in (
            uuid.UUID(first_result["source"]["id"]),
            uuid.UUID(second_result["source"]["id"]),
        ):
            memory = Memory(content="explicit lifecycle link", project_id=project_id)
            session.add(memory)
            session.flush()
            session.add(MemorySource(memory_id=memory.id, source_id=source_id))
        session.commit()

        request = ContextHubQuery(
            scope=ContextScope(project_id=project_id),
            families=(ContextFamily.LOCAL_SOURCE,),
            query="equal provenance content",
        )
        local_items = query_context(session, request).groups[0].items
        expected_source_ids = {
            uuid.UUID(first_result["source"]["id"]),
            uuid.UUID(second_result["source"]["id"]),
        }
        assert {
            item.provenance.source_id for item in local_items
        } == expected_source_ids
        for item in local_items:
            reopened = reopen_context(session, request.scope, item.provenance)
            assert reopened.provenance == item.provenance
            assert reopened.text == item.text
            with pytest.raises(ContextNotFoundError):
                reopen_context(
                    session, ContextScope(project_id=wrong_id), item.provenance
                )

    resolved = client.post(
        f"/capture-items/{first['id']}/source",
        json={"scope": _scope(project_id)},
    )
    assert resolved.status_code == 200
    assert resolved.json()["id"] == first_result["source"]["id"]
    assert (
        client.post(
            f"/capture-items/{first['id']}/source",
            json={"scope": _scope(wrong_id)},
        ).status_code
        == 404
    )


@pytest.mark.cp121_security
def test_failure_after_document_sql_rolls_back_entire_conversion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client()
    item = _create(client, "rollback text")
    original_updated_at = item["updated_at"]
    real_ingest = capture_service.source_repository.upsert_text_document

    def fail_after_sql(*args: Any, **kwargs: Any) -> Any:
        real_ingest(*args, **kwargs)
        raise OperationalError("controlled", {}, Exception("controlled"))

    monkeypatch.setattr(
        capture_service.source_repository, "upsert_text_document", fail_after_sql
    )
    response = _convert(client, item, None)
    assert response.status_code == 503
    with Session(get_engine()) as session:
        capture = session.get(CaptureItem, uuid.UUID(item["id"]))
        assert capture is not None
        assert capture.state == "pending" and capture.revision == 1
        assert capture.resulting_source_id is None and capture.processed_at is None
        assert capture.updated_at == datetime.fromisoformat(
            original_updated_at.replace("Z", "+00:00")
        )
        assert (
            session.scalar(
                select(func.count(Source.id)).where(Source.source_type == "capture")
            )
            == 0
        )
        assert session.scalar(select(func.count(SourceDocument.id))) == 0
        assert session.scalar(select(func.count(SourceChunk.id))) == 0


@pytest.mark.parametrize("stage", ["source", "document", "final_flush", "commit"])
@pytest.mark.cp121_security
def test_cap05_fault_boundaries_rollback_and_clean_retry_once(stage: str) -> None:
    client = _client()
    item = _create(client, f"atomic fault {stage} " + "x" * 2500)
    with pytest.MonkeyPatch.context() as patch:
        if stage == "source":
            real = capture_service.source_repository.create_source

            def fail_source(*args: Any, **kwargs: Any) -> Any:
                real(*args, **kwargs)
                raise OperationalError("controlled", {}, Exception("controlled"))

            patch.setattr(
                capture_service.source_repository, "create_source", fail_source
            )
        elif stage == "document":
            real = capture_service.source_repository.upsert_text_document

            def fail_document(*args: Any, **kwargs: Any) -> Any:
                real(*args, **kwargs)
                raise OperationalError("controlled", {}, Exception("controlled"))

            patch.setattr(
                capture_service.source_repository,
                "upsert_text_document",
                fail_document,
            )
        elif stage == "final_flush":
            real_flush = Session.flush

            def fail_final_flush(session: Session, *args: Any, **kwargs: Any) -> Any:
                if any(
                    isinstance(row, CaptureItem) and row.state == "processed"
                    for row in session.dirty
                ):
                    raise OperationalError("controlled", {}, Exception("controlled"))
                return real_flush(session, *args, **kwargs)

            patch.setattr(Session, "flush", fail_final_flush)
        else:
            real_commit = Session.commit
            commit_calls = 0

            def fail_commit(session: Session) -> Any:
                nonlocal commit_calls
                commit_calls += 1
                if commit_calls == 1:
                    raise OperationalError("controlled", {}, Exception("controlled"))
                return real_commit(session)

            patch.setattr(Session, "commit", fail_commit)
        failed = _convert(client, item, None)
        assert failed.status_code == 503
    with Session(get_engine()) as session:
        capture = session.get(CaptureItem, uuid.UUID(item["id"]))
        assert capture is not None and capture.state == "pending"
        assert capture.revision == 1 and capture.resulting_source_id is None
        assert (
            session.scalar(
                select(func.count(Source.id)).where(Source.source_type == "capture")
            )
            == 0
        )
        assert session.scalar(select(func.count(SourceDocument.id))) == 0
        assert session.scalar(select(func.count(SourceChunk.id))) == 0
    retried = _convert(client, item, None)
    assert retried.status_code == 200
    source_id = uuid.UUID(retried.json()["source"]["id"])
    with Session(get_engine()) as session:
        capture = session.get(CaptureItem, uuid.UUID(item["id"]))
        documents = session.scalars(
            select(SourceDocument).where(SourceDocument.source_id == source_id)
        ).all()
        assert capture is not None and capture.resulting_source_id == source_id
        assert capture.state == "processed" and capture.revision == 2
        assert len(documents) == 1
        chunks = session.scalars(
            select(SourceChunk)
            .where(SourceChunk.document_id == documents[0].id)
            .order_by(SourceChunk.chunk_index)
        ).all()
        expected_chunks = chunk_text(str(item["content"]), 2000, 200)
        assert [(row.chunk_index, row.content) for row in chunks] == [
            (row.chunk_index, row.content) for row in expected_chunks
        ]
        graph_snapshot = (
            capture.resulting_source_id,
            documents[0].id,
            tuple((row.id, row.content_hash) for row in chunks),
        )
    replay = _convert(client, item, None)
    assert replay.status_code == 200
    assert replay.json()["source"]["id"] == retried.json()["source"]["id"]
    with Session(get_engine()) as session:
        assert (
            session.scalar(
                select(func.count(Source.id)).where(Source.source_type == "capture")
            )
            == 1
        )
        documents = session.scalars(
            select(SourceDocument).where(SourceDocument.source_id == source_id)
        ).all()
        assert len(documents) == 1
        chunks = session.scalars(
            select(SourceChunk)
            .where(SourceChunk.document_id == documents[0].id)
            .order_by(SourceChunk.chunk_index)
        ).all()
        capture = session.get(CaptureItem, uuid.UUID(item["id"]))
        assert capture is not None
        assert (
            capture.resulting_source_id,
            documents[0].id,
            tuple((row.id, row.content_hash) for row in chunks),
        ) == graph_snapshot


@pytest.mark.parametrize(
    ("assigned", "operation", "expected"),
    [
        (False, "convert", 7),
        (True, "convert", 8),
        (False, "replay_original", 2),
        (True, "replay_original", 3),
        (False, "replay_current", 2),
        (True, "replay_current", 3),
        (False, "resolve", 2),
        (True, "resolve", 3),
    ],
)
@pytest.mark.cp121_security
def test_cp119_statement_ceilings(
    assigned: bool, operation: str, expected: int
) -> None:
    client = _client()
    project_id = _project() if assigned else None
    item = _create(client, f"statement count {operation}", project_id)
    converted: dict[str, Any] | None = None
    if operation != "convert":
        converted = _convert(client, item, project_id).json()
    statements: list[str] = []

    def count_statement(*args: Any) -> None:
        statement = str(args[2]).lstrip().upper()
        if not statement.startswith(("BEGIN", "COMMIT", "ROLLBACK")):
            statements.append(statement)

    event.listen(get_engine(), "before_cursor_execute", count_statement)
    try:
        if operation == "convert":
            response = _convert(client, item, project_id)
        elif operation == "resolve":
            response = client.post(
                f"/capture-items/{item['id']}/source",
                json={"scope": _scope(project_id)},
            )
        else:
            assert converted is not None
            revision = (
                item["revision"]
                if operation == "replay_original"
                else converted["capture"]["revision"]
            )
            response = _convert(client, item, project_id, revision)
    finally:
        event.remove(get_engine(), "before_cursor_execute", count_statement)
    assert response.status_code == 200
    assert len(statements) == expected
    assert len(statements) <= (3 if operation == "resolve" else 10)
