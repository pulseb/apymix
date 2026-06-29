"""SQLAdmin setup — plugs the back-office into the FastAPI app.

The core admin views (AppEntry, User) come from apymix/admin/views.py.
The admin views of business APIs are discovered automatically via amx.yaml.
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


def setup_admin(app: FastAPI, engine: AsyncEngine, base_url: str = "/admx") -> Admin:
    """Configures and mounts SQLAdmin on the FastAPI application.

    Args:
        app: Main FastAPI instance.
        engine: Async SQLAlchemy engine.
        base_url: URL prefix of the back-office (default: /admx).

    Returns:
        Configured Admin instance.
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

    # Register the core Apymix views
    admin.add_view(AppEntryAdmin)
    admin.add_view(UserAdmin)
    admin.add_view(RedirectAdmin)

    # Register the business API views (auto-discovery via amx.yaml)
    for view_class in discover_api_admin_views(_get_workspace_root()):
        admin.add_view(view_class)

    logger.info("SQLAdmin mounted on %s", base_url)
    return admin
