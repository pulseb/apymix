"""Storage and retrieval of internal Apymix configuration from the DB.

JWT secret priority:
    1. JWT_SECRET environment variable (dev: stable across reloads, or forced override)
    2. DB value (automatically generated on first startup if absent)

Usage:
    secret = await get_or_create_jwt_secret(session)
"""

import logging
import os
import secrets

from sqlalchemy.ext.asyncio import AsyncSession

from apymix.db.models import AmxConfig

logger = logging.getLogger(__name__)

_JWT_SECRET_KEY = "jwt_secret"
_VERBOSE_ERRORS_KEY = "verbose_errors"


async def get_or_create_jwt_secret(session: AsyncSession) -> str:
    """Returns the active JWT secret.

    - If JWT_SECRET is defined as an env var → use it directly.
    - Otherwise → load from amx_config, or generate and persist a random secret.
    """
    env_secret = os.environ.get("JWT_SECRET")
    if env_secret:
        logger.debug("JWT secret loaded from environment variable")
        return env_secret

    config = await session.get(AmxConfig, _JWT_SECRET_KEY)
    if config:
        logger.debug("JWT secret loaded from database")
        return config.value

    # First time: generate and persist
    new_secret = secrets.token_hex(32)
    session.add(AmxConfig(key=_JWT_SECRET_KEY, value=new_secret))
    await session.commit()
    logger.info("JWT secret generated and stored in database")
    return new_secret


async def get_verbose_errors(session: AsyncSession) -> bool:
    """Returns True if the verbose 500-error mode is enabled in the DB.

    DB key: verbose_errors = "true" | "false"
    Allows exposing the Python traceback in 500 responses without toggling is_dev.
    """
    config = await session.get(AmxConfig, _VERBOSE_ERRORS_KEY)
    if config:
        return config.value.strip().lower() == "true"
    return False
