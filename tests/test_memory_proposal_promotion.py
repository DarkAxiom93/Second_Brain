"""Unit coverage for explicit proposal promotion (no database)."""

import uuid
from collections.abc import Generator
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError

from app.api.routes import memory_proposals as routes
from app.db.dependencies import get_db_session
from app.main import create_app
from app.models.memory import Memory
from app.repositories import memory_proposal_promotions as repository
from app.schemas.memory_proposal import MemoryProposalPromotionResult


def memory() -> Memory:
    now = datetime.now(UTC)
    return Memory(
        id=uuid.uuid4(),
        project_id=None,
        content="promoted content",
        source="source reference",
        title="Title",
        summary="Summary",
        memory_type="decision",
        importance=0.8,
        confidence=0.9,
        status="active",
        event_time=None,
        expires_at=None,
        supersedes_id=None,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def client_and_session() -> tuple[TestClient, Mock]:
    session = Mock()

    def override() -> Generator[Mock, None, None]:
        yield session

    app = create_app()
    app.dependency_overrides[get_db_session] = override
    return TestClient(app), session


def test_typed_response_accepts_only_created_or_unchanged() -> None:
    stored = memory()
    for status in ("created", "unchanged"):
        result = MemoryProposalPromotionResult(
            proposal_id=uuid.uuid4(), promotion_status=status, memory=stored
        )
        dumped = result.model_dump()
        assert dumped["promotion_status"] == status
        assert set(dumped["memory"]) == {
            "id",
            "project_id",
            "content",
            "source",
            "title",
            "summary",
            "memory_type",
            "importance",
            "confidence",
            "status",
            "event_time",
            "expires_at",
            "supersedes_id",
            "created_at",
            "updated_at",
        }
        assert not (
            {"evidence_text", "proposal_hash", "source_chunk_hash", "vector"}
            & set(dumped)
        )
    with pytest.raises(ValidationError):
        MemoryProposalPromotionResult(
            proposal_id=uuid.uuid4(), promotion_status="updated", memory=stored
        )


def test_promote_route_has_no_request_body_or_client_memory_fields(
    client_and_session: tuple[TestClient, Mock],
) -> None:
    client, _ = client_and_session
    operation = client.app.openapi()["paths"][
        "/memory-proposals/{proposal_id}/promote"
    ]["post"]
    assert "requestBody" not in operation


@pytest.mark.parametrize("promotion_status", ["created", "unchanged"])
def test_success_commits_once_and_returns_complete_memory(
    promotion_status: str,
    monkeypatch: pytest.MonkeyPatch,
    client_and_session: tuple[TestClient, Mock],
) -> None:
    client, session = client_and_session
    stored = memory()
    proposal_id = uuid.uuid4()
    monkeypatch.setattr(
        routes.promotion_repository,
        "promote_proposal",
        Mock(
            return_value=repository.PromotionResult(
                proposal_id, promotion_status, stored
            )
        ),
    )
    response = client.post(f"/memory-proposals/{proposal_id}/promote")
    assert response.status_code == 200
    assert response.json()["promotion_status"] == promotion_status
    assert response.json()["memory"]["id"] == str(stored.id)
    session.commit.assert_called_once_with()


def test_exact_promotion_errors_do_not_commit(
    monkeypatch: pytest.MonkeyPatch,
    client_and_session: tuple[TestClient, Mock],
) -> None:
    client, session = client_and_session
    cases = (
        (repository.ProposalNotFoundError, 404, "memory proposal not found"),
        (repository.ProposalNotApprovedError, 409, "memory proposal not approved"),
        (
            repository.ExtractionRunNotCompletedError,
            409,
            "extraction run not completed",
        ),
    )
    for error, status, detail in cases:
        monkeypatch.setattr(
            routes.promotion_repository, "promote_proposal", Mock(side_effect=error)
        )
        response = client.post(f"/memory-proposals/{uuid.uuid4()}/promote")
        assert response.status_code == status
        assert response.json() == {"detail": detail}
    session.commit.assert_not_called()


def test_database_failure_rolls_back_without_details(
    monkeypatch: pytest.MonkeyPatch,
    client_and_session: tuple[TestClient, Mock],
) -> None:
    client, session = client_and_session
    failure = OperationalError("host:5432", {}, Exception("password=secret"))
    monkeypatch.setattr(
        routes.promotion_repository, "promote_proposal", Mock(side_effect=failure)
    )
    response = client.post(f"/memory-proposals/{uuid.uuid4()}/promote")
    assert response.status_code == 503
    assert response.json() == {"detail": "database unavailable"}
    assert "secret" not in response.text
    session.rollback.assert_called_once_with()


def test_repository_maps_proposal_and_provenance_without_committing() -> None:
    proposal_id = uuid.uuid4()
    project_id = uuid.uuid4()
    source_id = uuid.uuid4()
    proposal = SimpleNamespace(
        id=proposal_id,
        memory_id=None,
        review_status="approved",
        project_id=project_id,
        title="Exact title",
        summary="Exact summary",
        content="Exact content",
        memory_type="procedural",
        importance=0.7,
        confidence=0.6,
        source_locator=" page 2 ",
        evidence_char_start=10,
        evidence_char_end=20,
    )
    session = Mock()
    session.execute.return_value.one_or_none.return_value = (
        proposal,
        "completed",
        source_id,
        "Source name",
        "  https://example.test/ref  ",
    )

    def flush() -> None:
        for call in session.add.call_args_list:
            value = call.args[0]
            if isinstance(value, Memory) and value.id is None:
                value.id = uuid.uuid4()

    session.flush.side_effect = flush
    result = repository.promote_proposal(session, proposal_id)
    stored = result.memory
    assert result.promotion_status == "created"
    assert (
        stored.project_id,
        stored.title,
        stored.summary,
        stored.content,
        stored.memory_type,
        stored.importance,
        stored.confidence,
    ) == (
        project_id,
        "Exact title",
        "Exact summary",
        "Exact content",
        "procedural",
        0.7,
        0.6,
    )
    assert stored.source == "https://example.test/ref"
    assert stored.status == "active"
    assert stored.event_time is stored.expires_at is stored.supersedes_id is None
    link = session.add.call_args_list[1].args[0]
    assert link.memory_id == stored.id
    assert link.source_id == source_id
    assert link.source_location == "page 2"
    assert proposal.memory_id == stored.id
    session.commit.assert_not_called()


def test_repository_fallbacks_and_unchanged_path_do_not_write() -> None:
    proposal = SimpleNamespace(
        id=uuid.uuid4(),
        memory_id=None,
        review_status="approved",
        project_id=None,
        title=None,
        summary=None,
        content="Content",
        memory_type="semantic",
        importance=0.5,
        confidence=0.8,
        source_locator="   ",
        evidence_char_start=3,
        evidence_char_end=9,
    )
    session = Mock()
    session.execute.return_value.one_or_none.return_value = (
        proposal,
        "completed",
        uuid.uuid4(),
        "Fallback name",
        "   ",
    )

    def flush() -> None:
        first = session.add.call_args_list[0].args[0]
        if first.id is None:
            first.id = uuid.uuid4()

    session.flush.side_effect = flush
    created = repository.promote_proposal(session, proposal.id)
    assert created.memory.source == "Fallback name"
    assert session.add.call_args_list[1].args[0].source_location == "chars 3-9"

    existing = created.memory
    proposal.memory_id = existing.id
    unchanged_session = Mock()
    unchanged_session.execute.return_value.one_or_none.return_value = (
        proposal,
        "completed",
        uuid.uuid4(),
        "name",
        None,
    )
    unchanged_session.get.return_value = existing
    unchanged = repository.promote_proposal(unchanged_session, proposal.id)
    assert unchanged.promotion_status == "unchanged"
    assert unchanged.memory is existing
    unchanged_session.add.assert_not_called()
    unchanged_session.flush.assert_not_called()
    unchanged_session.commit.assert_not_called()
