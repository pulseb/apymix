"""HTTP redirect middleware driven by the amx_redirects table.

Rules are loaded from the DB at startup and cached in memory.
A reload is triggered every 60 seconds (lazily, on the next hit).

Evaluation priority of an incoming request:
    1. matching host + path_prefix
    2. host only (empty path_prefix)
    3. path_prefix only (empty host)
"""

import logging
import os
import time
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

logger = logging.getLogger(__name__)

_CACHE_TTL = 60  # seconds
_TABLE_PREFIX: str = os.environ.get("AMX_TABLE_PREFIX", "amx_")


class RedirectMiddleware:
    """ASGI middleware: evaluates redirect rules before the FastAPI router."""

    def __init__(self, app: Any, db_url: str) -> None:
        self.app = app
        self.db_url = db_url
        self._rules: list[dict] = []
        self._loaded_at: float = 0.0

    async def _load_rules(self) -> None:
        """Loads the active rules from the DB."""
        try:
            engine = create_async_engine(self.db_url, echo=False)
            async with engine.connect() as conn:
                result = await conn.execute(
                    text(
                        "SELECT host, path_prefix, destination, status_code "
                        f"FROM {_TABLE_PREFIX}redirects WHERE enabled = true "
                        "ORDER BY "
                        "  CASE WHEN (host IS NOT NULL AND host != '') AND (path_prefix IS NOT NULL AND path_prefix != '') THEN 0 "
                        "       WHEN (host IS NOT NULL AND host != '') THEN 1 "
                        "       ELSE 2 END"
                    )
                )
                self._rules = [dict(row._mapping) for row in result]
            await engine.dispose()
            self._loaded_at = time.monotonic()
            logger.debug("Redirect rules loaded: %d rule(s)", len(self._rules))
        except Exception as exc:
            logger.warning("Could not load redirect rules: %s", exc)

    def _match(self, host: str, path: str) -> dict | None:
        """Returns the first rule that matches (host, path), or None."""
        for rule in self._rules:
            r_host = rule.get("host") or ""
            r_prefix = rule.get("path_prefix") or ""
            host_match = (not r_host) or (host == r_host)
            path_match = (not r_prefix) or path.startswith(r_prefix)
            if host_match and path_match:
                return rule
        return None

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # TTL reload (lazy)
        if time.monotonic() - self._loaded_at > _CACHE_TTL:
            await self._load_rules()

        host = ""
        for name, value in scope.get("headers", []):
            if name == b"host":
                host = value.decode("latin-1").split(":")[0]
                break

        path = scope.get("path", "/")
        rule = self._match(host, path)

        if rule:
            destination = rule["destination"].encode("latin-1")
            status_code = rule.get("status_code") or 302
            await send({"type": "http.response.start", "status": status_code, "headers": [[b"location", destination]]})
            await send({"type": "http.response.body", "body": b""})
            return

        await self.app(scope, receive, send)
