"""Application-owned OS credential-store boundary."""

from app.credentials.contract import (
    CredentialReference,
    CredentialStore,
    CredentialStoreError,
    CredentialStoreLockedError,
    CredentialStoreMissingError,
    CredentialStoreStatus,
    CredentialStoreUnavailableError,
    clear_secret,
    validate_credential_reference,
)
from app.credentials.windows import WindowsCredentialStore

__all__ = [
    "CredentialReference",
    "CredentialStore",
    "CredentialStoreError",
    "CredentialStoreLockedError",
    "CredentialStoreMissingError",
    "CredentialStoreStatus",
    "CredentialStoreUnavailableError",
    "WindowsCredentialStore",
    "clear_secret",
    "validate_credential_reference",
]
