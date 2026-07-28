"""Unit tests for Memory repository query and transaction boundaries."""

import uuid
from unittest.mock import Mock

from app.repositories.memories import create_memory, get_memory, list_memories
from app.schemas.memory import MemoryCreate


def test_create_memory_flushes_and_refreshes_without_committing() -> None:
    session = Mock()
    memory = create_memory(session, MemoryCreate(content="fact"))
    session.add.assert_called_once_with(memory)
    session.flush.assert_called_once_with()
    session.refresh.assert_called_once_with(memory)
    session.commit.assert_not_called()


def test_list_memories_executes_filtered_paginated_select_without_committing() -> None:
    session = Mock()
    session.scalars.return_value.all.return_value = []
    project_id = uuid.uuid4()

    assert list_memories(session, project_id=project_id, limit=10, offset=20) == []

    statement = session.scalars.call_args.args[0]
    compiled = str(statement.compile(compile_kwargs={"literal_binds": True}))
    assert "memories.project_id" in compiled
    assert "ORDER BY memories.created_at DESC, memories.id ASC" in compiled
    assert "LIMIT 10" in compiled
    assert "OFFSET 20" in compiled
    session.commit.assert_not_called()


def test_get_memory_executes_select_without_committing() -> None:
    session = Mock()
    stored = Mock()
    session.scalar.return_value = stored
    memory_id = uuid.uuid4()

    assert get_memory(session, memory_id) is stored

    statement = session.scalar.call_args.args[0]
    compiled = str(statement.compile(compile_kwargs={"literal_binds": True}))
    assert memory_id.hex in compiled
    session.commit.assert_not_called()
