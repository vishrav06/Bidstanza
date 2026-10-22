"""
Application entry point: builds the FastAPI app and manages its lifecycle.

`create_app()` assembles the app: it registers the error handlers that produce the
uniform error envelope, and mounts the routes. The `lifespan` context runs once per
process. On startup it creates any missing tables (`create_all` never alters or
drops existing ones; Alembic replaces this later), and on shutdown it closes every
pooled database connection. Later steps add the auth, auction, bid and WebSocket
routers here, and start the settlement loop inside the lifespan.

Run with a single worker, because the WebSocket hub lives in this process:
    uv run uvicorn app.main:app --reload --workers 1
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

import app.models  # noqa: F401  (registers every table on Base.metadata)
from app.core.errors import error_response, register_exception_handlers
from app.db.base import Base
from app.db.session import engine, get_session


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # begin() commits the DDL (tables, indexes, the bids trigger) as one transaction.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(title="Bidstanza", version="0.1.0", lifespan=lifespan)
    register_exception_handlers(app)

    @app.get("/health", tags=["meta"], response_model=None)
    async def health(
        session: Annotated[AsyncSession, Depends(get_session)],
    ) -> dict[str, str] | JSONResponse:
        """Liveness plus a database round-trip; 503 if Postgres is unreachable."""
        try:
            await session.execute(text("SELECT 1"))
        except (SQLAlchemyError, OSError):
            return error_response(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "database_unavailable",
                "The database is not reachable.",
            )
        return {"status": "ok"}

    return app


app = create_app()
