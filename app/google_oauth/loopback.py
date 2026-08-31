"""Single-use, loopback-only installed-app OAuth callback."""

import http.server
import time
import urllib.parse
from dataclasses import dataclass

from app.google_oauth.contract import (
    CALLBACK_PATH,
    GoogleOAuthError,
    GoogleOAuthReplayError,
    GoogleOAuthTimeoutError,
)


@dataclass(frozen=True, slots=True)
class CallbackResult:
    code: str
    state: str


class LoopbackCallback:
    def __init__(self) -> None:
        self._result: CallbackResult | None = None
        self._error = False
        self._used = False
        owner = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                status = owner._receive(self.path)
                body = b"Authorization received. You may close this window."
                self.send_response(status)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format: str, *args: object) -> None:
                del format, args

        self._server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        self._server.timeout = 0.25
        self.redirect_uri = (
            f"http://127.0.0.1:{self._server.server_port}{CALLBACK_PATH}"
        )

    def _receive(self, target: str) -> int:
        if self._used:
            self._error = True
            return 409
        self._used = True
        parsed = urllib.parse.urlsplit(target)
        if (
            parsed.scheme
            or parsed.netloc
            or parsed.path != CALLBACK_PATH
            or parsed.fragment
        ):
            self._error = True
            return 400
        values = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
        if set(values) != {"code", "state"} or any(
            len(items) != 1 for items in values.values()
        ):
            self._error = True
            return 400
        code, state = values["code"][0], values["state"][0]
        if not code or len(code) > 4096 or not state or len(state) > 512:
            self._error = True
            return 400
        self._result = CallbackResult(code, state)
        return 200

    def wait(self, timeout: float = 180) -> CallbackResult:
        deadline = time.monotonic() + timeout
        try:
            while (
                self._result is None and not self._error and time.monotonic() < deadline
            ):
                self._server.handle_request()
            if self._error:
                raise GoogleOAuthReplayError() from None
            if self._result is None:
                raise GoogleOAuthTimeoutError() from None
            return self._result
        finally:
            self.close()

    def close(self) -> None:
        try:
            self._server.server_close()
        except OSError:
            raise GoogleOAuthError() from None
