"""PostgreSQL coverage for CP117 Capture persistence and creation."""

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from hashlib import sha256

import pytest
from sqlalchemy import delete, func, inspect, select, text, update
from sqlalchemy.exc import IntegrityError

from app.captures.service import (
    CaptureCreate,
    CaptureIdempotencyConflictError,
    CaptureProjectNotFoundError,
    create_capture,
    request_fingerprint,
)
from app.db.session import get_session_factory
from app.models.capture_item import CaptureItem
from app.models.project import Project
from app.models.source import Source

pytestmark = pytest.mark.usefixtures("migrated_test_database")


def _create_project() -> uuid.UUID:
    with get_session_factory()() as session:
        project = Project(name=f"capture-{uuid.uuid4()}")
        session.add(project)
        session.commit()
        return project.id


def _create(request: CaptureCreate):
    with get_session_factory()() as session:
        result = create_capture(session, request)
        session.commit()
        return result


def _valid_capture(
    *, content: str = "valid", project_id: uuid.UUID | None = None
) -> CaptureItem:
    identity = uuid.uuid4()
    return CaptureItem(
        id=identity,
        project_id=project_id,
        content=content,
        state="pending",
        revision=1,
        idempotency_key_hash=sha256(f"key:{identity}".encode()).hexdigest(),
        request_fingerprint=sha256(f"request:{identity}".encode()).hexdigest(),
    )


def test_schema_indexes_defaults_and_generated_search_vector() -> None:
    with get_session_factory()() as session:
        inspector = inspect(session.connection())
        indexes = {row["name"]: row for row in inspector.get_indexes("capture_items")}
        assert {
            "ix_capture_items_scope_state_browse",
            "ix_capture_items_search_vector",
        }.issubset(indexes)
        assert (
            indexes["ix_capture_items_search_vector"]["dialect_options"][
                "postgresql_using"
            ]
            == "gin"
        )
        index_definitions = {
            name: definition
            for name, definition in session.execute(
                text(
                    "SELECT indexname, indexdef FROM pg_indexes "
                    "WHERE schemaname='public' AND tablename='capture_items'"
                )
            )
        }
        browse_definition = " ".join(
            index_definitions["ix_capture_items_scope_state_browse"].lower().split()
        )
        assert "using btree (project_id, state, created_at desc, id desc)" in (
            browse_definition
        )
        vector_definition = " ".join(
            index_definitions["ix_capture_items_search_vector"].lower().split()
        )
        assert "using gin (search_vector)" in vector_definition
        generated = session.execute(
            text(
                "SELECT is_generated, generation_expression FROM "
                "information_schema.columns WHERE table_schema='public' "
                "AND table_name='capture_items' AND column_name='search_vector'"
            )
        ).one()
        expression = " ".join(generated.generation_expression.lower().split())
        assert generated.is_generated == "ALWAYS"
        assert "to_tsvector('simple'::regconfig" in expression
        assert "coalesce(content, ''::text)" in expression
        result = create_capture(
            session,
            CaptureCreate(content="lexical needle", idempotency_key="schema-key"),
        )
        session.commit()
        row = session.get(CaptureItem, result.item.id)
        assert row is not None
        assert row.state == "pending" and row.revision == 1
        assert row.created_at.tzinfo is not None and row.updated_at.tzinfo is not None
        assert session.scalar(
            text(
                "SELECT search_vector @@ plainto_tsquery('simple', 'needle') "
                "FROM capture_items WHERE id=:id"
            ),
            {"id": row.id},
        )
        original_updated_at = row.updated_at
        row.content = "replacement changed"
        session.commit()
        session.refresh(row)
        assert row.updated_at > original_updated_at
        assert session.scalar(
            text(
                "SELECT NOT search_vector @@ plainto_tsquery('simple', 'needle') "
                "AND search_vector @@ plainto_tsquery('simple', 'changed') "
                "FROM capture_items WHERE id=:id"
            ),
            {"id": row.id},
        )


@pytest.mark.parametrize(
    ("values", "requires_source"),
    [
        ({"state": "unknown"}, False),
        ({"revision": 0}, False),
        ({"revision": -1}, False),
        ({"state": "processed", "processed_at": datetime.now(UTC)}, False),
        ({"state": "processed"}, True),
        ({"processed_at": datetime.now(UTC)}, False),
        ({"state": "discarded"}, True),
        ({"idempotency_key_hash": "not-a-digest"}, False),
        ({"request_fingerprint": "A" * 64}, False),
        ({"content": "a" * 8_001}, False),
        ({"content": "😀" * 8_000 + "a"}, False),
    ],
    ids=(
        "invalid-state",
        "zero-revision",
        "negative-revision",
        "processed-missing-source",
        "processed-missing-time",
        "pending-retains-time",
        "discarded-retains-source",
        "malformed-key-hash",
        "malformed-fingerprint",
        "character-overflow",
        "utf8-byte-overflow",
    ),
)
def test_each_database_check_rejects_invalid_rows(
    values: dict[str, object], requires_source: bool
) -> None:
    with get_session_factory()() as session:
        source = Source(source_type="text", name="constraint source")
        if requires_source:
            session.add(source)
            session.flush()
            values = {**values, "resulting_source_id": source.id}
        item = _valid_capture()
        session.add(item)
        session.flush()
        with pytest.raises(IntegrityError):
            session.execute(
                update(CaptureItem).where(CaptureItem.id == item.id).values(**values)
            )
            session.commit()


def test_assigned_unassigned_replay_and_conflicts() -> None:
    project_id = _create_project()
    key = f"replay-{uuid.uuid4()}"
    first = _create(CaptureCreate("  note\r\n", key, project_id))
    replay = _create(CaptureCreate("  note\n", key, project_id))
    assert first.created is True and replay.created is False
    assert first.item == replay.item
    unassigned = _create(CaptureCreate("note", f"unassigned-{uuid.uuid4()}"))
    assert unassigned.item.project_id is None
    with pytest.raises(CaptureIdempotencyConflictError):
        _create(CaptureCreate("different", key, project_id))
    with pytest.raises(CaptureIdempotencyConflictError):
        _create(CaptureCreate("  note\n", key))
    with pytest.raises(CaptureProjectNotFoundError):
        _create(CaptureCreate("note", f"missing-{uuid.uuid4()}", uuid.uuid4()))


def test_database_constraints_and_delete_restrictions() -> None:
    project_id = _create_project()
    created = _create(CaptureCreate("note", f"constraint-{uuid.uuid4()}", project_id))
    with get_session_factory()() as session, pytest.raises(IntegrityError):
        session.execute(
            update(CaptureItem)
            .where(CaptureItem.id == created.item.id)
            .values(state="processed")
        )
        session.commit()
    with get_session_factory()() as session:
        with pytest.raises(IntegrityError):
            session.execute(delete(Project).where(Project.id == project_id))
            session.commit()
        session.rollback()

        source = Source(source_type="text", name="capture result")
        session.add(source)
        session.flush()
        session.execute(
            update(CaptureItem)
            .where(CaptureItem.id == created.item.id)
            .values(
                state="processed",
                processed_at=datetime.now(UTC),
                resulting_source_id=source.id,
            )
        )
        session.commit()
        with pytest.raises(IntegrityError):
            session.execute(delete(Source).where(Source.id == source.id))
            session.commit()


def test_resulting_source_is_unique() -> None:
    with get_session_factory()() as session:
        source = Source(source_type="text", name="unique capture result")
        first = _valid_capture(content="first")
        second = _valid_capture(content="second")
        session.add_all((source, first, second))
        session.flush()
        processed_at = datetime.now(UTC)
        first.state = "processed"
        first.processed_at = processed_at
        first.resulting_source_id = source.id
        session.flush()
        second.state = "processed"
        second.processed_at = processed_at
        second.resulting_source_id = source.id
        with pytest.raises(IntegrityError):
            session.flush()


def test_only_key_digest_is_persisted() -> None:
    raw_key = f"private-key-{uuid.uuid4()}"
    result = _create(CaptureCreate("private note", raw_key))
    with get_session_factory()() as session:
        row = session.get(CaptureItem, result.item.id)
        assert row is not None
        assert row.idempotency_key_hash == sha256(raw_key.encode("ascii")).hexdigest()
        assert raw_key not in {
            str(value)
            for value in (
                row.idempotency_key_hash,
                row.request_fingerprint,
                *result.item.__dict__.values(),
            )
        }


@pytest.mark.parametrize("conflicting", [False, True])
def test_concurrent_same_key_creation_has_one_winner(conflicting: bool) -> None:
    barrier = threading.Barrier(2)
    key = f"concurrent-{uuid.uuid4()}"

    def worker(index: int):
        content = "other" if conflicting and index else "same"
        request = CaptureCreate(content, key)
        with get_session_factory()() as session:
            barrier.wait(timeout=10)
            try:
                result = create_capture(session, request)
                session.commit()
                return ("ok", result.item.id, content)
            except CaptureIdempotencyConflictError:
                session.rollback()
                return ("conflict", None, content)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(worker, range(2)))
    with get_session_factory()() as session:
        key_hash = sha256(key.encode("ascii")).hexdigest()
        assert (
            session.scalar(
                select(func.count())
                .select_from(CaptureItem)
                .where(CaptureItem.idempotency_key_hash == key_hash)
            )
            == 1
        )
        persisted = session.scalar(
            select(CaptureItem).where(CaptureItem.idempotency_key_hash == key_hash)
        )
        assert persisted is not None
    if conflicting:
        assert sorted(status for status, _, _ in results) == ["conflict", "ok"]
        winner = next(result for result in results if result[0] == "ok")
        assert persisted.id == winner[1]
        assert persisted.content == winner[2]
        assert persisted.request_fingerprint == request_fingerprint(winner[2], None)
    else:
        assert {identity for _, identity, _ in results}.__len__() == 1


def test_no_public_capture_route_or_source_project_column() -> None:
    from app.main import app

    assert all("capture" not in getattr(route, "path", "") for route in app.routes)
    assert "project_id" not in {column.name for column in Source.__table__.columns}
