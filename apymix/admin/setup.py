"""Setup SQLAdmin — branche le back-office sur l'app FastAPI.

Les admin views du socle (AppEntry, User) viennent de apymix/admin/views.py.
Les admin views des APIs métier sont découvertes automatiquement via amx.yaml.
"""

import logging
import os
import secrets

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine
from sqladmin import Admin

from apymix.admin.auth import AdminAuth
from apymix.admin.views import AppEntryAdmin, UserAdmin, RedirectAdmin
from apymix.discovery import discover_api_admin_views, _get_workspace_root

logger = logging.getLogger(__name__)


def setup_admin(app: FastAPI, engine: AsyncEngine, base_url: str = "/padmin") -> Admin:
    """Configure et monte SQLAdmin sur l'application FastAPI.

    Args:
        app: Instance FastAPI principale.
        engine: Engine SQLAlchemy async.
        base_url: Préfixe URL du back-office (défaut: /padmin).

    Returns:
        Instance Admin configurée.
    """
    # SQLAdmin uses secret_key for its own session cookies (not JWT tokens).
    # Read JWT_SECRET from env directly — lifespan hasn't run yet at this point.
    admin_secret = os.environ.get("JWT_SECRET") or secrets.token_hex(32)
    authentication_backend = AdminAuth(secret_key=admin_secret, engine=engine)

    admin = Admin(
        app,
        engine,
        base_url=base_url,
        title="Apymix Admin",
        authentication_backend=authentication_backend,
    )

    # Enregistrer les vues du socle Apymix
    admin.add_view(AppEntryAdmin)
    admin.add_view(UserAdmin)
    admin.add_view(RedirectAdmin)

    # Enregistrer les vues des APIs métier (auto-discovery via amx.yaml)
    for view_class in discover_api_admin_views(_get_workspace_root()):
        admin.add_view(view_class)

    logger.info("SQLAdmin monté sur %s", base_url)
    return admin
