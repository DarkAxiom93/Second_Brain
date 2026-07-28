"""Tests for the FastAPI application and liveness endpoint."""

import logging
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from app.core.config import get_settings

APP_ENVIRONMENT_VARIABLES = (
    "APP_NAME",
    "APP_ENV",
    "APP_HOST",
    "APP_PORT",
    "APP_LOG_LEVEL",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "DATABASE_URL",
)


@pytest.fixture(autouse=True)
def isolate_application_environment(monkeypatch: MonkeyPatch) -> Iterator[None]:
    """Keep API tests independent from local environment and dotenv files."""

    for variable in APP_ENVIRONMENT_VARIABLES:
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.chdir(Path(__file__).parent)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def build_application() -> FastAPI:
    """Import and create the app only after test environment isolation."""

    from app.main import create_app

    return create_app()


def test_health_returns_http_200() -> None:
    response = TestClient(build_application()).get("/health")
    assert response.status_code == 200


def test_health_returns_exact_json() -> None:
    response = TestClient(build_application()).get("/health")
    assert response.json() == {"status": "ok"}


def test_health_returns_json_content_type() -> None:
    response = TestClient(build_application()).get("/health")
    assert response.headers["content-type"] == "application/json"


def test_health_rejects_post() -> None:
    response = TestClient(build_application()).post("/health")
    assert response.status_code == 405


def test_health_appears_in_openapi_schema() -> None:
    schema = build_application().openapi()
    assert "/health" in schema["paths"]
    assert "get" in schema["paths"]["/health"]


def test_application_title_uses_app_name(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("APP_NAME", "Configured Brain API")
    get_settings.cache_clear()
    application = build_application()
    assert application.title == "Configured Brain API"
    get_settings.cache_clear()


def test_application_creation_does_not_require_postgresql(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("POSTGRES_HOST", "unreachable.invalid")
    monkeypatch.setenv("DATABASE_URL", "postgresql://unreachable.invalid/database")
    get_settings.cache_clear()
    application = build_application()
    assert application.title
    assert TestClient(application).get("/health").status_code == 200
    get_settings.cache_clear()


def test_create_app_is_idempotent() -> None:
    first_application = build_application()
    first_route_paths = [
        path
        for route in first_application.routes
        if (path := getattr(route, "path", None)) is not None
    ]
    handler_count = len(logging.getLogger().handlers)
    second_application = build_application()
    second_route_paths = [
        path
        for route in second_application.routes
        if (path := getattr(route, "path", None)) is not None
    ]
    assert first_route_paths == second_route_paths
    assert len(second_route_paths) == len(set(second_route_paths))
    assert len(logging.getLogger().handlers) == handler_count
