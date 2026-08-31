"""Installed-app authorization and fenced credential lifecycle."""

import base64
import hashlib
import secrets
import threading
import urllib.parse
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass

from app.credentials import CredentialReference, CredentialStore, clear_secret
from app.google_oauth.contract import (
    AUTHORIZATION_ENDPOINT,
    SCOPE_SET,
    SCOPES,
    GoogleOAuthError,
    GoogleOAuthIdentityError,
    GoogleOAuthReplayError,
    GoogleOAuthTransportError,
    GoogleProvider,
)
from app.google_oauth.envelope import GoogleCredentialEnvelope
from app.google_oauth.identity import validate_id_token
from app.google_oauth.loopback import LoopbackCallback

_locks_guard = threading.Lock()
_locks: dict[str, threading.Lock] = {}


def _lock(reference: CredentialReference) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(str(reference), threading.Lock())


@dataclass(frozen=True, slots=True)
class AuthorizationResult:
    credential_reference: CredentialReference
    account_fingerprint: str


@dataclass(frozen=True, slots=True)
class RevocationResult:
    provider_revoked: bool
    local_deleted: bool


class GoogleOAuthService:
    def __init__(
        self,
        *,
        client_id: str,
        store: CredentialStore,
        provider: GoogleProvider,
        callback_factory: Callable[[], LoopbackCallback] = LoopbackCallback,
        browser_open: Callable[[str], bool] = webbrowser.open,
    ) -> None:
        if not client_id or len(client_id) > 512:
            raise GoogleOAuthError() from None
        self._client_id = client_id
        self._store = store
        self._provider = provider
        self._callback_factory = callback_factory
        self._browser_open = browser_open

    @staticmethod
    def _random() -> str:
        return secrets.token_urlsafe(32)

    def _authorize_envelope(self) -> GoogleCredentialEnvelope:
        verifier, state, nonce = self._random(), self._random(), self._random()
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .rstrip(b"=")
            .decode()
        )
        callback = self._callback_factory()
        query = urllib.parse.urlencode(
            {
                "client_id": self._client_id,
                "redirect_uri": callback.redirect_uri,
                "response_type": "code",
                "scope": " ".join(SCOPES),
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "state": state,
                "nonce": nonce,
            }
        )
        try:
            if not self._browser_open(f"{AUTHORIZATION_ENDPOINT}?{query}"):
                raise GoogleOAuthError() from None
            received = callback.wait()
            if not secrets.compare_digest(received.state, state):
                raise GoogleOAuthReplayError() from None
            tokens = self._provider.exchange_code(
                code=received.code,
                verifier=verifier,
                redirect_uri=callback.redirect_uri,
                client_id=self._client_id,
            )
            self._validate_scopes(tokens.scope)
            if tokens.id_token is None or tokens.refresh_token is None:
                raise GoogleOAuthIdentityError() from None
            fingerprint = validate_id_token(
                tokens.id_token,
                client_id=self._client_id,
                nonce=nonce,
                jwks=self._provider.jwks(),
            )
            return GoogleCredentialEnvelope(tokens.refresh_token, fingerprint)
        finally:
            callback.close()
            verifier = state = nonce = challenge = ""

    @staticmethod
    def _validate_scopes(scope: str) -> None:
        from app.google_oauth.contract import GoogleOAuthScopeError

        if frozenset(scope.split()) != SCOPE_SET:
            raise GoogleOAuthScopeError() from None

    def authorize(self) -> AuthorizationResult:
        envelope = self._authorize_envelope()
        secret = envelope.encode()
        try:
            reference = self._store.install(secret)
        finally:
            clear_secret(secret)
        return AuthorizationResult(reference, envelope.account_fingerprint)

    def status(self, reference: CredentialReference) -> dict[str, object]:
        secret = self._store.read(reference)
        try:
            envelope = GoogleCredentialEnvelope.decode(secret)
            return {
                "status": "authorized",
                "credential_reference": str(reference),
                "account_fingerprint": envelope.account_fingerprint,
                "generation": envelope.generation,
            }
        finally:
            clear_secret(secret)

    def refresh(self, reference: CredentialReference) -> str:
        secret = self._store.read(reference)
        try:
            original = GoogleCredentialEnvelope.decode(secret)
        finally:
            clear_secret(secret)
        tokens = self._provider.refresh(
            refresh_token=original.refresh_token, client_id=self._client_id
        )
        self._validate_scopes(tokens.scope)
        rotated = tokens.refresh_token or original.refresh_token
        replacement = GoogleCredentialEnvelope(
            rotated, original.account_fingerprint, original.generation + 1
        )
        encoded = replacement.encode()
        try:
            with _lock(reference):
                current_secret = self._store.read(reference)
                try:
                    current = GoogleCredentialEnvelope.decode(current_secret)
                finally:
                    clear_secret(current_secret)
                if current.generation != original.generation:
                    raise GoogleOAuthReplayError() from None
                self._store.replace(reference, encoded)
        finally:
            clear_secret(encoded)
        return tokens.access_token

    def reauthorize(self, reference: CredentialReference) -> AuthorizationResult:
        candidate = self._authorize_envelope()
        with _lock(reference):
            current_secret = self._store.read(reference)
            try:
                current = GoogleCredentialEnvelope.decode(current_secret)
            finally:
                clear_secret(current_secret)
            if candidate.account_fingerprint != current.account_fingerprint:
                raise GoogleOAuthIdentityError() from None
            replacement = GoogleCredentialEnvelope(
                candidate.refresh_token,
                current.account_fingerprint,
                current.generation + 1,
            ).encode()
            try:
                self._store.replace(reference, replacement)
            finally:
                clear_secret(replacement)
        return AuthorizationResult(reference, current.account_fingerprint)

    def revoke(self, reference: CredentialReference) -> RevocationResult:
        secret = self._store.read(reference)
        try:
            envelope = GoogleCredentialEnvelope.decode(secret)
        finally:
            clear_secret(secret)
        provider_revoked = True
        try:
            self._provider.revoke(token=envelope.refresh_token)
        except GoogleOAuthTransportError:
            provider_revoked = False
        local_deleted = True
        try:
            self._store.revoke(reference)
        except Exception:
            local_deleted = False
        return RevocationResult(provider_revoked, local_deleted)
