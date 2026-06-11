"""Seed de données initiales pour le développement.

Peuple la base avec des données réalistes si elle est vide :
- Un utilisateur admin (sebastien / pulse)
- Les données de démo de chaque API (auto-discovery via apis/<name>/seed.py)

Le seed se déclenche **automatiquement** au démarrage si la DB est vide.
Il est aussi appelé par le registre (`sync_app_registry`) lorsqu'une
nouvelle AppEntry de type API est insérée en DB pour la première fois.

Lancement manuel :
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
# Seed admin — réutilisable par toutes les apps métier
# ---------------------------------------------------------------------------

async def _seed_default_admin(session: AsyncSession) -> bool:
    """Crée l'utilisateur admin par défaut si aucun user n'existe.

    Returns:
        True si un admin a été créé, False sinon.
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
    admin_password = os.environ.get("ADMIN_PASSWORD", "papi")
    account = UserAccount(
        user_id=admin.id,
        provider="password",
        provider_user_id="admin",
        password_hash=get_password_hash(admin_password),
    )
    session.add(account)
    logger.info("👤 Utilisateur créé : admin / %s", "(ADMIN_PASSWORD)" if os.environ.get("ADMIN_PASSWORD") else "papi")
    return True


# ---------------------------------------------------------------------------
# Auto-discovery des seeds API — apis/<name>/seed.py
# ---------------------------------------------------------------------------

def _discover_api_seeds() -> dict[str, object]:
    """Scanne apis/*/seed.py et retourne {api_name: module}.

    Chaque module doit exposer une coroutine :
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
                logger.debug("Seed découvert : apis/%s/seed.py", api_dir.name)
            else:
                logger.warning("apis/%s/seed.py n'expose pas de coroutine 'seed(session)'", api_dir.name)
        except Exception:
            logger.exception("Erreur import apis/%s/seed.py", api_dir.name)

    return seeds


async def seed_api(api_name: str, session: AsyncSession) -> bool:
    """Appelle le seed d'une API spécifique par son nom.

    Utilisé par sync_app_registry quand une nouvelle AppEntry API est créée.

    Args:
        api_name: Nom de l'API (ex: 'eve').
        session: Session DB (le commit est à la charge de l'appelant).

    Returns:
        True si des données ont été insérées, False sinon.
    """
    seeds = _discover_api_seeds()
    module = seeds.get(api_name)
    if module is None:
        logger.debug("Pas de seed trouvé pour l'API '%s'", api_name)
        return False

    try:
        result = await module.seed(session)
        if result:
            logger.info("🌱 Seed API '%s' exécuté", api_name)
        return result
    except Exception:
        logger.exception("Erreur lors du seed de l'API '%s'", api_name)
        return False


# ---------------------------------------------------------------------------
# Orchestrateur — appelé au démarrage
# ---------------------------------------------------------------------------

async def seed_initial_data() -> bool:
    """Insère les données initiales si la base est vide.

    - _seed_default_admin : toujours (toute app a besoin d'un admin)
    - apis/*/seed.py : auto-découverte de chaque seed API

    Returns:
        True si des données ont été insérées, False sinon.
    """
    engine = _get_engine()
    seeded = False

    async with AsyncSession(engine, expire_on_commit=False) as session:
        if await _seed_default_admin(session):
            seeded = True

        # Auto-discovery : appeler le seed de chaque API
        for api_name, module in _discover_api_seeds().items():
            try:
                if await module.seed(session):
                    seeded = True
                    logger.info("🌱 Seed API '%s' exécuté", api_name)
            except Exception:
                logger.exception("Erreur seed API '%s'", api_name)

        if seeded:
            await session.commit()
            logger.info("🌱 Seed initial terminé")
        else:
            logger.debug("DB déjà peuplée — seed ignoré")

    return seeded


async def main() -> None:
    """Point d'entrée pour exécution manuelle."""
    from apymix.db import init_db
    await init_db(level=logging.INFO, format="%(message)s")
    inserted = await seed_initial_data()
    if not inserted:
        print("ℹ️  La base contient déjà des données — rien à faire.")


async def reset_and_seed() -> None:
    """Réinitialise toutes les tables et rejoue le seed complet.

    Utilisé quand FORCE_SEED=true au démarrage (option --seed en dev/CI).
    ⚠️  Toutes les données existantes sont supprimées.
    """
    from apymix.db import init_db
    from apymix.db.session import _get_engine
    from sqlmodel import SQLModel

    from apymix.discovery import import_all_api_models  # enregistre les modèles

    import_all_api_models()

    engine = _get_engine()

    # Drop + recreate toutes les tables
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)

    logger.info("🗑️  Tables réinitialisées")

    await seed_initial_data()


if __name__ == "__main__":
    asyncio.run(main())
