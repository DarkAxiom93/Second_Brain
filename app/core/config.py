"""Typed application configuration loaded from environment variables."""

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, SecretStr, StringConstraints, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

NonBlankString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
TcpPort = Annotated[int, Field(ge=1, le=65535)]
EmbeddingDimensions = Annotated[int, Field(ge=1536, le=1536)]
EmbeddingTimeout = Annotated[float, Field(gt=0, le=120)]
ExtractionPromptVersion = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)
]
ExtractionTimeout = Annotated[float, Field(gt=0, le=300)]
ExtractionMaxOutputTokens = Annotated[int, Field(ge=1, le=32000)]
AnswerMaxOutputTokens = Annotated[int, Field(ge=1, le=4000)]
AutomationBatchSize = Annotated[int, Field(ge=1, le=16)]
AutomationLeaseSeconds = Annotated[int, Field(ge=10, le=300)]


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

    openai_api_key: SecretStr | None = None
    embedding_provider: Literal["openai"] = "openai"
    embedding_model: NonBlankString = "text-embedding-3-small"
    embedding_dimensions: EmbeddingDimensions = 1536
    embedding_timeout_seconds: EmbeddingTimeout = 30
    extraction_provider: Literal["openai"] = "openai"
    extraction_model: NonBlankString = "gpt-5.6-terra"
    extraction_prompt_version: ExtractionPromptVersion = "memory_proposals_v1"
    extraction_timeout_seconds: ExtractionTimeout = 60
    extraction_max_output_tokens: ExtractionMaxOutputTokens = 8000
    answer_provider: Literal["openai"] = "openai"
    answer_model: NonBlankString = "gpt-5.6-terra"
    answer_timeout_seconds: ExtractionTimeout = 60
    answer_max_output_tokens: AnswerMaxOutputTokens = 1200
    automation_scheduler_batch_size: AutomationBatchSize = 16
    automation_lease_seconds: AutomationLeaseSeconds = 60

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
