"""Loading and modeling of the amx.yaml configuration for apymix projects.

Each project (API or static frontend) ships an ``amx.yaml`` file at its root.
This module provides:

- ``AmxConfig``: typed dataclass for the YAML contents.
- ``load_amx_config(package_file)``: loads ``amx.yaml`` from the root of the
  project containing the calling Python file.
- ``make_tablename(prefix, name)``: builds the prefixed DB table name.

Usage in an API module::

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
    """Configuration of an apymix project read from amx.yaml."""

    name: str = ""
    """Display name of the project (e.g. 'Eve-API', 'Eve')."""

    route: str = "/"
    """Mount prefix in the URL (e.g. '/eve')."""

    type: Literal["api", "static"] = "api"
    """Project type: 'api' (FastAPI sub-app) or 'static' (built SPA)."""

    # --- API only ---
    module: str = ""
    """Python module name to import (e.g. 'eve_api'). Required for type=api."""

    table_prefix: str = ""
    """SQL table prefix for this project (e.g. 'eve_'). Convention: always ends with _."""

    # --- Static only ---
    dist_dir: str = "dist"
    """Subfolder containing the static build (e.g. 'dist', 'dist/pwa')."""

    # --- Common ---
    version: str = "0.0.0"
    description: str = ""
    enabled: bool = True

    # Path to the project root (populated by load_amx_config)
    project_dir: Path = field(default_factory=Path)


def load_amx_config(package_file: str) -> AmxConfig:
    """Load amx.yaml from the root of the project containing ``package_file``.

    Walks up from the calling file until ``amx.yaml`` is found.
    If not found, returns an empty AmxConfig (fail-safe).

    Args:
        package_file: ``__file__`` of the calling module (e.g. ``eve_api/__init__.py``).

    Returns:
        AmxConfig populated from the YAML, or an empty config if not found.
    """
    start = Path(package_file).resolve().parent
    # Look for amx.yaml by walking up (max 3 levels above the module)
    candidate = start
    for _ in range(4):
        amx_path = candidate / "amx.yaml"
        if amx_path.exists():
            try:
                with open(amx_path) as f:
                    data = yaml.safe_load(f) or {}
                config = AmxConfig(project_dir=candidate, **{k: v for k, v in data.items() if k in AmxConfig.__dataclass_fields__})
                logger.debug("amx.yaml loaded from %s : %s", amx_path, config.name)
                return config
            except Exception:
                logger.exception("Error reading amx.yaml: %s", amx_path)
                return AmxConfig(project_dir=candidate)
        candidate = candidate.parent

    logger.debug("amx.yaml not found from %s", start)
    return AmxConfig(project_dir=start)


def make_tablename(prefix: str, name: str) -> str:
    """Build the prefixed SQL table name.

    Args:
        prefix: Project prefix (e.g. 'eve_', 'kif_').
        name: Short table name (e.g. 'events', 'rsvps').

    Returns:
        Full table name (e.g. 'eve_events').

    Example::

        class Event(SQLModel, table=True):
            __tablename__ = make_tablename(TABLE_PREFIX, "events")
    """
    return f"{prefix}{name}"
