"""Initial development seed.

Populates the database with realistic data if empty:
- An admin user (sebastien / pulse)
- Demo data for each API (auto-discovery via apis/<name>/seed.py)

The seed runs **automatically** at startup if the DB is empty.
It is also called by the registry (`sync_app_registry`) when a new
AppEntry of type API is inserted into the DB for the first time.

Manual run:
    uv run python -m scripts.db_init
"""

import asyncio
import importlib
import logging
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import func, select

from apymix.auth.models import User, UserAccount
from apymix.auth.security import get_password_hash
from apymix.db.session import _get_engine

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Admin seed — reusable by all business apps
# ---------------------------------------------------------------------------

async def _seed_default_admin(session: AsyncSession) -> bool:
    """Create the default admin user if no user exists.

    Returns:
        True if an admin was created, False otherwise.
    """
    user_count = (await session.execute(select(func.count()).select_from(User))).scalar_one()
    if user_count > 0:
        return False

    admin = User(
        email="admin",
        roles=["admin", "user"],
        status="active",
    )
    session.add(admin)
    await session.flush()  # obtenir admin.id

    import os
    admin_password = os.environ.get("ADMIN_PASSWORD", "apymix")
    account = UserAccount(
        user_id=admin.id,
        provider="password",
        provider_user_id="admin",
        password_hash=get_password_hash(admin_password),
    )
    session.add(account)
    logger.info("👤 User created: admin / %s", "(ADMIN_PASSWORD)" if os.environ.get("ADMIN_PASSWORD") else "apymix")
    return True


# ---------------------------------------------------------------------------
# Auto-discovery of API seeds — apis/<name>/seed.py
# ---------------------------------------------------------------------------

def _discover_api_seeds() -> dict[str, object]:
    """Scan apis/*/seed.py and return {api_name: module}.

    Each module must expose a coroutine:
        async def seed(session: AsyncSession) -> bool
    """
    apis_dir = Path(__file__).resolve().parent.parent / "apis"
    seeds: dict[str, object] = {}

    if not apis_dir.is_dir():
        return seeds

    for api_dir in sorted(apis_dir.iterdir()):
        seed_file = api_dir / "seed.py"
        if not seed_file.is_file():
            continue
        try:
            module = importlib.import_module(f"apis.{api_dir.name}.seed")
            if hasattr(module, "seed") and asyncio.iscoroutinefunction(module.seed):
                seeds[api_dir.name] = module
                logger.debug("Seed discovered: apis/%s/seed.py", api_dir.name)
            else:
                logger.warning("apis/%s/seed.py does not expose a 'seed(session)' coroutine", api_dir.name)
        except Exception:
            logger.exception("Error importing apis/%s/seed.py", api_dir.name)

    return seeds


async def seed_api(api_name: str, session: AsyncSession) -> bool:
    """Call the seed of a specific API by name.

    Used by sync_app_registry when a new API AppEntry is created.

    Args:
        api_name: API name (e.g. 'eve').
        session: DB session (caller is responsible for the commit).

    Returns:
        True if data was inserted, False otherwise.
    """
    seeds = _discover_api_seeds()
    module = seeds.get(api_name)
    if module is None:
        logger.debug("No seed found for API '%s'", api_name)
        return False

    try:
        result = await module.seed(session)
        if result:
            logger.info("🌱 Seed API '%s' executed", api_name)
        return result
    except Exception:
        logger.exception("Error during seed of API '%s'", api_name)
        return False


# ---------------------------------------------------------------------------
# Orchestrator — called at startup
# ---------------------------------------------------------------------------

async def seed_initial_data() -> bool:
    """Insert initial data if the database is empty.

    - _seed_default_admin: always (every app needs an admin)
    - apis/*/seed.py: auto-discovery of each API seed

    Returns:
        True if data was inserted, False otherwise.
    """
    engine = _get_engine()
    seeded = False

    async with AsyncSession(engine, expire_on_commit=False) as session:
        if await _seed_default_admin(session):
            seeded = True

        # Auto-discovery: call each API seed
        for api_name, module in _discover_api_seeds().items():
            try:
                if await module.seed(session):
                    seeded = True
                    logger.info("🌱 Seed API '%s' executed", api_name)
            except Exception:
                logger.exception("Error seeding API '%s'", api_name)

        if seeded:
            await session.commit()
            logger.info("🌱 Initial seed completed")
        else:
            logger.debug("DB already populated — seed skipped")

    return seeded


async def main() -> None:
    """Entry point for manual execution."""
    from apymix.db import init_db
    await init_db(level=logging.INFO, format="%(message)s")
    inserted = await seed_initial_data()
    if not inserted:
        print("ℹ️  Database already contains data — nothing to do.")


async def reset_and_seed() -> None:
    """Reset all tables and replay the full seed.

    Used when FORCE_SEED=true at startup (--seed option in dev/CI).
    ⚠️  All existing data is deleted.
    """
    from apymix.db.session import _get_engine
    from sqlmodel import SQLModel

    from apymix.discovery import import_all_api_models  # registers models

    import_all_api_models()

    engine = _get_engine()

    # Drop + recreate all tables
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)

    logger.info("🗑️  Tables reset")

    await seed_initial_data()


if __name__ == "__main__":
    asyncio.run(main())
