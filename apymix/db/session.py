from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from apymix.config import get_settings

_engine = None
_session_factory = None
_using_fallback: bool = False
_effective_db_url: str = ""


_FALLBACK_URL = "sqlite+aiosqlite:///:memory:"


def _get_engine():
    global _engine, _using_fallback, _effective_db_url
    if _engine is None:
        import logging

        settings = get_settings()
        url = settings.database_url or _FALLBACK_URL

        # Validate the URL before creating the engine — fall back to in-memory SQLite if invalid
        try:
            from sqlalchemy import make_url

            make_url(url)
        except Exception:
            logging.getLogger(__name__).warning(
                "DATABASE_URL invalid or empty (%r) — falling back to in-memory SQLite", url
            )
            url = _FALLBACK_URL

        _using_fallback = url == _FALLBACK_URL
        _effective_db_url = url

        # Normalize legacy postgres schemes → postgresql+asyncpg
        # postgres:// and postgres+asyncpg:// are no longer recognized by SQLAlchemy 2.x
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgres+asyncpg://"):
            url = url.replace("postgres+asyncpg://", "postgresql+asyncpg://", 1)

        connect_args = {}
        engine_kwargs: dict = {}
        if url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
        elif "asyncpg" in url or url.startswith("postgresql"):
            # PgBouncer / Supavisor in transaction/statement mode does not support
            # prepared statements — disable them on the asyncpg side.
            connect_args["statement_cache_size"] = 0
            # Conservative pool settings for hosted free-tier databases (e.g. Supabase).
            # Supabase free tier has a low connection limit; keeping the pool small avoids
            # "too many connections" errors.  pool_recycle prevents stale connections after
            # the server-side idle timeout (~5 min).
            engine_kwargs = {
                "pool_size": 1,
                "max_overflow": 1,
                "pool_recycle": 300,
            }
        _engine = create_async_engine(
            url,
            echo=settings.debug,
            connect_args=connect_args,
            **engine_kwargs,
        )
    return _engine


def get_db_info() -> dict:
    """Returns info about the DB connection (without exposing credentials)."""
    from sqlalchemy import make_url

    backend = "not initialized"
    masked_url = "not initialized"
    if _effective_db_url:
        try:
            parsed = make_url(_effective_db_url)
            backend = parsed.get_backend_name()
            # Mask the password
            masked_url = parsed.render_as_string(hide_password=True)
        except Exception:
            backend = "unknown"
            masked_url = "(unreadable)"

    return {
        "backend": backend,
        "url": masked_url,
        "fallback": _using_fallback,
    }


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(_get_engine(), class_=AsyncSession, expire_on_commit=False)
    return _session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: provides a DB session per request."""
    session_factory = _get_session_factory()
    async with session_factory() as session:
        yield session


async def init_db() -> None:
    """Creates the tables (dev only — in prod, use Alembic)."""
    engine = _get_engine()
    async with engine.begin() as conn:
        # Enable foreign keys for SQLite
        if get_settings().database_url.startswith("sqlite"):
            await conn.execute(
                __import__("sqlalchemy").text("PRAGMA foreign_keys = ON")
            )
        await conn.run_sync(SQLModel.metadata.create_all)
