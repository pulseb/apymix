"""Admin API for Apymix — seed management, audit, monitoring.

Mounted on `/-/api/*` — JSON endpoints protected by JWT Bearer.
Authentication: Authorization: Bearer <access_token>
All endpoints require a user with the 'admin' role.
"""

import importlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel

from apymix.auth.models import User
from apymix.auth.security import get_current_user
from apymix.db import get_db
from apymix.db.session import _get_engine
from apymix.scripts.db_init import seed_api
from apymix.backup import backup_and_upload, list_backups
from apymix.config import get_settings
logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["admin"])


async def _require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Dependency to verify authentication + admin role.

    Requires: Authorization: Bearer <jwt>
    Checks: user.role == 'admin'
    Raises HTTPException 403 if not admin.

    Returns the User for audit logging.
    """
    if not current_user.has_role("admin"):
        logger.warning(
            "Attempt to access /-/api/* with insufficient role (user_id=%s, roles=%s)",
            current_user.id,
            current_user.roles,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access restricted to administrators",
        )
    return current_user


def _discover_seedable_apis() -> list[str]:
    """List the APIs that have a seed.py file."""
    apis_dir = Path(__file__).resolve().parent.parent.parent / "apis"
    result = []
    if not apis_dir.is_dir():
        return result
    for api_dir in sorted(apis_dir.iterdir()):
        if api_dir.is_dir() and (api_dir / "seed.py").is_file():
            result.append(api_dir.name)
    return result


def _log_audit(user_id: str, action: str, resource: str, status: str, details: str = "") -> None:
    """Log an admin action for the audit trail.

    Format: [AUDIT] [user_id] action resource status details
    """
    timestamp = datetime.utcnow().isoformat()
    msg = f"[AUDIT] [{timestamp}] user={user_id} action={action} resource={resource} status={status}"
    if details:
        msg += f" | {details}"
    logger.info(msg)

@router.get("/docs", include_in_schema=False)
async def admin_docs():
    """Swagger UI for the admin routes (/-/api/*). No auth required to access the doc."""
    from fastapi.openapi.docs import get_swagger_ui_html
    return get_swagger_ui_html(
        openapi_url="/-/openapi.json",
        title="Apymix Admin — Swagger UI",
        swagger_ui_parameters={"persistAuthorization": True, "filter": "🔧 Admin"},
    )

@router.get("")
async def admin_api_root(current_user: User = Depends(_require_admin)) -> dict[str, Any]:
    _log_audit(str(current_user.id), "GET", "/-/api", "ok")
    return {
        "data": {
            "name": "PulseApps Admin API",
            "version": "0.1.0",
            "user": current_user.email,
            "endpoints": {
                "seeds": "GET /-/api/seeds — Lists all seedable APIs",
                "trigger_seed": "POST /-/api/seeds/{name} — Triggers a seed",
                "reset_tables": "POST /-/api/tables/reset — DROP + CREATE tables (destructive)",
            },
            "docs": "See /-/docs for full documentation",
        },
        "message": "ok",
    }


@router.get("/seeds")
async def list_seeds(current_user: User = Depends(_require_admin)) -> dict[str, Any]:
    """List all APIs that have an available seed.

    **Auth:** JWT Bearer (admin role required)
    **Audit:** Logged
    """
    apis = _discover_seedable_apis()
    _log_audit(str(current_user.id), "GET", "/-/api/seeds", "ok", f"found {len(apis)} seedable APIs")
    return {
        "data": {
            "available": apis,
            "count": len(apis),
        },
        "message": "ok",
    }


@router.post("/seeds/{api_name}")
async def trigger_seed(
    api_name: str,
    current_user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Trigger the seed of a specific API.

    **Auth:** JWT Bearer (admin role required)
    **Audit:** Action logged with user_id

    **200 response:** Seed triggered (or data already present)
    **404 response:** Seed not available for this API
    **500 response:** Error during the seed
    """
    available = _discover_seedable_apis()
    if api_name not in available:
        _log_audit(str(current_user.id), "POST", f"/-/api/seeds/{api_name}", "failed",
                   "API not seedable")
        raise HTTPException(
            status_code=404,
            detail=f"API '{api_name}' has no seed available"
        )

    try:
        seeded = await seed_api(api_name, db)
        if seeded:
            await db.commit()
            _log_audit(str(current_user.id), "POST", f"/-/api/seeds/{api_name}", "success",
                       "seed executed")
            logger.info("🌱 Seed '%s' triggered via admin API by user %s", api_name, current_user.id)
            return {
                "data": {
                    "api": api_name,
                    "seeded": True,
                    "message": "Seed executed successfully",
                    "timestamp": datetime.utcnow().isoformat(),
                },
                "message": "ok",
            }
        else:
            _log_audit(str(current_user.id), "POST", f"/-/api/seeds/{api_name}", "noop",
                       "data already present")
            return {
                "data": {
                    "api": api_name,
                    "seeded": False,
                    "message": "Data already present — no action taken",
                    "timestamp": datetime.utcnow().isoformat(),
                },
                "message": "ok",
            }
    except Exception as e:
        _log_audit(str(current_user.id), "POST", f"/-/api/seeds/{api_name}", "error",
                   f"exception: {str(e)}")
        logger.exception("Error in seed '%s' via admin API", api_name)
        raise HTTPException(
            status_code=500,
            detail=f"Error running seed '{api_name}': {str(e)}"
        )


# ---------------------------------------------------------------------------
# Tables — Reset
# ---------------------------------------------------------------------------

class TableResetRequest(BaseModel):
    """Body of the table reset request.

    Two modes:
    - ``tables``: explicit list of SQL table names (e.g. ``["eve_events", "eve_rsvps"]``)
    - ``api``: name of an API (e.g. ``"eve"``), which auto-discovers its tables via its ``models.py``

    Both can be combined. ``seed`` triggers the seed after the reset.
    """

    tables: list[str] | None = None
    api: str | None = None
    seed: bool = False


def _discover_api_tables(api_name: str) -> list[str]:
    """Imports the models of an API and returns the associated SQLModel table names.

    The import forces the tables to be registered in ``SQLModel.metadata``.
    """
    module_path = f"apis.{api_name}.models"
    try:
        importlib.import_module(module_path)
    except ModuleNotFoundError as e:
        raise ValueError(f"Module '{module_path}' not found: {e}") from e

    prefix = f"{api_name}_"
    return [
        name for name in SQLModel.metadata.tables
        if name.startswith(prefix)
    ]


@router.post("/tables/reset")
async def reset_tables(
    body: TableResetRequest,
    current_user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Reset (DROP + CREATE) the specified tables.

    **⚠️ Destructive — all data in the affected tables will be lost.**

    **Auth:** JWT Bearer (admin role)
    **Audit:** Action logged

    Two table-selection modes:
    - `tables`: explicit list of SQL names (`["eve_events", "eve_rsvps"]`)
    - `api`: name of an API (`"eve"`) → auto-discovery of its tables via `models.py`

    Both can be combined. `seed` (bool, default `false`) re-runs the seed after the reset.

    **Example:**
    ```json
    { "api": "eve", "seed": true }
    ```
    """
    if not body.tables and not body.api:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide at least 'tables' (SQL names) or 'api' (API name)",
        )

    # 1. Resolve the final list of table names
    table_names: set[str] = set(body.tables or [])

    if body.api:
        try:
            discovered = _discover_api_tables(body.api)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

        if not discovered:
            raise HTTPException(
                status_code=404,
                detail=f"No table found for API '{body.api}'"
                       " (tables must use the prefix '{body.api}_')",
            )
        table_names.update(discovered)

    # 2. Check that all tables are known to SQLModel.metadata
    unknown = table_names - set(SQLModel.metadata.tables.keys())
    if unknown:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown tables (not registered in SQLModel.metadata): {sorted(unknown)}",
        )

    sorted_tables = sorted(table_names)
    _log_audit(
        str(current_user.id), "POST", "/-/api/tables/reset", "started",
        f"tables={sorted_tables} seed={body.seed}",
    )
    logger.warning(
        "🗑️  Reset of tables %s requested by %s (seed=%s)",
        sorted_tables, current_user.email, body.seed,
    )

    # 3. DROP then CREATE via the SQLAlchemy engine (DDL outside session)
    engine = _get_engine()
    dropped: list[str] = []
    created: list[str] = []

    try:
        async with engine.begin() as conn:
            # DROP in reverse order (FKs)
            for name in reversed(sorted_tables):
                table = SQLModel.metadata.tables[name]
                await conn.run_sync(lambda sync_conn, t=table: t.drop(sync_conn, checkfirst=True))
                dropped.append(name)
                logger.info("  ✅ DROP %s", name)

            # CREATE in normal order
            for name in sorted_tables:
                table = SQLModel.metadata.tables[name]
                await conn.run_sync(lambda sync_conn, t=table: t.create(sync_conn, checkfirst=True))
                created.append(name)
                logger.info("  ✅ CREATE %s", name)

    except Exception as e:
        _log_audit(
            str(current_user.id), "POST", "/-/api/tables/reset", "error",
            f"tables={sorted_tables} exception={e}",
        )
        logger.exception("DDL error on tables %s", sorted_tables)
        raise HTTPException(status_code=500, detail=f"DDL error: {e}")

    # 4. Optional seed
    seeded = False
    seed_detail = None
    if body.seed and not body.api:
        seed_detail = "Seed skipped: 'api' is required to trigger an automatic seed"
    elif body.seed and body.api:
        available = _discover_seedable_apis()
        if body.api not in available:
            seed_detail = f"Seed skipped: no seed.py for API '{body.api}'"
            logger.warning(seed_detail)
        else:
            try:
                seeded = await seed_api(body.api, db)
                if seeded:
                    await db.commit()
                    seed_detail = "Seed executed successfully"
                    logger.info("🌱 Seed '%s' executed after reset", body.api)
                else:
                    seed_detail = "Seed: no data inserted (already present?)"
            except Exception as e:
                seed_detail = f"Seed error: {e}"
                logger.exception("Error in seed '%s' after table reset", body.api)

    _log_audit(
        str(current_user.id), "POST", "/-/api/tables/reset", "success",
        f"dropped={dropped} created={created} seeded={seeded}",
    )

    return {
        "data": {
            "dropped": dropped,
            "created": created,
            "seeded": seeded,
            "seed_detail": seed_detail,
            "timestamp": datetime.utcnow().isoformat(),
        },
        "message": "Tables reset successfully",
    }


# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------

@router.post("/backup")
async def trigger_backup(
    current_user: User = Depends(_require_admin),
) -> dict[str, Any]:
    """Trigger a full database backup and upload it to S3.

    **Auth:** JWT Bearer (admin role)
    **Audit:** Action logged

    Reads all tables via SQLAlchemy (no pg_dump required),
    serializes to JSON, compresses to gzip and uploads to the configured S3 bucket.

    **200 response:** Backup created — returns S3 key, size, timestamp
    **503 response:** Backup not configured (missing S3_* variables)
    **500 response:** Error during the backup
    """
    settings = get_settings()
    if not settings.backup_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Backup not configured — S3_ENDPOINT_URL, S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY, S3_BUCKET_NAME variables required",
        )

    try:
        engine = _get_engine()
        result = await backup_and_upload(engine, settings)
        _log_audit(
            str(current_user.id), "POST", "/-/api/backup", "success",
            f"key={result['key']} rows={result['rows']} size={result['size_bytes']}",
        )
        return {"data": result, "message": "Backup created successfully"}
    except Exception as e:
        _log_audit(str(current_user.id), "POST", "/-/api/backup", "error", str(e))
        logger.exception("Backup error")
        raise HTTPException(status_code=500, detail=f"Backup error: {e}")


@router.get("/backups")
async def list_available_backups(
    current_user: User = Depends(_require_admin),
) -> dict[str, Any]:
    """List the backups available in the S3 bucket.

    **Auth:** JWT Bearer (admin role)

    Returns the list sorted from most recent to oldest,
    with S3 key, size in bytes and last-modified date.
    """
    settings = get_settings()
    if not settings.backup_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Backup not configured — missing S3_* variables",
        )

    try:
        backups = await list_backups(settings)
        return {
            "data": {"backups": backups, "count": len(backups)},
            "message": "ok",
        }
    except Exception as e:
        logger.exception("Error listing backups")
        raise HTTPException(status_code=500, detail=f"Listing error: {e}")
