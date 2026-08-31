"""Fixed, bounded Google OAuth and JWK HTTP transport."""

import json
import threading
import time
from collections.abc import Callable

import httpx

from app.google_oauth.contract import (
    JWK_ENDPOINT,
    REVOCATION_ENDPOINT,
    SCOPE_SET,
    TOKEN_ENDPOINT,
    GoogleOAuthScopeError,
    GoogleOAuthTransportError,
    TokenResponse,
)

MAX_RESPONSE_BYTES = 1_048_576


class GoogleHttpProvider:
    """No generic request surface: three fixed provider operations only."""

    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._client = client or httpx.Client(
            timeout=httpx.Timeout(10, connect=5), follow_redirects=False
        )
        self._clock = clock
        self._cache_lock = threading.Lock()
        self._cached_jwks: dict[str, object] | None = None
        self._jwks_expires_at = 0.0

    @staticmethod
    def _json(response: httpx.Response) -> dict[str, object]:
        if response.is_redirect or response.status_code != 200:
            raise GoogleOAuthTransportError() from None
        content_type = response.headers.get("content-type", "").split(";", 1)[0]
        if content_type != "application/json":
            raise GoogleOAuthTransportError() from None
        try:
            body = bytearray()
            for chunk in response.iter_bytes():
                body.extend(chunk)
                if len(body) > MAX_RESPONSE_BYTES:
                    raise GoogleOAuthTransportError() from None
            value = json.loads(body)
        except (UnicodeError, json.JSONDecodeError):
            raise GoogleOAuthTransportError() from None
        if not isinstance(value, dict):
            raise GoogleOAuthTransportError() from None
        return value

    @staticmethod
    def _token(value: dict[str, object]) -> TokenResponse:
        try:
            access = value["access_token"]
            expires = value["expires_in"]
            scope = value["scope"]
            token_type = value["token_type"]
            if (
                not isinstance(access, str)
                or not access
                or len(access) > 8192
                or not isinstance(expires, int)
                or not 1 <= expires <= 86400
                or not isinstance(scope, str)
                or token_type != "Bearer"
            ):
                raise ValueError
            if frozenset(scope.split()) != SCOPE_SET:
                raise GoogleOAuthScopeError() from None
            refresh = value.get("refresh_token")
            identity = value.get("id_token")
            if refresh is not None and (
                not isinstance(refresh, str) or len(refresh) > 4096
            ):
                raise ValueError
            if identity is not None and (
                not isinstance(identity, str) or len(identity) > 16384
            ):
                raise ValueError
            return TokenResponse(access, expires, scope, identity, refresh)
        except GoogleOAuthScopeError:
            raise
        except (KeyError, TypeError, ValueError):
            raise GoogleOAuthTransportError() from None

    def exchange_code(
        self, *, code: str, verifier: str, redirect_uri: str, client_id: str
    ) -> TokenResponse:
        try:
            request = self._client.build_request(
                "POST",
                TOKEN_ENDPOINT,
                data={
                    "code": code,
                    "client_id": client_id,
                    "code_verifier": verifier,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
                headers={"accept": "application/json"},
            )
            response = self._client.send(request, stream=True)
            try:
                return self._token(self._json(response))
            finally:
                response.close()
        except (httpx.HTTPError, UnicodeError):
            raise GoogleOAuthTransportError() from None

    def refresh(self, *, refresh_token: str, client_id: str) -> TokenResponse:
        try:
            request = self._client.build_request(
                "POST",
                TOKEN_ENDPOINT,
                data={
                    "refresh_token": refresh_token,
                    "client_id": client_id,
                    "grant_type": "refresh_token",
                },
                headers={"accept": "application/json"},
            )
            response = self._client.send(request, stream=True)
            try:
                return self._token(self._json(response))
            finally:
                response.close()
        except (httpx.HTTPError, UnicodeError):
            raise GoogleOAuthTransportError() from None

    def revoke(self, *, token: str) -> None:
        try:
            request = self._client.build_request(
                "POST",
                REVOCATION_ENDPOINT,
                data={"token": token},
                headers={"accept": "application/json"},
            )
            response = self._client.send(request, stream=True)
            try:
                if response.is_redirect or response.status_code != 200:
                    raise GoogleOAuthTransportError() from None
                total = 0
                for chunk in response.iter_bytes():
                    total += len(chunk)
                    if total > 4096:
                        raise GoogleOAuthTransportError() from None
            finally:
                response.close()
        except httpx.HTTPError:
            raise GoogleOAuthTransportError() from None

    def jwks(self) -> dict[str, object]:
        with self._cache_lock:
            if self._cached_jwks is not None and self._clock() < self._jwks_expires_at:
                return self._cached_jwks
            try:
                request = self._client.build_request(
                    "GET", JWK_ENDPOINT, headers={"accept": "application/json"}
                )
                response = self._client.send(request, stream=True)
                try:
                    value = self._json(response)
                finally:
                    response.close()
                keys = value.get("keys")
                if not isinstance(keys, list) or not 1 <= len(keys) <= 20:
                    raise GoogleOAuthTransportError() from None
                self._cached_jwks = value
                self._jwks_expires_at = self._clock() + 3600
                return value
            except httpx.HTTPError:
                raise GoogleOAuthTransportError() from None
