"""Unit tests for Memory repository transaction boundaries."""

from unittest.mock import Mock

from app.repositories.memories import create_memory
from app.schemas.memory import MemoryCreate


def test_create_memory_flushes_and_refreshes_without_committing() -> None:
    session = Mock()
    memory = create_memory(session, MemoryCreate(content="fact"))
    session.add.assert_called_once_with(memory)
    session.flush.assert_called_once_with()
    session.refresh.assert_called_once_with(memory)
    session.commit.assert_not_called()
