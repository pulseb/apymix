"""StaticFiles avec fallback SPA (Single Page Application).

En mode ``html=True``, Starlette sert ``index.html`` pour les chemins
de répertoire (/eve/) mais retourne 404 pour les chemins profonds
(/eve/programme). Cette sous-classe intercepte le 404 et renvoie
``index.html`` pour que Vue Router gère le routing côté client.

Équivalent du ``try_files $uri $uri/ /index.html`` de Nginx.
"""

from starlette.staticfiles import StaticFiles
from starlette.types import Receive, Scope, Send


class SPAStaticFiles(StaticFiles):
    """StaticFiles qui sert index.html en fallback pour les routes SPA."""

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        try:
            await super().__call__(scope, receive, send)
        except Exception as exc:
            # Si le fichier n'existe pas (404), servir index.html
            if getattr(exc, "status_code", None) == 404:
                scope["path"] = "/"
                await super().__call__(scope, receive, send)
            else:
                raise
