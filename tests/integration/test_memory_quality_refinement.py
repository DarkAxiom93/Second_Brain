"""PostgreSQL behavior tests for explicit Memory quality refinement."""

import uuid
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.db.session import get_engine
from app.main import create_app
from app.models.memory import Memory
from app.models.project import Project
from tests.integration.conftest import verify_connected_test_database


@pytest.fixture(autouse=True)
def clean_rows(
    migrated_test_database: None, test_database_url: str
) -> Generator[None, None, None]:
    verify_connected_test_database(test_database_url)
    with Session(get_engine()) as session:
        session.execute(delete(Memory))
        session.execute(delete(Project))
        session.commit()
    yield
    with Session(get_engine()) as session:
        session.execute(delete(Memory))
        session.execute(delete(Project))
        session.commit()


def create_memory(
    client: TestClient, content: str, **values: object
) -> dict[str, object]:
    response = client.post("/memories", json={"content": content, **values})
    assert response.status_code == 201
    return response.json()


def refine(memory_id: object, payload: dict[str, float]):
    return TestClient(create_app()).post(f"/memories/{memory_id}/quality", json=payload)


def test_partial_boundaries_atomic_pair_preservation_retrieval_and_filters() -> None:
    client = TestClient(create_app())
    original = create_memory(
        client,
        "quality fact",
        source="manual",
        title="Title",
        summary="Summary",
        memory_type="decision",
        confidence=0.4,
        importance=0.6,
    )
    confidence = refine(original["id"], {"confidence": 0.0}).json()
    assert confidence["refinement_status"] == "updated"
    assert confidence["memory"]["confidence"] == 0.0
    assert confidence["memory"]["importance"] == 0.6
    importance = refine(original["id"], {"importance": 1.0}).json()
    assert importance["memory"]["confidence"] == 0.0
    assert importance["memory"]["importance"] == 1.0
    pair = refine(original["id"], {"confidence": 0.25, "importance": 0.75}).json()
    assert pair["refinement_status"] == "updated"
    assert (pair["memory"]["confidence"], pair["memory"]["importance"]) == (
        0.25,
        0.75,
    )
    for field in (
        "id",
        "project_id",
        "content",
        "source",
        "title",
        "summary",
        "memory_type",
        "status",
        "event_time",
        "expires_at",
        "supersedes_id",
        "created_at",
    ):
        assert pair["memory"][field] == original[field]
    retrieved = client.get(f"/memories/{original['id']}").json()
    assert (retrieved["confidence"], retrieved["importance"]) == (0.25, 0.75)
    filtered = client.get(
        "/memories", params={"confidence_min": 0.25, "importance_max": 0.75}
    ).json()
    assert [row["id"] for row in filtered] == [original["id"]]


def test_unchanged_preserves_updated_at_and_ineligible_and_missing() -> None:
    client = TestClient(create_app())
    row = create_memory(client, "same", confidence=0.3, importance=0.7)
    response = refine(row["id"], {"confidence": 0.3, "importance": 0.7})
    assert response.status_code == 200
    assert response.json()["refinement_status"] == "unchanged"
    assert response.json()["memory"]["updated_at"] == row["updated_at"]
    missing = refine(uuid.uuid4(), {"confidence": 0.3})
    assert missing.status_code == 404
    for status in ("superseded", "expired", "invalid", "archived"):
        inactive = create_memory(client, status, status=status)
        rejected = refine(inactive["id"], {"importance": 0.2})
        assert rejected.status_code == 409
        assert rejected.json() == {
            "detail": "memory not eligible for quality refinement"
        }


def test_concurrent_identical_and_complete_pairs_serialize_without_mixing() -> None:
    client = TestClient(create_app())
    identical = create_memory(client, "identical", confidence=0.1, importance=0.1)
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(
                lambda _: refine(
                    identical["id"], {"confidence": 0.8, "importance": 0.9}
                ).json()["refinement_status"],
                range(2),
            )
        )
    assert sorted(results) == ["unchanged", "updated"]

    competing = create_memory(client, "competing", confidence=0.1, importance=0.1)
    pairs = (
        {"confidence": 0.2, "importance": 0.3},
        {"confidence": 0.8, "importance": 0.9},
    )
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(
            executor.map(lambda pair: refine(competing["id"], pair), pairs)
        )
    assert all(response.status_code == 200 for response in responses)
    assert all(
        (body["memory"]["confidence"], body["memory"]["importance"])
        in {(0.2, 0.3), (0.8, 0.9)}
        for body in (response.json() for response in responses)
    )
    final = client.get(f"/memories/{competing['id']}").json()
    assert (final["confidence"], final["importance"]) in {(0.2, 0.3), (0.8, 0.9)}


def test_controlled_database_failure_rolls_back_both_values() -> None:
    client = TestClient(create_app())
    row = create_memory(client, "rollback", confidence=0.2, importance=0.3)
    engine = get_engine()
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE FUNCTION reject_quality_test() RETURNS trigger "
                "LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'controlled'; END $$"
            )
        )
        connection.execute(
            text(
                "CREATE TRIGGER reject_quality_test BEFORE UPDATE ON memories "
                "FOR EACH ROW EXECUTE FUNCTION reject_quality_test()"
            )
        )
    try:
        response = refine(row["id"], {"confidence": 0.8, "importance": 0.9})
        assert response.status_code == 503
        with Session(engine) as session:
            stored = session.scalar(
                select(Memory).where(Memory.id == uuid.UUID(str(row["id"])))
            )
            assert stored is not None
            assert (stored.confidence, stored.importance) == (0.2, 0.3)
    finally:
        with engine.begin() as connection:
            connection.execute(text("DROP TRIGGER reject_quality_test ON memories"))
            connection.execute(text("DROP FUNCTION reject_quality_test()"))
