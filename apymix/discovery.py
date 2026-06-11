"""Découverte automatique des projets apymix via amx.yaml.

Chaque projet (API ou frontend statique) à la racine du workspace doit
embarquer un fichier ``amx.yaml``. Apymix scanne tous les sous-dossiers
du workspace pour trouver ces fichiers et monte les projets correspondants.
"""

import importlib
import logging
from pathlib import Path

import yaml
from fastapi import FastAPI

logger = logging.getLogger(__name__)


def _load_amx(amx_path: Path) -> dict:
    """Charge un amx.yaml s'il existe, sinon retourne un dict vide."""
    if not amx_path.exists():
        return {}
    with open(amx_path) as f:
        return yaml.safe_load(f) or {}


def _add_root_route(sub_app: FastAPI, config: dict, folder_name: str) -> None:
    """Ajoute automatiquement une route GET / sur la sub-app avec les infos du amx.yaml."""
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


def discover_projects(workspace_root: Path) -> tuple[list[tuple[str, FastAPI, dict]], list[tuple[str, Path, dict]]]:
    """Scanne le workspace pour tous les projets déclarés via amx.yaml.

    Retourne deux listes :
    - ``api_entries`` : (route, FastAPI app, config dict) pour les APIs
    - ``front_entries`` : (route, chemin dist/, config dict) pour les frontends

    Sont ignorés :
    - Les dossiers commençant par '.' ou '_'
    - Le dossier 'apymix' lui-même (le framework ne se monte pas)
    - Les dossiers sans amx.yaml
    - Les projets avec ``enabled: false``
    """
    api_entries: list[tuple[str, FastAPI, dict]] = []
    front_entries: list[tuple[str, Path, dict]] = []

    if not workspace_root.exists():
        logger.warning("Workspace root introuvable : %s", workspace_root)
        return api_entries, front_entries

    for project_dir in sorted(workspace_root.iterdir()):
        if not project_dir.is_dir():
            continue
        if project_dir.name.startswith(".") or project_dir.name.startswith("_"):
            continue
        if project_dir.name == "apymix":
            continue  # le framework lui-même

        amx_path = project_dir / "amx.yaml"
        if not amx_path.exists():
            continue

        config = _load_amx(amx_path)
        if not config.get("enabled", True):
            logger.info("Projet ignoré (disabled) : %s", project_dir.name)
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
                # Dériver le nom du module depuis le nom du dossier (eve-api → eve_api)
                module_name = project_dir.name.replace("-", "_")
                config["module"] = module_name

            try:
                module = importlib.import_module(f"{module_name}.app")
                sub_app = getattr(module, "app", None)
            except Exception:
                logger.exception("Erreur lors du chargement de %s.app", module_name)
                continue

            if not isinstance(sub_app, FastAPI):
                logger.warning("%s.app ne contient pas d'instance FastAPI nommée 'app'", module_name)
                continue

            _add_root_route(sub_app, config, project_dir.name)
            logger.info("API découverte : %s → %s (module: %s)", project_dir.name, route, module_name)
            api_entries.append((route, sub_app, config))

        elif project_type == "static":
            dist_name = config.get("dist_dir", "dist")
            dist_dir = project_dir / dist_name
            logger.info("Frontend découvert : %s → %s", project_dir.name, route)
            front_entries.append((route, dist_dir, config))

        else:
            logger.warning("Type inconnu '%s' dans %s/amx.yaml — ignoré", project_type, project_dir.name)

    return api_entries, front_entries


def discover_api_admin_views(workspace_root: Path) -> list:
    """Scanne les projets API pour collecter leurs ModelView SQLAdmin.

    Convention : chaque module API peut exposer une liste ``admin_views``
    contenant les classes ModelView à enregistrer dans SQLAdmin.
    """
    from sqladmin import ModelView

    views: list[type[ModelView]] = []

    for project_dir in sorted(workspace_root.iterdir()):
        if not project_dir.is_dir() or project_dir.name.startswith((".", "_")):
            continue
        if project_dir.name == "apymix":
            continue

        amx_path = project_dir / "amx.yaml"
        if not amx_path.exists():
            continue

        config = _load_amx(amx_path)
        if config.get("type") != "api" or not config.get("enabled", True):
            continue

        module_name = config.get("module") or project_dir.name.replace("-", "_")

        try:
            module = importlib.import_module(f"{module_name}.admin")
            api_views = getattr(module, "admin_views", [])
            views.extend(api_views)
            logger.info("Admin views découvertes : %s → %d vue(s)", module_name, len(api_views))
        except ModuleNotFoundError:
            pass  # pas de admin.py — normal
        except Exception:
            logger.exception("Erreur lors du chargement de %s.admin", module_name)

    return views


def import_all_api_models(workspace_root: Path | None = None) -> None:
    """Importe dynamiquement tous les modules models.py des projets API.

    Nécessaire pour que ``SQLModel.metadata.create_all()`` connaisse les
    tables de toutes les APIs (auto-discovery, sans import statique).
    """
    if workspace_root is None:
        # Remonter depuis apymix/ jusqu'à la racine du workspace
        workspace_root = Path(__file__).resolve().parent.parent.parent

    for project_dir in sorted(workspace_root.iterdir()):
        if not project_dir.is_dir() or project_dir.name.startswith((".", "_")):
            continue
        if project_dir.name == "apymix":
            continue

        amx_path = project_dir / "amx.yaml"
        if not amx_path.exists():
            continue

        config = _load_amx(amx_path)
        if config.get("type") != "api" or not config.get("enabled", True):
            continue

        module_name = config.get("module") or project_dir.name.replace("-", "_")

        try:
            importlib.import_module(f"{module_name}.models")
            logger.debug("Modèles importés : %s.models", module_name)
        except ModuleNotFoundError:
            pass  # pas de models.py — normal (ex: aeria)
        except Exception:
            logger.exception("Erreur import %s.models — tables absentes de SQLModel.metadata", module_name)


# ---------------------------------------------------------------------------
# Compatibilité — fonctions legacy (utilisées par les scripts lors de la transition)
# ---------------------------------------------------------------------------

def _get_workspace_root() -> Path:
    """Déduit la racine du workspace depuis l'emplacement du module apymix."""
    return Path(__file__).resolve().parent.parent.parent

