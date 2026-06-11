"""Stockage et récupération de la configuration interne PAPI depuis la DB.

Priorité du JWT secret :
    1. Variable d'env JWT_SECRET (dev : stable entre reloads, ou override forcé)
    2. Valeur en DB (générée automatiquement au premier démarrage si absente)

Usage :
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
    """Retourne le JWT secret actif.

    - Si JWT_SECRET est défini en variable d'env → l'utilise directement.
    - Sinon → charge depuis papi_config, ou génère et persiste un secret aléatoire.
    """
    env_secret = os.environ.get("JWT_SECRET")
    if env_secret:
        logger.debug("JWT secret loaded from environment variable")
        return env_secret

    config = await session.get(AmxConfig, _JWT_SECRET_KEY)
    if config:
        logger.debug("JWT secret loaded from database")
        return config.value

    # Première fois : générer et persister
    new_secret = secrets.token_hex(32)
    session.add(AmxConfig(key=_JWT_SECRET_KEY, value=new_secret))
    await session.commit()
    logger.info("JWT secret generated and stored in database")
    return new_secret


async def get_verbose_errors(session: AsyncSession) -> bool:
    """Retourne True si le mode verbose des erreurs 500 est activé en DB.

    Clé DB : verbose_errors = "true" | "false"
    Permet d'exposer le traceback Python dans les réponses 500 sans passer en is_dev.
    """
    config = await session.get(AmxConfig, _VERBOSE_ERRORS_KEY)
    if config:
        return config.value.strip().lower() == "true"
    return False
