"""Checkpoint 99 deterministic fake-provider security and lifecycle tests."""

import json
import threading
import urllib.parse
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from app.credentials import CredentialReference, CredentialStoreUnavailableError
from app.credentials.fake import FakeCredentialStore
from app.google_oauth.contract import (
    SCOPES,
    GoogleOAuthIdentityError,
    GoogleOAuthReplayError,
    GoogleOAuthScopeError,
    GoogleOAuthTransportError,
    TokenResponse,
)
from app.google_oauth.envelope import GoogleCredentialEnvelope
from app.google_oauth.identity import account_fingerprint, validate_id_token
from app.google_oauth.loopback import LoopbackCallback
from app.google_oauth.service import GoogleOAuthService
from app.google_oauth.transport import GoogleHttpProvider

CLIENT_ID = "obviously-fake-google-client-id.apps.googleusercontent.com"
REFERENCE = CredentialReference("sbcred:v1:12345678-1234-4123-8123-123456789abc")
PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
JWK = json.loads(RSAAlgorithm.to_jwk(PRIVATE_KEY.public_key())) | {
    "kid": "fake-key",
    "alg": "RS256",
    "use": "sig",
}


def _token(attempt_nonce: str, **overrides: object) -> str:
    now = datetime.now(UTC)
    claims: dict[str, object] = {
        "iss": "https://accounts.google.com",
        "aud": CLIENT_ID,
        "exp": now + timedelta(minutes=5),
        "iat": now,
        "nonce": attempt_nonce,
        "sub": "synthetic-google-subject-123",
        "email": "must-be-discarded@example.invalid",
    }
    claims.update(overrides)
    return jwt.encode(
        claims, PRIVATE_KEY, algorithm="RS256", headers={"kid": "fake-key"}
    )


class Callback:
    redirect_uri = "http://127.0.0.1:43210/oauth/google/callback"

    def __init__(self) -> None:
        self.state = ""
        self.closed = False

    def wait(self) -> object:
        return type("Result", (), {"code": "synthetic-code", "state": self.state})()

    def close(self) -> None:
        self.closed = True


class Provider:
    def __init__(self) -> None:
        self.nonce = ""
        self.refreshes = 0
        self.revocation_failure = False

    def exchange_code(self, **kwargs: str) -> TokenResponse:
        assert kwargs["code"] == "synthetic-code"
        assert len(kwargs["verifier"]) >= 43
        return TokenResponse(
            "synthetic-access",
            3600,
            " ".join(reversed(SCOPES)),
            _token(self.nonce),
            "synthetic-refresh",
        )

    def refresh(self, **kwargs: str) -> TokenResponse:
        self.refreshes += 1
        return TokenResponse(
            "rotated-access", 3600, " ".join(SCOPES), None, "rotated-refresh"
        )

    def revoke(self, **kwargs: str) -> None:
        if self.revocation_failure:
            raise GoogleOAuthTransportError() from None
        assert kwargs["token"]

    def jwks(self) -> dict[str, object]:
        return {"keys": [JWK]}


def _service(store: FakeCredentialStore, provider: Provider) -> GoogleOAuthService:
    callback = Callback()

    def browser(url: str) -> bool:
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        assert set(query["scope"][0].split()) == set(SCOPES)
        assert "email" not in query["scope"] and "profile" not in query["scope"]
        assert query["code_challenge_method"] == ["S256"]
        callback.state = query["state"][0]
        provider.nonce = query["nonce"][0]
        return True

    return GoogleOAuthService(
        client_id=CLIENT_ID,
        store=store,
        provider=provider,
        callback_factory=lambda: callback,  # type: ignore[arg-type]
        browser_open=browser,
    )


def test_authorize_refresh_rotation_status_and_revoke_are_minimized() -> None:
    store = FakeCredentialStore(reference_factory=lambda: REFERENCE)
    provider = Provider()
    service = _service(store, provider)
    result = service.authorize()
    expected = account_fingerprint("synthetic-google-subject-123")
    assert result.account_fingerprint == expected
    assert service.status(REFERENCE) == {
        "status": "authorized",
        "credential_reference": str(REFERENCE),
        "account_fingerprint": expected,
        "generation": 1,
    }
    raw = store.read(REFERENCE)
    assert (
        b"email" not in raw
        and b"synthetic-access" not in raw
        and b"id_token" not in raw
    )
    assert service.refresh(REFERENCE) == "rotated-access"
    envelope = GoogleCredentialEnvelope.decode(store.read(REFERENCE))
    assert envelope.refresh_token == "rotated-refresh" and envelope.generation == 2
    revoked = service.revoke(REFERENCE)
    assert revoked.provider_revoked and revoked.local_deleted


@pytest.mark.parametrize(
    "overrides",
    [
        {"iss": "https://attacker.invalid"},
        {"aud": "wrong-client"},
        {"nonce": "wrong"},
        {"sub": ""},
        {"iat": datetime.now(UTC) - timedelta(hours=2)},
        {"exp": datetime.now(UTC) - timedelta(minutes=1)},
    ],
)
def test_id_token_claim_failures(overrides: dict[str, object]) -> None:
    with pytest.raises(GoogleOAuthIdentityError):
        validate_id_token(
            _token("expected", **overrides),
            client_id=CLIENT_ID,
            nonce="expected",
            jwks={"keys": [JWK]},
        )


def test_forged_malformed_unknown_key_and_exact_fingerprint() -> None:
    assert account_fingerprint("abc") == (
        "b6abc4eb824ae8a436da6ff9a3264777b8232631d76de1cc70f10838b45c51cc"
    )
    for token, keys in (("malformed", [JWK]), (_token("n"), [])):
        with pytest.raises(GoogleOAuthIdentityError):
            validate_id_token(
                token, client_id=CLIENT_ID, nonce="n", jwks={"keys": keys}
            )


def test_reauthorization_account_substitution_preserves_prior_envelope() -> None:
    store = FakeCredentialStore(reference_factory=lambda: REFERENCE)
    provider = Provider()
    service = _service(store, provider)
    service.authorize()
    before = bytes(store.read(REFERENCE))
    provider.jwks = lambda: {"keys": [JWK]}  # type: ignore[method-assign]
    original_exchange = provider.exchange_code

    def changed(**kwargs: str) -> TokenResponse:
        result = original_exchange(**kwargs)
        return TokenResponse(
            result.access_token,
            result.expires_in,
            result.scope,
            _token(provider.nonce, sub="different-account"),
            result.refresh_token,
        )

    provider.exchange_code = changed  # type: ignore[method-assign]
    with pytest.raises(GoogleOAuthIdentityError):
        service.reauthorize(REFERENCE)
    assert bytes(store.read(REFERENCE)) == before


def test_stale_refresh_is_generation_fenced_with_barrier() -> None:
    store = FakeCredentialStore(reference_factory=lambda: REFERENCE)
    provider = Provider()
    service = _service(store, provider)
    service.authorize()
    barrier = threading.Barrier(2)
    original = provider.refresh

    def synchronized(**kwargs: str) -> TokenResponse:
        result = original(**kwargs)
        barrier.wait()
        return result

    provider.refresh = synchronized  # type: ignore[method-assign]
    outcomes: list[str] = []

    def run() -> None:
        try:
            service.refresh(REFERENCE)
            outcomes.append("ok")
        except GoogleOAuthReplayError:
            outcomes.append("fenced")

    threads = [threading.Thread(target=run) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(outcomes) == ["fenced", "ok"]


def test_transport_rejects_scope_drift_and_caches_bounded_jwks() -> None:
    import httpx

    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if str(request.url).endswith("/certs"):
            return httpx.Response(200, json={"keys": [JWK]})
        return httpx.Response(
            200,
            json={
                "access_token": "fake",
                "expires_in": 3600,
                "scope": "openid email",
                "token_type": "Bearer",
            },
        )

    provider = GoogleHttpProvider(
        client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    with pytest.raises(GoogleOAuthScopeError):
        provider.refresh(refresh_token="fake", client_id=CLIENT_ID)
    assert provider.jwks() == provider.jwks()
    assert calls == 2


def test_revocation_reports_provider_failure_separately_and_deletes_local() -> None:
    store = FakeCredentialStore(reference_factory=lambda: REFERENCE)
    provider = Provider()
    service = _service(store, provider)
    service.authorize()
    provider.revocation_failure = True
    result = service.revoke(REFERENCE)
    assert not result.provider_revoked and result.local_deleted


def test_revocation_reports_local_deletion_failure_separately() -> None:
    class DeleteFailStore(FakeCredentialStore):
        def revoke(self, reference: CredentialReference) -> None:
            del reference
            raise CredentialStoreUnavailableError() from None

    store = DeleteFailStore(reference_factory=lambda: REFERENCE)
    provider = Provider()
    service = _service(store, provider)
    service.authorize()
    result = service.revoke(REFERENCE)
    assert result.provider_revoked and not result.local_deleted


def test_successful_same_account_reauthorization_rotates_generation() -> None:
    store = FakeCredentialStore(reference_factory=lambda: REFERENCE)
    provider = Provider()
    service = _service(store, provider)
    service.authorize()
    result = service.reauthorize(REFERENCE)
    assert result.credential_reference == REFERENCE
    assert service.status(REFERENCE)["generation"] == 2


def test_provider_error_body_and_exception_never_escape() -> None:
    import httpx

    canary = "cp99-provider-secret-canary-must-not-escape"

    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(500, content=canary.encode())

    provider = GoogleHttpProvider(
        client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    with pytest.raises(GoogleOAuthTransportError) as raised:
        provider.refresh(refresh_token=canary, client_id=CLIENT_ID)
    assert canary not in str(raised.value)
    assert canary not in repr(raised.value)


@pytest.mark.parametrize(
    "target",
    [
        "/wrong?code=x&state=y",
        "/oauth/google/callback?code=x&code=z&state=y",
        "/oauth/google/callback?code=x&state=y&email=forbidden",
        "/oauth/google/callback?error=access_denied&state=y",
        "https://attacker.invalid/oauth/google/callback?code=x&state=y",
    ],
)
def test_callback_rejects_wrong_path_duplicates_ambiguity_and_non_loopback(
    target: str,
) -> None:
    callback = LoopbackCallback()
    try:
        assert callback._receive(target) == 400
        assert callback._receive("/oauth/google/callback?code=x&state=y") == 409
    finally:
        callback.close()


def test_callback_timeout_is_bounded() -> None:
    from app.google_oauth.contract import GoogleOAuthTimeoutError

    callback = LoopbackCallback()
    with pytest.raises(GoogleOAuthTimeoutError):
        callback.wait(timeout=0)
