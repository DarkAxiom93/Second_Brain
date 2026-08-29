"""Closed, bounded, GET-only GitHub REST transport."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import quote

import httpx

GITHUB_HOST = "api.github.com"
PAGE_SIZE = 50
MAX_PAGES = 2
MAX_ATTEMPTS = 128
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_RUN_BYTES = 32 * 1024 * 1024
RUN_DEADLINE_SECONDS = 60.0
_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "second-brain-github-connector/1",
    "Accept-Encoding": "identity",
}


class GitHubTransportError(Exception):
    """Content-free transport failure."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class GitHubPage:
    value: object
    may_have_more: bool = False


class GitHubTransport(Protocol):
    def user(self, secret: bytearray) -> GitHubPage: ...

    def repository(self, secret: bytearray, repository: str) -> GitHubPage: ...

    def issues(self, secret: bytearray, repository: str, page: int) -> GitHubPage: ...

    def pulls(self, secret: bytearray, repository: str, page: int) -> GitHubPage: ...


class HttpxGitHubTransport:
    """Transport whose public surface cannot express arbitrary HTTP requests."""

    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._clock = clock
        self._started = clock()
        self._attempts = 0
        self._bytes = 0
        self._client = httpx.Client(
            base_url=f"https://{GITHUB_HOST}",
            headers=_HEADERS,
            follow_redirects=False,
            timeout=httpx.Timeout(10.0, connect=5.0),
        )

    def close(self) -> None:
        self._client.close()

    @staticmethod
    def _repository_path(repository: str) -> str:
        owner, name = repository.split("/", 1)
        return f"/repos/{quote(owner, safe='')}/{quote(name, safe='')}"

    def _get(
        self, secret: bytearray, path: str, params: dict[str, int | str] | None = None
    ) -> GitHubPage:
        if self._clock() - self._started >= RUN_DEADLINE_SECONDS:
            raise GitHubTransportError("github_deadline_ceiling")
        retry = False
        while True:
            if self._attempts >= MAX_ATTEMPTS:
                raise GitHubTransportError("github_request_ceiling")
            self._attempts += 1
            try:
                if not secret or any(value < 33 or value > 126 for value in secret):
                    raise GitHubTransportError("credential_invalid")
                authorization = f"Bearer {bytes(secret).decode('ascii')}"
                response = self._client.get(
                    path,
                    params=params,
                    headers={"Authorization": authorization},
                )
            except (httpx.ConnectError, httpx.TimeoutException):
                if retry:
                    raise GitHubTransportError("github_timeout") from None
                retry = True
                continue
            if self._clock() - self._started >= RUN_DEADLINE_SECONDS:
                raise GitHubTransportError("github_deadline_ceiling")
            if response.is_redirect:
                raise GitHubTransportError("github_redirect")
            if response.status_code == 401:
                raise GitHubTransportError("github_unauthorized")
            if response.status_code == 403:
                if (
                    response.headers.get("x-ratelimit-remaining") == "0"
                    or response.headers.get("retry-after") is not None
                ):
                    raise GitHubTransportError("github_rate_limited")
                raise GitHubTransportError("github_forbidden")
            if response.status_code == 404:
                raise GitHubTransportError("github_not_found")
            if response.status_code in {429}:
                raise GitHubTransportError("github_rate_limited")
            if response.status_code in {502, 503, 504}:
                if not retry:
                    retry = True
                    continue
                raise GitHubTransportError("github_unavailable")
            if response.status_code != 200:
                raise GitHubTransportError("github_unavailable")
            content = response.content
            if len(content) > MAX_RESPONSE_BYTES:
                raise GitHubTransportError("github_response_oversized")
            self._bytes += len(content)
            if self._bytes > MAX_RUN_BYTES:
                raise GitHubTransportError("github_run_byte_ceiling")
            try:
                value: Any = json.loads(content)
            except (UnicodeDecodeError, json.JSONDecodeError):
                raise GitHubTransportError("github_invalid_response") from None
            may_have_more = isinstance(value, list) and len(value) == PAGE_SIZE
            return GitHubPage(value=value, may_have_more=may_have_more)

    def user(self, secret: bytearray) -> GitHubPage:
        return self._get(secret, "/user")

    def repository(self, secret: bytearray, repository: str) -> GitHubPage:
        return self._get(secret, self._repository_path(repository))

    def issues(self, secret: bytearray, repository: str, page: int) -> GitHubPage:
        return self._get(
            secret,
            f"{self._repository_path(repository)}/issues",
            {"state": "all", "per_page": PAGE_SIZE, "page": page},
        )

    def pulls(self, secret: bytearray, repository: str, page: int) -> GitHubPage:
        return self._get(
            secret,
            f"{self._repository_path(repository)}/pulls",
            {"state": "all", "per_page": PAGE_SIZE, "page": page},
        )


@dataclass(frozen=True, slots=True)
class FakeGitHubCall:
    endpoint: str
    repository: str | None
    page: int | None


class FakeGitHubTransport:
    """Deterministic scripted transport with an inspectable closed call inventory."""

    def __init__(self, responses: list[GitHubPage | GitHubTransportError]) -> None:
        self._responses = list(responses)
        self.calls: list[FakeGitHubCall] = []

    def _take(
        self, endpoint: str, repository: str | None, page: int | None
    ) -> GitHubPage:
        self.calls.append(FakeGitHubCall(endpoint, repository, page))
        if not self._responses:
            raise AssertionError("unexpected fake GitHub request")
        value = self._responses.pop(0)
        if isinstance(value, GitHubTransportError):
            raise value
        return value

    def user(self, secret: bytearray) -> GitHubPage:
        return self._take("user", None, None)

    def repository(self, secret: bytearray, repository: str) -> GitHubPage:
        return self._take("repository", repository, None)

    def issues(self, secret: bytearray, repository: str, page: int) -> GitHubPage:
        return self._take("issues", repository, page)

    def pulls(self, secret: bytearray, repository: str, page: int) -> GitHubPage:
        return self._take("pulls", repository, page)
