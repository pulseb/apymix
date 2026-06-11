"""Chargement et modélisation de la configuration amx.yaml des projets apymix.

Chaque projet (API ou frontend statique) embarque un fichier ``amx.yaml`` à sa
racine. Ce module fournit :

- ``AmxConfig`` : dataclass typée du contenu YAML.
- ``load_amx_config(package_file)`` : charge ``amx.yaml`` depuis la racine du
  projet contenant le fichier Python appelant.
- ``make_tablename(prefix, name)`` : construit le nom de table DB préfixé.

Usage dans un module API ::

    # eve_api/__init__.py
    from apymix.manifest import load_amx_config, make_tablename
    _amx = load_amx_config(__file__)
    TABLE_PREFIX = _amx.table_prefix  # "eve_"

    # eve_api/models.py
    from eve_api import TABLE_PREFIX
    from apymix.manifest import make_tablename

    class Event(SQLModel, table=True):
        __tablename__ = make_tablename(TABLE_PREFIX, "events")  # "eve_events"
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml

logger = logging.getLogger(__name__)


@dataclass
class AmxConfig:
    """Configuration d'un projet apymix lue depuis amx.yaml."""

    name: str = ""
    """Nom affiché du projet (ex: 'Eve-API', 'Eve')."""

    route: str = "/"
    """Préfixe de montage dans l'URL (ex: '/eve')."""

    type: Literal["api", "static"] = "api"
    """Type de projet : 'api' (FastAPI sub-app) ou 'static' (SPA compilée)."""

    # --- API only ---
    module: str = ""
    """Nom du module Python à importer (ex: 'eve_api'). Obligatoire pour type=api."""

    table_prefix: str = ""
    """Préfixe des tables SQL de ce projet (ex: 'eve_'). Convention : toujours avec _ final."""

    # --- Static only ---
    dist_dir: str = "dist"
    """Sous-dossier contenant le build statique (ex: 'dist', 'dist/pwa')."""

    # --- Commun ---
    version: str = "0.0.0"
    description: str = ""
    enabled: bool = True

    # Chemin vers la racine du projet (rempli par load_amx_config)
    project_dir: Path = field(default_factory=Path)


def load_amx_config(package_file: str) -> AmxConfig:
    """Charge amx.yaml depuis la racine du projet contenant ``package_file``.

    Remonte depuis le fichier appelant jusqu'à trouver ``amx.yaml``.
    Si absent, retourne un AmxConfig vide (fail-safe).

    Args:
        package_file: ``__file__`` du module appelant (ex: ``eve_api/__init__.py``).

    Returns:
        AmxConfig peuplé depuis le YAML, ou config vide si non trouvé.
    """
    start = Path(package_file).resolve().parent
    # Chercher amx.yaml en remontant (max 3 niveaux au-dessus du module)
    candidate = start
    for _ in range(4):
        amx_path = candidate / "amx.yaml"
        if amx_path.exists():
            try:
                with open(amx_path) as f:
                    data = yaml.safe_load(f) or {}
                config = AmxConfig(project_dir=candidate, **{k: v for k, v in data.items() if k in AmxConfig.__dataclass_fields__})
                logger.debug("amx.yaml chargé depuis %s : %s", amx_path, config.name)
                return config
            except Exception:
                logger.exception("Erreur lecture amx.yaml : %s", amx_path)
                return AmxConfig(project_dir=candidate)
        candidate = candidate.parent

    logger.debug("amx.yaml introuvable depuis %s", start)
    return AmxConfig(project_dir=start)


def make_tablename(prefix: str, name: str) -> str:
    """Construit le nom de table SQL préfixé.

    Args:
        prefix: Préfixe du projet (ex: 'eve_', 'kif_').
        name: Nom court de la table (ex: 'events', 'rsvps').

    Returns:
        Nom de table complet (ex: 'eve_events').

    Example::

        class Event(SQLModel, table=True):
            __tablename__ = make_tablename(TABLE_PREFIX, "events")
    """
    return f"{prefix}{name}"
