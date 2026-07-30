"""PostgreSQL API coverage for read-only Memory similarity detection."""

import uuid
from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db.session import get_engine
from app.main import create_app
from app.models import (
    Memory,
    MemoryEmbedding,
    MemoryProposal,
    MemorySource,
    Project,
    Source,
)
from tests.integration.conftest import verify_connected_test_database


def vector(x: float, y: float) -> list[float]:
    return [x, y, *([0.0] * 1534)]


@pytest.fixture
def similarity_client(
    migrated_test_database: None, test_database_url: str
) -> Generator[TestClient, None, None]:
    verify_connected_test_database(test_database_url)
    with Session(get_engine()) as session:
        session.execute(delete(Memory))
        session.execute(delete(Project))
        session.commit()
    yield TestClient(create_app())
    verify_connected_test_database(test_database_url)
    with Session(get_engine()) as session:
        session.execute(delete(Memory))
        session.execute(delete(Project))
        session.commit()


def add_memory(
    session: Session,
    content: str,
    *,
    project_id: uuid.UUID | None,
    memory_id: uuid.UUID | None = None,
    status: str = "active",
    embedding: list[float] | None = None,
    embedding_provider: str = "fake",
    embedding_model: str = "fixed-1536",
) -> Memory:
    now = datetime(2026, 7, 30, tzinfo=UTC)
    memory = Memory(
        id=memory_id or uuid.uuid4(),
        project_id=project_id,
        content=content,
        status=status,
        created_at=now,
        updated_at=now,
    )
    session.add(memory)
    session.flush()
    if embedding is not None:
        session.add(
            MemoryEmbedding(
                memory_id=memory.id,
                provider=embedding_provider,
                model=embedding_model,
                dimensions=1536,
                embedding=embedding,
                input_hash="a" * 64,
                embedded_at=now,
            )
        )
    return memory


def snapshot(session: Session) -> dict[str, object]:
    rows = session.scalars(select(Memory).order_by(Memory.id)).all()
    embeddings = session.scalars(
        select(MemoryEmbedding).order_by(MemoryEmbedding.id)
    ).all()
    return {
        "memories": [
            (
                row.id,
                row.project_id,
                row.content,
                row.status,
                row.importance,
                row.confidence,
                row.updated_at,
            )
            for row in rows
        ],
        "embeddings": [
            (row.id, row.memory_id, list(row.embedding), row.updated_at)
            for row in embeddings
        ],
        "projects": session.scalar(select(func.count()).select_from(Project)),
        "sources": session.scalar(select(func.count()).select_from(Source)),
        "links": session.scalar(select(func.count()).select_from(MemorySource)),
        "proposals": session.scalar(select(func.count()).select_from(MemoryProposal)),
    }


def test_exact_similar_scope_order_limit_and_no_mutation(
    similarity_client: TestClient,
) -> None:
    low_id = uuid.UUID(int=1)
    high_id = uuid.UUID(int=2)
    with Session(get_engine()) as session:
        project = Project(name="Similarity project")
        other_project = Project(name="Other similarity project")
        session.add_all([project, other_project])
        session.flush()
        target = add_memory(
            session,
            "alpha beta gamma delta",
            project_id=project.id,
        )
        exact_high = add_memory(
            session,
            " alpha\n beta  gamma delta ",
            project_id=project.id,
            memory_id=high_id,
        )
        exact_low = add_memory(
            session,
            "alpha beta gamma delta",
            project_id=project.id,
            memory_id=low_id,
        )
        similar = add_memory(
            session,
            "alpha beta gamma epsilon",
            project_id=project.id,
        )
        add_memory(session, "alpha unrelated words", project_id=project.id)
        add_memory(
            session,
            "alpha beta gamma delta",
            project_id=other_project.id,
        )
        add_memory(
            session,
            "alpha beta gamma delta",
            project_id=project.id,
            status="archived",
        )
        session.commit()
        target_id = target.id
        exact_ids = [exact_low.id, exact_high.id]
        similar_id = similar.id
        before = snapshot(session)

    response = similarity_client.get(f"/memories/{target_id}/similarities")
    assert response.status_code == 200
    body = response.json()
    assert body["target_memory_id"] == str(target_id)
    assert [item["memory_id"] for item in body["candidates"]] == [
        str(item) for item in [*exact_ids, similar_id]
    ]
    assert [item["classification"] for item in body["candidates"]] == [
        "exact_duplicate",
        "exact_duplicate",
        "similar",
    ]
    assert all(item["memory_id"] != str(target_id) for item in body["candidates"])
    assert body["candidates"][2]["lexical_similarity"] == 0.6
    assert body["candidates"][2]["semantic_similarity"] is None
    assert "Jaccard 0.600" in body["candidates"][2]["reason"]
    assert (
        len(
            similarity_client.get(
                f"/memories/{target_id}/similarities", params={"limit": 1}
            ).json()["candidates"]
        )
        == 1
    )
    with Session(get_engine()) as session:
        assert snapshot(session) == before


def test_stored_embeddings_are_optional_and_ties_use_uuid(
    similarity_client: TestClient,
) -> None:
    low_id = uuid.UUID(int=10)
    high_id = uuid.UUID(int=11)
    with Session(get_engine()) as session:
        project = Project(name="Semantic similarity project")
        session.add(project)
        session.flush()
        target = add_memory(
            session,
            "target has unique lexical vocabulary",
            project_id=project.id,
            embedding=vector(1, 0),
        )
        for memory_id in (high_id, low_id):
            add_memory(
                session,
                "entirely different candidate wording",
                project_id=project.id,
                memory_id=memory_id,
                embedding=vector(1, 0),
            )
        session.commit()
        target_id = target.id

    body = similarity_client.get(f"/memories/{target_id}/similarities").json()
    assert [item["memory_id"] for item in body["candidates"]] == [
        str(low_id),
        str(high_id),
    ]
    assert all(item["classification"] == "similar" for item in body["candidates"])
    assert all(item["semantic_similarity"] == 1.0 for item in body["candidates"])


def test_empty_missing_and_validation_responses(similarity_client: TestClient) -> None:
    with Session(get_engine()) as session:
        target = add_memory(session, "standalone memory", project_id=None)
        session.commit()
        target_id = target.id

    response = similarity_client.get(f"/memories/{target_id}/similarities")
    assert response.status_code == 200
    assert response.json() == {
        "target_memory_id": str(target_id),
        "candidates": [],
    }
    missing = similarity_client.get(f"/memories/{uuid.uuid4()}/similarities")
    assert missing.status_code == 404
    assert missing.json() == {"detail": "memory not found"}
    assert (
        similarity_client.get(
            f"/memories/{target_id}/similarities", params={"limit": 0}
        ).status_code
        == 422
    )


def test_exact_and_lexical_recall_beyond_250_unrelated_rows(
    similarity_client: TestClient,
) -> None:
    with Session(get_engine()) as session:
        project = Project(name="Large similarity project")
        session.add(project)
        session.flush()
        target = add_memory(session, "relevant alpha beta gamma", project_id=project.id)
        for index in range(300):
            add_memory(
                session,
                f"noise item {index} filler",
                project_id=project.id,
                memory_id=uuid.UUID(int=1000 + index),
            )
        similar = add_memory(
            session,
            "relevant alpha beta delta",
            project_id=project.id,
            memory_id=uuid.UUID(int=(1 << 128) - 2),
        )
        exact = add_memory(
            session,
            " \trelevant alpha\n beta  gamma ",
            project_id=project.id,
            memory_id=uuid.UUID(int=(1 << 128) - 1),
        )
        session.commit()
        target_id = target.id
        similar_id = similar.id
        exact_id = exact.id

    body = similarity_client.get(f"/memories/{target_id}/similarities").json()
    assert [item["memory_id"] for item in body["candidates"]] == [
        str(exact_id),
        str(similar_id),
    ]


def test_ascii_normalization_and_nonbreaking_space_remains_significant(
    similarity_client: TestClient,
) -> None:
    with Session(get_engine()) as session:
        target = add_memory(session, "Alpha beta gamma", project_id=None)
        ascii_whitespace = add_memory(
            session, " \tAlpha\n beta\r\f\v gamma ", project_id=None
        )
        nonbreaking = add_memory(session, "Alpha\u00a0beta gamma", project_id=None)
        session.commit()
        target_id = target.id
        ascii_whitespace_id = ascii_whitespace.id
        nonbreaking_id = nonbreaking.id

    candidates = similarity_client.get(f"/memories/{target_id}/similarities").json()[
        "candidates"
    ]
    classifications = {item["memory_id"]: item["classification"] for item in candidates}
    assert classifications[str(ascii_whitespace_id)] == "exact_duplicate"
    assert classifications.get(str(nonbreaking_id)) != "exact_duplicate"


def test_embedding_compatibility_and_undefined_cosine_are_safe(
    similarity_client: TestClient,
) -> None:
    with Session(get_engine()) as session:
        project = Project(name="Compatible embedding project")
        session.add(project)
        session.flush()
        target = add_memory(
            session,
            "target unique words here",
            project_id=project.id,
            embedding=vector(1, 0),
        )
        compatible = add_memory(
            session,
            "different compatible wording",
            project_id=project.id,
            embedding=vector(1, 0),
        )
        wrong_provider = add_memory(
            session,
            "different provider wording",
            project_id=project.id,
            embedding=vector(1, 0),
            embedding_provider="other",
        )
        wrong_model = add_memory(
            session,
            "different model wording",
            project_id=project.id,
            embedding=vector(1, 0),
            embedding_model="other-1536",
        )
        zero_vector = add_memory(
            session,
            "zero vector wording",
            project_id=project.id,
            embedding=vector(0, 0),
        )
        session.commit()
        target_id = target.id
        compatible_id = compatible.id
        wrong_provider_id = wrong_provider.id
        wrong_model_id = wrong_model.id
        zero_vector_id = zero_vector.id

    response = similarity_client.get(f"/memories/{target_id}/similarities")
    assert response.status_code == 200
    ids = {item["memory_id"] for item in response.json()["candidates"]}
    assert str(compatible_id) in ids
    assert str(wrong_provider_id) not in ids
    assert str(wrong_model_id) not in ids
    assert str(zero_vector_id) not in ids


def test_assigned_and_unassigned_scopes_are_bidirectionally_isolated(
    similarity_client: TestClient,
) -> None:
    with Session(get_engine()) as session:
        project = Project(name="Scope project")
        session.add(project)
        session.flush()
        assigned_target = add_memory(session, "scope exact text", project_id=project.id)
        assigned_match = add_memory(session, "scope exact text", project_id=project.id)
        unassigned_target = add_memory(session, "scope exact text", project_id=None)
        unassigned_match = add_memory(session, "scope exact text", project_id=None)
        session.commit()
        assigned_target_id = assigned_target.id
        assigned_match_id = assigned_match.id
        unassigned_target_id = unassigned_target.id
        unassigned_match_id = unassigned_match.id

    assigned = similarity_client.get(
        f"/memories/{assigned_target_id}/similarities"
    ).json()["candidates"]
    assert [item["memory_id"] for item in assigned] == [str(assigned_match_id)]
    unassigned = similarity_client.get(
        f"/memories/{unassigned_target_id}/similarities"
    ).json()["candidates"]
    assert [item["memory_id"] for item in unassigned] == [str(unassigned_match_id)]
