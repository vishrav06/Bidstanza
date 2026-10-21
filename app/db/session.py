"""
Async database engine, session factory and the per-request session dependency.

A single `AsyncEngine` owns the asyncpg connection pool for the whole process.
Its pool settings come from config: `pool_size` connections stay open,
`max_overflow` extra connections are allowed during bursts, and `pool_pre_ping`
checks each connection before handing it out so stale ones (for example after
Postgres restarts) are replaced. `SessionLocal` creates lightweight `AsyncSession`
objects on top of that pool.

`get_session()` is the FastAPI dependency that gives each request its own session.
It does not open a transaction itself. Services do that explicitly with
`async with session.begin():`, which keeps transaction boundaries, and the row
locks held inside them, visible in the code that owns them. The dependency only
guarantees rollback on error and that the connection goes back to the pool.
"""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings


def build_engine(url: str) -> AsyncEngine:
    """Create an engine with the project's pool settings. Tests reuse this with the test DB URL."""
    settings = get_settings()
    return create_async_engine(
        url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout,
        pool_pre_ping=True,
        # Pin the Postgres session timezone so server-side now() and TIMESTAMPTZ
        # rendering are UTC regardless of the server's default.
        connect_args={"server_settings": {"timezone": "UTC"}},
    )


def build_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    # expire_on_commit=False: ORM objects stay readable after commit. That's needed
    # because routes serialize them (and broadcast them) after the transaction ends;
    # otherwise each attribute access would trigger a lazy reload, which async forbids.
    return async_sessionmaker(engine, expire_on_commit=False)


engine: AsyncEngine = build_engine(get_settings().database_url)
SessionLocal: async_sessionmaker[AsyncSession] = build_sessionmaker(engine)


async def get_session() -> AsyncIterator[AsyncSession]:
    """Yield one session per request; roll back on any error, always release the connection."""
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
