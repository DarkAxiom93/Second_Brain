"""PostgreSQL integration coverage for explicit plain-text ingestion."""

import uuid
from collections.abc import Generator
from hashlib import sha256

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db.session import get_engine
from app.main import create_app
from app.models import Memory, MemoryEmbedding, Source, SourceChunk, SourceDocument
from tests.integration.conftest import verify_connected_test_database


@pytest.fixture(autouse=True)
def clean_ingestion_sources(
    migrated_test_database: None, test_database_url: str
) -> Generator[None, None, None]:
    """Clean only Sources owned by this test module on the verified test DB."""

    def clean() -> None:
        verify_connected_test_database(test_database_url)
        with Session(get_engine()) as session:
            session.execute(delete(Source).where(Source.name.like("ingestion-test-%")))
            session.commit()

    clean()
    yield
    clean()


def test_text_ingestion_lifecycle_is_idempotent_and_transactional() -> None:
    client = TestClient(create_app())
    with Session(get_engine()) as session:
        memory_count = session.scalar(select(func.count()).select_from(Memory))
        embedding_count = session.scalar(
            select(func.count()).select_from(MemoryEmbedding)
        )
    source = client.post(
        "/sources",
        json={
            "source_type": "note",
            "name": f"ingestion-test-{uuid.uuid4()}",
            "reference": "keep-reference",
            "checksum": "keep-checksum",
        },
    ).json()
    url = f"/sources/{source['id']}/document/text"
    first_payload = {
        "text": "אבג\r\nEnglish 😀" + "x" * 2100,
        "original_filename": " notes.txt ",
        "chunk_size": 1000,
        "chunk_overlap": 100,
    }
    first = client.put(url, json=first_payload)
    assert first.status_code == 200
    assert first.json()["generation_status"] == "created"
    assert first.json()["media_type"] == "text/plain"
    assert first.json()["original_filename"] == "notes.txt"

    source_id = uuid.UUID(source["id"])
    normalized = first_payload["text"].replace("\r\n", "\n")
    with Session(get_engine()) as session:
        document = session.scalar(
            select(SourceDocument).where(SourceDocument.source_id == source_id)
        )
        assert document is not None
        document_id = document.id
        original_updated_at = document.updated_at
        original_extracted_at = document.extracted_at
        assert document.extracted_text == normalized
        assert document.byte_size == len(normalized.encode("utf-8"))
        assert document.ingestion_status == "extracted" and document.error_code is None
        assert (
            document.extracted_at is not None
            and document.extracted_at.tzinfo is not None
        )
        chunks = list(
            session.scalars(
                select(SourceChunk)
                .where(SourceChunk.document_id == document.id)
                .order_by(SourceChunk.chunk_index)
            )
        )
        original_chunk_ids = [chunk.id for chunk in chunks]
        for index, chunk in enumerate(chunks):
            assert chunk.chunk_index == index
            assert normalized[chunk.char_start : chunk.char_end] == chunk.content
            assert (
                chunk.content_hash == sha256(chunk.content.encode("utf-8")).hexdigest()
            )

    unchanged = client.put(url, json=first_payload)
    assert unchanged.status_code == 200
    assert unchanged.json()["generation_status"] == "unchanged"
    with Session(get_engine()) as session:
        document = session.get(SourceDocument, document_id)
        assert document is not None
        assert document.updated_at == original_updated_at
        assert document.extracted_at == original_extracted_at
        assert (
            list(
                session.scalars(
                    select(SourceChunk.id)
                    .where(SourceChunk.document_id == document_id)
                    .order_by(SourceChunk.chunk_index)
                )
            )
            == original_chunk_ids
        )

    updated = client.put(
        url,
        json={
            "text": "replacement " * 300,
            "original_filename": "notes.txt",
            "chunk_size": 1200,
            "chunk_overlap": 50,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["generation_status"] == "updated"
    assert updated.json()["id"] == str(document_id)
    with Session(get_engine()) as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(SourceDocument)
                .where(SourceDocument.source_id == source_id)
            )
            == 1
        )
        assert not session.scalars(
            select(SourceChunk.id).where(SourceChunk.id.in_(original_chunk_ids))
        ).all()
        stored_source = session.get(Source, source_id)
        assert stored_source is not None
        assert stored_source.reference == "keep-reference"
        assert stored_source.checksum == "keep-checksum"
        assert session.scalar(select(func.count()).select_from(Memory)) == memory_count
        assert (
            session.scalar(select(func.count()).select_from(MemoryEmbedding))
            == embedding_count
        )


def test_unknown_and_invalid_ingestion_create_no_document() -> None:
    client = TestClient(create_app())
    missing = client.put(
        f"/sources/{uuid.uuid4()}/document/text", json={"text": "valid"}
    )
    assert missing.status_code == 404
    source = client.post(
        "/sources",
        json={"source_type": "note", "name": f"ingestion-test-{uuid.uuid4()}"},
    ).json()
    invalid = client.put(f"/sources/{source['id']}/document/text", json={"text": "   "})
    assert invalid.status_code == 422
    with Session(get_engine()) as session:
        assert session.scalar(select(func.count()).select_from(SourceDocument)) == 0
