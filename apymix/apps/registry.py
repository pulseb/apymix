"""Application registry — synchronizes discovered apps with the DB.

When a new AppEntry of type API is inserted for the first time, the registry
automatically triggers the seed of that API (via ``apis/<name>/seed.py``)
to populate its tables with initial data.
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
    """Synchronizes the app registry with the discovered folders.

    For each app in ``discovered``:
    - If it does not exist in the DB → INSERT (status=active)
      → if it is an API, its seed is automatically triggered
    - If it exists with status 'unavailable' → switch back to 'active' (it has returned)
    - If it exists with status 'active' or 'disabled' → update last_seen_at

    For each DB app not present in ``discovered``:
    - If status != 'unavailable' → switch to 'unavailable'

    Args:
        session: Async DB session.
        discovered: List of dicts with keys: name, app_type, prefix, description, version.

    Returns:
        Dict {app_name: {"status": ..., "docs_enabled": ...}} after sync.
    """
    from apymix.db.models import _utcnow
    now = _utcnow()
    discovered_names = {d["name"] for d in discovered}
    new_api_names: list[str] = []  # Newly inserted APIs → to be seeded

    # Load all existing apps
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
                logger.info("App '%s' is back → active", name)
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
            logger.info("New app registered: %s (%s)", name, app_info["app_type"])

            # Mark new APIs for auto-seed
            if app_info["app_type"] == "api":
                new_api_names.append(name)

    # --- Mark missing apps as unavailable, delete already-unavailable ghosts ---
    for name, entry in existing.items():
        if name not in discovered_names:
            if entry.status == AppStatus.unavailable.value:
                # Already unavailable from a previous run — purge it
                await session.delete(entry)
                logger.warning("App '%s' still missing → removed from registry", name)
            else:
                entry.status = AppStatus.unavailable.value
                entry.updated_at = now
                logger.warning("App '%s' not found → unavailable", name)

    await session.commit()

    # --- Auto-seed new APIs ---
    if new_api_names:
        await _seed_new_apis(session, new_api_names)

    # Return final state: {app_name: {"status": ..., "docs_enabled": ...}}
    result = await session.execute(select(AppEntry))
    return {
        app.name: {"status": app.status, "docs_enabled": app.docs_enabled}
        for app in result.scalars().all()
    }


async def _seed_new_apis(session: AsyncSession, api_names: list[str]) -> None:
    """Triggers the seed of each newly registered API.

    Uses the auto-discovery from ``scripts.db_init.seed_api`` to call the
    corresponding ``apis/<name>/seed.py``.
    """
    from apymix.scripts.db_init import seed_api

    for name in api_names:
        try:
            seeded = await seed_api(name, session)
            if seeded:
                await session.commit()
                logger.info("🌱 Auto-seed API '%s' completed", name)
        except Exception:
            logger.exception("Auto-seed error for API '%s'", name)
