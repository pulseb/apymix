"""Vues ModelAdmin du socle PAPI — CRUD auto-généré pour les modèles partagés.

Les admin views des APIs métier sont dans leurs propres modules
(ex : apis/eve/admin.py) et découvertes automatiquement par setup.py.
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

# Templates Jinja2 pour les pages de feedback admin
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def _short_uuid(model, name):
    """Formate un UUID en affichant seulement la première section (8 car.)."""
    value = getattr(model, name, None)
    if value is None:
        return ""
    return str(value).split("-")[0]


def _seed_key_from_app(app: AppEntry) -> str | None:
    """Déduit la clé de seed d'une AppEntry API.

    Le seed est indexé par le nom de dossier sous ``apis/`` (ex: ``eve``),
    alors que ``AppEntry.name`` peut contenir un nom métier (ex: ``Eve-API``).
    On se base donc sur le préfixe canonique ``/api/<key>``.
    """
    if app.app_type != "api":
        return None
    prefix = (app.prefix or "").strip("/")
    parts = prefix.split("/")
    if len(parts) >= 2 and parts[0] == "api" and parts[1]:
        return parts[1]
    return None


class AppEntryAdmin(ModelView, model=AppEntry):
    """Admin view pour le registre des applications."""

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
    category = "PAPI"

    @action(
        name="seed_api",
        label="Lancer seed API",
        confirmation_message="Lancer le seed pour les applications API sélectionnées ?",
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
                    error_apps.append(f"{app.name} (clé seed introuvable)")
                    continue
                if await seed_api(seed_key, session):
                    seeded_apps.append(app.name)
                else:
                    skipped_apps.append(f"{app.name} (DB déjà peuplée)")

            if seeded_apps:
                await session.commit()

        logger.info("Seed action SQLAdmin : seedées=%s, ignorées=%s, erreurs=%s", 
                   seeded_apps, skipped_apps, error_apps)

        # Message de feedback
        if seeded_apps:
            icon = "✅"
            message = f"Seed réussi pour {len(seeded_apps)} API(s) : {', '.join(seeded_apps)}"
            if skipped_apps or error_apps:
                details = []
                if skipped_apps:
                    details.append(f"{len(skipped_apps)} ignorée(s) : {', '.join(skipped_apps)}")
                if error_apps:
                    details.append(f"{len(error_apps)} erreur(s) : {', '.join(error_apps)}")
                message += f"<br><small>{' | '.join(details)}</small>"
        elif error_apps:
            icon = "⚠️"
            message = f"Erreur : {', '.join(error_apps)}"
            if skipped_apps:
                message += f"<br><small>{len(skipped_apps)} ignorée(s) : {', '.join(skipped_apps)}</small>"
        elif skipped_apps:
            icon = "ℹ️"
            message = f"Aucune donnée seedée — {', '.join(skipped_apps)}"
        else:
            icon = "⚠️"
            message = "Aucune application sélectionnée."

        return templates.TemplateResponse(
            request, "seed_feedback.html", {"icon": icon, "message": message, "referer": referer}
        )

    @action(
        name="toggle_status",
        label="Toggle Status",
        confirmation_message="Inverser le statut (active ↔ inactive) ?",
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
        confirmation_message="Inverser l'activation de la documentation ?",
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
    """Admin view pour les utilisateurs."""

    column_list = [User.id, User.email, User.display_name, User.roles, User.status, User.is_email_verified, User.created_at]
    column_searchable_list = [User.email, User.display_name]
    column_sortable_list = [User.email, User.status, User.created_at]
    column_default_sort = ("created_at", True)
    column_formatters = {User.id: lambda m, n: _short_uuid(m, "id")}

    form_excluded_columns = ["accounts", "created_at", "updated_at", "last_login_at"]
    column_details_exclude_list = ["accounts"]

    name = "Utilisateur"
    name_plural = "Utilisateurs"
    icon = "fa-solid fa-user"
    category = "PAPI"


class RedirectAdmin(ModelView, model=Redirect):
    """Admin view pour les règles de redirection HTTP."""

    column_list = [Redirect.id, Redirect.host, Redirect.path_prefix, Redirect.destination, Redirect.status_code, Redirect.enabled]
    column_searchable_list = [Redirect.host, Redirect.destination]
    column_sortable_list = [Redirect.host, Redirect.status_code, Redirect.enabled]
    column_default_sort = ("id", False)

    name = "Redirection"
    name_plural = "Redirections"
    icon = "fa-solid fa-route"
    category = "PAPI"
