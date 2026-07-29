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
from app.models.source_document import SourceDocument
from app.repositories.sources import DocumentIngestionResult


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


def test_only_approved_source_paths_exist(
    route_client: tuple[TestClient, Mock],
) -> None:
    client, _ = route_client
    assert client.get("/sources").status_code == 405
    assert client.get("/api/sources").status_code == 404


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
