"""Database restore CLI script.

Usage:
    # List available backups on S3
    uv run scripts/db_restore.py --list

    # Restore the most recent backup from S3 to the target DB
    uv run scripts/db_restore.py --source latest

    # Restore a specific S3 key
    uv run scripts/db_restore.py --source backups/20260312_100000.json.gz

    # Restore from a local file
    uv run scripts/db_restore.py --source ./backup.json.gz

    # Restore to another DB (e.g. local SQLite for staging)
    uv run scripts/db_restore.py --source latest --target-db-url sqlite+aiosqlite:///./staging.db

    # Restore to another PostgreSQL
    uv run scripts/db_restore.py --source latest \\
        --target-db-url postgresql+asyncpg://user:pass@host/dbname

Notes:
    - Without --target-db-url, the target DB is DATABASE_URL from .env
    - Tables are created if they do not exist (via SQLModel.metadata)
    - Existing data is deleted before restore
    - Idempotent operation: safe to re-run on an empty DB

Main use case (preprod/staging):
    DATABASE_URL=sqlite+aiosqlite:///./staging.db \\
    uv run scripts/db_restore.py --source latest
"""

import argparse
import asyncio
import importlib
import logging
import sys
from pathlib import Path

# Add the project root to the path for apymix.* imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel

from apymix.backup import download_backup, list_backups, load_from_bytes
from apymix.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _import_all_models() -> None:
    """Import all models modules to populate SQLModel.metadata.

    Required so that create_all() creates the right tables in the target DB.
    Add each new `models.py` created in apymix/ or apis/* here.
    """
    modules = [
        "apymix.db.models",
        "apymix.apps.models",
        "apymix.auth.models",
    ]
    # Auto-discovery of APIs
    apis_dir = Path(__file__).resolve().parent.parent / "apis"
    if apis_dir.is_dir():
        for api_dir in sorted(apis_dir.iterdir()):
            models_path = api_dir / "models.py"
            if models_path.is_file():
                modules.append(f"apis.{api_dir.name}.models")

    for module in modules:
        try:
            importlib.import_module(module)
            logger.debug("Models imported: %s", module)
        except ImportError as e:
            logger.warning("Could not import %s: %s", module, e)


async def restore(backup_data: dict, target_db_url: str) -> None:
    """Restore a backup into the target DB.

    - Creates missing tables (via SQLModel.metadata)
    - Empties existing tables in reverse order (respects FK)
    - Inserts all rows from the backup
    """
    engine = create_async_engine(target_db_url, echo=False)

    _import_all_models()

    async with engine.begin() as conn:
        # Create tables if they do not exist
        await conn.run_sync(SQLModel.metadata.create_all)
        logger.info("Tables verified / created")

        # Disable FKs for the duration of the restore
        def get_table_names(sync_conn):
            return inspect(sync_conn).get_table_names()

        def get_column_names(sync_conn, table_name):
            return {c["name"] for c in inspect(sync_conn).get_columns(table_name)}

        existing_tables = await conn.run_sync(get_table_names)

        is_sqlite = "sqlite" in target_db_url
        if is_sqlite:
            await conn.execute(text("PRAGMA foreign_keys = OFF"))
        else:
            await conn.execute(text("SET session_replication_role = 'replica'"))

        # Empty tables in reverse order (FK)
        tables_in_backup = list(backup_data["tables"].keys())
        for table_name in reversed(tables_in_backup):
            if table_name in existing_tables:
                await conn.execute(text(f'DELETE FROM "{table_name}"'))
                logger.debug("Table emptied: %s", table_name)

        # Insert data
        total_inserted = 0
        for table_name, rows in backup_data["tables"].items():
            if not rows:
                logger.info("Table %s: empty (0 rows)", table_name)
                continue
            if table_name not in existing_tables:
                logger.warning("Table %s missing from target DB — skipped", table_name)
                continue

            columns_in_backup = list(rows[0].keys())

            # Columns actually present in the target table
            target_columns = await conn.run_sync(get_column_names, table_name)

            # Backup columns missing from the target (dropped column)
            dropped = [c for c in columns_in_backup if c not in target_columns]
            if dropped:
                logger.warning(
                    "Table %s: column(s) skipped because missing from target: %s",
                    table_name, dropped,
                )

            # Target columns missing from the backup (added column) → NULL/default
            added = [c for c in target_columns if c not in columns_in_backup]
            if added:
                logger.info(
                    "Table %s: column(s) not present in backup → NULL/default value: %s",
                    table_name, added,
                )

            # Only insert common columns
            columns = [c for c in columns_in_backup if c in target_columns]
            if not columns:
                logger.warning("Table %s: no common columns — skipped", table_name)
                continue

            # Filter rows to keep only common columns
            # SQLite does not handle dict/list natively → serialize as JSON string
            def _coerce(v):
                if is_sqlite and isinstance(v, (dict, list)):
                    import json as _json
                    return _json.dumps(v, ensure_ascii=False)
                return v

            filtered_rows = [{c: _coerce(row[c]) for c in columns} for row in rows]

            col_list = ", ".join(f'"{c}"' for c in columns)
            placeholders = ", ".join(f":{c}" for c in columns)
            query = text(f'INSERT INTO "{table_name}" ({col_list}) VALUES ({placeholders})')

            await conn.execute(query, filtered_rows)
            logger.info("Table %s: %d rows inserted", table_name, len(rows))
            total_inserted += len(rows)

        # Re-enable FKs
        if is_sqlite:
            await conn.execute(text("PRAGMA foreign_keys = ON"))
        else:
            await conn.execute(text("SET session_replication_role = 'origin'"))

    await engine.dispose()
    logger.info("✅ Restore completed: %d total rows", total_inserted)


async def main(args: argparse.Namespace) -> None:
    settings = get_settings()

    # --- Listing ---
    if args.list:
        if not settings.backup_enabled:
            logger.error("❌ S3 not configured — cannot list backups")
            sys.exit(1)
        backups = await list_backups(settings)
        if not backups:
            logger.info("No backup available")
            return
        for b in backups:
            size_kb = b["size_bytes"] / 1024
            logger.info("%-50s  %6.1f Ko  %s", b["key"], size_kb, b["last_modified"])
        return

    # --- Resolve source ---
    source = args.source
    if not source:
        logger.error("Provide --source <S3 key | 'latest' | local file> or --list")
        sys.exit(1)

    # Load raw data
    if Path(source).exists():
        logger.info("Loading from local file: %s", source)
        raw = Path(source).read_bytes()
    else:
        if not settings.backup_enabled:
            logger.error("❌ S3 not configured — cannot download %s", source)
            sys.exit(1)
        if source == "latest":
            backups = await list_backups(settings)
            if not backups:
                logger.error("No backup available on S3")
                sys.exit(1)
            source = backups[0]["key"]
            logger.info("Most recent backup: %s", source)
        logger.info("Downloading from S3: %s", source)
        raw = await download_backup(source, settings)

    backup_data = load_from_bytes(raw)
    tables = backup_data.get("tables", {})
    rows_total = sum(len(r) for r in tables.values())
    logger.info(
        "Backup loaded: v%s created on %s — %d tables, %d rows",
        backup_data.get("version", "?"),
        backup_data.get("created_at", "?"),
        len(tables), rows_total,
    )

    # --- Target DB ---
    target_db_url = args.target_db_url or settings.database_url
    logger.info("Target DB: %s", target_db_url.split("@")[-1] if "@" in target_db_url else target_db_url)

    await restore(backup_data, target_db_url)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Restore the Apymix database from a backup",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--source",
        metavar="SOURCE",
        help="S3 key (e.g. backups/20260312_100000.json.gz), 'latest', or local path",
    )
    parser.add_argument(
        "--target-db-url",
        metavar="URL",
        help="Target DB URL (default: DATABASE_URL from .env). "
             "Examples: sqlite+aiosqlite:///./staging.db, postgresql+asyncpg://user:pass@host/db",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available backups on S3 and quit",
    )
    args = parser.parse_args()
    asyncio.run(main(args))
