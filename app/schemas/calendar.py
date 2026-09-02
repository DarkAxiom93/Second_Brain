"""Safe public contracts for Calendar account metadata management."""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

CredentialReference = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=46, max_length=46)
]
AccountFingerprint = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
CalendarId = Annotated[str, StringConstraints(min_length=1, max_length=1024)]


class ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CalendarScope(ClosedModel):
    kind: Literal["project", "unassigned"]
    project_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def exact_scope(self) -> "CalendarScope":
        if (self.kind == "project") != (self.project_id is not None):
            raise ValueError("scope must be one exact Project or explicit unassigned")
        return self


class CalendarAccountCreate(ClosedModel):
    credential_reference: CredentialReference
    account_fingerprint: AccountFingerprint
    scope: CalendarScope
    calendar_ids: Annotated[list[CalendarId], Field(min_length=1, max_length=10)]


class CalendarAccountUpdate(ClosedModel):
    expected_revision: Annotated[int, Field(ge=1)]
    scope: CalendarScope | None = None
    calendar_ids: (
        Annotated[list[CalendarId], Field(min_length=1, max_length=10)] | None
    ) = None
    credential_reference: CredentialReference | None = None

    @model_validator(mode="after")
    def require_change(self) -> "CalendarAccountUpdate":
        if (
            self.scope is None
            and self.calendar_ids is None
            and self.credential_reference is None
        ):
            raise ValueError("at least one configuration field is required")
        return self


class CalendarRevisionRequest(ClosedModel):
    expected_revision: Annotated[int, Field(ge=1)]


class CalendarRevocationRead(ClosedModel):
    account: "CalendarAccountRead"
    provider_revoked: bool
    local_deleted: bool


class CalendarAccountRead(ClosedModel):
    id: uuid.UUID
    provider: Literal["google_calendar"] = "google_calendar"
    account_fingerprint: str
    lifecycle: Literal["enabled", "disabled", "revoked"]
    configuration_revision: int
    scope: CalendarScope
    calendar_ids: list[str]
    credential_status: Literal["valid", "missing", "unavailable", "revoked"]
    created_at: datetime
    updated_at: datetime
