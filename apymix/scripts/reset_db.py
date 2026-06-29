"""Reset script — drops and recreates the database (SQLite dev or PostgreSQL).

Usage:
    python -m scripts.reset_db                   # reset SQLite (dev)
    python -m scripts.reset_db --seed            # reset + admin seed
    python -m scripts.reset_db --force-postgres  # allow reset on PostgreSQL
    python -m scripts.reset_db --force-postgres --seed
"""

import argparse
import asyncio
from pathlib import Path

from apymix.config import get_settings


async def reset_db(seed: bool = False, force_postgres: bool = False) -> None:
    """Drop and recreate tables (SQLite or PostgreSQL with --force-postgres)."""
    settings = get_settings()
    is_sqlite = settings.database_url.startswith("sqlite")

    db_label = settings.database_url[:60] + ("…" if len(settings.database_url) > 60 else "")
    print(f"🗄️  Target database: {db_label}")

    if not is_sqlite and not force_postgres:
        print("❌ PostgreSQL database detected. Use --force-postgres to confirm the reset.")
        return

    # Import models before any operation
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
            print(f"🗑️  File deleted: {db_file}")
        else:
            print(f"ℹ️  No file to delete ({db_file})")
    else:
        from apymix.db.session import _get_engine
        from sqlmodel import SQLModel

        engine = _get_engine()
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.drop_all)
        print("🗑️  PostgreSQL tables dropped")

    await init_db()
    print("✅ Database recreated")

    if seed:
        from apymix.scripts.db_init import seed_initial_data
        await seed_initial_data()
        print("🌱 Full seed (admin + APIs) completed")


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset the database")
    parser.add_argument("--seed", action="store_true", help="Create an admin after the reset")
    parser.add_argument(
        "--force-postgres",
        action="store_true",
        help="Allow reset on a PostgreSQL database (⚠️ destructive)",
    )
    args = parser.parse_args()

    asyncio.run(reset_db(seed=args.seed, force_postgres=args.force_postgres))


if __name__ == "__main__":
    main()
