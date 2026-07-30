"""PostgreSQL integration tests for explicit Memory supersession."""

import uuid
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
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
    verify_connected_test_database(test_database_url)
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


def supersede(
    client: TestClient, older: dict[str, object], replacement: dict[str, object]
):
    return client.post(
        f"/memories/{older['id']}/supersede",
        json={"replacement_memory_id": replacement["id"]},
    )


def test_success_preserves_fields_and_repeat_is_timestamp_stable() -> None:
    client = TestClient(create_app())
    project = client.post("/projects", json={"name": "Supersession"}).json()
    event_time = datetime(2026, 1, 2, tzinfo=UTC).isoformat()
    older = create_memory(
        client,
        "old fact",
        project_id=project["id"],
        source="manual",
        title="Old",
        summary="Old summary",
        memory_type="decision",
        importance=0.8,
        confidence=0.7,
        event_time=event_time,
    )
    replacement = create_memory(
        client,
        "new fact",
        project_id=project["id"],
        source="review",
        title="New",
        summary="New summary",
        memory_type="semantic",
        importance=0.9,
        confidence=0.95,
    )
    result = supersede(client, older, replacement)
    assert result.status_code == 200
    body = result.json()
    assert body["supersession_status"] == "updated"
    assert body["superseded_memory"]["status"] == "superseded"
    assert body["replacement_memory"]["status"] == "active"
    assert body["replacement_memory"]["supersedes_id"] == older["id"]
    for field in (
        "project_id",
        "content",
        "source",
        "title",
        "summary",
        "memory_type",
        "importance",
        "confidence",
        "event_time",
        "expires_at",
        "created_at",
    ):
        assert body["superseded_memory"][field] == older[field]
        assert body["replacement_memory"][field] == replacement[field]

    timestamps = (
        body["superseded_memory"]["updated_at"],
        body["replacement_memory"]["updated_at"],
    )
    repeated = supersede(client, older, replacement)
    assert repeated.status_code == 200
    assert repeated.json()["supersession_status"] == "unchanged"
    assert (
        repeated.json()["superseded_memory"]["updated_at"],
        repeated.json()["replacement_memory"]["updated_at"],
    ) == timestamps


@pytest.mark.parametrize(
    ("which", "detail"),
    [
        ("older", "older memory not found"),
        ("replacement", "replacement memory not found"),
    ],
)
def test_missing_memories(which: str, detail: str) -> None:
    client = TestClient(create_app())
    existing = create_memory(client, "existing")
    older_id = uuid.uuid4() if which == "older" else existing["id"]
    replacement_id = uuid.uuid4() if which == "replacement" else existing["id"]
    response = client.post(
        f"/memories/{older_id}/supersede",
        json={"replacement_memory_id": str(replacement_id)},
    )
    assert response.status_code == 404
    assert response.json() == {"detail": detail}


def test_self_scope_inactive_and_competing_conflicts() -> None:
    client = TestClient(create_app())
    first = create_memory(client, "first")
    self_response = supersede(client, first, first)
    assert self_response.status_code == 409
    assert self_response.json() == {"detail": "memory cannot supersede itself"}

    project = client.post("/projects", json={"name": "Assigned"}).json()
    assigned = create_memory(client, "assigned", project_id=project["id"])
    assert supersede(client, first, assigned).json() == {
        "detail": "memory project scope mismatch"
    }

    inactive = create_memory(client, "inactive", status="archived")
    assert supersede(client, first, inactive).json() == {
        "detail": "memory is not eligible for superseding"
    }

    predecessor = create_memory(client, "predecessor")
    linked = create_memory(client, "linked", supersedes_id=predecessor["id"])
    assert supersede(client, first, linked).json() == {
        "detail": "replacement memory already has a predecessor"
    }

    winner = create_memory(client, "winner")
    assert supersede(client, first, winner).status_code == 200
    loser = create_memory(client, "loser")
    assert supersede(client, first, loser).json() == {
        "detail": "older memory already has a replacement"
    }


def test_valid_chain_and_direct_and_indirect_cycles() -> None:
    client = TestClient(create_app())
    a = create_memory(client, "a")
    b = create_memory(client, "b")
    c = create_memory(client, "c")
    assert supersede(client, a, b).json()["supersession_status"] == "updated"
    assert supersede(client, b, c).json()["supersession_status"] == "updated"

    direct_a = create_memory(client, "direct a")
    direct_b = create_memory(client, "direct b", supersedes_id=direct_a["id"])
    direct = supersede(client, direct_b, direct_a)
    assert direct.status_code == 409
    assert direct.json() == {"detail": "memory supersession would create a cycle"}

    indirect_a = create_memory(client, "indirect a")
    indirect_b = create_memory(client, "indirect b", supersedes_id=indirect_a["id"])
    indirect_c = create_memory(client, "indirect c", supersedes_id=indirect_b["id"])
    indirect = supersede(client, indirect_c, indirect_a)
    assert indirect.status_code == 409
    assert indirect.json() == {"detail": "memory supersession would create a cycle"}


def test_concurrent_identical_requests_are_updated_then_unchanged() -> None:
    client = TestClient(create_app())
    older = create_memory(client, "older")
    replacement = create_memory(client, "replacement")

    def request() -> tuple[int, str]:
        response = supersede(TestClient(create_app()), older, replacement)
        return response.status_code, response.json().get("supersession_status", "")

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: request(), range(2)))
    assert sorted(results) == [(200, "unchanged"), (200, "updated")]


def test_concurrent_competing_requests_have_one_winner() -> None:
    client = TestClient(create_app())
    older = create_memory(client, "older")
    replacements = [create_memory(client, f"replacement {index}") for index in range(2)]

    def request(replacement: dict[str, object]) -> int:
        return supersede(TestClient(create_app()), older, replacement).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(executor.map(request, replacements))
    assert sorted(statuses) == [200, 409]
    with Session(get_engine()) as session:
        stored = session.scalars(
            select(Memory).where(Memory.supersedes_id == uuid.UUID(str(older["id"])))
        ).all()
        assert len(stored) == 1
