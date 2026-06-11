"""Alembic env — workspace-level migration runner.

Agnostique des apps : on charge la config depuis apymix (DB URL), on importe
tous les modèles via l'auto-discovery d'apymix, et on utilise SQLModel.metadata
comme target_metadata. Les révisions sont versionnées par branche via
``branch_labels`` (``apymix``, ``eve``, ``kif``).
"""
from __future__ import annotations

from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlmodel import SQLModel

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Workspace root = parent of apymix/ (since env.py lives in apymix/alembic/).
# Compatible avec alembic.ini à la racine du workspace pointant vers
# script_location = <workspace>/apymix/alembic.
WORKSPACE_ROOT = Path(__file__).resolve().parents[2]


def _normalized_database_url() -> str:
    # Lazy import: la config apymix charge .env
    from apymix.config import get_settings

    url = get_settings().database_url
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres+asyncpg://"):
        return url.replace("postgres+asyncpg://", "postgresql+asyncpg://", 1)
    return url


def _import_all_models() -> None:
    """Importe tous les modèles (apymix core + APIs auto-discovered)."""
    # Apymix core
    import apymix.apps.models  # noqa: F401
    import apymix.auth.models  # noqa: F401

    # Toutes les APIs du workspace (via amx.yaml)
    from apymix.discovery import import_all_api_models
    import_all_api_models(WORKSPACE_ROOT)


_import_all_models()
target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    url = _normalized_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _normalized_database_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    import asyncio
    asyncio.run(run_migrations_online())
