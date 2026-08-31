"""Immutable CP99 OAuth constants, safe types, and errors."""

from dataclasses import dataclass
from typing import Protocol

AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
REVOCATION_ENDPOINT = "https://oauth2.googleapis.com/revoke"
JWK_ENDPOINT = "https://www.googleapis.com/oauth2/v3/certs"
CALLBACK_PATH = "/oauth/google/callback"
SCOPES = (
    "openid",
    "https://www.googleapis.com/auth/calendar.events.readonly",
)
SCOPE_SET = frozenset(SCOPES)


class GoogleOAuthError(Exception):
    """Content-free application-owned OAuth failure."""

    code = "google_oauth_failed"

    def __init__(self) -> None:
        super().__init__(self.code)


class GoogleOAuthTimeoutError(GoogleOAuthError):
    code = "google_oauth_timeout"


class GoogleOAuthIdentityError(GoogleOAuthError):
    code = "google_oauth_identity_invalid"


class GoogleOAuthScopeError(GoogleOAuthError):
    code = "google_oauth_scope_invalid"


class GoogleOAuthReplayError(GoogleOAuthError):
    code = "google_oauth_replay"


class GoogleOAuthTransportError(GoogleOAuthError):
    code = "google_oauth_provider_failed"


@dataclass(frozen=True, slots=True)
class TokenResponse:
    access_token: str
    expires_in: int
    scope: str
    id_token: str | None = None
    refresh_token: str | None = None


class GoogleProvider(Protocol):
    def exchange_code(
        self, *, code: str, verifier: str, redirect_uri: str, client_id: str
    ) -> TokenResponse: ...

    def refresh(self, *, refresh_token: str, client_id: str) -> TokenResponse: ...

    def revoke(self, *, token: str) -> None: ...

    def jwks(self) -> dict[str, object]: ...
