"""StaticFiles with SPA (Single Page Application) fallback.

In ``html=True`` mode, Starlette serves ``index.html`` for directory paths
(/eve/) but returns 404 for deep paths (/eve/programme). This subclass
intercepts the 404 and returns ``index.html`` so Vue Router can handle
client-side routing.

Equivalent to Nginx's ``try_files $uri $uri/ /index.html``.
"""

from starlette.staticfiles import StaticFiles
from starlette.types import Receive, Scope, Send


class SPAStaticFiles(StaticFiles):
    """StaticFiles that serves index.html as fallback for SPA routes."""

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        try:
            await super().__call__(scope, receive, send)
        except Exception as exc:
            # If the file does not exist (404), serve index.html
            if getattr(exc, "status_code", None) == 404:
                scope["path"] = "/"
                await super().__call__(scope, receive, send)
            else:
                raise
