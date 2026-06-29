"""Automatic discovery of apymix projects via amx.yaml.

Each project (API or static frontend) at the root of the workspace must
ship an ``amx.yaml`` file. Apymix scans all subfolders of the workspace
to find these files and mounts the corresponding projects.
"""

import importlib
import logging
import os
from pathlib import Path

import yaml
from fastapi import FastAPI

logger = logging.getLogger(__name__)


def _find_workspace_root() -> Path:
    """Determine the Apymix workspace root.

    Resolution order:
    1. The ``APYMIX_WORKSPACE`` environment variable (explicit path).
       If the path is invalid, log a warning and fall back to CWD.
    2. Otherwise, CWD (``Path.cwd()``).

    The project scan then runs over the direct children of the workspace
    root (see ``_iter_project_dirs``): for each ``<project>/`` subfolder,
    we look for ``<project>/amx.yaml``.

    Returns:
        Absolute path to the workspace root.
    """
    # 1. Environment variable (explicit override)
    env_root = os.environ.get("APYMIX_WORKSPACE")
    if env_root:
        root = Path(env_root).expanduser().resolve()
        if root.is_dir():
            logger.debug("Workspace root from APYMIX_WORKSPACE: %s", root)
            return root
        logger.warning("APYMIX_WORKSPACE=%s not found, falling back to CWD", env_root)

    # 2. Default to CWD
    cwd = Path.cwd().resolve()
    logger.debug("Workspace root = CWD: %s", cwd)
    return cwd


def _load_amx(amx_path: Path) -> dict:
    """Load an amx.yaml if it exists, otherwise return an empty dict."""
    if not amx_path.exists():
        return {}
    with open(amx_path) as f:
        return yaml.safe_load(f) or {}


def _add_root_route(sub_app: FastAPI, config: dict, folder_name: str) -> None:
    """Automatically add a GET / route on the sub-app with the amx.yaml info."""
    name = config.get("name", folder_name)
    version = config.get("version", "0.0.0")
    description = config.get("description", "")

    for route in sub_app.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", set())
        if path == "/" and "GET" in methods:
            return

    @sub_app.get("/", tags=["info"])
    async def api_root():
        return {"name": name, "version": version, "description": description}


def _iter_project_dirs(workspace_root: Path) -> list[Path]:
    """List the project directories to scan in a workspace.

    Two layouts are supported:
    1. **Monorepo**: ``workspace/`` contains several sub-projects
       (``workspace/eve-api/amx.yaml``, ``workspace/kif-api/amx.yaml``, …)
    2. **Single project**: ``workspace/`` is itself a project
       (``workspace/amx.yaml``)

    The following are ignored:
    - Hidden/private directories (``.foo``, ``_bar``)
    - The ``apymix`` directory (the framework does not mount itself)
    - Directories without an ``amx.yaml`` file
    """
    if not workspace_root.exists() or not workspace_root.is_dir():
        return []

    # Case 1: amx.yaml at the root → the workspace is the project itself
    if (workspace_root / "amx.yaml").is_file():
        return [workspace_root]

    # Case 2: scan direct subfolders
    dirs: list[Path] = []
    for project_dir in sorted(workspace_root.iterdir()):
        if not project_dir.is_dir():
            continue
        if project_dir.name.startswith(".") or project_dir.name.startswith("_"):
            continue
        if project_dir.name == "apymix":
            continue
        if not (project_dir / "amx.yaml").is_file():
            continue
        dirs.append(project_dir)

    return dirs


def discover_projects(workspace_root: Path) -> tuple[list[tuple[str, FastAPI, dict]], list[tuple[str, Path, dict]]]:
    """Scan the workspace for all projects declared via amx.yaml.

    Returns two lists:
    - ``api_entries``: (route, FastAPI app, config dict) for APIs
    - ``front_entries``: (route, dist/ path, config dict) for frontends

    The following are ignored:
    - Directories starting with '.' or '_'
    - The 'apymix' directory itself (the framework does not mount itself)
    - Directories without an amx.yaml
    - Projects with ``enabled: false``
    """
    api_entries: list[tuple[str, FastAPI, dict]] = []
    front_entries: list[tuple[str, Path, dict]] = []

    if not workspace_root.exists():
        logger.warning("Workspace root not found: %s", workspace_root)
        return api_entries, front_entries

    for project_dir in _iter_project_dirs(workspace_root):
        amx_path = project_dir / "amx.yaml"

        config = _load_amx(amx_path)
        if not config.get("enabled", True):
            logger.info("Project ignored (disabled): %s", project_dir.name)
            continue

        project_type = config.get("type", "api")
        route = config.get("route", f"/{project_dir.name}")
        config.setdefault("name", project_dir.name)
        config["route"] = route
        config.setdefault("version", "0.0.0")
        config.setdefault("description", "")

        if project_type == "api":
            module_name = config.get("module")
            if not module_name:
                # Derive the module name from the directory name (eve-api → eve_api)
                module_name = project_dir.name.replace("-", "_")
                config["module"] = module_name

            try:
                module = importlib.import_module(f"{module_name}.app")
                sub_app = getattr(module, "app", None)
            except Exception:
                logger.exception("Error loading %s.app", module_name)
                continue

            if not isinstance(sub_app, FastAPI):
                logger.warning("%s.app does not contain a FastAPI instance named 'app'", module_name)
                continue

            _add_root_route(sub_app, config, project_dir.name)
            logger.info("API discovered: %s → %s (module: %s)", project_dir.name, route, module_name)
            api_entries.append((route, sub_app, config))

        elif project_type == "static":
            dist_name = config.get("dist_dir", "dist")
            dist_dir = project_dir / dist_name
            logger.info("Frontend discovered: %s → %s", project_dir.name, route)
            front_entries.append((route, dist_dir, config))

        else:
            logger.warning("Unknown type '%s' in %s/amx.yaml — ignored", project_type, project_dir.name)

    return api_entries, front_entries


def discover_api_admin_views(workspace_root: Path) -> list:
    """Scan API projects to collect their SQLAdmin ModelView classes.

    Convention: each API module may expose an ``admin_views`` list
    containing the ModelView classes to register in SQLAdmin.
    """
    from sqladmin import ModelView

    views: list[type[ModelView]] = []

    for project_dir in _iter_project_dirs(workspace_root):
        config = _load_amx(project_dir / "amx.yaml")
        if config.get("type") != "api" or not config.get("enabled", True):
            continue

        module_name = config.get("module") or project_dir.name.replace("-", "_")

        try:
            module = importlib.import_module(f"{module_name}.admin")
            api_views = getattr(module, "admin_views", [])
            views.extend(api_views)
            logger.info("Admin views discovered: %s → %d view(s)", module_name, len(api_views))
        except ModuleNotFoundError:
            pass  # no admin.py — normal
        except Exception:
            logger.exception("Error loading %s.admin", module_name)

    return views


def import_all_api_models(workspace_root: Path | None = None) -> None:
    """Dynamically import all models.py modules of the API projects.

    Required so that ``SQLModel.metadata.create_all()`` knows the
    tables of all APIs (auto-discovery, without static imports).
    """
    if workspace_root is None:
        # Walk up from apymix/ to the workspace root
        workspace_root = _find_workspace_root()

    for project_dir in _iter_project_dirs(workspace_root):
        config = _load_amx(project_dir / "amx.yaml")
        if config.get("type") != "api" or not config.get("enabled", True):
            continue

        module_name = config.get("module") or project_dir.name.replace("-", "_")

        try:
            importlib.import_module(f"{module_name}.models")
            logger.debug("Models imported: %s.models", module_name)
        except ModuleNotFoundError:
            pass  # no models.py — normal (e.g. aeria)
        except Exception:
            logger.exception("Error importing %s.models — tables missing from SQLModel.metadata", module_name)


# ---------------------------------------------------------------------------
# Compatibility — legacy function, kept for scripts
# ---------------------------------------------------------------------------

def _get_workspace_root() -> Path:
    """Deduce the workspace root (backward-compatible alias of ``_find_workspace_root``)."""
    return _find_workspace_root()

