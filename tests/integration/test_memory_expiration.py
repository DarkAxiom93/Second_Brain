"""PostgreSQL behavior tests for explicit Memory expiration."""

import uuid
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

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


def expire(client: TestClient, memory_id: object):
    return client.post(f"/memories/{memory_id}/expire")


@pytest.mark.parametrize("kind", ["null", "future", "past"])
def test_timestamp_rules_preservation_retrieval_and_filtering(kind: str) -> None:
    client = TestClient(create_app())
    project = client.post("/projects", json={"name": f"Expiration {kind}"}).json()
    now = datetime.now(UTC)
    supplied = None
    if kind == "future":
        supplied = now + timedelta(days=2)
    elif kind == "past":
        supplied = now - timedelta(days=2)
    original = create_memory(
        client,
        "fact",
        project_id=project["id"],
        source="manual",
        title="Title",
        summary="Summary",
        memory_type="decision",
        importance=0.8,
        confidence=0.7,
        event_time=(now - timedelta(days=4)).isoformat(),
        **({"expires_at": supplied.isoformat()} if supplied else {}),
    )
    response = expire(client, original["id"])
    assert response.status_code == 200
    body = response.json()
    assert body["expiration_status"] == "updated"
    assert body["memory"]["status"] == "expired"
    actual = datetime.fromisoformat(body["memory"]["expires_at"])
    if kind == "past":
        assert actual == supplied
    else:
        assert now <= actual <= datetime.now(UTC)
    for field in (
        "id",
        "project_id",
        "content",
        "source",
        "title",
        "summary",
        "memory_type",
        "importance",
        "confidence",
        "event_time",
        "supersedes_id",
        "created_at",
    ):
        assert body["memory"][field] == original[field]
    repeated = expire(client, original["id"])
    assert repeated.json()["expiration_status"] == "unchanged"
    assert repeated.json()["memory"]["expires_at"] == body["memory"]["expires_at"]
    assert repeated.json()["memory"]["updated_at"] == body["memory"]["updated_at"]
    assert client.get(f"/memories/{original['id']}").json()["status"] == "expired"
    filtered = client.get("/memories", params={"status": "expired"}).json()
    assert [row["id"] for row in filtered] == [original["id"]]
    similarity = client.get(f"/memories/{original['id']}/similarities")
    assert similarity.status_code == 200
    assert similarity.json()["candidates"] == []
    assert client.get(f"/memories/{original['id']}/contradictions").status_code == 404


def test_missing_ineligible_inconsistent_and_no_automatic_expiration() -> None:
    client = TestClient(create_app())
    missing = expire(client, uuid.uuid4())
    assert missing.status_code == 404 and missing.json() == {
        "detail": "memory not found"
    }
    for status in ("superseded", "invalid", "archived"):
        row = create_memory(client, status, status=status)
        response = expire(client, row["id"])
        assert response.status_code == 409
        assert response.json() == {"detail": "memory not eligible for expiration"}
    scheduled = create_memory(
        client,
        "scheduled",
        expires_at=(datetime.now(UTC) - timedelta(days=1)).isoformat(),
    )
    assert client.get(f"/memories/{scheduled['id']}").json()["status"] == "active"
    with get_engine().begin() as connection:
        inconsistent_id = uuid.uuid4()
        connection.execute(
            text(
                "INSERT INTO memories (id, content, status) "
                "VALUES (:id, 'bad', 'expired')"
            ),
            {"id": inconsistent_id},
        )
    inconsistent = expire(client, inconsistent_id)
    assert inconsistent.status_code == 409
    assert inconsistent.json() == {"detail": "memory expiration state is inconsistent"}


def test_concurrent_requests_have_one_update_and_stable_timestamp() -> None:
    client = TestClient(create_app())
    row = create_memory(client, "concurrent")

    def request() -> tuple[str, str]:
        body = expire(TestClient(create_app()), row["id"]).json()
        return body["expiration_status"], body["memory"]["expires_at"]

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: request(), range(2)))
    assert sorted(status for status, _ in results) == ["unchanged", "updated"]
    assert len({timestamp for _, timestamp in results}) == 1


def test_real_database_failure_rolls_back_transition() -> None:
    client = TestClient(create_app())
    row = create_memory(client, "rollback")
    engine = get_engine()
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE FUNCTION reject_expiration_test() RETURNS trigger "
                "LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'controlled'; END $$"
            )
        )
        connection.execute(
            text(
                "CREATE TRIGGER reject_expiration_test BEFORE UPDATE ON memories "
                "FOR EACH ROW EXECUTE FUNCTION reject_expiration_test()"
            )
        )
    try:
        response = expire(client, row["id"])
        assert response.status_code == 503
        assert response.json() == {"detail": "database unavailable"}
        with Session(engine) as session:
            stored = session.scalar(
                select(Memory).where(Memory.id == uuid.UUID(str(row["id"])))
            )
            assert stored is not None
            assert stored.status == "active" and stored.expires_at is None
    finally:
        with engine.begin() as connection:
            connection.execute(text("DROP TRIGGER reject_expiration_test ON memories"))
            connection.execute(text("DROP FUNCTION reject_expiration_test()"))


def test_expired_candidate_is_excluded_and_supersession_is_unchanged() -> None:
    client = TestClient(create_app())
    target = create_memory(client, "same fact")
    candidate = create_memory(client, "same fact")
    assert expire(client, candidate["id"]).status_code == 200
    assert (
        client.get(f"/memories/{target['id']}/similarities").json()["candidates"] == []
    )
    older = create_memory(client, "older")
    replacement = create_memory(client, "replacement")
    response = client.post(
        f"/memories/{older['id']}/supersede",
        json={"replacement_memory_id": replacement["id"]},
    )
    assert response.status_code == 200
    assert response.json()["supersession_status"] == "updated"
