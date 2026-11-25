"""Async PostgreSQL database engine, session factory and health check."""

from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    """Declarative base for SQLAlchemy ORM models."""


def create_engine() -> AsyncEngine:
    """Create the async SQLAlchemy engine using current settings."""
    settings = get_settings()
    return create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        echo=settings.originlabs_env == "development",
    )


engine: AsyncEngine = create_engine()
async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session per request."""
    async with async_session_factory() as session:
        yield session


async def check_database_health() -> tuple[bool, str | None]:
    """Run a lightweight connectivity check against PostgreSQL."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True, None
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)
