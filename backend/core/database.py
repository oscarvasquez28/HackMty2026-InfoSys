import logging
from typing import Any, AsyncGenerator, Dict, Optional, Tuple
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from backend.core.config import settings
from backend.models.forensic import Base, seed_legal_knowledge

logger = logging.getLogger("forensic_auditor.database")

_engine: Optional[AsyncEngine] = None
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


def sanitize_database_url(url: str) -> str:
    """Masks sensitive credentials in database URL for safe logging."""
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        if parsed.password:
            netloc = parsed.netloc.replace(f":{parsed.password}@", ":****@")
            return urlunparse(parsed._replace(netloc=netloc))
        return url
    except Exception:
        return "<malformed_url>"


def normalize_database_url(raw_url: str) -> Tuple[str, Dict[str, Any]]:
    """
    Normalizes a database URL to ensure async driver compatibility and SSL enforcement.
    Converts generic 'postgres://' or 'postgresql://' schemes to 'postgresql+asyncpg://'
    or 'postgresql+psycopg://'.
    For asyncpg, extracts 'sslmode' or 'ssl' query parameters and translates them
    into connect_args={'ssl': mode} because asyncpg does not accept query parameters for SSL.
    Returns a tuple of (normalized_url, connect_args).
    """
    if not raw_url:
        return "", {}

    # Support SQLite memory or file URLs directly
    if raw_url.startswith("sqlite"):
        return raw_url, {}

    parsed = urlparse(raw_url)
    scheme = parsed.scheme.lower()

    # Normalize scheme to async driver
    if scheme in ("postgres", "postgresql"):
        scheme = "postgresql+asyncpg"
    elif scheme == "postgresql+psycopg2":
        scheme = "postgresql+psycopg"

    # Extract query parameters
    query_params = parse_qs(parsed.query)
    connect_args: Dict[str, Any] = {}

    if "asyncpg" in scheme:
        # AsyncPG requires ssl config passed in connect_args, not as URL query param
        if "sslmode" in query_params:
            mode = query_params.pop("sslmode")[0]
            if mode in ("require", "verify-ca", "verify-full"):
                connect_args["ssl"] = mode
            elif mode in ("disable", "allow", "prefer"):
                connect_args["ssl"] = False
        elif "ssl" in query_params:
            mode = query_params.pop("ssl")[0]
            if mode.lower() in ("false", "0", "disable"):
                connect_args["ssl"] = False
            elif mode.lower() in ("true", "1", "require"):
                connect_args["ssl"] = "require"
            else:
                connect_args["ssl"] = mode
        elif settings.DB_SSL_REQUIRE:
            connect_args["ssl"] = "require"
    elif "psycopg" in scheme:
        # psycopg handles sslmode query parameter directly
        if "sslmode" not in query_params and settings.DB_SSL_REQUIRE:
            query_params["sslmode"] = ["require"]

    new_query = urlencode(query_params, doseq=True)
    normalized_url = urlunparse((
        scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        new_query,
        parsed.fragment,
    ))

    return normalized_url, connect_args


def create_engine_and_sessionmaker(
    database_url: str,
    echo: Optional[bool] = None,
) -> Tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """
    Creates an AsyncEngine and bound async_sessionmaker for the specified database URL.
    Configures StaticPool and enables foreign keys for SQLite; configures connection
    pooling and pre-ping for PostgreSQL.
    """
    db_url, connect_args = normalize_database_url(database_url)
    is_echo = echo if echo is not None else settings.DB_ECHO

    if "sqlite" in db_url:
        connect_args.setdefault("check_same_thread", False)
        engine = create_async_engine(
            db_url,
            echo=is_echo,
            poolclass=StaticPool,
            connect_args=connect_args,
        )

        @event.listens_for(engine.sync_engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, connection_record):
            try:
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON;")
                cursor.close()
            except Exception:
                pass
    else:
        engine = create_async_engine(
            db_url,
            echo=is_echo,
            pool_size=settings.DB_POOL_SIZE,
            max_overflow=settings.DB_MAX_OVERFLOW,
            pool_pre_ping=settings.DB_POOL_PRE_PING,
            pool_recycle=settings.DB_POOL_RECYCLE,
            connect_args=connect_args,
        )

    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    return engine, session_factory


def get_engine() -> AsyncEngine:
    """Returns or creates the singleton AsyncEngine instance."""
    global _engine, _session_factory
    if _engine is None:
        if not settings.DATABASE_URL:
            raise RuntimeError(
                "DATABASE_URL is not configured. Please set the DATABASE_URL "
                "environment variable or configure it in .env"
            )

        safe_url = sanitize_database_url(settings.DATABASE_URL)
        logger.info(f"Initializing AsyncEngine for: {safe_url}")
        _engine, _session_factory = create_engine_and_sessionmaker(settings.DATABASE_URL)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Returns the async sessionmaker factory."""
    if _session_factory is None:
        get_engine()
    assert _session_factory is not None
    return _session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency yielding a transactional AsyncSession.
    Automatically commits on success, rolls back on unhandled exception,
    and closes when completed.
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db(engine: Optional[AsyncEngine] = None) -> None:
    """
    Initializes database schema, creates pgvector extension if on PostgreSQL,
    and populates seed Mexican AML legal precedent articles idempotently.
    """
    if engine is None:
        if not settings.DATABASE_URL:
            logger.info("DATABASE_URL is not configured; skipping database initialization.")
            return
        engine = get_engine()

    async with engine.begin() as conn:
        if engine.dialect.name == "postgresql":
            try:
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            except Exception as exc:
                logger.warning(f"Failed to create pgvector extension: {exc}")

        # Create all registered tables
        await conn.run_sync(Base.metadata.create_all)

    if _session_factory is not None and engine == _engine:
        factory = _session_factory
    else:
        factory = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

    async with factory() as session:
        count = await seed_legal_knowledge(session)
        logger.info(f"Database schema initialized and seed precedents verified ({count} new records added).")


async def close_db() -> None:
    """Disposes of the database engine connection pool."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("Database engine connection pool disposed.")
