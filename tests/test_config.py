"""Tests for application configuration."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic import ValidationError
from pytest import MonkeyPatch

from app.core.config import Settings, get_settings

SUPPORTED_ENVIRONMENT_VARIABLES = (
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
    "SECOND_BRAIN_APP_NAME",
)


@pytest.fixture(autouse=True)
def isolate_settings_environment(
    monkeypatch: MonkeyPatch,
) -> Iterator[None]:
    """Keep tests independent from developer environment and local dotenv files."""

    for variable in SUPPORTED_ENVIRONMENT_VARIABLES:
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.chdir(Path(__file__).parent)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_settings_use_documented_development_placeholders() -> None:
    settings = Settings(_env_file=None)

    assert settings.app_name == "Second Brain API"
    assert settings.app_env == "development"
    assert settings.app_host == "0.0.0.0"
    assert settings.app_port == 8000
    assert settings.app_log_level == "INFO"
    assert settings.postgres_db == "second_brain"
    assert settings.postgres_user == "second_brain"
    assert settings.postgres_password.get_secret_value() == "change-me"
    assert settings.postgres_host == "db"
    assert settings.postgres_port == 5432
    assert settings.database_url.endswith("@db:5432/second_brain")


def test_settings_load_exact_environment_variable_names(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_NAME", "Knowledge API")
    monkeypatch.setenv("POSTGRES_PORT", "6543")

    settings = Settings(_env_file=None)

    assert settings.app_name == "Knowledge API"
    assert settings.postgres_port == 6543


def test_second_brain_prefix_is_not_required(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("SECOND_BRAIN_APP_NAME", "Legacy Name")

    settings = Settings(_env_file=None)

    assert settings.app_name == "Second Brain API"


def test_get_settings_returns_same_object_until_cleared() -> None:
    assert get_settings() is get_settings()


def test_clearing_cache_reloads_environment(monkeypatch: MonkeyPatch) -> None:
    first = get_settings()
    monkeypatch.setenv("APP_NAME", "Reloaded API")

    assert get_settings() is first

    get_settings.cache_clear()
    assert get_settings().app_name == "Reloaded API"


@pytest.mark.parametrize(
    ("variable", "value"),
    [("APP_PORT", "0"), ("APP_PORT", "65536"), ("POSTGRES_PORT", "0")],
)
def test_invalid_ports_are_rejected(
    monkeypatch: MonkeyPatch,
    variable: str,
    value: str,
) -> None:
    monkeypatch.setenv(variable, value)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@pytest.mark.parametrize(
    "variable",
    [
        "APP_NAME",
        "APP_ENV",
        "APP_HOST",
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_HOST",
        "DATABASE_URL",
    ],
)
def test_blank_required_strings_are_rejected(
    monkeypatch: MonkeyPatch,
    variable: str,
) -> None:
    monkeypatch.setenv(variable, "   ")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_postgres_password_is_masked(monkeypatch: MonkeyPatch) -> None:
    secret = "not-for-display"
    monkeypatch.setenv("POSTGRES_PASSWORD", secret)

    settings = Settings(_env_file=None)

    assert secret not in repr(settings)
    assert secret not in str(settings)
    assert "**********" in repr(settings)
