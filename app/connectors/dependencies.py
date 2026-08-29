"""Production dependencies for the manual GitHub connector boundary."""

from collections.abc import Callable

from app.connectors.github import GitHubTransport, HttpxGitHubTransport
from app.credentials.contract import CredentialStore
from app.credentials.windows import WindowsCredentialStore


def credential_store_dependency() -> CredentialStore:
    return WindowsCredentialStore()


def github_transport_factory_dependency() -> Callable[[], GitHubTransport]:
    return HttpxGitHubTransport
