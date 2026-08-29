"""Structural tests for the closed GitHub HTTP request inventory."""

from dataclasses import fields

import httpx
import pytest

from app.connectors.github import (
    GITHUB_HOST,
    MAX_ATTEMPTS,
    MAX_RUN_BYTES,
    GitHubTransportError,
    HttpxGitHubTransport,
)
from app.connectors.validation import granted_scope_fingerprint

_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "second-brain-github-connector/1",
    "Accept-Encoding": "identity",
}


def _replace_client(
    transport: HttpxGitHubTransport, handler: httpx.MockTransport
) -> None:
    transport._client.close()
    transport._client = httpx.Client(
        base_url=f"https://{GITHUB_HOST}",
        headers=_HEADERS,
        follow_redirects=False,
        transport=handler,
    )


def test_exact_get_only_request_inventory_and_headers() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/user":
            return httpx.Response(200, json={"login": "operator"})
        if request.url.path == "/repos/owner/repo":
            return httpx.Response(200, json={"id": 1})
        return httpx.Response(200, json=[])

    transport = HttpxGitHubTransport()
    _replace_client(transport, httpx.MockTransport(handler))
    secret = bytearray(b"fake-secret")
    transport.user(secret)
    transport.repository(secret, "owner/repo")
    transport.issues(secret, "owner/repo", 1)
    transport.pulls(secret, "owner/repo", 2)
    assert [(r.method, r.url.path, r.url.query.decode()) for r in requests] == [
        ("GET", "/user", ""),
        ("GET", "/repos/owner/repo", ""),
        ("GET", "/repos/owner/repo/issues", "state=all&per_page=50&page=1"),
        ("GET", "/repos/owner/repo/pulls", "state=all&per_page=50&page=2"),
    ]
    assert all(r.url.host == GITHUB_HOST and r.content == b"" for r in requests)
    assert all(r.headers["accept"] == "application/vnd.github+json" for r in requests)
    assert all(r.headers["x-github-api-version"] == "2022-11-28" for r in requests)
    assert all(r.headers["accept-encoding"] == "identity" for r in requests)
    assert not {"request", "post", "put", "patch", "delete", "graphql"} & set(
        dir(transport)
    )


def test_redirect_is_rejected_and_retry_is_at_most_once() -> None:
    redirect = HttpxGitHubTransport()
    _replace_client(
        redirect,
        httpx.MockTransport(
            lambda request: httpx.Response(
                302, headers={"location": "https://evil.invalid"}
            )
        ),
    )
    with pytest.raises(GitHubTransportError, match=r"^github_redirect$"):
        redirect.user(bytearray(b"fake"))

    attempts = 0

    def unavailable(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(503)

    retry = HttpxGitHubTransport()
    _replace_client(retry, httpx.MockTransport(unavailable))
    with pytest.raises(GitHubTransportError, match=r"^github_unavailable$"):
        retry.user(bytearray(b"fake"))
    assert attempts == 2


def test_non_json_and_oversized_responses_fail_closed() -> None:
    invalid = HttpxGitHubTransport()
    _replace_client(
        invalid,
        httpx.MockTransport(lambda request: httpx.Response(200, content=b"not-json")),
    )
    with pytest.raises(GitHubTransportError, match=r"^github_invalid_response$"):
        invalid.user(bytearray(b"fake"))

    oversized = HttpxGitHubTransport()
    _replace_client(
        oversized,
        httpx.MockTransport(
            lambda request: httpx.Response(200, content=b" " * (2 * 1024 * 1024 + 1))
        ),
    )
    with pytest.raises(GitHubTransportError, match=r"^github_response_oversized$"):
        oversized.user(bytearray(b"fake"))


@pytest.mark.parametrize(
    ("status", "headers", "code"),
    [
        (401, {}, "github_unauthorized"),
        (403, {}, "github_forbidden"),
        (403, {"x-ratelimit-remaining": "0"}, "github_rate_limited"),
        (429, {"retry-after": "999999"}, "github_rate_limited"),
        (404, {}, "github_not_found"),
    ],
)
def test_auth_rate_limit_and_not_found_are_never_retried(
    status: int, headers: dict[str, str], code: str
) -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(status, headers=headers)

    transport = HttpxGitHubTransport()
    _replace_client(transport, httpx.MockTransport(handler))
    with pytest.raises(GitHubTransportError, match=rf"^{code}$"):
        transport.user(bytearray(b"fake"))
    assert attempts == 1


def test_request_run_byte_and_deadline_ceilings_prevent_requests() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={})

    request_ceiling = HttpxGitHubTransport()
    _replace_client(request_ceiling, httpx.MockTransport(handler))
    request_ceiling._attempts = MAX_ATTEMPTS
    with pytest.raises(GitHubTransportError, match=r"^github_request_ceiling$"):
        request_ceiling.user(bytearray(b"fake"))
    assert calls == 0

    byte_ceiling = HttpxGitHubTransport()
    _replace_client(byte_ceiling, httpx.MockTransport(handler))
    byte_ceiling._bytes = MAX_RUN_BYTES
    with pytest.raises(GitHubTransportError, match=r"^github_run_byte_ceiling$"):
        byte_ceiling.user(bytearray(b"fake"))

    times = iter((0.0, 61.0))
    deadline = HttpxGitHubTransport(clock=lambda: next(times))
    _replace_client(deadline, httpx.MockTransport(handler))
    with pytest.raises(GitHubTransportError, match=r"^github_deadline_ceiling$"):
        deadline.user(bytearray(b"fake"))


@pytest.mark.parametrize(
    "secret", [bytearray(), bytearray(b"line\nbreak"), bytearray(b"\xff")]
)
def test_invalid_credential_bytes_fail_before_http(secret: bytearray) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={})

    transport = HttpxGitHubTransport()
    _replace_client(transport, httpx.MockTransport(handler))
    with pytest.raises(GitHubTransportError, match=r"^credential_invalid$"):
        transport.user(secret)
    assert calls == 0


def test_provider_permission_headers_are_discarded_and_cannot_define_authority() -> (
    None
):
    approved = ("metadata_read", "issues_read", "pull_requests_read")
    before = granted_scope_fingerprint(approved)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"login": "operator"},
            headers={
                "X-Accepted-GitHub-Permissions": (
                    "contents=write, administration=write"
                ),
                "X-OAuth-Scopes": "repo, admin:org",
            },
        )

    transport = HttpxGitHubTransport()
    _replace_client(transport, httpx.MockTransport(handler))
    page = transport.user(bytearray(b"fake"))
    assert page.value == {"login": "operator"}
    assert [field.name for field in fields(page)] == ["value", "may_have_more"]
    assert "permission" not in repr(page).casefold()
    assert granted_scope_fingerprint(approved) == before
    with pytest.raises(ValueError):
        granted_scope_fingerprint(("contents_write",))
