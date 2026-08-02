"""Unit tests for Source creation and linking routes."""

import uuid
from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.api.routes import memories as memory_routes
from app.api.routes import sources as source_routes
from app.db.dependencies import get_db_session
from app.main import create_app
from app.models.memory import Memory
from app.models.source import Source
from app.models.source_chunk import SourceChunk
from app.models.source_document import SourceDocument
from app.repositories.sources import DocumentIngestionResult, DocumentRead


@pytest.fixture
def route_client() -> tuple[TestClient, Mock]:
    session = Mock()

    def override() -> Generator[Mock, None, None]:
        yield session

    app = create_app()
    app.dependency_overrides[get_db_session] = override
    return TestClient(app), session


def test_create_source_returns_exact_fields_and_commits(
    monkeypatch: pytest.MonkeyPatch, route_client: tuple[TestClient, Mock]
) -> None:
    client, session = route_client
    now = datetime.now(UTC)
    source = Source(
        id=uuid.uuid4(),
        source_type="note",
        name="Notes",
        reference=None,
        checksum=None,
        created_at=now,
        updated_at=now,
    )
    monkeypatch.setattr(
        source_routes.source_repository, "create_source", Mock(return_value=source)
    )
    response = client.post("/sources", json={"source_type": "note", "name": "Notes"})
    assert response.status_code == 201
    assert set(response.json()) == {
        "id",
        "source_type",
        "name",
        "reference",
        "checksum",
        "created_at",
        "updated_at",
    }
    session.commit.assert_called_once_with()


@pytest.mark.parametrize(
    "missing,detail", [("memory", "memory not found"), ("source", "source not found")]
)
def test_link_unknown_parent_exact_404(
    missing: str,
    detail: str,
    monkeypatch: pytest.MonkeyPatch,
    route_client: tuple[TestClient, Mock],
) -> None:
    client, session = route_client
    monkeypatch.setattr(
        memory_routes.memory_repository,
        "get_memory",
        Mock(return_value=None if missing == "memory" else Memory()),
    )
    monkeypatch.setattr(
        memory_routes.source_repository,
        "get_source",
        Mock(return_value=None if missing == "source" else Source()),
    )
    response = client.post(
        f"/memories/{uuid.uuid4()}/sources", json={"source_id": str(uuid.uuid4())}
    )
    assert response.status_code == 404 and response.json() == {"detail": detail}
    session.commit.assert_not_called()


def test_duplicate_link_and_integrity_race_return_exact_409(
    monkeypatch: pytest.MonkeyPatch, route_client: tuple[TestClient, Mock]
) -> None:
    client, session = route_client
    monkeypatch.setattr(
        memory_routes.memory_repository, "get_memory", Mock(return_value=Memory())
    )
    monkeypatch.setattr(
        memory_routes.source_repository, "get_source", Mock(return_value=Source())
    )
    monkeypatch.setattr(
        memory_routes.source_repository,
        "memory_source_link_exists",
        Mock(return_value=True),
    )
    response = client.post(
        f"/memories/{uuid.uuid4()}/sources", json={"source_id": str(uuid.uuid4())}
    )
    assert response.status_code == 409 and response.json() == {
        "detail": "source already linked to memory"
    }
    session.commit.assert_not_called()


def test_database_failure_is_generic(
    monkeypatch: pytest.MonkeyPatch, route_client: tuple[TestClient, Mock]
) -> None:
    client, session = route_client
    failure = OperationalError("secret SQL", {}, Exception("password=secret"))
    monkeypatch.setattr(
        source_routes.source_repository, "create_source", Mock(side_effect=failure)
    )
    response = client.post("/sources", json={"source_type": "note", "name": "Notes"})
    assert response.status_code == 503 and response.json() == {
        "detail": "database unavailable"
    }
    assert "secret" not in response.text
    session.rollback.assert_called_once_with()


def test_source_listing_and_detail_are_read_only(
    monkeypatch: pytest.MonkeyPatch, route_client: tuple[TestClient, Mock]
) -> None:
    client, session = route_client
    now = datetime.now(UTC)
    source = Source(
        id=uuid.uuid4(),
        source_type="note",
        name="Notes",
        created_at=now,
        updated_at=now,
    )
    listing = Mock(return_value=[source])
    retrieval = Mock(return_value=source)
    monkeypatch.setattr(source_routes.source_repository, "list_sources", listing)
    monkeypatch.setattr(source_routes.source_repository, "get_source", retrieval)
    assert client.get("/sources?limit=20&offset=3").json()[0]["id"] == str(source.id)
    assert client.get(f"/sources/{source.id}").json()["name"] == "Notes"
    listing.assert_called_once_with(session, limit=20, offset=3)
    retrieval.assert_called_once_with(session, source.id)
    session.commit.assert_not_called()
    session.flush.assert_not_called()


def test_source_detail_validation_missing_and_database_failure(
    monkeypatch: pytest.MonkeyPatch, route_client: tuple[TestClient, Mock]
) -> None:
    client, session = route_client
    retrieval = Mock(return_value=None)
    monkeypatch.setattr(source_routes.source_repository, "get_source", retrieval)
    assert client.get("/sources/not-a-uuid").status_code == 422
    retrieval.assert_not_called()
    response = client.get(f"/sources/{uuid.uuid4()}")
    assert response.status_code == 404
    assert response.json() == {"detail": "source not found"}
    failure = OperationalError("secret SQL", {}, Exception("password=secret"))
    retrieval.side_effect = failure
    response = client.get(f"/sources/{uuid.uuid4()}")
    assert response.status_code == 503
    assert response.json() == {"detail": "database unavailable"}
    assert "secret" not in response.text
    session.commit.assert_not_called()
    session.flush.assert_not_called()


def test_only_approved_source_paths_exist(
    route_client: tuple[TestClient, Mock],
) -> None:
    client, _ = route_client
    assert client.get("/api/sources").status_code == 404
    paths = client.app.openapi()["paths"]
    assert set(paths["/sources"]) == {"get", "post"}
    assert set(paths["/sources/{source_id}"]) == {"get"}
    assert set(paths["/sources/{source_id}/documents"]) == {"get"}
    assert set(paths["/source-documents/{document_id}"]) == {"get"}
    assert set(paths["/source-documents/{document_id}/chunks"]) == {"get"}


def test_document_reads_are_scoped_paginated_and_read_only(
    monkeypatch: pytest.MonkeyPatch, route_client: tuple[TestClient, Mock]
) -> None:
    client, session = route_client
    now = datetime.now(UTC)
    source_id, document_id = uuid.uuid4(), uuid.uuid4()
    document = DocumentRead(
        document_id,
        source_id,
        "text/plain",
        "note.txt",
        7,
        "extracted",
        None,
        now,
        now,
        now,
        1,
    )
    chunk = SourceChunk(
        id=uuid.uuid4(),
        document_id=document_id,
        chunk_index=0,
        content="content",
        char_start=0,
        char_end=7,
        content_hash="a" * 64,
        locator=None,
        created_at=now,
    )
    monkeypatch.setattr(
        source_routes.source_repository, "get_source", Mock(return_value=Source())
    )
    list_documents = Mock(return_value=[document])
    get_document = Mock(return_value=document)
    list_chunks = Mock(return_value=[chunk])
    monkeypatch.setattr(
        source_routes.source_repository, "list_documents_for_source", list_documents
    )
    monkeypatch.setattr(source_routes.source_repository, "get_document", get_document)
    monkeypatch.setattr(
        source_routes.source_repository, "list_chunks_for_document", list_chunks
    )
    assert (
        client.get(f"/sources/{source_id}/documents?limit=7&offset=2").json()[0][
            "chunk_count"
        ]
        == 1
    )
    assert (
        client.get(f"/source-documents/{document_id}").json()["original_filename"]
        == "note.txt"
    )
    assert (
        client.get(f"/source-documents/{document_id}/chunks?limit=8&offset=3").json()[
            0
        ]["content"]
        == "content"
    )
    list_documents.assert_called_once_with(
        session, source_id=source_id, limit=7, offset=2
    )
    list_chunks.assert_called_once_with(
        session, document_id=document_id, limit=8, offset=3
    )
    session.commit.assert_not_called()
    session.flush.assert_not_called()


def test_document_reads_validate_missing_and_hide_database_failures(
    monkeypatch: pytest.MonkeyPatch, route_client: tuple[TestClient, Mock]
) -> None:
    client, session = route_client
    retrieval = Mock(return_value=None)
    monkeypatch.setattr(source_routes.source_repository, "get_document", retrieval)
    assert client.get("/source-documents/not-a-uuid").status_code == 422
    retrieval.assert_not_called()
    response = client.get(f"/source-documents/{uuid.uuid4()}")
    assert response.status_code == 404 and response.json() == {
        "detail": "source document not found"
    }
    response = client.get(f"/source-documents/{uuid.uuid4()}/chunks")
    assert response.status_code == 404 and response.json() == {
        "detail": "source document not found"
    }
    failure = OperationalError("secret SQL", {}, Exception("password=secret"))
    retrieval.side_effect = failure
    response = client.get(f"/source-documents/{uuid.uuid4()}")
    assert response.status_code == 503 and response.json() == {
        "detail": "database unavailable"
    }
    assert "secret" not in response.text
    session.commit.assert_not_called()
    session.flush.assert_not_called()


def test_ingest_unknown_source_returns_exact_404(
    monkeypatch: pytest.MonkeyPatch, route_client: tuple[TestClient, Mock]
) -> None:
    client, session = route_client
    monkeypatch.setattr(
        source_routes.source_repository, "get_source", Mock(return_value=None)
    )
    response = client.put(
        f"/sources/{uuid.uuid4()}/document/text", json={"text": "content"}
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "source not found"}
    session.commit.assert_not_called()


@pytest.mark.parametrize("generation_status", ["created", "updated", "unchanged"])
def test_ingestion_outcomes_commit_once_without_exposing_content(
    generation_status: str,
    monkeypatch: pytest.MonkeyPatch,
    route_client: tuple[TestClient, Mock],
) -> None:
    client, session = route_client
    now = datetime.now(UTC)
    source_id = uuid.uuid4()
    document = SourceDocument(
        id=uuid.uuid4(),
        source_id=source_id,
        media_type="text/plain",
        original_filename=None,
        byte_size=7,
        extracted_text="content",
        ingestion_status="extracted",
        error_code=None,
        extracted_at=now,
        created_at=now,
        updated_at=now,
    )
    monkeypatch.setattr(
        source_routes.source_repository, "get_source", Mock(return_value=Source())
    )
    monkeypatch.setattr(
        source_routes.source_repository,
        "upsert_text_document",
        Mock(
            return_value=DocumentIngestionResult(
                document=document,
                chunk_count=1,
                generation_status=generation_status,  # type: ignore[arg-type]
            )
        ),
    )
    response = client.put(
        f"/sources/{source_id}/document/text", json={"text": "content"}
    )
    assert response.status_code == 200
    assert response.json()["generation_status"] == generation_status
    assert "extracted_text" not in response.json() and "chunks" not in response.json()
    session.commit.assert_called_once_with()


def test_ingestion_database_failure_rolls_back_and_is_generic(
    monkeypatch: pytest.MonkeyPatch, route_client: tuple[TestClient, Mock]
) -> None:
    client, session = route_client
    monkeypatch.setattr(
        source_routes.source_repository, "get_source", Mock(return_value=Source())
    )
    failure = OperationalError("secret SQL", {}, Exception("password=secret"))
    monkeypatch.setattr(
        source_routes.source_repository,
        "upsert_text_document",
        Mock(side_effect=failure),
    )
    response = client.put(
        f"/sources/{uuid.uuid4()}/document/text", json={"text": "content"}
    )
    assert response.status_code == 503
    assert response.json() == {"detail": "database unavailable"}
    assert "secret" not in response.text and "password" not in response.text
    session.rollback.assert_called_once_with()


def test_file_upload_success_commits_once_and_closes_upload(
    monkeypatch: pytest.MonkeyPatch, route_client: tuple[TestClient, Mock]
) -> None:
    client, session = route_client
    now = datetime.now(UTC)
    source_id = uuid.uuid4()
    document = SourceDocument(
        id=uuid.uuid4(),
        source_id=source_id,
        media_type="text/plain",
        original_filename="note.txt",
        byte_size=7,
        extracted_text="content",
        ingestion_status="extracted",
        error_code=None,
        extracted_at=now,
        created_at=now,
        updated_at=now,
    )
    monkeypatch.setattr(
        source_routes.source_repository, "get_source", Mock(return_value=Source())
    )
    upsert = Mock(return_value=DocumentIngestionResult(document, 1, "created"))
    monkeypatch.setattr(source_routes.source_repository, "upsert_document", upsert)
    response = client.put(
        f"/sources/{source_id}/document/file",
        files={"file": (" note.txt ", b"content", "text/plain")},
    )
    assert response.status_code == 200
    assert response.json()["generation_status"] == "created"
    assert "extracted_text" not in response.json()
    session.commit.assert_called_once_with()
    assert upsert.call_args.kwargs["byte_size"] == 7


@pytest.mark.parametrize(
    "files,expected",
    [
        (
            {"file": ("note.docx", b"content", "application/octet-stream")},
            (415, "unsupported document type"),
        ),
        (
            {"file": ("note.txt", b"\xff", "text/plain")},
            (422, "document extraction failed"),
        ),
        (
            {"file": ("note.txt", b"", "text/plain")},
            (422, "document extraction failed"),
        ),
    ],
)
def test_file_upload_exact_validation_errors(
    files: dict[str, tuple[str, bytes, str]],
    expected: tuple[int, str],
    monkeypatch: pytest.MonkeyPatch,
    route_client: tuple[TestClient, Mock],
) -> None:
    client, session = route_client
    monkeypatch.setattr(
        source_routes.source_repository, "get_source", Mock(return_value=Source())
    )
    response = client.put(f"/sources/{uuid.uuid4()}/document/file", files=files)
    assert (response.status_code, response.json()["detail"]) == expected
    session.commit.assert_not_called()


def test_file_upload_unknown_source_and_database_failure_are_generic(
    monkeypatch: pytest.MonkeyPatch, route_client: tuple[TestClient, Mock]
) -> None:
    client, session = route_client
    get_source = Mock(return_value=None)
    monkeypatch.setattr(source_routes.source_repository, "get_source", get_source)
    url = f"/sources/{uuid.uuid4()}/document/file"
    missing = client.put(url, files={"file": ("a.txt", b"hello", "text/plain")})
    assert missing.status_code == 404
    assert missing.json() == {"detail": "source not found"}

    get_source.return_value = Source()
    failure = OperationalError("secret SQL", {}, Exception("password=secret"))
    monkeypatch.setattr(
        source_routes.source_repository, "upsert_document", Mock(side_effect=failure)
    )
    failed = client.put(url, files={"file": ("a.txt", b"hello", "text/plain")})
    assert failed.status_code == 503
    assert failed.json() == {"detail": "database unavailable"}
    assert "secret" not in failed.text and "password" not in failed.text
    session.rollback.assert_called_once_with()
