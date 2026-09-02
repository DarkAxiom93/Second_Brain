"""Production CP99 credential boundary for Calendar metadata lifecycle."""

from typing import Protocol

from app.core.config import get_settings
from app.credentials import CredentialReference
from app.credentials.windows import WindowsCredentialStore
from app.google_oauth.service import GoogleOAuthService, RevocationResult
from app.google_oauth.transport import GoogleHttpProvider


class CalendarCredentialBoundary(Protocol):
    def status(self, reference: CredentialReference) -> dict[str, object]: ...
    def revoke(self, reference: CredentialReference) -> RevocationResult: ...


def calendar_credential_dependency() -> CalendarCredentialBoundary:
    client_id = get_settings().google_oauth_client_id
    if client_id is None:
        raise RuntimeError("google oauth is not configured")
    return GoogleOAuthService(
        client_id=client_id,
        store=WindowsCredentialStore(),
        provider=GoogleHttpProvider(),
    )
