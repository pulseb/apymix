from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration centralisée de l'application, chargée depuis les variables d'environnement."""

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),  # .env.local surcharge .env (jamais commité)
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Général
    env: str = "development"
    debug: bool = False

    # Base de données
    database_url: str = "sqlite+aiosqlite:///./dev.db"

    # JWT
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 7
    # jwt_secret est géré par papi.db.config_store (env var JWT_SECRET ou DB papi_config)

    # CORS
    cors_origins: str = "http://localhost:5173,http://localhost:8000,http://localhost:9000"

    # Logging
    log_level: str = "INFO"

    # Backup S3 (Scaleway Object Storage ou tout S3-compatible)
    s3_endpoint_url: str | None = None
    """URL endpoint S3, ex: https://s3.fr-par.scw.cloud"""
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None
    s3_bucket_name: str | None = None
    """Nom du bucket S3 pour stocker les backups."""
    s3_region: str = "fr-par"

    @property
    def backup_enabled(self) -> bool:
        """True si la config S3 est complète (backup disponible)."""
        return bool(self.s3_endpoint_url and self.s3_access_key_id and self.s3_secret_access_key and self.s3_bucket_name)

    # Notifications email (Resend)
    resend_api_key: str | None = None
    """Clé API Resend (https://resend.com). Si None, les emails ne sont pas envoyés."""
    resend_from_email: str = "noreply@pulsapps.fr"
    """Adresse expéditrice des notifications (doit être vérifiée dans Resend)."""

    # Virtual host routing (host → front name)
    vhost_map: str = ""
    """Map hostnames to mounted frontend names, e.g. app.example.com=myapp,other.example.com=otherapp
    When set, requests on a mapped hostname are transparently rewritten to the
    corresponding frontend prefix, with no visible redirect."""

    @property
    def vhost_map_dict(self) -> dict[str, str]:
        """Parse VHOST_MAP into a {host: front_name} dict."""
        result: dict[str, str] = {}
        for pair in self.vhost_map.split(","):
            pair = pair.strip()
            if "=" in pair:
                host, front = pair.split("=", 1)
                result[host.strip()] = front.strip()
        return result

    # Dev / CI
    force_seed: bool = False
    """Si True, réinitialise la BDD et rejoue le seed au démarrage.
    Activé via variable d'env FORCE_SEED=true ou argument CLI --seed (voir app.py)."""

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def cors_origins_regex(self) -> str | None:
        """Convert wildcard patterns (https://*.example.com) to a regex for CORSMiddleware.

        Exact origins are passed via allow_origins; wildcard patterns via allow_origin_regex.
        Returns None if there are no wildcard patterns.
        """
        import re

        patterns = []
        for origin in self.cors_origins_list:
            if "*" in origin:
                # https://*.example.com → https://[^/]+\.example\.com
                escaped = re.escape(origin).replace(r"\*", "[^/]+")
                patterns.append(escaped)
        if not patterns:
            return None
        return "|".join(patterns)

    @property
    def is_dev(self) -> bool:
        return self.env == "development"


@lru_cache
def get_settings() -> Settings:
    """Singleton : charge la configuration une seule fois."""
    return Settings()
