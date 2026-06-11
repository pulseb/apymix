"""Registre d'applications — synchronise les apps découvertes avec la DB.

Lorsqu'une nouvelle AppEntry de type API est insérée pour la première fois,
le registre déclenche automatiquement le seed de cette API (via
``apis/<name>/seed.py``) pour peupler ses tables avec des données initiales.
"""

import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from apymix.apps.models import AppEntry, AppStatus

logger = logging.getLogger(__name__)


async def sync_app_registry(
    session: AsyncSession,
    discovered: list[dict],
) -> dict[str, dict]:
    """Synchronise le registre des apps avec les dossiers découverts.

    Pour chaque app dans ``discovered`` :
    - Si elle n'existe pas en DB → INSERT (status=active)
      → si c'est une API, son seed est déclenché automatiquement
    - Si elle existe en 'unavailable' → repasse en 'active' (elle est revenue)
    - Si elle existe en 'active' ou 'disabled' → met à jour last_seen_at

    Pour chaque app en DB non présente dans ``discovered`` :
    - Si status != 'unavailable' → passe en 'unavailable'

    Args:
        session: Session DB async.
        discovered: Liste de dicts avec keys: name, app_type, prefix, description, version.

    Returns:
        Dict {app_name: {"status": ..., "docs_enabled": ...}} après sync.
    """
    from apymix.db.models import _utcnow
    now = _utcnow()
    discovered_names = {d["name"] for d in discovered}
    new_api_names: list[str] = []  # APIs nouvellement insérées → à seeder

    # Charger toutes les apps existantes
    result = await session.execute(select(AppEntry))
    existing: dict[str, AppEntry] = {app.name: app for app in result.scalars().all()}

    # --- Sync discovered → DB ---
    for app_info in discovered:
        name = app_info["name"]

        if name in existing:
            entry = existing[name]
            entry.last_seen_at = now
            entry.updated_at = now
            entry.prefix = app_info["prefix"]
            entry.description = app_info.get("description", "")
            entry.version = app_info.get("version", "0.0.0")

            if entry.status == AppStatus.unavailable.value:
                entry.status = AppStatus.active.value
                logger.info("App '%s' de retour → active", name)
        else:
            entry = AppEntry(
                name=name,
                app_type=app_info["app_type"],
                prefix=app_info["prefix"],
                status=AppStatus.active.value,
                description=app_info.get("description", ""),
                version=app_info.get("version", "0.0.0"),
                last_seen_at=now,
            )
            session.add(entry)
            logger.info("Nouvelle app enregistrée : %s (%s)", name, app_info["app_type"])

            # Marquer les nouvelles APIs pour auto-seed
            if app_info["app_type"] == "api":
                new_api_names.append(name)

    # --- Mark missing apps as unavailable, delete already-unavailable ghosts ---
    for name, entry in existing.items():
        if name not in discovered_names:
            if entry.status == AppStatus.unavailable.value:
                # Already unavailable from a previous run — purge it
                await session.delete(entry)
                logger.warning("App '%s' toujours introuvable → supprimée du registre", name)
            else:
                entry.status = AppStatus.unavailable.value
                entry.updated_at = now
                logger.warning("App '%s' introuvable → unavailable", name)

    await session.commit()

    # --- Auto-seed des nouvelles APIs ---
    if new_api_names:
        await _seed_new_apis(session, new_api_names)

    # Return final state: {app_name: {"status": ..., "docs_enabled": ...}}
    result = await session.execute(select(AppEntry))
    return {
        app.name: {"status": app.status, "docs_enabled": app.docs_enabled}
        for app in result.scalars().all()
    }


async def _seed_new_apis(session: AsyncSession, api_names: list[str]) -> None:
    """Déclenche le seed de chaque API nouvellement enregistrée.

    Utilise l'auto-discovery de ``scripts.db_init.seed_api`` pour appeler
    le ``apis/<name>/seed.py`` correspondant.
    """
    from apymix.scripts.db_init import seed_api

    for name in api_names:
        try:
            seeded = await seed_api(name, session)
            if seeded:
                await session.commit()
                logger.info("🌱 Auto-seed API '%s' terminé", name)
        except Exception:
            logger.exception("Erreur auto-seed API '%s'", name)
