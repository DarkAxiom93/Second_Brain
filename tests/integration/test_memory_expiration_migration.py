"""PostgreSQL lifecycle tests for the Memory expiration status migration."""

import uuid

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.db.session import get_engine, reset_database_state
from tests.integration.conftest import verify_connected_test_database


def test_expiration_migration_upgrade_clean_downgrade_and_reupgrade(
    test_database_url: str, alembic_config: Config
) -> None:
    verify_connected_test_database(test_database_url)
    command.downgrade(alembic_config, "0008_memory_proposals")
    command.upgrade(alembic_config, "0009_memory_expiration")
    with get_engine().begin() as connection:
        memory_id = uuid.uuid4()
        connection.execute(
            text(
                "INSERT INTO memories (id, content, status) "
                "VALUES (:id, 'x', 'expired')"
            ),
            {"id": memory_id},
        )
    with pytest.raises(DBAPIError, match="cannot downgrade memory expiration"):
        command.downgrade(alembic_config, "0008_memory_proposals")
    with get_engine().begin() as connection:
        connection.execute(
            text("DELETE FROM memories WHERE id = :id"), {"id": memory_id}
        )
    command.downgrade(alembic_config, "0008_memory_proposals")
    command.upgrade(alembic_config, "head")
    reset_database_state()
