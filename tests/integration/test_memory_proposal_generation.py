"""PostgreSQL coverage for explicit proposal generation."""

import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db.session import get_engine
from app.extraction.dependencies import get_extraction_provider
from app.extraction.provider import (
    ChunkExtraction,
    ChunkSnapshot,
    ExtractedProposal,
    ExtractionResult,
)
from app.main import create_app
from app.models import (
    Memory,
    MemoryEmbedding,
    MemoryExtractionRun,
    MemoryProposal,
    Source,
)
from tests.integration.conftest import verify_connected_test_database


class FakeProvider:
    name = "openai"
    model = "fake-model"
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
        results = []
        for chunk in chunks:
            evidence = "PostgreSQL"
            start = chunk.content.index(evidence)
            results.append(
                ChunkExtraction(
                    chunk_index=chunk.chunk_index,
                    proposals=[
                        ExtractedProposal(
                            title=" Database ",
                            summary=None,
                            content="The project uses PostgreSQL.",
                            memory_type="semantic",
                            importance=0.7,
                            confidence=0.9,
                            evidence_text=evidence,
                            evidence_start=start,
                            evidence_end=start + len(evidence),
                        )
                    ],
                )
            )
        return ExtractionResult(chunks=results)


@pytest.fixture(autouse=True)
def clean_generation_sources(
    migrated_test_database: None, test_database_url: str
) -> Generator[None, None, None]:
    def clean() -> None:
        verify_connected_test_database(test_database_url)
        with Session(get_engine()) as session:
            session.execute(
                delete(Source).where(Source.name.like("proposal-generation-%"))
            )
            session.commit()

    clean()
    yield
    clean()


def test_generation_persists_pending_provenance_and_reuses_completed_run() -> None:
    provider = FakeProvider()
    app = create_app()
    app.dependency_overrides[get_extraction_provider] = lambda: provider
    client = TestClient(app)
    with Session(get_engine()) as session:
        memory_count = session.scalar(select(func.count()).select_from(Memory))
        embedding_count = session.scalar(
            select(func.count()).select_from(MemoryEmbedding)
        )
    source = client.post(
        "/sources",
        json={"source_type": "note", "name": f"proposal-generation-{uuid.uuid4()}"},
    ).json()
    ingested = client.put(
        f"/sources/{source['id']}/document/text",
        json={"text": "The project explicitly selected PostgreSQL for storage."},
    )
    assert ingested.status_code == 200
    url = f"/sources/{source['id']}/memory-proposals"
    first = client.post(url, json={})
    assert first.status_code == 200
    assert first.json()["generation_status"] == "created"
    assert first.json()["proposal_count"] == 1
    assert "evidence_text" not in first.json() and "proposals" not in first.json()
    with Session(get_engine()) as session:
        run = session.scalar(
            select(MemoryExtractionRun).where(
                MemoryExtractionRun.id == uuid.UUID(first.json()["id"])
            )
        )
        proposal = session.scalar(
            select(MemoryProposal).where(MemoryProposal.run_id == run.id)
        )  # type: ignore[union-attr]
        assert run is not None and run.run_status == "completed"
        assert proposal is not None and proposal.review_status == "pending"
        assert proposal.memory_id is None and proposal.review_note is None
        assert proposal.source_chunk_id is not None
        assert proposal.evidence_text == "PostgreSQL"
        assert session.scalar(select(func.count()).select_from(Memory)) == memory_count
        assert (
            session.scalar(select(func.count()).select_from(MemoryEmbedding))
            == embedding_count
        )
        proposal_id, completed_at = proposal.id, run.completed_at
    unchanged = client.post(url, json={})
    assert unchanged.status_code == 200
    assert unchanged.json()["generation_status"] == "unchanged"
    assert provider.calls == 1
    with Session(get_engine()) as session:
        proposal = session.scalar(
            select(MemoryProposal).where(
                MemoryProposal.run_id == uuid.UUID(first.json()["id"])
            )
        )
        run = session.get(MemoryExtractionRun, uuid.UUID(first.json()["id"]))
        assert proposal is not None and proposal.id == proposal_id
        assert run is not None and run.completed_at == completed_at
