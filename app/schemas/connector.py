"""Closed public contracts for metadata-only connector account management."""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

ExternalAccountIdentity = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
]
RepositoryIdentity = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=3, max_length=201)
]
CredentialReference = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=46, max_length=46)
]
Lifecycle = Literal["disabled", "enabled", "revoked"]
ValidationStatus = Literal["unvalidated", "valid", "invalid", "expired", "revoked"]


class ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ConnectorScope(ClosedModel):
    kind: Literal["project", "unassigned"]
    project_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def exact_scope(self) -> "ConnectorScope":
        if (self.kind == "project") != (self.project_id is not None):
            raise ValueError("scope must be one exact Project or explicit unassigned")
        return self


class ConnectorAccountCreate(ClosedModel):
    external_account_identity: ExternalAccountIdentity
    credential_reference: CredentialReference
    scope: ConnectorScope
    repositories: Annotated[
        list[RepositoryIdentity], Field(min_length=1, max_length=32)
    ]


class ConnectorAccountUpdate(ClosedModel):
    expected_revision: Annotated[int, Field(ge=0)]
    scope: ConnectorScope | None = None
    repositories: (
        Annotated[list[RepositoryIdentity], Field(min_length=1, max_length=32)] | None
    ) = None

    @model_validator(mode="after")
    def require_change(self) -> "ConnectorAccountUpdate":
        if self.scope is None and self.repositories is None:
            raise ValueError("at least one configuration field is required")
        return self


class ConnectorRevisionRequest(ClosedModel):
    expected_revision: Annotated[int, Field(ge=0)]


class ConnectorAccountRead(ClosedModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: uuid.UUID
    provider: Literal["github"]
    external_account_identity: str
    scope: ConnectorScope
    repositories: list[str]
    lifecycle: Lifecycle
    validation_status: ValidationStatus
    revision: int
    last_validated_at: datetime | None
    created_at: datetime
    updated_at: datetime
