"""App factory PulseApps — main entry point."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

import pyfiglet
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from apymix.apps.models import AppStatus
from apymix.spa_static import SPAStaticFiles
from apymix.apps.registry import sync_app_registry
from apymix.config import get_settings
from apymix.db import init_db
from apymix.db.session import _get_engine, get_db
from apymix.discovery import discover_projects
from apymix.auth.routes import router as auth_router
from apymix.auth.security import get_current_user
from apymix.auth.jwt import init_jwt_secret
from apymix.admin import setup_admin
from apymix.admin.api import router as admin_api_router
from apymix.db.config_store import get_or_create_jwt_secret, get_verbose_errors

# Prefix for all internal Apymix routes (admin, auth, docs, health…)
PAPI_PREFIX = "/-"
# Prefix for business APIs (e.g. /api/eve)
API_PREFIX = "/api"

logger = logging.getLogger(__name__)

# Noisy library loggers — silenced even when LOG_LEVEL=DEBUG.
# To re-enable a specific logger, comment out or remove its entry.
_QUIET_LOGGERS = [
    "aiosqlite",
    "sqlalchemy.engine",
    "sqlalchemy.engine.base.Engine",
    "sqlalchemy.pool",
    "sqlalchemy.dialects",
    "httpx",
    "httpcore",
]

# Jinja2 templates for Apymix system pages
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

DB_CONNECT_RETRIES = 30
DB_CONNECT_DELAY = 2  # seconds


async def _wait_for_db() -> None:
    """Wait until the database is reachable (retry with simple backoff)."""
    from sqlalchemy import text

    engine = _get_engine()
    for attempt in range(1, DB_CONNECT_RETRIES + 1):
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            logger.info("Database ready (attempt %d)", attempt)
            return
        except Exception as exc:
            if attempt == DB_CONNECT_RETRIES:
                logger.error("Database unreachable after %d attempts", DB_CONNECT_RETRIES)
                raise
            logger.warning("Waiting for DB (%d/%d): %s", attempt, DB_CONNECT_RETRIES, exc)
            await __import__("asyncio").sleep(DB_CONNECT_DELAY)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: init DB, seed data, sync app registry."""
    settings = get_settings()

    # Wait for DB to be ready (useful in pod: postgres may start in parallel)
    await _wait_for_db()

    # Import all API models so SQLModel.metadata knows every table before create_all
    from apymix.discovery import import_all_api_models
    import_all_api_models()

    # Create tables if they don't exist (dev + first prod startup)
    await init_db()
    logger.info("Database initialized")

    # Load or generate JWT secret (env var > DB)
    async with AsyncSession(_get_engine(), expire_on_commit=False) as session:
        jwt_secret = await get_or_create_jwt_secret(session)
        verbose_errors = await get_verbose_errors(session)
    init_jwt_secret(jwt_secret)
    app.state.verbose_errors = verbose_errors
    logger.info("JWT secret ready")

    from apymix.scripts.db_init import reset_and_seed, seed_initial_data

    if settings.force_seed:
        # --seed mode: full reset + reseed (dev/CI only)
        logger.warning("FORCE_SEED enabled — resetting database")
        await reset_and_seed()
    else:
        # Auto-seed if database is empty
        await seed_initial_data()

    # Sync app registry
    await _sync_registry(app)

    yield


async def _sync_registry(app: FastAPI) -> None:
    """Sync discovered apps with the amx_apps table and mount active ones.

    Called during lifespan (after init_db). Only active apps are mounted.
    """
    # Workspace root resolved by discovery._find_workspace_root() :
    # APYMIX_WORKSPACE env > scan CWD > mode monorepo > fallback CWD
    from apymix.discovery import _find_workspace_root
    workspace_root = _find_workspace_root()

    # Discover all projects via amx.yaml
    api_entries, front_entries = discover_projects(workspace_root)

    # Build list of discovered apps (APIs + Fronts)
    discovered: list[dict] = []

    for route, sub_app, config in api_entries:
        discovered.append({
            "name": config["name"],
            "app_type": "api",
            "prefix": f"{API_PREFIX}{route}",  # /api/eve
            "description": config.get("description", ""),
            "version": config.get("version", "0.0.0"),
        })

    for route, dist_dir, config in front_entries:
        discovered.append({
            "name": config["name"],
            "app_type": "front",
            "prefix": route,  # /eve (no extra prefix)
            "description": config.get("description", ""),
            "version": config.get("version", "0.0.0"),
        })

    # Sync with DB
    engine = _get_engine()
    async with AsyncSession(engine, expire_on_commit=False) as session:
        registry = await sync_app_registry(session, discovered)

    # Mount active APIs under /api/{route}
    for route, sub_app, config in api_entries:
        name = config["name"]
        mount_prefix = f"{API_PREFIX}{route}"
        info = registry.get(name, {"status": AppStatus.unavailable.value, "docs_enabled": True})
        if info["status"] == AppStatus.active.value:
            # Disable docs if docs_enabled is False
            if not info.get("docs_enabled", True):
                sub_app.docs_url = None
                sub_app.openapi_url = None
                sub_app.redoc_url = None
            app.mount(mount_prefix, sub_app)
            logger.info("API mounted: %s → %s (docs=%s)", name, mount_prefix, info.get("docs_enabled", True))
        else:
            logger.info("API '%s' not mounted (status=%s)", name, info["status"])

    # Mount active frontends
    settings = get_settings()
    for route, dist_dir, config in front_entries:
        name = config["name"]
        info = registry.get(name, {"status": AppStatus.unavailable.value})
        if info["status"] != AppStatus.active.value:
            logger.info("Frontend '%s' not mounted (status=%s)", name, info["status"])
            continue

        dev_port = config.get("dev_port")
        if settings.is_dev and dev_port:
            # Dev mode: proxy to quasar dev server (HMR)
            from apymix.dev_proxy import DevProxy

            proxy = DevProxy(target=f"http://localhost:{dev_port}", prefix=route)
            app.mount(route, proxy, name=f"front-{name}")
            logger.info("Frontend mounted (dev proxy): %s → localhost:%s", name, dev_port)
        elif dist_dir.exists():
            app.mount(route, SPAStaticFiles(directory=str(dist_dir), html=True), name=f"front-{name}")
            logger.info("Frontend mounted: %s → %s", name, route)
        else:
            logger.debug("Frontend '%s' is active but dist/ not found — skipping", name)


def _generate_ascii_art(text: str) -> str:
    """Generate ASCII art from text."""
    try:
        return pyfiglet.figlet_format(text, font="ansi_shadow").strip()
    except Exception as e:
        logger.warning("ASCII art generation failed: %s. Using default font.", e)
        try:
            # Fallback to default font
            return pyfiglet.figlet_format(text).strip()
        except Exception as e2:
            logger.error("ASCII art fallback failed: %s. Returning plain text.", e2)
            return text


def _build_root_page_data(name: str, version: str, description: str) -> dict:
    """Build data for the home page."""
    ascii_art = _generate_ascii_art(name)
    return {"name": name, "version": version, "description": description, "ascii_art": ascii_art}


def _build_apps_page_data(apps: list, version: str) -> dict:
    """Build data for the apps monitoring page."""
    STATUS_BADGE = {
        "active": ("🟢", "#22c55e"),
        "disabled": ("🟡", "#eab308"),
        "unavailable": ("🔴", "#ef4444"),
    }

    apps_data = []
    for a in apps:
        icon, color = STATUS_BADGE.get(a.status, ("⚪", "#64748b"))
        type_label = "API" if a.app_type == "api" else "Front"
        type_bg = "#1e3a5f" if a.app_type == "api" else "#3b1f5e"
        link = (
            f'<a href="{a.prefix}">{a.prefix}</a>'
            if a.status == "active"
            else f'<span class="muted">{a.prefix}</span>'
        )
        docs = ""
        if a.app_type == "api" and a.status == "active":
            docs_url = f"{a.prefix}/docs"
            docs = (
                f'<a href="{docs_url}" class="docs-link">docs</a>'
                if a.docs_enabled
                else '<span class="muted">off</span>'
            )
        seen = a.last_seen_at.strftime("%Y-%m-%d %H:%M") if a.last_seen_at else "—"
        apps_data.append({
            "type_label": type_label,
            "type_bg": type_bg,
            "name": a.name,
            "description": a.description,
            "version": a.version,
            "link": link,
            "status": a.status,
            "status_icon": icon,
            "status_color": color,
            "docs": docs,
            "last_seen": seen,
        })

    total = len(apps)
    active = sum(1 for a in apps if a.status == "active")

    return {
        "apps": apps_data,
        "version": version,
        "total": total,
        "active": active,
    }


def create_app() -> FastAPI:
    """Factory: create and configure the Apymix application."""
    settings = get_settings()

    # Logging
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )
    for _noisy_logger in _QUIET_LOGGERS:
        logging.getLogger(_noisy_logger).setLevel(logging.WARNING)

    # Load root metadata from workspace root pyproject.toml
    import tomllib
    # apymix/ project is at workspace_root/apymix/ — root pyproject is one level up
    project_root = Path(__file__).resolve().parent.parent
    workspace_root = project_root.parent
    pyproject_path = workspace_root / "pyproject.toml"
    papi_name = "Apymix"
    papi_version = "0.0.0"
    papi_description = "API Python Mix"
    
    if pyproject_path.exists():
        with open(pyproject_path, "rb") as f:
            pyproject = tomllib.load(f)
            project = pyproject.get("project", {})
            papi_name = project.get("name", papi_name)
            papi_version = project.get("version", papi_version)
            papi_description = project.get("description", papi_description)

    logger.info("Starting %s v%s — %s", papi_name, papi_version, papi_description)

    app = FastAPI(
        title=papi_name,
        description=papi_description,
        version=papi_version,
        lifespan=lifespan,
        docs_url=f"{PAPI_PREFIX}/docs",
        openapi_url=f"{PAPI_PREFIX}/openapi.json",
        redoc_url=f"{PAPI_PREFIX}/redoc",
        swagger_ui_oauth2_redirect_url=f"{PAPI_PREFIX}/docs/oauth2-redirect",
    )

    # Inject OAuth2 password flow in OpenAPI schema → bouton "Authorize" Swagger avec formulaire email/password
    _orig_openapi = app.openapi

    def _custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        schema = _orig_openapi()
        schema.setdefault("components", {}).setdefault("securitySchemes", {})
        schema["components"]["securitySchemes"]["OAuth2PasswordBearer"] = {
            "type": "oauth2",
            "flows": {
                "password": {
                    "tokenUrl": f"{PAPI_PREFIX}/auth/token",
                    "scopes": {},
                }
            },
        }
        return schema

    app.openapi = _custom_openapi

    # --- Middleware ---
    # ProxyHeaders: trust X-Forwarded-* from local reverse proxy only
    # Restricted to local IPs to prevent header spoofing
    app.add_middleware(
        ProxyHeadersMiddleware,
        trusted_hosts=["127.0.0.1", "localhost", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"],
    )

    # --- Redirect rules (papi_redirects table, evaluated first) ---
    from apymix.middleware.redirect import RedirectMiddleware
    app.add_middleware(RedirectMiddleware, db_url=settings.database_url)

    # --- VHost routing (host → frontend) ---
    vhost_map = settings.vhost_map_dict
    if vhost_map:
        from apymix.middleware.vhost import VHostMiddleware
        app.add_middleware(VHostMiddleware, vhost_map=vhost_map)
        logger.info("VHost routing: %s", vhost_map)

    _cors_origins = [o for o in settings.cors_origins_list if "*" not in o]
    _cors_regex = settings.cors_origins_regex
    logger.info(
        "[CORS] Origines autorisées : %s%s",
        _cors_origins,
        f"  +regex: {_cors_regex}" if _cors_regex else "",
    )

    from apymix.middleware.cors_log import CORSLogMiddleware
    app.add_middleware(CORSLogMiddleware, allow_origins=_cors_origins, allow_origin_regex=_cors_regex)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_origin_regex=_cors_regex,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Global rate limiting (SlowAPI) ---
    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=["200/minute"],  # 200 req/min per IP
        storage_uri="memory://",  # In-memory (OK for dev; use Redis in prod)
    )
    app.state.limiter = limiter
    app.add_exception_handler(
        RateLimitExceeded,
        lambda request, exc: JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded", "message": "Too many requests"},
        ),
    )

    # --- Global 500 handler — return JSON with traceback detail ---
    import traceback

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request, exc):
        logger.error("Unhandled exception: %s", exc, exc_info=True)
        content = {"detail": f"{type(exc).__name__}: {exc}"}
        verbose = settings.is_dev or getattr(app.state, "verbose_errors", False)
        if verbose:
            content["traceback"] = traceback.format_exc()
        return JSONResponse(status_code=500, content=content)

    # --- Health check ---
    @app.get(f"{PAPI_PREFIX}/health", tags=["system"])
    async def health():
        """Check that the app and database are operational."""
        from sqlalchemy import text
        from apymix.db.session import get_db_info

        db_info = get_db_info()
        db_ok = False
        db_error = None
        try:
            engine = _get_engine()
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            db_ok = True
        except Exception as e:
            db_error = str(e)

        result = {
            "status": "healthy" if db_ok else "degraded",
            "version": papi_version,
            "db": {
                "status": "ok" if db_ok else "error",
                "backend": db_info["backend"],
                "fallback": db_info["fallback"],
            },
        }
        if db_error:
            result["db"]["error"] = db_error
        if db_info["fallback"]:
            result["db"]["warning"] = "DATABASE_URL missing or invalid — data will not be persisted"

        status_code = 200 if db_ok else 503
        return JSONResponse(content=result, status_code=status_code)

    @app.get(f"{PAPI_PREFIX}/status", tags=["system"])
    async def status_detailed(current_user=Depends(get_current_user)):
        """Detailed status (authenticated) — DB, config, env."""
        from apymix.db.session import get_db_info

        db_info = get_db_info()
        return {
            "version": papi_version,
            "env": settings.env,
            "debug": settings.debug,
            "db": db_info,
        }

    # --- Root: minimal message (avoid exposing internals) ---
    @app.get("/", tags=["system"])
    async def root():
        return {"message": f"{papi_name} is running"}

    # --- Internal dashboard (ASCII art + links) ---
    @app.get(f"{PAPI_PREFIX}/", include_in_schema=False)
    async def dashboard(request: Request, db: AsyncSession = Depends(get_db)):
        from sqlmodel import select
        from apymix.apps.models import AppEntry, AppStatus

        # Fetch active frontends to display buttons
        result = await db.execute(
            select(AppEntry)
            .where(AppEntry.app_type == "front")
            .where(AppEntry.status == AppStatus.active.value)
            .order_by(AppEntry.name)
        )
        active_fronts = result.scalars().all()

        data = _build_root_page_data(papi_name, papi_version, papi_description)
        data["fronts"] = [
            {
                "name": f.name,
                "prefix": f.prefix,
                "icon": f"{f.prefix}/icons/icon-128x128.png" if f.prefix else None,
            }
            for f in active_fronts
        ]
        return templates.TemplateResponse(request, "root_page.html", data)

    # --- App registry (monitoring) ---
    @app.get(f"{PAPI_PREFIX}/apps", tags=["system"])
    async def list_apps(request: Request, db: AsyncSession = Depends(get_db)):
        """List all registered applications with their status."""
        from sqlmodel import select
        from apymix.apps.models import AppEntry

        result = await db.execute(select(AppEntry).order_by(AppEntry.name))
        apps = result.scalars().all()

        accept = request.headers.get("accept", "")
        if "text/html" in accept:
            data = _build_apps_page_data(apps, papi_version)
            return templates.TemplateResponse(request, "apps_page.html", data)

        return {
            "total": len(apps),
            "apis": [a for a in apps if a.app_type == "api"],
            "fronts": [a for a in apps if a.app_type == "front"],
        }

    # --- Auth ---
    app.include_router(auth_router, prefix=PAPI_PREFIX)

    # --- Admin API (JSON, protected) — visible dans /-/docs sous le tag "Admin" ---

    app.include_router(admin_api_router, prefix=PAPI_PREFIX)

    # --- Back-office (SQLAdmin UI) ---
    setup_admin(app, _get_engine(), base_url=f"{PAPI_PREFIX}/padmin")

    # --- APIs and Fronts mounted dynamically during lifespan (_sync_registry) ---

    logger.info("PulseApps started (env=%s)", settings.env)
    return app


# Instance used by uvicorn (e.g. uvicorn papi.app:app)
app = create_app()
