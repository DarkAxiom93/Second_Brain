"""Integration test for database readiness."""

from fastapi.testclient import TestClient

from app.main import create_app


def test_readiness_returns_200_with_real_test_database(
    migrated_test_database: None,
) -> None:
    response = TestClient(create_app()).get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
