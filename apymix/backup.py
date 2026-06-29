"""Database backup and restore.

Strategy:
- Read all tables via SQLAlchemy (shared connection with the app)
- JSON serialization + gzip compression
- Upload/download to an S3-compatible bucket (Scaleway Object Storage)

No dependency on pg_dump — works with PostgreSQL and SQLite.
The backup file can be restored into any target database, including
a local SQLite (staging / preprod).

Backup file format:
    {
        "version": "1",
        "created_at": "2026-03-12T10:00:00+00:00",
        "tables": {
            "eve_events": [{"id": "...", "name": "...", ...}, ...],
            "eve_rsvps":  [...],
            ...
        }
    }
"""

import asyncio
import gzip
import json
import logging
from datetime import date, datetime, timezone
from typing import Any

import boto3
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger(__name__)

BACKUP_KEY_PREFIX = "backups/"


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def _serialize_value(v: Any) -> Any:
    """Make a value JSON-serializable."""
    import uuid
    if isinstance(v, uuid.UUID):
        return str(v)
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, bytes):
        return v.hex()
    return v


def dump_to_bytes(backup_data: dict) -> bytes:
    """Serialize and compress a backup dict into gzip bytes."""
    json_bytes = json.dumps(backup_data, ensure_ascii=False).encode("utf-8")
    return gzip.compress(json_bytes)


def load_from_bytes(data: bytes) -> dict:
    """Decompress and deserialize a gzip backup → dict."""
    return json.loads(gzip.decompress(data).decode("utf-8"))


# ---------------------------------------------------------------------------
# Reading the DB (async)
# ---------------------------------------------------------------------------

async def create_backup(engine: AsyncEngine) -> dict:
    """Read all tables via SQLAlchemy and return the backup dict.

    Uses the app's existing connection — no pg_dump needed.
    Works with PostgreSQL and SQLite.
    """
    async with engine.connect() as conn:

        def _get_table_names(sync_conn):
            return inspect(sync_conn).get_table_names()

        table_names = await conn.run_sync(_get_table_names)

        tables: dict[str, list[dict]] = {}
        for table_name in table_names:
            result = await conn.execute(text(f'SELECT * FROM "{table_name}"'))
            rows = result.mappings().all()
            tables[table_name] = [
                {k: _serialize_value(v) for k, v in row.items()}
                for row in rows
            ]
            logger.debug("Backup table %s : %d row(s)", table_name, len(tables[table_name]))

    rows_total = sum(len(rows) for rows in tables.values())
    logger.info(
        "Backup created: %d tables, %d rows total",
        len(tables), rows_total,
    )
    return {
        "version": "1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "tables": tables,
    }


# ---------------------------------------------------------------------------
# S3
# ---------------------------------------------------------------------------

def _make_s3_client(settings):
    """Create a boto3 client configured from settings."""
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key_id,
        aws_secret_access_key=settings.s3_secret_access_key,
        region_name=settings.s3_region,
    )


def _upload_sync(data: bytes, key: str, settings) -> None:
    """Sync upload (called via asyncio.to_thread)."""
    client = _make_s3_client(settings)
    client.put_object(
        Bucket=settings.s3_bucket_name,
        Key=key,
        Body=data,
        ContentType="application/gzip",
    )


def _list_sync(settings) -> list[dict]:
    """List available backups (called via asyncio.to_thread)."""
    client = _make_s3_client(settings)
    response = client.list_objects_v2(
        Bucket=settings.s3_bucket_name,
        Prefix=BACKUP_KEY_PREFIX,
    )
    objects = response.get("Contents", [])
    return [
        {
            "key": obj["Key"],
            "size_bytes": obj["Size"],
            "last_modified": obj["LastModified"].isoformat(),
        }
        for obj in sorted(objects, key=lambda x: x["LastModified"], reverse=True)
    ]


def _download_sync(key: str, settings) -> bytes:
    """Download a backup from S3 (called via asyncio.to_thread)."""
    client = _make_s3_client(settings)
    response = client.get_object(Bucket=settings.s3_bucket_name, Key=key)
    return response["Body"].read()


# ---------------------------------------------------------------------------
# High-level pipeline (async)
# ---------------------------------------------------------------------------

async def backup_and_upload(engine: AsyncEngine, settings) -> dict:
    """Full pipeline: dump DB → gzip → upload to S3.

    Returns a dict with the S3 key, size and timestamp.
    """
    if not settings.backup_enabled:
        raise RuntimeError("S3 backup not configured (missing S3_* variables)")

    backup_data = await create_backup(engine)
    data_bytes = dump_to_bytes(backup_data)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    key = f"{BACKUP_KEY_PREFIX}{timestamp}.json.gz"

    await asyncio.to_thread(_upload_sync, data_bytes, key, settings)

    rows_total = sum(len(rows) for rows in backup_data["tables"].values())
    logger.info(
        "Backup uploaded: %s (%d tables, %d rows, %.1f KB)",
        key, len(backup_data["tables"]), rows_total, len(data_bytes) / 1024,
    )
    return {
        "key": key,
        "size_bytes": len(data_bytes),
        "created_at": backup_data["created_at"],
        "tables": len(backup_data["tables"]),
        "rows": rows_total,
    }


async def list_backups(settings) -> list[dict]:
    """List the backups available in S3."""
    if not settings.backup_enabled:
        raise RuntimeError("S3 backup not configured (missing S3_* variables)")
    return await asyncio.to_thread(_list_sync, settings)


async def download_backup(key: str, settings) -> bytes:
    """Download a backup from S3 as gzip bytes."""
    if not settings.backup_enabled:
        raise RuntimeError("S3 backup not configured (missing S3_* variables)")
    return await asyncio.to_thread(_download_sync, key, settings)
