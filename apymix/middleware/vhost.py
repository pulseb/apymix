"""VHost middleware — routes incoming requests to a mounted frontend based on the Host header.

Configured via the VHOST_MAP environment variable:
    VHOST_MAP=app.example.com=myapp,other.example.com=otherapp

When a request arrives on app.example.com/, the path is rewritten from /foo
to /myapp/foo before FastAPI's router handles it. The frontend mounted at
/myapp receives the request transparently, with no visible redirect.
"""

from typing import Any


class VHostMiddleware:
    """ASGI middleware: rewrites the request path based on the Host header."""

    def __init__(self, app: Any, vhost_map: dict[str, str]) -> None:
        self.app = app
        # e.g. {"app.example.com": "myapp", "other.example.com": "otherapp"}
        self.vhost_map = vhost_map

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] in ("http", "websocket") and self.vhost_map:
            host = self._get_host(scope)
            original_path = scope.get("path", "/")
            if host in self.vhost_map and not original_path.startswith("/api/"):
                prefix = "/" + self.vhost_map[host].strip("/")
                new_path = prefix + original_path
                scope = {**scope, "path": new_path, "raw_path": new_path.encode("latin-1")}

        await self.app(scope, receive, send)

    @staticmethod
    def _get_host(scope: dict) -> str:
        """Extrait le hostname (sans port) depuis les headers ASGI."""
        for name, value in scope.get("headers", []):
            if name == b"host":
                return value.decode("latin-1").split(":")[0]
        return ""
