"""Focused real-PostgreSQL API evidence for Checkpoint 118."""

import threading
import uuid
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from itertools import combinations
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, event, select
from sqlalchemy.orm import Session

from app.db.session import get_engine, get_session_factory
from app.main import create_app
from app.models.capture_item import CaptureItem
from app.models.project import Project
from app.models.source import Source
from app.schemas.capture import CaptureScope
from tests.integration.conftest import verify_connected_test_database

pytestmark = pytest.mark.usefixtures("migrated_test_database")


@pytest.fixture(autouse=True)
def clean_capture_rows(test_database_url: str) -> Generator[None, None, None]:
    verify_connected_test_database(test_database_url)
    with Session(get_engine()) as session:
        session.execute(delete(CaptureItem))
        session.commit()
    yield
    verify_connected_test_database(test_database_url)
    with Session(get_engine()) as session:
        session.execute(delete(CaptureItem))
        session.commit()


def _project() -> str:
    with Session(get_engine()) as session:
        project = Project(name=f"capture-api-{uuid.uuid4()}")
        session.add(project)
        session.commit()
        return str(project.id)


def _create(
    client: TestClient, content: str = "note", project_id: str | None = None
) -> dict[str, object]:
    body: dict[str, object] = {"content": content}
    if project_id is not None:
        body["project_id"] = project_id
    response = client.post(
        "/capture-items",
        json=body,
        headers={"Idempotency-Key": f"capture-{uuid.uuid4()}"},
    )
    assert response.status_code == 201
    return response.json()


def _scope(project_id: str | None) -> dict[str, object]:
    return {"unassigned": True} if project_id is None else {"project_id": project_id}


def _seed_item(
    *,
    content: str,
    project_id: str | None = None,
    state: str = "pending",
    revision: int = 1,
    created_at: datetime | None = None,
    item_id: uuid.UUID | None = None,
) -> CaptureItem:
    identity = item_id or uuid.uuid4()
    instant = created_at or datetime.now(UTC)
    with Session(get_engine(), expire_on_commit=False) as session:
        source_id = None
        processed_at = None
        if state == "processed":
            source = Source(source_type="text", name=f"capture-test-{identity}")
            session.add(source)
            session.flush()
            source_id = source.id
            processed_at = instant
        item = CaptureItem(
            id=identity,
            project_id=None if project_id is None else uuid.UUID(project_id),
            content=content,
            state=state,
            revision=revision,
            created_at=instant,
            updated_at=instant,
            processed_at=processed_at,
            resulting_source_id=source_id,
            idempotency_key_hash=sha256(f"key:{identity}".encode()).hexdigest(),
            request_fingerprint=sha256(f"request:{identity}".encode()).hexdigest(),
        )
        session.add(item)
        session.commit()
        return item


def test_create_replay_scope_and_private_projection() -> None:
    client = TestClient(create_app(), client=("127.0.0.1", 52118))
    project_id = _project()
    key = f"replay-{uuid.uuid4()}"
    first = client.post(
        "/capture-items",
        json={"content": "line\r\n", "project_id": project_id},
        headers={"Idempotency-Key": key},
    )
    replay = client.post(
        "/capture-items",
        json={"content": "line\n", "project_id": project_id},
        headers={"Idempotency-Key": key},
    )
    conflict = client.post(
        "/capture-items",
        json={"content": "other", "project_id": project_id},
        headers={"Idempotency-Key": key},
    )
    unassigned = _create(client)
    assert first.status_code == 201 and replay.status_code == 200
    assert first.json() == replay.json() and conflict.status_code == 409
    assert unassigned["project_id"] is None
    assert set(first.json()) == {
        "id",
        "project_id",
        "content",
        "state",
        "revision",
        "created_at",
        "updated_at",
        "processed_at",
        "resulting_source_id",
    }


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"project_id": None},
        {"unassigned": False},
        {"project_id": str(uuid.uuid4()), "unassigned": True},
    ],
)
def test_exact_scope_validation_matrix(body: dict[str, object]) -> None:
    response = TestClient(create_app(), client=("127.0.0.1", 52119)).post(
        "/capture-items/query", json={"scope": body}
    )
    assert response.status_code == 422


def test_query_detail_isolation_pagination_and_cursor_binding() -> None:
    client = TestClient(create_app(), client=("127.0.0.1", 52120))
    project_a, project_b = _project(), _project()
    created = [_create(client, f"needle {index}", project_a) for index in range(4)]
    other = _create(client, "needle private", project_b)
    unassigned = _create(client, "needle loose")
    request = {"scope": {"project_id": project_a}, "query": " needle ", "page_size": 2}
    first = client.post("/capture-items/query", json=request).json()
    second = client.post(
        "/capture-items/query", json={**request, "cursor": first["next_cursor"]}
    ).json()
    ids = [item["id"] for item in first["items"] + second["items"]]
    assert len(ids) == 4 and len(set(ids)) == 4
    assert other["id"] not in ids and unassigned["id"] not in ids
    assert first["next_cursor"] and second["next_cursor"] is None
    assert (
        client.post(
            "/capture-items/query",
            json={**request, "page_size": 3, "cursor": first["next_cursor"]},
        ).status_code
        == 422
    )
    cursor = first["next_cursor"]
    assert (
        client.post(
            "/capture-items/query",
            json={
                **request,
                "cursor": cursor[:-1] + ("A" if cursor[-1] != "A" else "B"),
            },
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/capture-items/{created[0]['id']}/detail",
            json={"scope": {"project_id": project_b}},
        ).status_code
        == 404
    )


def test_edit_reassign_discard_restore_and_authoritative_stale_conflict() -> None:
    client = TestClient(create_app(), client=("127.0.0.1", 52121))
    project_id = _project()
    item = _create(client, "before")
    edit = client.patch(
        f"/capture-items/{item['id']}",
        json={"scope": {"unassigned": True}, "revision": 1, "content": "after\r\n"},
    )
    assert (
        edit.status_code == 200
        and edit.json()["content"] == "after\n"
        and edit.json()["revision"] == 2
    )
    stale = client.post(
        f"/capture-items/{item['id']}/discard",
        json={"scope": {"unassigned": True}, "revision": 1},
    )
    assert stale.status_code == 409 and stale.json()["detail"]["item"]["revision"] == 2
    moved = client.post(
        f"/capture-items/{item['id']}/reassign",
        json={
            "scope": {"unassigned": True},
            "target_scope": {"project_id": project_id},
            "revision": 2,
        },
    )
    discarded = client.post(
        f"/capture-items/{item['id']}/discard",
        json={"scope": {"project_id": project_id}, "revision": 3},
    )
    restored = client.post(
        f"/capture-items/{item['id']}/restore",
        json={"scope": {"project_id": project_id}, "revision": 4},
    )
    assert [
        moved.json()["revision"],
        discarded.json()["revision"],
        restored.json()["revision"],
    ] == [3, 4, 5]
    mutation_times = [
        item["updated_at"],
        edit.json()["updated_at"],
        moved.json()["updated_at"],
        discarded.json()["updated_at"],
        restored.json()["updated_at"],
    ]
    assert mutation_times == sorted(mutation_times)
    assert len(set(mutation_times)) == len(mutation_times)
    assert (
        discarded.json()["state"] == "discarded"
        and restored.json()["state"] == "pending"
    )
    assert (
        client.post(
            f"/capture-items/{item['id']}/restore",
            json={"scope": {"project_id": project_id}, "revision": 5},
        ).status_code
        == 409
    )


def test_two_real_sessions_same_revision_have_exactly_one_winner() -> None:
    client = TestClient(create_app(), client=("127.0.0.1", 52122))
    item = _create(client, "race")
    barrier = threading.Barrier(2)

    def mutate(content: str) -> str:
        from app.captures.service import CaptureRevisionConflictError, edit_capture
        from app.schemas.capture import CaptureScope

        with get_session_factory()() as session:
            barrier.wait(timeout=10)
            try:
                edit_capture(
                    session,
                    uuid.UUID(str(item["id"])),
                    CaptureScope(unassigned=True),
                    1,
                    content,
                )
                session.commit()
                return "ok"
            except CaptureRevisionConflictError:
                session.rollback()
                return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(mutate, ("winner-a", "winner-b")))
    assert sorted(outcomes) == ["conflict", "ok"]
    with Session(get_engine()) as session:
        persisted = session.scalar(
            select(CaptureItem).where(CaptureItem.id == uuid.UUID(str(item["id"])))
        )
        assert (
            persisted is not None
            and persisted.revision == 2
            and persisted.content in {"winner-a", "winner-b"}
        )


@pytest.mark.parametrize(
    "value",
    [
        "\tneedle",
        "needle\t",
        "\nneedle",
        "needle\n",
        "need\tle",
        "need\nle",
        "\x00needle",
        "need\x00le",
        "needle\x00",
        "\x01needle",
        "needle\x1f",
        "\x7fneedle",
        "needle\x80",
        "\x9fneedle",
    ],
)
def test_query_rejects_raw_nul_c0_and_c1_controls(value: str) -> None:
    client = TestClient(create_app(), client=("127.0.0.1", 52124))
    response = client.post(
        "/capture-items/query",
        json={"scope": {"unassigned": True}, "query": value},
    )
    assert response.status_code == 422


def test_query_normalization_character_utf8_and_page_cursor_boundaries() -> None:
    client = TestClient(create_app(), client=("127.0.0.1", 52125))
    _create(client, "needle")
    base = {"scope": {"unassigned": True}}
    accepted = (
        {"query": " needle "},
        {"query": "a"},
        {"query": "a" * 200},
        {"query": "😀" * 200},
        {"page_size": 1},
        {"page_size": 25},
        {"page_size": 50},
    )
    for values in accepted:
        assert (
            client.post("/capture-items/query", json={**base, **values}).status_code
            == 200
        )
    for values in (
        {"query": " "},
        {"query": "a" * 201},
        {"query": "😀" * 201},
        {"page_size": 0},
        {"page_size": 51},
        {"cursor": "x" * 2048},
        {"cursor": "x" * 2049},
    ):
        assert (
            client.post("/capture-items/query", json={**base, **values}).status_code
            == 422
        )


def test_public_creation_header_and_scope_matrix() -> None:
    client = TestClient(create_app(), client=("127.0.0.1", 52126))
    project_id = _project()
    missing = client.post("/capture-items", json={"content": "missing key"})
    malformed = client.post(
        "/capture-items",
        json={"content": "bad key"},
        headers={"Idempotency-Key": "short"},
    )
    assert missing.status_code == malformed.status_code == 422
    omitted = client.post(
        "/capture-items",
        json={"content": "omitted"},
        headers={"Idempotency-Key": f"omitted-{uuid.uuid4()}"},
    )
    explicit = client.post(
        "/capture-items",
        json={"content": "explicit", "unassigned": True},
        headers={"Idempotency-Key": f"explicit-{uuid.uuid4()}"},
    )
    assigned = client.post(
        "/capture-items",
        json={"content": "assigned", "project_id": project_id},
        headers={"Idempotency-Key": f"assigned-{uuid.uuid4()}"},
    )
    assert omitted.status_code == explicit.status_code == assigned.status_code == 201
    assert (
        omitted.json()["project_id"] is None and explicit.json()["project_id"] is None
    )
    assert assigned.json()["project_id"] == project_id
    for body in (
        {"content": "null", "project_id": None},
        {"content": "false", "unassigned": False},
        {"content": "both", "project_id": project_id, "unassigned": True},
    ):
        response = client.post(
            "/capture-items",
            json=body,
            headers={"Idempotency-Key": f"invalid-{uuid.uuid4()}"},
        )
        assert response.status_code == 422
    forged = client.post(
        "/capture-items",
        json={"content": "forged", "project_id": str(uuid.uuid4())},
        headers={"Idempotency-Key": f"invalid-{uuid.uuid4()}"},
    )
    assert forged.status_code == 404


def test_state_filters_default_all_combinations_and_bounds() -> None:
    client = TestClient(create_app(), client=("127.0.0.1", 52127))
    expected: dict[str, str] = {}
    for state in ("pending", "discarded", "processed"):
        item = _seed_item(content=state, state=state)
        expected[state] = str(item.id)
    default = client.post("/capture-items/query", json={"scope": {"unassigned": True}})
    assert [item["id"] for item in default.json()["items"]] == [expected["pending"]]
    states = ("pending", "discarded", "processed")
    for size in (1, 2, 3):
        for selected in combinations(states, size):
            response = client.post(
                "/capture-items/query",
                json={"scope": {"unassigned": True}, "states": list(selected)},
            )
            assert response.status_code == 200
            assert {item["id"] for item in response.json()["items"]} == {
                expected[state] for state in selected
            }
    for invalid in ([], ["pending", "pending"], [*states, "pending"], ["unknown"]):
        assert (
            client.post(
                "/capture-items/query",
                json={"scope": {"unassigned": True}, "states": invalid},
            ).status_code
            == 422
        )


def test_browse_and_lexical_ordering_with_deterministic_ties() -> None:
    client = TestClient(create_app(), client=("127.0.0.1", 52128))
    instant = datetime(2026, 1, 2, tzinfo=UTC)
    low_id = uuid.UUID(int=1)
    high_id = uuid.UUID(int=2)
    older = _seed_item(
        content="alpha alpha alpha", created_at=instant - timedelta(seconds=1)
    )
    _seed_item(content="alpha", created_at=instant, item_id=low_id)
    _seed_item(content="alpha", created_at=instant, item_id=high_id)
    browse = client.post(
        "/capture-items/query",
        json={"scope": {"unassigned": True}, "states": ["pending"]},
    ).json()["items"]
    assert [row["id"] for row in browse] == [str(high_id), str(low_id), str(older.id)]
    lexical = client.post(
        "/capture-items/query",
        json={"scope": {"unassigned": True}, "query": "alpha"},
    ).json()["items"]
    assert lexical[0]["id"] == str(older.id)
    assert [row["id"] for row in lexical[1:]] == [str(high_id), str(low_id)]


def test_cursor_all_bindings_malformed_canonical_and_stable_browse_pages() -> None:
    client = TestClient(create_app(), client=("127.0.0.1", 52129))
    project_id = _project()
    for index in range(5):
        _create(client, f"cursor needle {index}")
    request: dict[str, Any] = {
        "scope": {"unassigned": True},
        "states": ["pending"],
        "page_size": 2,
    }
    seen: list[str] = []
    cursor = None
    while True:
        body = request if cursor is None else {**request, "cursor": cursor}
        page = client.post("/capture-items/query", json=body)
        assert page.status_code == 200
        seen.extend(item["id"] for item in page.json()["items"])
        cursor = page.json()["next_cursor"]
        if cursor is None:
            break
    assert len(seen) == 5 and len(set(seen)) == 5
    first = client.post("/capture-items/query", json=request).json()
    token = first["next_cursor"]
    assert token
    mismatches = (
        {**request, "scope": {"project_id": project_id}, "cursor": token},
        {**request, "query": "needle", "cursor": token},
        {**request, "states": ["discarded"], "cursor": token},
        {**request, "page_size": 3, "cursor": token},
    )
    for body in mismatches:
        assert client.post("/capture-items/query", json=body).status_code == 422
    for invalid in (
        "malformed",
        token + "=",
        token[:-1] + ("A" if token[-1] != "A" else "B"),
    ):
        assert (
            client.post(
                "/capture-items/query", json={**request, "cursor": invalid}
            ).status_code
            == 422
        )
    lexical_request = {**request, "query": "needle"}
    lexical_token = client.post("/capture-items/query", json=lexical_request).json()[
        "next_cursor"
    ]
    assert lexical_token
    assert (
        client.post(
            "/capture-items/query",
            json={**lexical_request, "query": "cursor", "cursor": lexical_token},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/capture-items/query", json={**request, "cursor": lexical_token}
        ).status_code
        == 422
    )


def test_cursor_ordering_version_mismatch_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.captures import tokens

    client = TestClient(create_app(), client=("127.0.0.1", 52130))
    for index in range(2):
        _create(client, f"version {index}")
    request = {"scope": {"unassigned": True}, "page_size": 1}
    token = client.post("/capture-items/query", json=request).json()["next_cursor"]
    original = tokens._request

    def changed(value: Any) -> dict[str, Any]:
        result = original(value)
        result["ordering"] = "future-order-v2"
        return result

    monkeypatch.setattr(tokens, "_request", changed)
    assert (
        client.post(
            "/capture-items/query", json={**request, "cursor": token}
        ).status_code
        == 422
    )


def test_scope_isolation_across_detail_and_every_mutation() -> None:
    client = TestClient(create_app(), client=("127.0.0.1", 52131))
    project_a, project_b = _project(), _project()
    assigned = _create(client, "assigned", project_a)
    unassigned = _create(client, "unassigned")
    attempts = (
        (assigned, {"project_id": project_b}),
        (assigned, {"unassigned": True}),
        (unassigned, {"project_id": project_a}),
    )
    for item, wrong_scope in attempts:
        item_id = item["id"]
        assert (
            client.post(
                f"/capture-items/{item_id}/detail", json={"scope": wrong_scope}
            ).status_code
            == 404
        )
        assert (
            client.patch(
                f"/capture-items/{item_id}",
                json={"scope": wrong_scope, "revision": 1, "content": "forbidden"},
            ).status_code
            == 404
        )
        assert (
            client.post(
                f"/capture-items/{item_id}/reassign",
                json={
                    "scope": wrong_scope,
                    "target_scope": {"unassigned": True},
                    "revision": 1,
                },
            ).status_code
            == 404
        )
        assert (
            client.post(
                f"/capture-items/{item_id}/discard",
                json={"scope": wrong_scope, "revision": 1},
            ).status_code
            == 404
        )
    assigned_discarded = _seed_item(
        content="assigned discarded", project_id=project_a, state="discarded"
    )
    unassigned_discarded = _seed_item(content="unassigned discarded", state="discarded")
    assert (
        client.post(
            f"/capture-items/{assigned_discarded.id}/restore",
            json={"scope": {"unassigned": True}, "revision": 1},
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/capture-items/{unassigned_discarded.id}/restore",
            json={"scope": {"project_id": project_a}, "revision": 1},
        ).status_code
        == 404
    )


def test_reassignment_directions_stale_conflicts_and_timestamps() -> None:
    client = TestClient(create_app(), client=("127.0.0.1", 52132))
    project_a, project_b = _project(), _project()
    item = _create(client, "move")
    initial_updated = item["updated_at"]
    to_a = client.post(
        f"/capture-items/{item['id']}/reassign",
        json={
            "scope": {"unassigned": True},
            "target_scope": {"project_id": project_a},
            "revision": 1,
        },
    )
    to_b = client.post(
        f"/capture-items/{item['id']}/reassign",
        json={
            "scope": {"project_id": project_a},
            "target_scope": {"project_id": project_b},
            "revision": 2,
        },
    )
    to_none = client.post(
        f"/capture-items/{item['id']}/reassign",
        json={
            "scope": {"project_id": project_b},
            "target_scope": {"unassigned": True},
            "revision": 3,
        },
    )
    assert [
        to_a.json()["revision"],
        to_b.json()["revision"],
        to_none.json()["revision"],
    ] == [2, 3, 4]
    assert [
        to_a.json()["project_id"],
        to_b.json()["project_id"],
        to_none.json()["project_id"],
    ] == [project_a, project_b, None]
    timestamps = [
        initial_updated,
        to_a.json()["updated_at"],
        to_b.json()["updated_at"],
        to_none.json()["updated_at"],
    ]
    assert timestamps == sorted(timestamps) and len(set(timestamps)) == 4
    nonexistent = client.post(
        f"/capture-items/{item['id']}/reassign",
        json={
            "scope": {"unassigned": True},
            "target_scope": {"project_id": str(uuid.uuid4())},
            "revision": 4,
        },
    )
    assert nonexistent.status_code == 404
    stale_reassign = client.post(
        f"/capture-items/{item['id']}/reassign",
        json={
            "scope": {"unassigned": True},
            "target_scope": {"project_id": project_a},
            "revision": 3,
        },
    )
    stale_edit = client.patch(
        f"/capture-items/{item['id']}",
        json={"scope": {"unassigned": True}, "revision": 3, "content": "stale"},
    )
    assert stale_reassign.status_code == stale_edit.status_code == 409
    assert stale_reassign.json()["detail"]["item"]["revision"] == 4


def test_stale_discard_restore_and_complete_state_action_matrix() -> None:
    client = TestClient(create_app(), client=("127.0.0.1", 52133))
    pending = _create(client, "pending")
    discarded = _seed_item(content="discarded", state="discarded")
    processed = _seed_item(content="processed", state="processed")
    first_discard = client.post(
        f"/capture-items/{pending['id']}/discard",
        json={"scope": {"unassigned": True}, "revision": 1},
    )
    assert first_discard.status_code == 200
    stale_discard = client.post(
        f"/capture-items/{pending['id']}/discard",
        json={"scope": {"unassigned": True}, "revision": 1},
    )
    restored = client.post(
        f"/capture-items/{pending['id']}/restore",
        json={"scope": {"unassigned": True}, "revision": 2},
    )
    stale_restore = client.post(
        f"/capture-items/{pending['id']}/restore",
        json={"scope": {"unassigned": True}, "revision": 2},
    )
    assert stale_discard.status_code == stale_restore.status_code == 409
    assert restored.status_code == 200 and restored.json()["revision"] == 3
    actions = (
        ("patch", "", {"content": "changed"}),
        ("post", "/reassign", {"target_scope": {"unassigned": True}}),
        ("post", "/discard", {}),
        ("post", "/restore", {}),
    )
    for row in (discarded, processed):
        for method, suffix, extra in actions:
            response = getattr(client, method)(
                f"/capture-items/{row.id}{suffix}",
                json={"scope": {"unassigned": True}, "revision": row.revision, **extra},
            )
            expected = 200 if row.state == "discarded" and suffix == "/restore" else 409
            assert response.status_code == expected
            if expected == 200:
                break
    for suffix in ("/restore",):
        assert (
            client.post(
                f"/capture-items/{pending['id']}{suffix}",
                json={"scope": {"unassigned": True}, "revision": 3},
            ).status_code
            == 409
        )


@pytest.mark.parametrize("kind", ["edit", "reassign", "discard", "restore"])
def test_concurrent_same_revision_mutations_correlate_persisted_winner(
    kind: str,
) -> None:
    from app.captures.service import (
        CaptureNotFoundError,
        CaptureRevisionConflictError,
        edit_capture,
        reassign_capture,
        transition_capture,
    )

    project_a, project_b = _project(), _project()
    initial_state = "discarded" if kind == "restore" else "pending"
    item = _seed_item(content="race", state=initial_state)
    barrier = threading.Barrier(2)

    def worker(index: int) -> tuple[str, int]:
        with get_session_factory()() as session:
            barrier.wait(timeout=10)
            try:
                if kind == "edit":
                    edit_capture(
                        session,
                        item.id,
                        CaptureScope(unassigned=True),
                        1,
                        f"winner-{index}",
                    )
                elif kind == "reassign":
                    target = project_a if index == 0 else project_b
                    reassign_capture(
                        session,
                        item.id,
                        CaptureScope(unassigned=True),
                        CaptureScope(project_id=target),
                        1,
                    )
                elif kind == "discard":
                    transition_capture(
                        session,
                        item.id,
                        CaptureScope(unassigned=True),
                        1,
                        expected="pending",
                        target="discarded",
                    )
                else:
                    transition_capture(
                        session,
                        item.id,
                        CaptureScope(unassigned=True),
                        1,
                        expected="discarded",
                        target="pending",
                    )
                session.commit()
                return ("ok", index)
            except (CaptureRevisionConflictError, CaptureNotFoundError):
                session.rollback()
                return ("conflict", index)

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(worker, (0, 1)))
    winner = next(index for status, index in outcomes if status == "ok")
    assert sorted(status for status, _ in outcomes) == ["conflict", "ok"]
    with Session(get_engine()) as session:
        persisted = session.get(CaptureItem, item.id)
        assert persisted is not None and persisted.revision == 2
        if kind == "edit":
            assert persisted.content == f"winner-{winner}"
        elif kind == "reassign":
            assert str(persisted.project_id) == (
                project_a if winner == 0 else project_b
            )
        elif kind == "discard":
            assert persisted.state == "discarded"
        else:
            assert persisted.state == "pending"


def test_reassignment_vs_old_scope_edit_has_one_correlated_winner() -> None:
    from app.captures.service import (
        CaptureNotFoundError,
        CaptureRevisionConflictError,
        edit_capture,
        reassign_capture,
    )

    project_id = _project()
    item = _seed_item(content="old")
    barrier = threading.Barrier(2)

    def reassign_worker() -> str:
        with get_session_factory()() as session:
            barrier.wait(timeout=10)
            try:
                reassign_capture(
                    session,
                    item.id,
                    CaptureScope(unassigned=True),
                    CaptureScope(project_id=project_id),
                    1,
                )
                session.commit()
                return "reassign"
            except (CaptureNotFoundError, CaptureRevisionConflictError):
                session.rollback()
                return "lost"

    def edit_worker() -> str:
        with get_session_factory()() as session:
            barrier.wait(timeout=10)
            try:
                edit_capture(
                    session, item.id, CaptureScope(unassigned=True), 1, "edited"
                )
                session.commit()
                return "edit"
            except (CaptureNotFoundError, CaptureRevisionConflictError):
                session.rollback()
                return "lost"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = [pool.submit(reassign_worker), pool.submit(edit_worker)]
        results = [future.result() for future in outcomes]
    assert results.count("lost") == 1
    winner = next(value for value in results if value != "lost")
    with Session(get_engine()) as session:
        persisted = session.get(CaptureItem, item.id)
        assert persisted is not None and persisted.revision == 2
        if winner == "reassign":
            assert (
                str(persisted.project_id) == project_id and persisted.content == "old"
            )
        else:
            assert persisted.project_id is None and persisted.content == "edited"


def test_normal_success_statement_ceilings() -> None:
    client = TestClient(create_app(), client=("127.0.0.1", 52123))
    project_a, project_b = _project(), _project()
    counts: list[str] = []

    def counted(
        _connection: object,
        _cursor: object,
        statement: str,
        _parameters: object,
        _context: object,
        _many: bool,
    ) -> None:
        if not statement.lstrip().upper().startswith(("BEGIN", "COMMIT", "ROLLBACK")):
            counts.append(statement)

    event.listen(get_engine(), "before_cursor_execute", counted)
    try:

        def request_count(
            method: str, path: str, *, expected: int, **kwargs: Any
        ) -> Any:
            counts.clear()
            response = getattr(client, method)(path, **kwargs)
            assert response.status_code in {200, 201}
            assert len(counts) == expected
            return response

        unassigned_key = f"sql-u-{uuid.uuid4()}"
        assigned_key = f"sql-a-{uuid.uuid4()}"
        unassigned = request_count(
            "post",
            "/capture-items",
            expected=1,
            json={"content": "sql unassigned"},
            headers={"Idempotency-Key": unassigned_key},
        ).json()
        request_count(
            "post",
            "/capture-items",
            expected=2,
            json={"content": "sql unassigned"},
            headers={"Idempotency-Key": unassigned_key},
        )
        assigned = request_count(
            "post",
            "/capture-items",
            expected=2,
            json={"content": "sql assigned", "project_id": project_a},
            headers={"Idempotency-Key": assigned_key},
        ).json()
        request_count(
            "post",
            "/capture-items",
            expected=3,
            json={"content": "sql assigned", "project_id": project_a},
            headers={"Idempotency-Key": assigned_key},
        )
        request_count(
            "post",
            "/capture-items/query",
            expected=1,
            json={"scope": {"unassigned": True}},
        )
        request_count(
            "post",
            "/capture-items/query",
            expected=2,
            json={"scope": {"project_id": project_a}},
        )
        request_count(
            "post",
            f"/capture-items/{unassigned['id']}/detail",
            expected=1,
            json={"scope": {"unassigned": True}},
        )
        request_count(
            "post",
            f"/capture-items/{assigned['id']}/detail",
            expected=2,
            json={"scope": {"project_id": project_a}},
        )
        request_count(
            "patch",
            f"/capture-items/{unassigned['id']}",
            expected=2,
            json={
                "scope": {"unassigned": True},
                "revision": 1,
                "content": "sql unassigned edited",
            },
        )
        request_count(
            "patch",
            f"/capture-items/{assigned['id']}",
            expected=3,
            json={
                "scope": {"project_id": project_a},
                "revision": 1,
                "content": "sql assigned edited",
            },
        )

        ua_transition = _create(client, "ua transition")
        assigned_transition = _create(client, "assigned transition", project_a)
        request_count(
            "post",
            f"/capture-items/{ua_transition['id']}/discard",
            expected=2,
            json={"scope": {"unassigned": True}, "revision": 1},
        )
        request_count(
            "post",
            f"/capture-items/{ua_transition['id']}/restore",
            expected=2,
            json={"scope": {"unassigned": True}, "revision": 2},
        )
        request_count(
            "post",
            f"/capture-items/{assigned_transition['id']}/discard",
            expected=3,
            json={"scope": {"project_id": project_a}, "revision": 1},
        )
        request_count(
            "post",
            f"/capture-items/{assigned_transition['id']}/restore",
            expected=3,
            json={"scope": {"project_id": project_a}, "revision": 2},
        )

        ua_to_assigned = _create(client, "ua assigned")
        assigned_to_ua = _create(client, "assigned ua", project_a)
        assigned_to_assigned = _create(client, "assigned assigned", project_a)
        request_count(
            "post",
            f"/capture-items/{ua_to_assigned['id']}/reassign",
            expected=3,
            json={
                "scope": {"unassigned": True},
                "target_scope": {"project_id": project_a},
                "revision": 1,
            },
        )
        request_count(
            "post",
            f"/capture-items/{assigned_to_ua['id']}/reassign",
            expected=3,
            json={
                "scope": {"project_id": project_a},
                "target_scope": {"unassigned": True},
                "revision": 1,
            },
        )
        request_count(
            "post",
            f"/capture-items/{assigned_to_assigned['id']}/reassign",
            expected=4,
            json={
                "scope": {"project_id": project_a},
                "target_scope": {"project_id": project_b},
                "revision": 1,
            },
        )
    finally:
        event.remove(get_engine(), "before_cursor_execute", counted)
