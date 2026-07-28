"""Unit tests for readiness and database-session lifecycle behavior."""

from collections.abc import Generator
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.db import dependencies
from app.db.dependencies import get_db_session
from app.main import create_app


def test_readiness_returns_generic_503_on_database_failure() -> None:
    failing_session = Mock()
    failing_session.execute.side_effect = OperationalError(
        "SELECT 1",
        {},
        Exception("sensitive connection details"),
    )

    def override_session() -> Generator[Mock, None, None]:
        yield failing_session

    application = create_app()
    application.dependency_overrides[get_db_session] = override_session
    response = TestClient(application).get("/ready")

    assert response.status_code == 503
    assert response.json() == {"detail": "database unavailable"}
    assert "sensitive" not in response.text


def test_database_dependency_closes_session(monkeypatch: pytest.MonkeyPatch) -> None:
    session = Mock()
    monkeypatch.setattr(dependencies, "get_session_factory", lambda: lambda: session)

    dependency = dependencies.get_db_session()
    assert next(dependency) is session
    dependency.close()

    session.close.assert_called_once_with()
    session.rollback.assert_not_called()


def test_database_dependency_rolls_back_and_closes_on_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = Mock()
    monkeypatch.setattr(dependencies, "get_session_factory", lambda: lambda: session)

    dependency = dependencies.get_db_session()
    next(dependency)
    with pytest.raises(RuntimeError, match="request failed"):
        dependency.throw(RuntimeError("request failed"))

    session.rollback.assert_called_once_with()
    session.close.assert_called_once_with()
