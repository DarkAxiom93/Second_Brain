"""PostgreSQL/API coverage for evidence-backed Memory answers."""

from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.answers.provider import AnswerProviderResult
from app.api.routes import answers as answer_routes
from app.db.session import get_engine
from app.main import create_app
from app.models import Memory, MemoryEmbedding, Project
from tests.integration.conftest import verify_connected_test_database


def vector() -> list[float]:
    return [1.0, *([0.0] * 1535)]


class FakeEmbeddingProvider:
    def __init__(self) -> None:
        self.inputs: list[str] = []

    def embed(self, text: str) -> list[float]:
        self.inputs.append(text)
        return vector()


class FakeAnswerProvider:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def answer(self, *, query: str, evidence_context: str) -> AnswerProviderResult:
        self.calls.append((query, evidence_context))
        return AnswerProviderResult(
            answer_status="answered",
            answer="Evidence-backed answer",
            citation_labels=["M1"],
        )


@pytest.fixture
def answer_client(
    migrated_test_database: None,
    test_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[
    tuple[TestClient, FakeEmbeddingProvider, FakeAnswerProvider], None, None
]:
    verify_connected_test_database(test_database_url)
    with Session(get_engine()) as session:
        session.execute(delete(Memory))
        session.execute(delete(Project))
        session.commit()
    embedding = FakeEmbeddingProvider()
    answer = FakeAnswerProvider()
    monkeypatch.setattr(answer_routes, "get_embedding_provider", lambda: embedding)
    monkeypatch.setattr(answer_routes, "get_answer_provider", lambda: answer)
    yield TestClient(create_app()), embedding, answer
    verify_connected_test_database(test_database_url)
    with Session(get_engine()) as session:
        session.execute(delete(Memory))
        session.execute(delete(Project))
        session.commit()


def add_memory(
    session: Session,
    *,
    content: str,
    project_id=None,
    status: str = "active",
    embedded: bool = True,
) -> Memory:
    now = datetime.now(UTC)
    memory = Memory(
        content=content,
        project_id=project_id,
        status=status,
        importance=0.5,
        confidence=1.0,
        created_at=now,
        updated_at=now,
    )
    session.add(memory)
    session.flush()
    if embedded:
        session.add(
            MemoryEmbedding(
                memory_id=memory.id,
                provider="fake",
                model="fake",
                dimensions=1536,
                embedding=vector(),
                input_hash="a" * 64,
                embedded_at=now,
            )
        )
    return memory


def test_no_evidence_is_200_and_resolves_no_provider(
    answer_client: tuple[TestClient, FakeEmbeddingProvider, FakeAnswerProvider],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, embedding, answer = answer_client
    monkeypatch.setattr(
        answer_routes,
        "get_answer_provider",
        lambda: pytest.fail("answer provider must not resolve"),
    )
    response = client.post(
        "/answers", json={"query": "absent", "search_mode": "lexical"}
    )
    assert response.status_code == 200
    assert response.json()["answer_status"] == "insufficient_evidence"
    assert response.json()["citations"] == []
    assert embedding.inputs == []
    assert answer.calls == []


@pytest.mark.parametrize("mode", ["lexical", "semantic", "hybrid"])
def test_modes_project_active_scores_and_read_only(
    answer_client: tuple[TestClient, FakeEmbeddingProvider, FakeAnswerProvider],
    mode: str,
) -> None:
    client, embedding, answer = answer_client
    with Session(get_engine()) as session:
        project = Project(name=f"Answer {mode}")
        other = Project(name=f"Other {mode}")
        session.add_all([project, other])
        session.flush()
        project_id = project.id
        expected = add_memory(
            session, content="unique answer needle", project_id=project.id
        )
        add_memory(session, content="unique answer needle", project_id=other.id)
        for status in ("superseded", "expired", "invalid", "archived"):
            add_memory(
                session,
                content="unique answer needle",
                project_id=project.id,
                status=status,
            )
        session.commit()
        expected_id = str(expected.id)
        before = session.scalar(select(func.count()).select_from(Memory))
    response = client.post(
        "/answers",
        json={
            "query": "unique answer needle",
            "search_mode": mode,
            "project_id": str(project_id),
            "limit": 10,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["answer_status"] == "answered"
    assert [item["memory"]["id"] for item in body["citations"]] == [expected_id]
    citation = body["citations"][0]
    assert (citation["lexical_score"] is not None) == (mode != "semantic")
    assert (citation["semantic_score"] is not None) == (mode != "lexical")
    assert len(answer.calls) == 1
    assert len(embedding.inputs) == (0 if mode == "lexical" else 1)
    with Session(get_engine()) as session:
        assert session.scalar(select(func.count()).select_from(Memory)) == before
        assert session.scalar(select(func.count()).select_from(MemoryEmbedding)) == 6
