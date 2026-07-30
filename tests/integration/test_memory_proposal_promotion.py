"""PostgreSQL coverage for explicit, concurrent proposal promotion."""

import uuid
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_engine
from app.main import create_app
from app.models import (
    Memory,
    MemoryEmbedding,
    MemoryExtractionRun,
    MemoryProposal,
    MemorySource,
    Source,
    SourceChunk,
    SourceDocument,
)
from tests.integration.conftest import verify_connected_test_database

PREFIX = "proposal-promotion-"


@pytest.fixture(autouse=True)
def clean_promotion_sources(
    migrated_test_database: None, test_database_url: str
) -> Generator[None, None, None]:
    def clean() -> None:
        verify_connected_test_database(test_database_url)
        with Session(get_engine()) as session:
            session.execute(delete(Source).where(Source.name.like(f"{PREFIX}%")))
            session.commit()

    clean()
    yield
    clean()


def seed(
    *,
    review_status: str = "approved",
    run_status: str = "completed",
    reference: str | None = "https://example.test/origin",
    locator: str | None = "paragraph 2",
    content: str = "Unique lexical promotion phrase",
) -> tuple[uuid.UUID, uuid.UUID]:
    source = Source(
        source_type="note", name=f"{PREFIX}{uuid.uuid4()}", reference=reference
    )
    document = SourceDocument(
        source=source,
        media_type="text/plain",
        byte_size=25,
        extracted_text="Evidence for exact mapping.",
        ingestion_status="extracted",
        extracted_at=datetime.now(UTC),
    )
    chunk = SourceChunk(
        document=document,
        chunk_index=0,
        content="Evidence for exact mapping.",
        char_start=0,
        char_end=27,
        content_hash="a" * 64,
    )
    run = MemoryExtractionRun(
        document=document,
        provider="test",
        model="test-model",
        prompt_version="v1",
        input_hash=uuid.uuid4().hex + uuid.uuid4().hex,
        run_status=run_status,
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC) if run_status == "completed" else None,
    )
    proposal = MemoryProposal(
        run=run,
        source_chunk=chunk,
        source_chunk_hash=chunk.content_hash,
        project_id=None,
        proposal_index=0,
        title="Exact title",
        summary="Exact summary",
        content=content,
        memory_type="decision",
        importance=0.7,
        confidence=0.8,
        evidence_text="exact mapping",
        evidence_char_start=13,
        evidence_char_end=26,
        source_locator=locator,
        proposal_hash=uuid.uuid4().hex + uuid.uuid4().hex,
        review_status=review_status,
        review_note="verified",
        reviewed_at=datetime.now(UTC),
    )
    with Session(get_engine()) as session:
        session.add(proposal)
        session.commit()
        return proposal.id, source.id


def test_promotion_mapping_links_search_and_idempotency() -> None:
    proposal_id, source_id = seed()
    client = TestClient(create_app())
    first = client.post(f"/memory-proposals/{proposal_id}/promote")
    assert first.status_code == 200
    body = first.json()
    assert body["promotion_status"] == "created"
    memory = body["memory"]
    assert memory["project_id"] is None
    assert (
        memory["title"],
        memory["summary"],
        memory["content"],
        memory["memory_type"],
        memory["importance"],
        memory["confidence"],
    ) == (
        "Exact title",
        "Exact summary",
        "Unique lexical promotion phrase",
        "decision",
        0.7,
        0.8,
    )
    assert memory["source"] == "https://example.test/origin"
    assert memory["status"] == "active"
    assert memory["event_time"] is memory["expires_at"] is None
    assert memory["supersedes_id"] is None
    memory_id = uuid.UUID(memory["id"])

    with Session(get_engine()) as session:
        proposal = session.get(MemoryProposal, proposal_id)
        link = session.scalar(
            select(MemorySource).where(MemorySource.memory_id == memory_id)
        )
        assert proposal is not None and proposal.memory_id == memory_id
        assert proposal.review_status == "approved"
        assert proposal.review_note == "verified"
        assert link is not None and link.source_id == source_id
        assert link.source_location == "paragraph 2"
        assert (
            session.scalar(
                select(func.count())
                .select_from(MemoryEmbedding)
                .where(MemoryEmbedding.memory_id == memory_id)
            )
            == 0
        )

    assert client.get(f"/memories/{memory_id}").status_code == 200
    assert client.get(f"/memories/{memory_id}/sources").json()[0]["source_id"] == str(
        source_id
    )
    assert client.get(f"/sources/{source_id}/memories").json()[0]["memory_id"] == str(
        memory_id
    )
    assert client.get("/memories?query=promotion%20phrase").json()[0]["id"] == str(
        memory_id
    )
    assert client.get("/memories?memory_type=decision&status=active").json()[0][
        "id"
    ] == str(memory_id)

    repeated = client.post(f"/memory-proposals/{proposal_id}/promote")
    assert repeated.json()["promotion_status"] == "unchanged"
    assert repeated.json()["memory"] == memory
    with Session(get_engine()) as session:
        assert (
            session.scalar(
                select(func.count()).select_from(Memory).where(Memory.id == memory_id)
            )
            == 1
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(MemorySource)
                .where(MemorySource.memory_id == memory_id)
            )
            == 1
        )


def test_source_fallback_eligibility_concurrency_and_replacement() -> None:
    client = TestClient(create_app())
    for review_status, run_status, detail in (
        ("pending", "completed", "memory proposal not approved"),
        ("rejected", "completed", "memory proposal not approved"),
        ("approved", "pending", "extraction run not completed"),
        ("approved", "failed", "extraction run not completed"),
    ):
        proposal_id, _ = seed(review_status=review_status, run_status=run_status)
        response = client.post(f"/memory-proposals/{proposal_id}/promote")
        assert response.status_code == 409 and response.json() == {"detail": detail}

    proposal_id, source_id = seed(reference="  ", locator=None)

    def promote() -> dict[str, object]:
        response = TestClient(create_app()).post(
            f"/memory-proposals/{proposal_id}/promote"
        )
        assert response.status_code == 200
        return response.json()

    with ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(lambda _: promote(), range(3)))
    assert sorted(result["promotion_status"] for result in results) == [
        "created",
        "unchanged",
        "unchanged",
    ]
    memory_ids = {result["memory"]["id"] for result in results}  # type: ignore[index]
    assert len(memory_ids) == 1
    memory_id = uuid.UUID(str(memory_ids.pop()))
    with Session(get_engine()) as session:
        stored = session.get(Memory, memory_id)
        link = session.scalar(
            select(MemorySource).where(MemorySource.memory_id == memory_id)
        )
        assert stored is not None and stored.source.startswith(PREFIX)
        assert link is not None and link.source_location == "chars 13-26"
        session.delete(stored)
        session.commit()
        assert session.get(MemoryProposal, proposal_id).memory_id is None  # type: ignore[union-attr]

    replacement = client.post(f"/memory-proposals/{proposal_id}/promote").json()
    assert replacement["promotion_status"] == "created"
    assert replacement["memory"]["id"] != str(memory_id)
    assert client.get(f"/sources/{source_id}/memories").status_code == 200


def test_database_failure_after_first_flush_rolls_back_all_promotion_effects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unique_content = f"rollback promotion {uuid.uuid4()}"
    proposal_id, source_id = seed(content=unique_content)
    with Session(get_engine()) as session:
        proposal = session.get(MemoryProposal, proposal_id)
        assert proposal is not None and proposal.memory_id is None
        baseline_memory_count = session.scalar(select(func.count()).select_from(Memory))
        baseline_link_count = session.scalar(
            select(func.count()).select_from(MemorySource)
        )

    original_flush = Session.flush
    flush_calls = 0
    successful_flushes = 0
    forced_failure = False

    def fail_after_first_flush(session: Session, objects: object | None = None) -> None:
        nonlocal flush_calls, successful_flushes, forced_failure
        flush_calls += 1
        if flush_calls == 1:
            original_flush(session, objects)  # type: ignore[arg-type]
            successful_flushes += 1
            return
        forced_failure = True
        raise SQLAlchemyError("forced failure after successful promotion flush")

    with monkeypatch.context() as patch:
        patch.setattr(Session, "flush", fail_after_first_flush)
        response = TestClient(create_app()).post(
            f"/memory-proposals/{proposal_id}/promote"
        )

    assert response.status_code == 503
    assert response.json() == {"detail": "database unavailable"}
    assert flush_calls == 2
    assert successful_flushes == 1
    assert forced_failure is True

    with Session(get_engine()) as verification_session:
        proposal = verification_session.get(MemoryProposal, proposal_id)
        assert proposal is not None
        assert proposal.memory_id is None
        assert (
            verification_session.scalar(
                select(func.count())
                .select_from(Memory)
                .where(Memory.content == unique_content)
            )
            == 0
        )
        assert (
            verification_session.scalar(
                select(func.count())
                .select_from(MemorySource)
                .where(MemorySource.source_id == source_id)
            )
            == 0
        )
        assert (
            verification_session.scalar(select(func.count()).select_from(Memory))
            == baseline_memory_count
        )
        assert (
            verification_session.scalar(select(func.count()).select_from(MemorySource))
            == baseline_link_count
        )
