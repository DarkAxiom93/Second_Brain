"""Unit coverage for proposal review schemas and routes (no database)."""

import uuid
from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError

from app.api.routes import memory_proposals as routes
from app.db.dependencies import get_db_session
from app.main import create_app
from app.repositories.memory_proposals import ProposalView, ReviewTransition
from app.schemas.memory_proposal import (
    ApproveMemoryProposal,
    MemoryProposalDetail,
    MemoryProposalFilters,
    MemoryProposalListItem,
    MemoryProposalReviewResult,
    RejectMemoryProposal,
)


@pytest.fixture
def client_and_session() -> tuple[TestClient, Mock]:
    session = Mock()

    def override() -> Generator[Mock, None, None]:
        yield session

    app = create_app()
    app.dependency_overrides[get_db_session] = override
    return TestClient(app), session


def proposal_view(**changes: object) -> ProposalView:
    now = datetime.now(UTC)
    values: dict[str, object] = {
        "id": uuid.uuid4(),
        "run_id": uuid.uuid4(),
        "source_id": uuid.uuid4(),
        "document_id": uuid.uuid4(),
        "source_chunk_id": uuid.uuid4(),
        "project_id": None,
        "proposal_index": 0,
        "title": "Title",
        "summary": "Summary",
        "content": "Content",
        "memory_type": "semantic",
        "importance": 0.5,
        "confidence": 0.8,
        "source_locator": "chars 0-8",
        "review_status": "pending",
        "review_note": None,
        "reviewed_at": None,
        "memory_id": None,
        "created_at": now,
        "updated_at": now,
        "source_type": "document",
        "source_name": "Notes",
        "original_filename": "notes.txt",
        "run_provider": "test",
        "run_model": "test-model",
        "run_prompt_version": "v1",
        "source_chunk_hash": "a" * 64,
        "evidence_text": "Evidence",
        "evidence_char_start": 0,
        "evidence_char_end": 8,
        "proposal_hash": "b" * 64,
        "run_status": "completed",
        "source_chunk_available": True,
    }
    values.update(changes)
    return ProposalView(values)


def test_filter_defaults_and_validation() -> None:
    assert MemoryProposalFilters().review_status == "pending"
    assert MemoryProposalFilters(review_status="all").review_status == "all"
    for memory_type in (
        "working",
        "episodic",
        "semantic",
        "decision",
        "procedural",
        "preference",
        "temporary",
    ):
        assert MemoryProposalFilters(memory_type=memory_type).memory_type == memory_type
    MemoryProposalFilters(
        importance_min=0, importance_max=1, confidence_min=0, confidence_max=1
    )
    for values in (
        {"review_status": "bad"},
        {"memory_type": "bad"},
        {"importance_min": -0.1},
        {"confidence_max": 1.1},
        {"importance_min": 0.8, "importance_max": 0.2},
        {"confidence_min": 0.8, "confidence_max": 0.2},
        {"limit": 0},
        {"limit": 101},
        {"offset": -1},
    ):
        with pytest.raises(ValidationError):
            MemoryProposalFilters(**values)  # type: ignore[arg-type]


def test_review_note_normalization_and_schema_boundaries() -> None:
    assert ApproveMemoryProposal(review_note=" note ").review_note == "note"
    assert ApproveMemoryProposal(review_note="  ").review_note is None
    assert RejectMemoryProposal(review_note=" reason ").review_note == "reason"
    for model, value in (
        (RejectMemoryProposal, " "),
        (ApproveMemoryProposal, "x" * 2001),
    ):
        with pytest.raises(ValidationError):
            model(review_note=value)  # type: ignore[call-arg]
    assert "review_status" not in ApproveMemoryProposal.model_fields
    assert "memory_id" not in RejectMemoryProposal.model_fields


def test_list_and_detail_schema_exposure() -> None:
    view = proposal_view()
    listed = MemoryProposalListItem.model_validate(view).model_dump()
    assert "evidence_text" not in listed
    assert "source_chunk_hash" not in listed
    detail = MemoryProposalDetail.model_validate(view).model_dump()
    assert detail["evidence_text"] == "Evidence"
    reviewed = MemoryProposalReviewResult(**view.values, transition_status="updated")
    assert reviewed.transition_status == "updated"


def test_list_passes_all_filters_and_returns_bare_array(
    monkeypatch: pytest.MonkeyPatch, client_and_session: tuple[TestClient, Mock]
) -> None:
    client, session = client_and_session
    call = Mock(return_value=[])
    monkeypatch.setattr(routes.repository, "list_proposals", call)
    ids = [uuid.uuid4() for _ in range(4)]
    response = client.get(
        "/memory-proposals?review_status=all&run_id={}&source_id={}&document_id={}"
        "&project_id={}&memory_type=decision&importance_min=0&importance_max=1"
        "&confidence_min=0.2&confidence_max=0.9&limit=10&offset=2".format(*ids)
    )
    assert response.status_code == 200 and response.json() == []
    filters = call.call_args.args[1]
    assert call.call_args.args[0] is session
    assert filters.model_dump()["run_id"] == ids[0]
    assert filters.model_dump()["offset"] == 2


def test_detail_null_chunk_and_exact_not_found(
    monkeypatch: pytest.MonkeyPatch, client_and_session: tuple[TestClient, Mock]
) -> None:
    client, _ = client_and_session
    view = proposal_view(source_chunk_id=None, source_chunk_available=False)
    monkeypatch.setattr(routes.repository, "get_proposal", Mock(return_value=view))
    response = client.get(f"/memory-proposals/{view.id}")
    assert response.status_code == 200
    assert response.json()["source_chunk_available"] is False
    routes.repository.get_proposal.return_value = None  # type: ignore[attr-defined]
    response = client.get(f"/memory-proposals/{uuid.uuid4()}")
    assert response.status_code == 404
    assert response.json() == {"detail": "memory proposal not found"}


@pytest.mark.parametrize("decision", ["approve", "reject"])
def test_successful_review_commits_once(
    decision: str,
    monkeypatch: pytest.MonkeyPatch,
    client_and_session: tuple[TestClient, Mock],
) -> None:
    client, session = client_and_session
    view = proposal_view(
        review_status="approved" if decision == "approve" else "rejected"
    )
    call = Mock(return_value=ReviewTransition(view, "updated"))
    monkeypatch.setattr(routes.repository, "review_proposal", call)
    body = {"review_note": " note "} if decision == "reject" else {}
    response = client.post(f"/memory-proposals/{view.id}/{decision}", json=body)
    assert response.status_code == 200
    assert response.json()["transition_status"] == "updated"
    session.commit.assert_called_once_with()
    assert call.call_args.args[3] == ("note" if decision == "reject" else None)


def test_database_failures_are_generic_and_rollback_review(
    monkeypatch: pytest.MonkeyPatch, client_and_session: tuple[TestClient, Mock]
) -> None:
    client, session = client_and_session
    failure = OperationalError("SQL host:5432", {}, Exception("password=secret"))
    monkeypatch.setattr(routes.repository, "list_proposals", Mock(side_effect=failure))
    response = client.get("/memory-proposals")
    assert response.status_code == 503 and response.json() == {
        "detail": "database unavailable"
    }
    monkeypatch.setattr(routes.repository, "review_proposal", Mock(side_effect=failure))
    response = client.post(f"/memory-proposals/{uuid.uuid4()}/approve", json={})
    assert response.status_code == 503 and "secret" not in response.text
    session.rollback.assert_called_once_with()


def test_exact_review_conflicts(
    monkeypatch: pytest.MonkeyPatch, client_and_session: tuple[TestClient, Mock]
) -> None:
    client, session = client_and_session
    cases = (
        (routes.repository.ProposalNotFoundError, 404, "memory proposal not found"),
        (
            routes.repository.ProposalAlreadyReviewedError,
            409,
            "memory proposal already reviewed",
        ),
        (
            routes.repository.ExtractionRunNotCompletedError,
            409,
            "extraction run not completed",
        ),
    )
    for error, code, detail in cases:
        monkeypatch.setattr(
            routes.repository, "review_proposal", Mock(side_effect=error)
        )
        response = client.post(f"/memory-proposals/{uuid.uuid4()}/approve", json={})
        assert response.status_code == code and response.json() == {"detail": detail}
    session.commit.assert_not_called()


def test_only_approved_review_routes_added(
    client_and_session: tuple[TestClient, Mock],
) -> None:
    client, _ = client_and_session
    paths = client.app.openapi()["paths"]
    assert set(path for path in paths if path.startswith("/memory-proposals")) == {
        "/memory-proposals",
        "/memory-proposals/{proposal_id}",
        "/memory-proposals/{proposal_id}/approve",
        "/memory-proposals/{proposal_id}/reject",
    }
