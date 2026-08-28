"""Exact-reference credential-store contract and safe failures."""

import re
from dataclasses import dataclass
from typing import NewType, Protocol

CredentialReference = NewType("CredentialReference", str)
_REFERENCE_PATTERN = re.compile(
    r"\Asbcred:v1:[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-"
    r"[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z"
)


def validate_credential_reference(value: str) -> CredentialReference:
    """Return the exact application-owned opaque form or fail closed."""

    if _REFERENCE_PATTERN.fullmatch(value) is None:
        raise ValueError("invalid credential reference")
    return CredentialReference(value)


@dataclass(frozen=True, slots=True)
class CredentialStoreStatus:
    """Content-free capability status safe for operator diagnostics."""

    available: bool
    code: str


class CredentialStoreError(Exception):
    """Base failure with an application-owned, non-sensitive message."""

    code = "credential_store_error"

    def __init__(self) -> None:
        super().__init__(self.code)


class CredentialStoreMissingError(CredentialStoreError):
    code = "credential_missing"


class CredentialStoreLockedError(CredentialStoreError):
    code = "credential_store_locked"


class CredentialStoreUnavailableError(CredentialStoreError):
    code = "credential_store_unavailable"


class CredentialStore(Protocol):
    """Small non-enumerating store contract for future internal connector use."""

    def install(self, secret: bytearray) -> CredentialReference: ...
    def read(self, reference: CredentialReference) -> bytearray: ...
    def replace(self, reference: CredentialReference, secret: bytearray) -> None: ...
    def revoke(self, reference: CredentialReference) -> None: ...
    def status(self) -> CredentialStoreStatus: ...


def clear_secret(secret: bytearray) -> None:
    """Overwrite a transient mutable secret buffer in place."""

    secret[:] = b"\x00" * len(secret)
