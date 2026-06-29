"""ASGI reverse proxy for frontend development.

In dev mode, this serves the frontend through uvicorn/PAPI while still
benefiting from the Vite HMR (hot module replacement) of ``quasar dev``.

Uses:
- ``httpx`` (dev dependency) for the HTTP proxy
- ``websockets`` (via uvicorn[standard]) for the WebSocket proxy (HMR)
"""

import asyncio
import logging

from starlette.types import Receive, Scope, Send

logger = logging.getLogger(__name__)


class DevProxy:
    """HTTP and WebSocket proxy to a frontend dev server.

    Mounted in place of ``StaticFiles`` when ``settings.is_dev`` is True
    and the frontend manifest declares a ``dev_port``.

    Usage in app.py::

        app.mount("/eve", DevProxy(target="http://localhost:9000", prefix="/eve"))

    Args:
        target: Dev server URL (e.g. ``http://localhost:9000``).
        prefix: Frontend URL prefix (e.g. ``/eve``). Needed because
                Starlette strips the prefix before calling the sub-app.
    """

    def __init__(self, target: str, prefix: str = ""):
        self.target = target.rstrip("/")
        self.prefix = prefix
        self._http_client = None

    @property
    def _ws_target(self) -> str:
        return self.target.replace("http://", "ws://").replace("https://", "wss://")

    async def _get_http_client(self):
        if self._http_client is None:
            import httpx  # dev dependency uniquement

            self._http_client = httpx.AsyncClient(follow_redirects=True, timeout=30.0)
        return self._http_client

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            await self._handle_http(scope, receive, send)
        elif scope["type"] == "websocket":
            await self._handle_ws(scope, receive, send)

    # ------------------------------------------------------------------
    # HTTP
    # ------------------------------------------------------------------

    async def _handle_http(self, scope: Scope, receive: Receive, send: Send) -> None:
        from starlette.requests import Request
        from starlette.responses import Response

        request = Request(scope, receive)

        # Rebuild the full path to forward to the Quasar dev server.
        # Starlette strips the mount prefix before calling the sub-app, so
        # scope["path"] is the relative path (e.g. "/sw.js" for "/eve/sw.js").
        # We re-add self.prefix so the request reaches the right publicPath on
        # the dev server (e.g. "http://localhost:9001/eve/sw.js").
        # Guard against double-prefix in case Starlette didn't strip (e.g. root_path quirks).
        raw_path = scope.get("path", "/")
        if raw_path.startswith(self.prefix):
            path = raw_path  # already full path, don't add prefix again
        else:
            path = self.prefix + raw_path
        query = request.url.query
        url = f"{self.target}{path}{'?' + query if query else ''}"
        logger.debug("Dev proxy raw scope path: %s", raw_path)

        # Filter hop-by-hop headers
        headers = {
            k: v
            for k, v in request.headers.items()
            if k.lower() not in ("host", "transfer-encoding")
        }

        logger.info("Dev proxy → %s %s", request.method, url)
        try:
            client = await self._get_http_client()
            resp = await client.request(
                method=request.method,
                url=url,
                headers=headers,
                content=await request.body(),
            )
            # Do not relay encoding headers (httpx already decompressed)
            skip = {"transfer-encoding", "content-encoding", "content-length"}
            resp_headers = {k: v for k, v in resp.headers.items() if k.lower() not in skip}

            response = Response(content=resp.content, status_code=resp.status_code, headers=resp_headers)
            await response(scope, receive, send)
        except Exception as exc:
            logger.warning("Dev proxy → %s : %s", url, exc)
            error = Response(
                content=f"Dev proxy: cannot reach {self.target}\n"
                f"Is the quasar dev server running? (npx quasar dev)",
                status_code=502,
                media_type="text/plain",
            )
            await error(scope, receive, send)

    # ------------------------------------------------------------------
    # WebSocket (required for Vite HMR)
    # ------------------------------------------------------------------

    async def _handle_ws(self, scope: Scope, receive: Receive, send: Send) -> None:
        from starlette.websockets import WebSocket, WebSocketDisconnect

        client_ws = WebSocket(scope, receive, send)
        raw_path = scope.get("path", "/")
        path = raw_path if raw_path.startswith(self.prefix) else self.prefix + raw_path
        target_url = f"{self._ws_target}{path}"

        try:
            import websockets  # via uvicorn[standard]
        except ImportError:
            logger.warning("websockets not installed — HMR WebSocket not proxied")
            await client_ws.close(code=1001)
            return

        await client_ws.accept()

        try:
            async with websockets.connect(target_url) as server_ws:

                async def _relay_client_to_server():
                    """Relay messages from the browser to the Vite server."""
                    try:
                        while True:
                            data = await client_ws.receive_text()
                            await server_ws.send(data)
                    except (WebSocketDisconnect, Exception):
                        pass

                async def _relay_server_to_client():
                    """Relay messages from the Vite server to the browser."""
                    try:
                        async for msg in server_ws:
                            if isinstance(msg, str):
                                await client_ws.send_text(msg)
                            else:
                                await client_ws.send_bytes(msg)
                    except (WebSocketDisconnect, Exception):
                        pass

                done, pending = await asyncio.wait(
                    [
                        asyncio.create_task(_relay_client_to_server()),
                        asyncio.create_task(_relay_server_to_client()),
                    ],
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in pending:
                    task.cancel()
        except Exception as exc:
            logger.warning("Dev proxy WS → %s : %s", target_url, exc)
        finally:
            try:
                await client_ws.close()
            except Exception:
                pass
