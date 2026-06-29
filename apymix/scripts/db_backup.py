"""Database backup CLI script.

Usage:
    uv run scripts/db_backup.py                    # backup → S3 (config from .env)
    uv run scripts/db_backup.py --local out.json.gz  # backup → local file only

Prerequisites (environment variables):
    DATABASE_URL            Source database URL (SQLite or async PostgreSQL)
    S3_ENDPOINT_URL         S3 endpoint, e.g. https://s3.fr-par.scw.cloud
    S3_ACCESS_KEY_ID
    S3_SECRET_ACCESS_KEY
    S3_BUCKET_NAME

Variables can be defined in a .env file at the project root.
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add the project root to the path for apymix.* imports
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
        logger.info("Backup → local file: %s", local_path)
        backup_data = await create_backup(engine)
        data_bytes = dump_to_bytes(backup_data)
        Path(local_path).write_bytes(data_bytes)
        rows = sum(len(rows) for rows in backup_data["tables"].values())
        logger.info(
            "✅ Local backup: %d tables, %d rows, %.1f Ko → %s",
            len(backup_data["tables"]), rows, len(data_bytes) / 1024, local_path,
        )
    else:
        if not settings.backup_enabled:
            logger.error(
                "❌ S3 backup not configured. "
                "Check S3_ENDPOINT_URL, S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY, S3_BUCKET_NAME in .env"
            )
            sys.exit(1)
        result = await backup_and_upload(engine, settings)
        logger.info(
            "✅ S3 backup: %s — %d tables, %d rows, %.1f Ko",
            result["key"], result["tables"], result["rows"], result["size_bytes"] / 1024,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Apymix database backup")
    parser.add_argument(
        "--local",
        metavar="FILE",
        help="Save locally (e.g. backup.json.gz) instead of uploading to S3",
    )
    args = parser.parse_args()
    asyncio.run(main(args.local))
