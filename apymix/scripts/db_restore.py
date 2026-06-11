"""Script CLI de restore de la base de données.

Usage :
    # Lister les backups disponibles sur S3
    uv run scripts/db_restore.py --list

    # Restaurer le backup le plus récent depuis S3 vers la DB cible
    uv run scripts/db_restore.py --source latest

    # Restaurer une clé S3 spécifique
    uv run scripts/db_restore.py --source backups/20260312_100000.json.gz

    # Restaurer depuis un fichier local
    uv run scripts/db_restore.py --source ./backup.json.gz

    # Restaurer vers une autre DB (ex: SQLite local pour recette)
    uv run scripts/db_restore.py --source latest --target-db-url sqlite+aiosqlite:///./recette.db

    # Restaurer vers un autre PostgreSQL
    uv run scripts/db_restore.py --source latest \\
        --target-db-url postgresql+asyncpg://user:pass@host/dbname

Notes :
    - Sans --target-db-url, la DB cible est DATABASE_URL depuis .env
    - Les tables sont créées si elles n'existent pas (via SQLModel.metadata)
    - Les données existantes sont supprimées avant restauration
    - Opération idempotente : peut être relancée sans risque sur une DB vide

Cas d'usage principal (preprod/recette) :
    DATABASE_URL=sqlite+aiosqlite:///./recette.db \\
    uv run scripts/db_restore.py --source latest
"""

import argparse
import asyncio
import importlib
import logging
import sys
from pathlib import Path

# Ajouter la racine du projet au path pour les imports papi.*
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel

from apymix.backup import download_backup, list_backups, load_from_bytes
from apymix.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _import_all_models() -> None:
    """Importe tous les modules models pour peupler SQLModel.metadata.

    Nécessaire pour que create_all() crée les bonnes tables dans la DB cible.
    Ajouter ici chaque nouveau `models.py` créé dans papi/ ou apis/*.
    """
    modules = [
        "papi.db.models",
        "papi.apps.models",
        "papi.auth.models",
    ]
    # Auto-découverte des APIs
    apis_dir = Path(__file__).resolve().parent.parent / "apis"
    if apis_dir.is_dir():
        for api_dir in sorted(apis_dir.iterdir()):
            models_path = api_dir / "models.py"
            if models_path.is_file():
                modules.append(f"apis.{api_dir.name}.models")

    for module in modules:
        try:
            importlib.import_module(module)
            logger.debug("Modèles importés : %s", module)
        except ImportError as e:
            logger.warning("Impossible d'importer %s : %s", module, e)


async def restore(backup_data: dict, target_db_url: str) -> None:
    """Restaure un backup dans la DB cible.

    - Crée les tables manquantes (via SQLModel.metadata)
    - Vide les tables existantes dans l'ordre inverse (respect FK)
    - Insère toutes les lignes du backup
    """
    engine = create_async_engine(target_db_url, echo=False)

    _import_all_models()

    async with engine.begin() as conn:
        # Créer les tables si elles n'existent pas
        await conn.run_sync(SQLModel.metadata.create_all)
        logger.info("Tables vérifiées / créées")

        # Désactiver les FK le temps du restore
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

        # Vider les tables dans l'ordre inverse (FK)
        tables_in_backup = list(backup_data["tables"].keys())
        for table_name in reversed(tables_in_backup):
            if table_name in existing_tables:
                await conn.execute(text(f'DELETE FROM "{table_name}"'))
                logger.debug("Table vidée : %s", table_name)

        # Insérer les données
        total_inserted = 0
        for table_name, rows in backup_data["tables"].items():
            if not rows:
                logger.info("Table %s : vide (0 lignes)", table_name)
                continue
            if table_name not in existing_tables:
                logger.warning("Table %s absente de la DB cible — ignorée", table_name)
                continue

            columns_in_backup = list(rows[0].keys())

            # Colonnes réellement présentes dans la table cible
            target_columns = await conn.run_sync(get_column_names, table_name)

            # Colonnes du backup absentes de la cible (colonne supprimée)
            dropped = [c for c in columns_in_backup if c not in target_columns]
            if dropped:
                logger.warning(
                    "Table %s : colonne(s) ignorée(s) car absente(s) de la cible : %s",
                    table_name, dropped,
                )

            # Colonnes de la cible absentes du backup (colonne ajoutée) → NULL/défaut
            added = [c for c in target_columns if c not in columns_in_backup]
            if added:
                logger.info(
                    "Table %s : colonne(s) non présentes dans le backup → valeur NULL/défaut : %s",
                    table_name, added,
                )

            # On n'insère que les colonnes communes
            columns = [c for c in columns_in_backup if c in target_columns]
            if not columns:
                logger.warning("Table %s : aucune colonne commune — ignorée", table_name)
                continue

            # Filtrer les rows pour ne garder que les colonnes communes
            # SQLite ne gère pas les dict/list nativement → sérialiser en JSON string
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
            logger.info("Table %s : %d lignes insérées", table_name, len(rows))
            total_inserted += len(rows)

        # Réactiver les FK
        if is_sqlite:
            await conn.execute(text("PRAGMA foreign_keys = ON"))
        else:
            await conn.execute(text("SET session_replication_role = 'origin'"))

    await engine.dispose()
    logger.info("✅ Restore terminé : %d lignes au total", total_inserted)


async def main(args: argparse.Namespace) -> None:
    settings = get_settings()

    # --- Listing ---
    if args.list:
        if not settings.backup_enabled:
            logger.error("❌ S3 non configuré — impossible de lister les backups")
            sys.exit(1)
        backups = await list_backups(settings)
        if not backups:
            logger.info("Aucun backup disponible")
            return
        for b in backups:
            size_kb = b["size_bytes"] / 1024
            logger.info("%-50s  %6.1f Ko  %s", b["key"], size_kb, b["last_modified"])
        return

    # --- Resolve source ---
    source = args.source
    if not source:
        logger.error("Fournir --source <clé S3 | 'latest' | fichier local> ou --list")
        sys.exit(1)

    # Charger les données brutes
    if Path(source).exists():
        logger.info("Chargement depuis fichier local : %s", source)
        raw = Path(source).read_bytes()
    else:
        if not settings.backup_enabled:
            logger.error("❌ S3 non configuré — impossible de télécharger %s", source)
            sys.exit(1)
        if source == "latest":
            backups = await list_backups(settings)
            if not backups:
                logger.error("Aucun backup disponible sur S3")
                sys.exit(1)
            source = backups[0]["key"]
            logger.info("Backup le plus récent : %s", source)
        logger.info("Téléchargement depuis S3 : %s", source)
        raw = await download_backup(source, settings)

    backup_data = load_from_bytes(raw)
    tables = backup_data.get("tables", {})
    rows_total = sum(len(r) for r in tables.values())
    logger.info(
        "Backup chargé : v%s créé le %s — %d tables, %d lignes",
        backup_data.get("version", "?"),
        backup_data.get("created_at", "?"),
        len(tables), rows_total,
    )

    # --- Target DB ---
    target_db_url = args.target_db_url or settings.database_url
    logger.info("DB cible : %s", target_db_url.split("@")[-1] if "@" in target_db_url else target_db_url)

    await restore(backup_data, target_db_url)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Restore de la base de données PAPI depuis un backup",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--source",
        metavar="SOURCE",
        help="Clé S3 (ex: backups/20260312_100000.json.gz), 'latest', ou chemin local",
    )
    parser.add_argument(
        "--target-db-url",
        metavar="URL",
        help="URL de la DB cible (défaut: DATABASE_URL depuis .env). "
             "Exemples: sqlite+aiosqlite:///./recette.db, postgresql+asyncpg://user:pass@host/db",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Lister les backups disponibles sur S3 et quitter",
    )
    args = parser.parse_args()
    asyncio.run(main(args))
