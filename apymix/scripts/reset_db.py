"""Script de reset — supprime et recrée la BDD (SQLite dev ou PostgreSQL).

Usage :
    python -m scripts.reset_db                   # reset SQLite (dev)
    python -m scripts.reset_db --seed            # reset + seed admin
    python -m scripts.reset_db --force-postgres  # permet le reset sur PostgreSQL
    python -m scripts.reset_db --force-postgres --seed
"""

import argparse
import asyncio
from pathlib import Path

from apymix.config import get_settings


async def reset_db(seed: bool = False, force_postgres: bool = False) -> None:
    """Supprime et recrée les tables (SQLite ou PostgreSQL avec --force-postgres)."""
    settings = get_settings()
    is_sqlite = settings.database_url.startswith("sqlite")

    db_label = settings.database_url[:60] + ("…" if len(settings.database_url) > 60 else "")
    print(f"🗄️  Base cible : {db_label}")

    if not is_sqlite and not force_postgres:
        print("❌ Base PostgreSQL détectée. Utilise --force-postgres pour confirmer le reset.")
        return

    # Import des modèles avant toute opération
    from apymix.auth.models import User  # noqa: F401
    from apymix.auth.models import UserAccount  # noqa: F401
    from apymix.discovery import import_all_api_models
    from apymix.db.session import init_db

    import_all_api_models()

    if is_sqlite:
        db_path = settings.database_url.replace("sqlite+aiosqlite:///", "")
        db_file = Path(db_path)
        if db_file.exists():
            db_file.unlink()
            print(f"🗑️  Fichier supprimé : {db_file}")
        else:
            print(f"ℹ️  Pas de fichier à supprimer ({db_file})")
    else:
        from apymix.db.session import _get_engine
        from sqlmodel import SQLModel

        engine = _get_engine()
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.drop_all)
        print("🗑️  Tables PostgreSQL supprimées")

    await init_db()
    print("✅ Base recréée")

    if seed:
        from apymix.scripts.db_init import seed_initial_data
        await seed_initial_data()
        print("🌱 Seed complet (admin + APIs) terminé")


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset la base de données")
    parser.add_argument("--seed", action="store_true", help="Créer un admin après le reset")
    parser.add_argument(
        "--force-postgres",
        action="store_true",
        help="Autoriser le reset sur une base PostgreSQL (⚠️ destructif)",
    )
    args = parser.parse_args()

    asyncio.run(reset_db(seed=args.seed, force_postgres=args.force_postgres))


if __name__ == "__main__":
    main()
