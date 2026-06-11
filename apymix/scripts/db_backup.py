"""Script CLI de backup de la base de données.

Usage :
    uv run scripts/db_backup.py                    # backup → S3 (config depuis .env)
    uv run scripts/db_backup.py --local out.json.gz  # backup → fichier local uniquement

Prérequis (variables d'environnement) :
    DATABASE_URL            URL de la BDD source (SQLite ou PostgreSQL async)
    S3_ENDPOINT_URL         Endpoint S3, ex: https://s3.fr-par.scw.cloud
    S3_ACCESS_KEY_ID
    S3_SECRET_ACCESS_KEY
    S3_BUCKET_NAME

Les variables peuvent être dans un fichier .env à la racine du projet.
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Ajouter la racine du projet au path pour les imports papi.*
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from apymix.backup import backup_and_upload, create_backup, dump_to_bytes
from apymix.config import get_settings
from apymix.db.session import _get_engine

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def main(local_path: str | None) -> None:
    settings = get_settings()
    engine = _get_engine()

    if local_path:
        logger.info("Backup → fichier local : %s", local_path)
        backup_data = await create_backup(engine)
        data_bytes = dump_to_bytes(backup_data)
        Path(local_path).write_bytes(data_bytes)
        rows = sum(len(rows) for rows in backup_data["tables"].values())
        logger.info(
            "✅ Backup local : %d tables, %d lignes, %.1f Ko → %s",
            len(backup_data["tables"]), rows, len(data_bytes) / 1024, local_path,
        )
    else:
        if not settings.backup_enabled:
            logger.error(
                "❌ Backup S3 non configuré. "
                "Vérifier S3_ENDPOINT_URL, S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY, S3_BUCKET_NAME dans .env"
            )
            sys.exit(1)
        result = await backup_and_upload(engine, settings)
        logger.info(
            "✅ Backup S3 : %s — %d tables, %d lignes, %.1f Ko",
            result["key"], result["tables"], result["rows"], result["size_bytes"] / 1024,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backup de la base de données PAPI")
    parser.add_argument(
        "--local",
        metavar="FICHIER",
        help="Sauvegarder en local (ex: backup.json.gz) au lieu d'uploader sur S3",
    )
    args = parser.parse_args()
    asyncio.run(main(args.local))
