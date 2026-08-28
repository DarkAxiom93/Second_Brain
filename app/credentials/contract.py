"""Exact-reference credential-store contract and safe failures."""

from dataclasses import dataclass
from typing import NewType, Protocol

CredentialReference = NewType("CredentialReference", str)


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
