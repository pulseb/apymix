"""ModelAdmin views of the Apymix core — auto-generated CRUD for shared models.

The admin views of business APIs live in their own modules
(e.g. apis/eve/admin.py) and are discovered automatically by setup.py.
"""

import logging
from pathlib import Path

from fastapi.templating import Jinja2Templates
from sqladmin import ModelView, action
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from starlette.responses import RedirectResponse

from apymix.apps.models import AppEntry
from apymix.auth.models import User
from apymix.db.models import Redirect
from apymix.db.session import _get_engine
from apymix.scripts.db_init import seed_api

logger = logging.getLogger(__name__)

# Jinja2 templates for admin feedback pages
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def _short_uuid(model, name):
    """Formats a UUID by displaying only the first section (8 chars)."""
    value = getattr(model, name, None)
    if value is None:
        return ""
    return str(value).split("-")[0]


def _seed_key_from_app(app: AppEntry) -> str | None:
    """Derives the seed key of an API AppEntry.

    The seed is indexed by the folder name under ``apis/`` (e.g. ``eve``),
    while ``AppEntry.name`` may contain a business name (e.g. ``Eve-API``).
    We therefore rely on the canonical prefix ``/api/<key>``.
    """
    if app.app_type != "api":
        return None
    prefix = (app.prefix or "").strip("/")
    parts = prefix.split("/")
    if len(parts) >= 2 and parts[0] == "api" and parts[1]:
        return parts[1]
    return None


class AppEntryAdmin(ModelView, model=AppEntry):
    """Admin view for the application registry."""

    column_list = [
        AppEntry.id,
        AppEntry.name,
        AppEntry.app_type,
        AppEntry.prefix,
        AppEntry.status,
        AppEntry.docs_enabled,
        AppEntry.version,
        AppEntry.last_seen_at,
    ]
    column_searchable_list = [AppEntry.name]
    column_sortable_list = [AppEntry.name, AppEntry.app_type, AppEntry.status, AppEntry.last_seen_at]
    column_default_sort = ("name", False)
    column_formatters = {AppEntry.id: lambda m, n: _short_uuid(m, "id")}

    form_include_pk = False
    form_columns = [AppEntry.status, AppEntry.docs_enabled]

    name = "Application"
    name_plural = "Applications"
    icon = "fa-solid fa-cubes"
    category = "Apymix"

    @action(
        name="seed_api",
        label="Run API seed",
        confirmation_message="Run the seed for the selected API applications?",
        add_in_list=True,
        add_in_detail=True,
    )
    async def seed_api_action(self, request):
        from uuid import UUID
        params = request.query_params.get("pks", "")
        pks = []
        for pk in params.split(","):
            try:
                pks.append(UUID(pk.strip()))
            except ValueError:
                continue

        referer = request.headers.get("referer") or str(request.url_for("admin:list", identity=self.identity))
        if not pks:
            return RedirectResponse(referer, status_code=302)

        engine = _get_engine()
        async with AsyncSession(engine, expire_on_commit=False) as session:
            result = await session.execute(select(AppEntry).where(AppEntry.id.in_(pks)))
            apps = result.scalars().all()

            seeded_apps = []
            skipped_apps = []
            error_apps = []
            for app in apps:
                if app.app_type != "api":
                    skipped_apps.append(f"{app.name} (type={app.app_type})")
                    continue
                seed_key = _seed_key_from_app(app)
                if not seed_key:
                    error_apps.append(f"{app.name} (seed key not found)")
                    continue
                if await seed_api(seed_key, session):
                    seeded_apps.append(app.name)
                else:
                    skipped_apps.append(f"{app.name} (DB already populated)")

            if seeded_apps:
                await session.commit()

        logger.info("SQLAdmin seed action: seeded=%s, skipped=%s, errors=%s",
                   seeded_apps, skipped_apps, error_apps)

        # Feedback message
        if seeded_apps:
            icon = "✅"
            message = f"Seed succeeded for {len(seeded_apps)} API(s): {', '.join(seeded_apps)}"
            if skipped_apps or error_apps:
                details = []
                if skipped_apps:
                    details.append(f"{len(skipped_apps)} skipped: {', '.join(skipped_apps)}")
                if error_apps:
                    details.append(f"{len(error_apps)} error(s): {', '.join(error_apps)}")
                message += f"<br><small>{' | '.join(details)}</small>"
        elif error_apps:
            icon = "⚠️"
            message = f"Error: {', '.join(error_apps)}"
            if skipped_apps:
                message += f"<br><small>{len(skipped_apps)} skipped: {', '.join(skipped_apps)}</small>"
        elif skipped_apps:
            icon = "ℹ️"
            message = f"No data seeded — {', '.join(skipped_apps)}"
        else:
            icon = "⚠️"
            message = "No application selected."

        return templates.TemplateResponse(
            request, "seed_feedback.html", {"icon": icon, "message": message, "referer": referer}
        )

    @action(
        name="toggle_status",
        label="Toggle Status",
        confirmation_message="Toggle the status (active ↔ inactive)?",
        add_in_list=True,
        add_in_detail=True,
    )
    async def toggle_status_action(self, request):
        from uuid import UUID
        params = request.query_params.get("pks", "")
        pks = []
        for pk in params.split(","):
            try:
                pks.append(UUID(pk.strip()))
            except ValueError:
                continue
        referer = request.headers.get("referer") or str(request.url_for("admin:list", identity=self.identity))

        if not pks:
            return RedirectResponse(referer, status_code=302)

        engine = _get_engine()
        async with AsyncSession(engine) as session:
            result = await session.execute(select(AppEntry).where(AppEntry.id.in_(pks)))
            apps = result.scalars().all()
            for app in apps:
                app.status = "inactive" if app.status == "active" else "active"
            await session.commit()

        return RedirectResponse(referer, status_code=302)

    @action(
        name="toggle_docs",
        label="Toggle Docs",
        confirmation_message="Toggle the documentation activation?",
        add_in_list=True,
        add_in_detail=True,
    )
    async def toggle_docs_action(self, request):
        from uuid import UUID
        params = request.query_params.get("pks", "")
        pks = []
        for pk in params.split(","):
            try:
                pks.append(UUID(pk.strip()))
            except ValueError:
                continue
        referer = request.headers.get("referer") or str(request.url_for("admin:list", identity=self.identity))

        if not pks:
            return RedirectResponse(referer, status_code=302)

        engine = _get_engine()
        async with AsyncSession(engine) as session:
            result = await session.execute(select(AppEntry).where(AppEntry.id.in_(pks)))
            apps = result.scalars().all()
            for app in apps:
                app.docs_enabled = not app.docs_enabled
            await session.commit()

        return RedirectResponse(referer, status_code=302)


class UserAdmin(ModelView, model=User):
    """Admin view for users."""

    column_list = [User.id, User.email, User.display_name, User.roles, User.status, User.is_email_verified, User.created_at]
    column_searchable_list = [User.email, User.display_name]
    column_sortable_list = [User.email, User.status, User.created_at]
    column_default_sort = ("created_at", True)
    column_formatters = {User.id: lambda m, n: _short_uuid(m, "id")}

    form_excluded_columns = ["accounts", "created_at", "updated_at", "last_login_at"]
    column_details_exclude_list = ["accounts"]

    name = "User"
    name_plural = "Users"
    icon = "fa-solid fa-user"
    category = "Apymix"


class RedirectAdmin(ModelView, model=Redirect):
    """Admin view for HTTP redirect rules."""

    column_list = [Redirect.id, Redirect.host, Redirect.path_prefix, Redirect.destination, Redirect.status_code, Redirect.enabled]
    column_searchable_list = [Redirect.host, Redirect.destination]
    column_sortable_list = [Redirect.host, Redirect.status_code, Redirect.enabled]
    column_default_sort = ("id", False)

    name = "Redirect"
    name_plural = "Redirects"
    icon = "fa-solid fa-route"
    category = "Apymix"
