"""PostgreSQL integration tests for Memory endpoints."""

import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db.session import get_engine
from app.main import create_app
from app.models.memory import Memory
from app.models.project import Project
from tests.integration.conftest import verify_connected_test_database


@pytest.fixture(autouse=True)
def clean_memory_endpoint_rows(
    migrated_test_database: None,
    test_database_url: str,
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


def test_create_unassigned_and_assigned_memories_with_exact_fields() -> None:
    client = TestClient(create_app())
    unassigned = client.post(
        "/memories", json={"content": "  fact  ", "source": "  note  "}
    )
    project = client.post("/projects", json={"name": "Pure Axiom"})
    assigned = client.post(
        "/memories",
        json={"project_id": project.json()["id"], "content": "fact"},
    )
    assert unassigned.status_code == assigned.status_code == 201
    assert unassigned.json()["project_id"] is None
    assert unassigned.json()["content"] == "fact"
    assert unassigned.json()["source"] == "note"
    assert assigned.json()["project_id"] == project.json()["id"]
    expected = {
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
    assert set(unassigned.json()) == expected
    assert unassigned.json()["memory_type"] == "semantic"
    assert unassigned.json()["importance"] == 0.5
    assert unassigned.json()["confidence"] == 1.0
    assert unassigned.json()["status"] == "active"
    for field in ("created_at", "updated_at"):
        assert datetime.fromisoformat(unassigned.json()[field]).tzinfo is not None


def test_unknown_project_returns_404_and_inserts_nothing() -> None:
    response = TestClient(create_app()).post(
        "/memories",
        json={"project_id": str(uuid.uuid4()), "content": "fact"},
    )
    with Session(get_engine()) as session:
        count = session.scalar(select(func.count()).select_from(Memory))
    assert response.status_code == 404
    assert response.json() == {"detail": "project not found"}
    assert count == 0


def test_invalid_input_returns_422_and_inserts_nothing() -> None:
    response = TestClient(create_app()).post("/memories", json={"content": "   "})
    with Session(get_engine()) as session:
        count = session.scalar(select(func.count()).select_from(Memory))
    assert response.status_code == 422
    assert count == 0


def test_full_metadata_and_superseding_persist_without_automatic_status_change() -> (
    None
):
    client = TestClient(create_app())
    older = client.post("/memories", json={"content": "older"}).json()
    event_time = datetime(2026, 2, 3, 4, 5, tzinfo=UTC)
    expires_at = datetime(2027, 2, 3, 4, 5, tzinfo=UTC)
    payload = {
        "content": "newer",
        "source": "legacy",
        "title": " Title ",
        "summary": " Summary ",
        "memory_type": "decision",
        "importance": 0.0,
        "confidence": 1.0,
        "status": "archived",
        "event_time": event_time.isoformat(),
        "expires_at": expires_at.isoformat(),
        "supersedes_id": older["id"],
    }
    response = client.post("/memories", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Title"
    assert body["summary"] == "Summary"
    assert body["memory_type"] == "decision"
    assert body["importance"] == 0.0
    assert body["confidence"] == 1.0
    assert body["status"] == "archived"
    assert body["supersedes_id"] == older["id"]
    for field, expected in (("event_time", event_time), ("expires_at", expires_at)):
        parsed = datetime.fromisoformat(body[field])
        assert parsed.tzinfo is not None
        assert parsed == expected
    assert client.get(f"/memories/{older['id']}").json()["status"] == "active"
    assert client.get(f"/memories/{body['id']}").json() == body
    assert body in client.get("/memories").json()

    with Session(get_engine()) as session:
        stored = session.get(Memory, uuid.UUID(body["id"]))
        assert stored is not None
        assert stored.title == "Title"
        assert stored.summary == "Summary"
        assert stored.supersedes_id == uuid.UUID(older["id"])


@pytest.mark.parametrize(
    ("field", "values"),
    [
        (
            "memory_type",
            [
                "working",
                "episodic",
                "semantic",
                "decision",
                "procedural",
                "preference",
                "temporary",
            ],
        ),
        ("status", ["active", "superseded", "invalid", "archived"]),
        ("importance", [0.0, 1.0]),
        ("confidence", [0.0, 1.0]),
    ],
)
def test_allowed_metadata_values_work_through_api(
    field: str, values: list[str] | list[float]
) -> None:
    client = TestClient(create_app())
    for value in values:
        response = client.post("/memories", json={"content": str(value), field: value})
        assert response.status_code == 201
        assert response.json()[field] == value


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("memory_type", "unknown"),
        ("status", "unknown"),
        ("importance", -0.01),
        ("importance", 1.01),
        ("confidence", -0.01),
        ("confidence", 1.01),
        ("event_time", "2026-01-01T00:00:00"),
        ("expires_at", "2026-01-01T00:00:00"),
    ],
)
def test_invalid_metadata_values_insert_no_rows(field: str, value: object) -> None:
    response = TestClient(create_app()).post(
        "/memories", json={"content": "invalid", field: value}
    )
    with Session(get_engine()) as session:
        count = session.scalar(select(func.count()).select_from(Memory))
    assert response.status_code == 422
    assert count == 0


def test_unknown_supersedes_inserts_no_row() -> None:
    response = TestClient(create_app()).post(
        "/memories",
        json={"content": "new", "supersedes_id": str(uuid.uuid4())},
    )
    with Session(get_engine()) as session:
        count = session.scalar(select(func.count()).select_from(Memory))
    assert response.status_code == 404
    assert response.json() == {"detail": "superseded memory not found"}
    assert count == 0


def test_deleting_superseded_memory_sets_reference_to_null() -> None:
    client = TestClient(create_app())
    older = client.post("/memories", json={"content": "older"}).json()
    newer = client.post(
        "/memories",
        json={"content": "newer", "supersedes_id": older["id"]},
    ).json()
    with Session(get_engine()) as session:
        stored_older = session.get(Memory, uuid.UUID(older["id"]))
        assert stored_older is not None
        session.delete(stored_older)
        session.commit()
        stored_newer = session.get(Memory, uuid.UUID(newer["id"]))
        assert stored_newer is not None
        assert stored_newer.supersedes_id is None


def test_list_memories_filters_orders_and_paginates() -> None:
    client = TestClient(create_app())
    first_project = client.post("/projects", json={"name": "One"}).json()
    second_project = client.post("/projects", json={"name": "Two"}).json()
    created = [
        client.post("/memories", json={"content": "unassigned"}).json(),
        client.post(
            "/memories",
            json={"project_id": first_project["id"], "content": "first"},
        ).json(),
        client.post(
            "/memories",
            json={"project_id": second_project["id"], "content": "second"},
        ).json(),
    ]
    base_time = datetime(2026, 1, 1, tzinfo=UTC)
    with Session(get_engine()) as session:
        for index, item in enumerate(created):
            stored = session.get(Memory, uuid.UUID(item["id"]))
            assert stored is not None
            stored.created_at = base_time + timedelta(minutes=index)
        session.commit()

    listing = client.get("/memories")
    assert listing.status_code == 200
    assert [item["content"] for item in listing.json()] == [
        "second",
        "first",
        "unassigned",
    ]
    first_filter = client.get(f"/memories?project_id={first_project['id']}")
    assert [item["content"] for item in first_filter.json()] == ["first"]
    second_filter = client.get(f"/memories?project_id={second_project['id']}")
    assert [item["content"] for item in second_filter.json()] == ["second"]
    assert client.get(f"/memories?project_id={uuid.uuid4()}").json() == []
    page = client.get("/memories?limit=1&offset=1")
    assert [item["content"] for item in page.json()] == ["first"]


def test_deterministic_id_order_for_equal_created_at() -> None:
    shared_time = datetime(2026, 1, 1, tzinfo=UTC)
    lower_id = uuid.UUID(int=1)
    higher_id = uuid.UUID(int=2)
    with Session(get_engine()) as session:
        session.add_all(
            [
                Memory(id=higher_id, content="higher", created_at=shared_time),
                Memory(id=lower_id, content="lower", created_at=shared_time),
            ]
        )
        session.commit()
    response = TestClient(create_app()).get("/memories")
    assert [item["id"] for item in response.json()] == [str(lower_id), str(higher_id)]


@pytest.mark.parametrize(
    "field,values",
    [
        (
            "memory_type",
            [
                "working",
                "episodic",
                "semantic",
                "decision",
                "procedural",
                "preference",
                "temporary",
            ],
        ),
        ("status", ["active", "superseded", "invalid", "archived"]),
    ],
)
def test_list_memories_filters_every_approved_enum(
    field: str, values: list[str]
) -> None:
    client = TestClient(create_app())
    for value in values:
        response = client.post("/memories", json={"content": value, field: value})
        assert response.status_code == 201
    for value in values:
        response = client.get("/memories", params={field: value})
        assert [item["content"] for item in response.json()] == [value]


def test_list_memories_score_and_time_ranges_are_inclusive_and_sql_paginated() -> None:
    client = TestClient(create_app())
    base = datetime(2026, 1, 1, tzinfo=UTC)
    rows = [
        Memory(
            id=uuid.UUID(int=1),
            content="lower",
            importance=0.2,
            confidence=0.3,
            event_time=base,
            created_at=base,
        ),
        Memory(
            id=uuid.UUID(int=3),
            content="middle",
            importance=0.5,
            confidence=0.6,
            event_time=base + timedelta(days=1),
            created_at=base + timedelta(days=1),
        ),
        Memory(
            id=uuid.UUID(int=4),
            content="upper",
            importance=0.8,
            confidence=0.9,
            event_time=base + timedelta(days=2),
            created_at=base + timedelta(days=2),
        ),
        Memory(
            id=uuid.UUID(int=2),
            content="null event",
            event_time=None,
            created_at=base,
        ),
    ]
    with Session(get_engine()) as session:
        session.add_all(rows)
        session.commit()

    cases = [
        ({"importance_min": 0.5}, ["upper", "middle", "null event"]),
        ({"importance_max": 0.5}, ["middle", "lower", "null event"]),
        (
            {"importance_min": 0.2, "importance_max": 0.8},
            ["upper", "middle", "lower", "null event"],
        ),
        ({"confidence_min": 0.6}, ["upper", "middle", "null event"]),
        ({"confidence_max": 0.6}, ["middle", "lower"]),
        ({"confidence_min": 0.3, "confidence_max": 0.9}, ["upper", "middle", "lower"]),
        ({"event_time_from": base.isoformat()}, ["upper", "middle", "lower"]),
        (
            {"event_time_to": (base + timedelta(days=1)).isoformat()},
            ["middle", "lower"],
        ),
        (
            {"created_at_from": (base + timedelta(days=1)).isoformat()},
            ["upper", "middle"],
        ),
        (
            {"created_at_to": (base + timedelta(days=1)).isoformat()},
            ["middle", "lower", "null event"],
        ),
        ({"importance_min": 0.2, "limit": 1, "offset": 1}, ["middle"]),
    ]
    for params, expected in cases:
        response = client.get("/memories", params=params)
        assert response.status_code == 200
        assert [item["content"] for item in response.json()] == expected


def test_list_memories_combines_all_filter_categories_and_no_match() -> None:
    client = TestClient(create_app())
    project = client.post("/projects", json={"name": "Filtered"}).json()
    event_time = datetime(2026, 2, 1, tzinfo=UTC)
    target = client.post(
        "/memories",
        json={
            "project_id": project["id"],
            "content": "target",
            "memory_type": "decision",
            "status": "archived",
            "importance": 0.7,
            "confidence": 0.8,
            "event_time": event_time.isoformat(),
        },
    )
    assert target.status_code == 201
    client.post("/memories", json={"content": "other"})
    params = {
        "project_id": project["id"],
        "memory_type": "decision",
        "status": "archived",
        "importance_min": 0.7,
        "importance_max": 0.7,
        "confidence_min": 0.8,
        "confidence_max": 0.8,
        "event_time_from": event_time.isoformat(),
        "event_time_to": event_time.isoformat(),
        "created_at_from": target.json()["created_at"],
        "created_at_to": target.json()["created_at"],
    }
    assert [
        item["content"] for item in client.get("/memories", params=params).json()
    ] == ["target"]
    params["status"] = "invalid"
    assert client.get("/memories", params=params).json() == []


def test_get_memory_and_validation_responses() -> None:
    client = TestClient(create_app())
    created = client.post("/memories", json={"content": "retrieve me"}).json()
    found = client.get(f"/memories/{created['id']}")
    assert found.status_code == 200
    assert found.json() == created
    missing = client.get(f"/memories/{uuid.uuid4()}")
    assert missing.status_code == 404
    assert missing.json() == {"detail": "memory not found"}
    assert client.get("/memories/not-a-uuid").status_code == 422


@pytest.mark.parametrize("query", ["limit=0", "limit=101", "offset=-1"])
def test_list_memories_rejects_invalid_pagination(query: str) -> None:
    assert TestClient(create_app()).get(f"/memories?{query}").status_code == 422


@pytest.mark.parametrize(
    "query",
    [
        "memory_type=nope",
        "status=nope",
        "importance_min=-0.1",
        "confidence_max=1.1",
        "importance_min=0.9&importance_max=0.1",
        "confidence_min=0.9&confidence_max=0.1",
        "event_time_from=2026-02-01T00:00:00Z&event_time_to=2026-01-01T00:00:00Z",
        "created_at_from=2026-02-01T00:00:00Z&created_at_to=2026-01-01T00:00:00Z",
        "event_time_from=2026-01-01T00:00:00",
        "created_at_to=2026-01-01T00:00:00",
    ],
)
def test_list_memories_rejects_invalid_filters(query: str) -> None:
    assert TestClient(create_app()).get(f"/memories?{query}").status_code == 422


def test_existing_endpoints_and_routing_remain_unchanged() -> None:
    client = TestClient(create_app())
    assert client.post("/memories", json={"content": "same"}).status_code == 201
    assert client.post("/memories", json={"content": "same"}).status_code == 201
    assert client.get("/memories").status_code == 200
    assert client.get("/api/memories").status_code == 404
    assert client.get("/health").status_code == 200
    assert client.get("/ready").status_code == 200
    assert client.post("/projects", json={"name": "Still works"}).status_code == 201
    assert client.get("/projects").status_code == 200
