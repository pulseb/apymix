"""Admin routes to trigger the API seeds.

Mounted on ``/-/admin/seed/`` — JSON utilities for dev/scripts.
The official UI is the SQLAdmin action on Applications.
"""

import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from apymix.db import get_db
from apymix.discovery import discover_projects, _get_workspace_root
from apymix.scripts.db_init import seed_api

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/-/admin/seed", tags=["admin-seed"])


def _discover_seedable_apis() -> list[str]:
    """Lists the APIs that have an available seed module (via amx.yaml)."""
    api_entries, _ = discover_projects(_get_workspace_root())
    result = []
    for _route, _app, config in api_entries:
        module_name = config.get("module", "")
        try:
            import importlib
            mod = importlib.import_module(f"{module_name}.seed")
            if hasattr(mod, "seed"):
                result.append(config["name"])
        except ModuleNotFoundError:
            pass
    return result


@router.get("", response_class=JSONResponse)
async def list_seeds(request: Request):
    """Lists the APIs with an available seed."""
    apis = _discover_seedable_apis()
    return {"apis": apis}


@router.post("/{api_name}", response_class=JSONResponse)
async def trigger_seed(
    api_name: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Triggers the seed of a specific API."""
    available = _discover_seedable_apis()
    if api_name not in available:
        return JSONResponse({"detail": f"API '{api_name}' has no seed"}, status_code=404)

    try:
        seeded = await seed_api(api_name, db)
        if seeded:
            await db.commit()
            logger.info("🌱 Seed '%s' triggered via admin", api_name)
            return {"status": "ok", "api": api_name, "seeded": True}
        else:
            return {"status": "ok", "api": api_name, "seeded": False, "message": "Data already present"}
    except Exception as e:
        logger.exception("Error in seed '%s' via admin", api_name)
        return JSONResponse({"detail": str(e)}, status_code=500)
