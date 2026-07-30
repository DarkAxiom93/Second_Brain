"""PostgreSQL API coverage for the human proposal-review queue."""

import uuid
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db.session import get_engine
from app.main import create_app
from app.models import (
    Memory,
    MemoryEmbedding,
    MemoryExtractionRun,
    MemoryProposal,
    Source,
)
from app.models.source_chunk import SourceChunk
from app.models.source_document import SourceDocument
from tests.integration.conftest import verify_connected_test_database

PREFIX = "proposal-review-"


@pytest.fixture(autouse=True)
def clean_review_sources(
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


def seed(client: TestClient) -> tuple[dict[str, object], list[uuid.UUID]]:
    source = client.post(
        "/sources", json={"source_type": "note", "name": f"{PREFIX}{uuid.uuid4()}"}
    ).json()
    client.put(
        f"/sources/{source['id']}/document/text",
        json={"text": "Deterministic evidence for review."},
    )
    now = datetime.now(UTC)
    with Session(get_engine()) as session:
        document = session.scalar(
            select(SourceDocument).where(
                SourceDocument.source_id == uuid.UUID(source["id"])
            )
        )
        chunk = session.scalar(
            select(SourceChunk).where(SourceChunk.document_id == document.id)
        )  # type: ignore[union-attr]
        assert document is not None and chunk is not None
        run = MemoryExtractionRun(
            document_id=document.id,
            project_id=None,
            provider="test",
            model="model",
            prompt_version="v1",
            input_hash="a" * 64,
            run_status="completed",
            started_at=now,
            completed_at=now,
        )
        session.add(run)
        session.flush()
        proposals = []
        for index, status in enumerate(("pending", "pending", "approved", "rejected")):
            proposals.append(
                MemoryProposal(
                    run_id=run.id,
                    source_chunk_id=chunk.id,
                    source_chunk_hash=chunk.content_hash,
                    project_id=None,
                    proposal_index=index,
                    title=f"P{index}",
                    summary=None,
                    content=f"Content {index}",
                    memory_type="semantic" if index != 1 else "decision",
                    importance=0.2 + index / 10,
                    confidence=0.6 + index / 10,
                    evidence_text="evidence",
                    evidence_char_start=14,
                    evidence_char_end=22,
                    source_locator=chunk.locator,
                    proposal_hash=f"{index + 1:064x}",
                    review_status=status,
                    review_note="existing" if status != "pending" else None,
                    reviewed_at=now if status != "pending" else None,
                    created_at=now + timedelta(seconds=index),
                )
            )
        session.add_all(proposals)
        session.commit()
        return source, [proposal.id for proposal in proposals]


def test_review_queue_detail_filters_transitions_and_chunk_deletion() -> None:
    client = TestClient(create_app())
    with Session(get_engine()) as session:
        memory_count = session.scalar(select(func.count()).select_from(Memory))
        embedding_count = session.scalar(
            select(func.count()).select_from(MemoryEmbedding)
        )
    source, ids = seed(client)
    pending = client.get("/memory-proposals")
    assert pending.status_code == 200
    assert [row["id"] for row in pending.json()] == [str(ids[0]), str(ids[1])]
    assert (
        "evidence_text" not in pending.json()[0]
        and "proposal_hash" not in pending.json()[0]
    )
    all_rows = client.get(
        f"/memory-proposals?review_status=all&source_id={source['id']}"
    ).json()
    assert [row["review_status"] for row in all_rows] == [
        "pending",
        "pending",
        "approved",
        "rejected",
    ]
    assert client.get(f"/memory-proposals?run_id={uuid.uuid4()}").json() == []
    assert (
        len(
            client.get(
                f"/memory-proposals?source_id={source['id']}&memory_type=decision&importance_min=0.3&confidence_max=0.7"
            ).json()
        )
        == 1
    )
    detail = client.get(f"/memory-proposals/{ids[0]}")
    assert detail.status_code == 200 and detail.json()["evidence_text"] == "evidence"
    assert detail.json()["source_chunk_available"] is True

    approved = client.post(
        f"/memory-proposals/{ids[0]}/approve", json={"review_note": " ok "}
    )
    assert (
        approved.status_code == 200
        and approved.json()["transition_status"] == "updated"
    )
    reviewed_at = approved.json()["reviewed_at"]
    repeated = client.post(
        f"/memory-proposals/{ids[0]}/approve", json={"review_note": "changed"}
    )
    assert repeated.json()["transition_status"] == "unchanged"
    assert (
        repeated.json()["review_note"] == "ok"
        and repeated.json()["reviewed_at"] == reviewed_at
    )
    assert (
        client.post(
            f"/memory-proposals/{ids[0]}/reject", json={"review_note": "no"}
        ).status_code
        == 409
    )

    rejected = client.post(
        f"/memory-proposals/{ids[1]}/reject", json={"review_note": " no "}
    )
    assert rejected.status_code == 200 and rejected.json()["review_note"] == "no"
    assert (
        client.post(
            f"/memory-proposals/{ids[1]}/reject", json={"review_note": "other"}
        ).json()["transition_status"]
        == "unchanged"
    )
    assert (
        client.post(f"/memory-proposals/{ids[1]}/approve", json={}).status_code == 409
    )

    with Session(get_engine()) as session:
        proposal = session.get(MemoryProposal, ids[0])
        assert proposal is not None and proposal.memory_id is None
        session.delete(proposal.source_chunk)
        session.commit()
        assert session.scalar(select(func.count()).select_from(Memory)) == memory_count
        assert (
            session.scalar(select(func.count()).select_from(MemoryEmbedding))
            == embedding_count
        )
    after_delete = client.get(f"/memory-proposals/{ids[0]}")
    assert after_delete.status_code == 200
    assert after_delete.json()["source_chunk_available"] is False
    assert after_delete.json()["evidence_text"] == "evidence"
    assert client.get(f"/memory-proposals/{uuid.uuid4()}").json() == {
        "detail": "memory proposal not found"
    }


@pytest.mark.parametrize("run_status", ["pending", "failed"])
def test_incomplete_run_cannot_be_reviewed(run_status: str) -> None:
    client = TestClient(create_app())
    _, ids = seed(client)
    with Session(get_engine()) as session:
        proposal = session.get(MemoryProposal, ids[0])
        assert proposal is not None
        proposal.run.run_status = run_status
        session.commit()
    response = client.post(f"/memory-proposals/{ids[0]}/approve", json={})
    assert response.status_code == 409
    assert response.json() == {"detail": "extraction run not completed"}


def test_concurrent_same_and_opposite_reviews_are_serialized() -> None:
    client = TestClient(create_app())
    _, ids = seed(client)

    def review(proposal_id: uuid.UUID, decision: str) -> tuple[int, str | None]:
        local_client = TestClient(create_app())
        body = {} if decision == "approve" else {"review_note": "reason"}
        response = local_client.post(
            f"/memory-proposals/{proposal_id}/{decision}", json=body
        )
        return response.status_code, response.json().get("transition_status")

    with ThreadPoolExecutor(max_workers=2) as executor:
        same = list(executor.map(lambda _: review(ids[0], "approve"), range(2)))
    assert sorted(same) == [(200, "unchanged"), (200, "updated")]

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(review, ids[1], "approve"),
            executor.submit(review, ids[1], "reject"),
        ]
        opposite = [future.result() for future in futures]
    assert sorted(code for code, _ in opposite) == [200, 409]
    with Session(get_engine()) as session:
        proposal = session.get(MemoryProposal, ids[1])
        assert proposal is not None and proposal.review_status in {
            "approved",
            "rejected",
        }
        assert (
            session.scalar(
                select(func.count())
                .select_from(MemoryProposal)
                .where(MemoryProposal.id == ids[1])
            )
            == 1
        )
