"""Typed application configuration loaded from environment variables."""

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, SecretStr, StringConstraints, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

NonBlankString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
TcpPort = Annotated[int, Field(ge=1, le=65535)]


class Settings(BaseSettings):
    """Runtime settings with documented development-placeholder defaults."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: NonBlankString = "Second Brain API"
    app_env: NonBlankString = "development"
    app_host: NonBlankString = "0.0.0.0"
    app_port: TcpPort = 8000
    app_log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    postgres_db: NonBlankString = "second_brain"
    postgres_user: NonBlankString = "second_brain"
    postgres_password: SecretStr = Field(
        default=SecretStr("change-me"),
        min_length=1,
    )
    postgres_host: NonBlankString = "db"
    postgres_port: TcpPort = 5432

    database_url: NonBlankString = (
        "postgresql+psycopg://second_brain:change-me@db:5432/second_brain"
    )

    @field_validator("postgres_password", mode="before")
    @classmethod
    def reject_blank_postgres_password(cls, value: object) -> object:
        """Reject a password containing no non-whitespace characters."""

        if isinstance(value, str) and not value.strip():
            raise ValueError("POSTGRES_PASSWORD must not be blank")
        return value


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings instance for dependency injection."""

    return Settings()
