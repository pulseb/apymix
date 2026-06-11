"""CORS logging middleware — warns when a request carries a disallowed Origin."""

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


class CORSLogMiddleware:
    """ASGI middleware that logs a WARNING for every request with an unauthorized Origin.

    Must be registered AFTER CORSMiddleware (i.e. executed before it in the ASGI stack)
    so that it inspects the Origin header before CORSMiddleware issues its response.
    """

    def __init__(
        self,
        app: Any,
        allow_origins: list[str],
        allow_origin_regex: str | None = None,
    ) -> None:
        self.app = app
        self._origins = set(allow_origins)
        self._regex = re.compile(allow_origin_regex) if allow_origin_regex else None

    def _is_allowed(self, origin: str) -> bool:
        if origin in self._origins:
            return True
        if self._regex and self._regex.fullmatch(origin):
            return True
        return False

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] in ("http", "websocket"):
            headers = dict(scope.get("headers", []))
            origin = headers.get(b"origin", b"").decode()
            if origin and not self._is_allowed(origin):
                method = scope.get("method", "WS")
                path = scope.get("path", "")
                logger.warning(
                    "[CORS] Rejected origin: %s  %s %s",
                    origin,
                    method,
                    path,
                )
        await self.app(scope, receive, send)
