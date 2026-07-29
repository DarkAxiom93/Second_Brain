"""PostgreSQL integration coverage for explicit TXT/PDF uploads."""

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
from tests.test_file_ingestion import _pdf_bytes


@pytest.fixture(autouse=True)
def clean_file_ingestion_sources(
    migrated_test_database: None, test_database_url: str
) -> Generator[None, None, None]:
    """Clean only this module's Sources on the verified test database."""

    def clean() -> None:
        verify_connected_test_database(test_database_url)
        with Session(get_engine()) as session:
            session.execute(delete(Source).where(Source.name.like("file-test-%")))
            session.commit()

    clean()
    yield
    clean()


def test_txt_and_pdf_upload_lifecycle_preserves_source_and_other_models() -> None:
    client = TestClient(create_app())
    with Session(get_engine()) as session:
        memory_count = session.scalar(select(func.count()).select_from(Memory))
        embedding_count = session.scalar(
            select(func.count()).select_from(MemoryEmbedding)
        )
    source = client.post(
        "/sources",
        json={
            "source_type": "file",
            "name": f"file-test-{uuid.uuid4()}",
            "reference": "keep-reference",
            "checksum": "keep-checksum",
        },
    ).json()
    source_id = uuid.UUID(source["id"])
    url = f"/sources/{source['id']}/document/file"
    txt = b"first\r\n" + b"x" * 2100
    txt_form = {
        "files": {"file": ("note.txt", txt, "text/plain")},
        "data": {"chunk_size": "1000", "chunk_overlap": "100"},
    }
    created = client.put(url, **txt_form)
    assert created.status_code == 200
    assert created.json()["generation_status"] == "created"
    with Session(get_engine()) as session:
        document = session.scalar(
            select(SourceDocument).where(SourceDocument.source_id == source_id)
        )
        assert document is not None
        document_id = document.id
        updated_at = document.updated_at
        extracted_at = document.extracted_at
        assert document.byte_size == len(txt)
        assert document.extracted_text == txt.decode().replace("\r\n", "\n")
        chunks = list(
            session.scalars(
                select(SourceChunk)
                .where(SourceChunk.document_id == document_id)
                .order_by(SourceChunk.chunk_index)
            )
        )
        chunk_ids = [chunk.id for chunk in chunks]
        assert all(chunk.locator is None for chunk in chunks)

    unchanged = client.put(url, **txt_form)
    assert unchanged.json()["generation_status"] == "unchanged"
    with Session(get_engine()) as session:
        document = session.get(SourceDocument, document_id)
        assert document is not None
        assert (document.updated_at, document.extracted_at) == (
            updated_at,
            extracted_at,
        )
        assert (
            list(
                session.scalars(
                    select(SourceChunk.id)
                    .where(SourceChunk.document_id == document_id)
                    .order_by(SourceChunk.chunk_index)
                )
            )
            == chunk_ids
        )

    pdf = _pdf_bytes(["First page", "Second page"])
    updated = client.put(
        url,
        files={"file": ("pages.pdf", pdf, "application/pdf")},
        data={"chunk_size": "1000", "chunk_overlap": "0"},
    )
    assert updated.status_code == 200
    assert updated.json()["generation_status"] == "updated"
    assert updated.json()["id"] == str(document_id)
    with Session(get_engine()) as session:
        document = session.get(SourceDocument, document_id)
        assert document is not None
        assert document.media_type == "application/pdf"
        assert document.byte_size == len(pdf)
        assert document.extracted_text == "First page\n\nSecond page"
        chunks = list(
            session.scalars(
                select(SourceChunk).where(SourceChunk.document_id == document_id)
            )
        )
        assert len(chunks) == 1 and chunks[0].locator == "pages 1-2"
        assert (
            document.extracted_text[chunks[0].char_start : chunks[0].char_end]
            == chunks[0].content
        )
        assert chunks[0].content_hash == sha256(chunks[0].content.encode()).hexdigest()
        stored_source = session.get(Source, source_id)
        assert stored_source is not None
        assert stored_source.reference == "keep-reference"
        assert stored_source.checksum == "keep-checksum"
        assert (
            session.scalar(
                select(func.count())
                .select_from(SourceDocument)
                .where(SourceDocument.source_id == source_id)
            )
            == 1
        )
        assert session.scalar(select(func.count()).select_from(Memory)) == memory_count
        assert (
            session.scalar(select(func.count()).select_from(MemoryEmbedding))
            == embedding_count
        )


def test_invalid_file_does_not_create_or_replace_document() -> None:
    client = TestClient(create_app())
    source = client.post(
        "/sources",
        json={"source_type": "file", "name": f"file-test-{uuid.uuid4()}"},
    ).json()
    source_id = uuid.UUID(source["id"])
    url = f"/sources/{source['id']}/document/file"
    assert (
        client.put(
            url, files={"file": ("a.pdf", b"bad", "application/pdf")}
        ).status_code
        == 415
    )
    with Session(get_engine()) as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(SourceDocument)
                .where(SourceDocument.source_id == source_id)
            )
            == 0
        )
    valid = client.put(url, files={"file": ("a.txt", b"valid", "text/plain")})
    assert valid.status_code == 200
    with Session(get_engine()) as session:
        before = session.scalar(
            select(SourceDocument).where(SourceDocument.source_id == source_id)
        )
        assert before is not None
        before_state = (
            before.id,
            before.extracted_text,
            [chunk.id for chunk in before.chunks],
        )
    assert (
        client.put(
            url, files={"file": ("a.pdf", b"%PDF-broken", "application/pdf")}
        ).status_code
        == 422
    )
    with Session(get_engine()) as session:
        after = session.scalar(
            select(SourceDocument).where(SourceDocument.source_id == source_id)
        )
        assert after is not None
        assert (
            after.id,
            after.extracted_text,
            [chunk.id for chunk in after.chunks],
        ) == before_state
