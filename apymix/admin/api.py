"""API admin pour PAPI — gestion des seeds, audit, monitoring.

Montée sur `/-/api/*` — endpoints JSON protégés par JWT Bearer.
Authentification: Authorization: Bearer <access_token>
Tous les endpoints requièrent un utilisateur avec rôle 'admin'.
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
    """Dépendance pour vérifier l'authentification + rôle admin.
    
    Requiert: Authorization: Bearer <jwt>
    Vérifie: user.role == 'admin'
    Lève HTTPException 403 si pas admin.
    
    Retourne l'User pour audit logging.
    """
    if not current_user.has_role("admin"):
        logger.warning(
            "Tentative d'accès /-/api/* avec rôle insuffisant (user_id=%s, roles=%s)",
            current_user.id,
            current_user.roles,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé aux administrateurs",
        )
    return current_user


def _discover_seedable_apis() -> list[str]:
    """Liste les APIs qui ont un fichier seed.py."""
    apis_dir = Path(__file__).resolve().parent.parent.parent / "apis"
    result = []
    if not apis_dir.is_dir():
        return result
    for api_dir in sorted(apis_dir.iterdir()):
        if api_dir.is_dir() and (api_dir / "seed.py").is_file():
            result.append(api_dir.name)
    return result


def _log_audit(user_id: str, action: str, resource: str, status: str, details: str = "") -> None:
    """Log une action admin pour audit trail.
    
    Format: [AUDIT] [user_id] action resource status details
    """
    timestamp = datetime.utcnow().isoformat()
    msg = f"[AUDIT] [{timestamp}] user={user_id} action={action} resource={resource} status={status}"
    if details:
        msg += f" | {details}"
    logger.info(msg)

@router.get("/docs", include_in_schema=False)
async def admin_docs():
    """Swagger UI pour les routes admin (/-/api/*). Pas d'auth requise pour accéder à la doc."""
    from fastapi.openapi.docs import get_swagger_ui_html
    return get_swagger_ui_html(
        openapi_url="/-/openapi.json",
        title="PAPI Admin — Swagger UI",
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
                "seeds": "GET /-/api/seeds — Liste toutes les APIs seedables",
                "trigger_seed": "POST /-/api/seeds/{name} — Déclenche un seed",
                "reset_tables": "POST /-/api/tables/reset — DROP + CREATE de tables (destructif)",
            },
            "docs": "Voir /-/docs pour la documentation complète",
        },
        "message": "ok",
    }


@router.get("/seeds")
async def list_seeds(current_user: User = Depends(_require_admin)) -> dict[str, Any]:
    """Liste toutes les APIs qui ont un seed disponible.
    
    **Auth:** JWT Bearer (role admin requise)
    **Audit:** Enregistré
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
    """Déclenche le seed d'une API spécifique.
    
    **Auth:** JWT Bearer (role admin requise)
    **Audit:** Action enregistrée avec user_id
    
    **Réponse 200:** Seed déclenché (ou données déjà présentes)
    **Réponse 404:** Seed non disponible pour cette API
    **Réponse 500:** Erreur lors du seed
    """
    available = _discover_seedable_apis()
    if api_name not in available:
        _log_audit(str(current_user.id), "POST", f"/-/api/seeds/{api_name}", "failed", 
                   "API not seedable")
        raise HTTPException(
            status_code=404,
            detail=f"API '{api_name}' n'a pas de seed disponible"
        )

    try:
        seeded = await seed_api(api_name, db)
        if seeded:
            await db.commit()
            _log_audit(str(current_user.id), "POST", f"/-/api/seeds/{api_name}", "success", 
                       "seed executed")
            logger.info("🌱 Seed '%s' déclenché via API admin par user %s", api_name, current_user.id)
            return {
                "data": {
                    "api": api_name,
                    "seeded": True,
                    "message": "Seed exécuté avec succès",
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
                    "message": "Données déjà présentes — aucune action",
                    "timestamp": datetime.utcnow().isoformat(),
                },
                "message": "ok",
            }
    except Exception as e:
        _log_audit(str(current_user.id), "POST", f"/-/api/seeds/{api_name}", "error", 
                   f"exception: {str(e)}")
        logger.exception("Erreur seed '%s' via API admin", api_name)
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors du seed '{api_name}': {str(e)}"
        )


# ---------------------------------------------------------------------------
# Tables — Reset
# ---------------------------------------------------------------------------

class TableResetRequest(BaseModel):
    """Corps de la requête de réinitialisation de tables.

    Deux modes :
    - ``tables`` : liste explicite de noms de tables SQL (ex: ``["eve_events", "eve_rsvps"]``)
    - ``api`` : nom d'une API (ex: ``"eve"``), qui auto-découvre ses tables via son ``models.py``

    Les deux peuvent être combinés. ``seed`` déclenche le seed après la remise à zéro.
    """

    tables: list[str] | None = None
    api: str | None = None
    seed: bool = False


def _discover_api_tables(api_name: str) -> list[str]:
    """Importe les modèles d'une API et retourne les noms de tables SQLModel associées.

    L'import force l'enregistrement des tables dans ``SQLModel.metadata``.
    """
    module_path = f"apis.{api_name}.models"
    try:
        importlib.import_module(module_path)
    except ModuleNotFoundError as e:
        raise ValueError(f"Module '{module_path}' introuvable : {e}") from e

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
    """Réinitialise (DROP + CREATE) les tables spécifiées.

    **⚠️ Destructif — toutes les données des tables concernées seront perdues.**

    **Auth:** JWT Bearer (role admin)
    **Audit:** Action enregistrée

    Deux modes de sélection des tables :
    - `tables` : liste explicite de noms SQL (`["eve_events", "eve_rsvps"]`)
    - `api` : nom d'une API (`"eve"`) → auto-découverte de ses tables via `models.py`

    Les deux peuvent être combinés. `seed` (bool, défaut `false`) relance le seed après reset.

    **Exemple :**
    ```json
    { "api": "eve", "seed": true }
    ```
    """
    if not body.tables and not body.api:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Fournir au moins 'tables' (noms SQL) ou 'api' (nom de l'API)",
        )

    # 1. Résoudre la liste finale de noms de tables
    table_names: set[str] = set(body.tables or [])

    if body.api:
        try:
            discovered = _discover_api_tables(body.api)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

        if not discovered:
            raise HTTPException(
                status_code=404,
                detail=f"Aucune table trouvée pour l'API '{body.api}'"
                       " (les tables doivent porter le préfixe '{body.api}_')",
            )
        table_names.update(discovered)

    # 2. Vérifier que toutes les tables sont connues de SQLModel.metadata
    unknown = table_names - set(SQLModel.metadata.tables.keys())
    if unknown:
        raise HTTPException(
            status_code=404,
            detail=f"Tables inconnues (non enregistrées dans SQLModel.metadata) : {sorted(unknown)}",
        )

    sorted_tables = sorted(table_names)
    _log_audit(
        str(current_user.id), "POST", "/-/api/tables/reset", "started",
        f"tables={sorted_tables} seed={body.seed}",
    )
    logger.warning(
        "🗑️  Réinitialisation tables %s demandée par %s (seed=%s)",
        sorted_tables, current_user.email, body.seed,
    )

    # 3. DROP puis CREATE via le moteur SQLAlchemy (DDL hors session)
    engine = _get_engine()
    dropped: list[str] = []
    created: list[str] = []

    try:
        async with engine.begin() as conn:
            # DROP dans l'ordre inverse (FKs)
            for name in reversed(sorted_tables):
                table = SQLModel.metadata.tables[name]
                await conn.run_sync(lambda sync_conn, t=table: t.drop(sync_conn, checkfirst=True))
                dropped.append(name)
                logger.info("  ✅ DROP %s", name)

            # CREATE dans l'ordre normal
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
        logger.exception("Erreur DDL sur tables %s", sorted_tables)
        raise HTTPException(status_code=500, detail=f"Erreur DDL : {e}")

    # 4. Seed optionnel
    seeded = False
    seed_detail = None
    if body.seed and not body.api:
        seed_detail = "Seed ignoré : 'api' requis pour déclencher un seed automatique"
    elif body.seed and body.api:
        available = _discover_seedable_apis()
        if body.api not in available:
            seed_detail = f"Seed ignoré : pas de seed.py pour l'API '{body.api}'"
            logger.warning(seed_detail)
        else:
            try:
                seeded = await seed_api(body.api, db)
                if seeded:
                    await db.commit()
                    seed_detail = "Seed exécuté avec succès"
                    logger.info("🌱 Seed '%s' exécuté après reset", body.api)
                else:
                    seed_detail = "Seed : aucune donnée insérée (déjà présentes ?)"
            except Exception as e:
                seed_detail = f"Erreur seed : {e}"
                logger.exception("Erreur seed '%s' après reset tables", body.api)

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
        "message": "Tables réinitialisées avec succès",
    }


# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------

@router.post("/backup")
async def trigger_backup(
    current_user: User = Depends(_require_admin),
) -> dict[str, Any]:
    """Déclenche un backup complet de la base de données et l'uploade sur S3.

    **Auth:** JWT Bearer (role admin)
    **Audit:** Action enregistrée

    Lit toutes les tables via SQLAlchemy (pas de pg_dump requis),
    sérialise en JSON, compresse en gzip et uploade sur le bucket S3 configuré.

    **Réponse 200:** Backup créé — retourne clé S3, taille, timestamp
    **Réponse 503:** Backup non configuré (variables S3_* manquantes)
    **Réponse 500:** Erreur lors du backup
    """
    settings = get_settings()
    if not settings.backup_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Backup non configuré — variables S3_ENDPOINT_URL, S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY, S3_BUCKET_NAME requises",
        )

    try:
        engine = _get_engine()
        result = await backup_and_upload(engine, settings)
        _log_audit(
            str(current_user.id), "POST", "/-/api/backup", "success",
            f"key={result['key']} rows={result['rows']} size={result['size_bytes']}",
        )
        return {"data": result, "message": "Backup créé avec succès"}
    except Exception as e:
        _log_audit(str(current_user.id), "POST", "/-/api/backup", "error", str(e))
        logger.exception("Erreur backup")
        raise HTTPException(status_code=500, detail=f"Erreur backup : {e}")


@router.get("/backups")
async def list_available_backups(
    current_user: User = Depends(_require_admin),
) -> dict[str, Any]:
    """Liste les backups disponibles dans le bucket S3.

    **Auth:** JWT Bearer (role admin)

    Retourne la liste triée du plus récent au plus ancien,
    avec clé S3, taille en octets et date de dernière modification.
    """
    settings = get_settings()
    if not settings.backup_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Backup non configuré — variables S3_* manquantes",
        )

    try:
        backups = await list_backups(settings)
        return {
            "data": {"backups": backups, "count": len(backups)},
            "message": "ok",
        }
    except Exception as e:
        logger.exception("Erreur listing backups")
        raise HTTPException(status_code=500, detail=f"Erreur listing : {e}")
