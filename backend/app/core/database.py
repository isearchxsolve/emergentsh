"""Database — SQLite default for smoke; Postgres in docker."""
from __future__ import annotations
import os
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from backend.app.models import Base

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./emergent.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql+asyncpg://" + DATABASE_URL[len("postgres://"):]
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = "postgresql+asyncpg://" + DATABASE_URL[len("postgresql://"):]
_kwargs = {"echo": os.getenv("DEBUG", "false").lower() == "true"}
if DATABASE_URL.startswith("sqlite"):
    _kwargs["connect_args"] = {"check_same_thread": False}
else:
    _kwargs.update(pool_pre_ping=True, pool_size=10, max_overflow=20)
engine = create_async_engine(DATABASE_URL, **_kwargs)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def init_db() -> None:
    """Compatibility-only schema creation for disposable local test runs.

    Production schema changes are exclusively managed by Alembic. Set
    ``AUTO_CREATE_SCHEMA=true`` only for an ephemeral local database.
    """
    if os.getenv("AUTO_CREATE_SCHEMA", "false").lower() not in {"true", "1"}:
        return
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def close_db() -> None:
    await engine.dispose()
