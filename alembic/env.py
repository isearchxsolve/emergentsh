from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from backend.app.models import Base

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

# The runtime URL is canonical.  This supports both SQLite smoke databases and
# production PostgreSQL without maintaining a second migration configuration.
database_url = os.getenv("DATABASE_URL")
if database_url:
    if database_url.startswith("postgres://"):
        database_url = "postgresql+asyncpg://" + database_url[len("postgres://"):]
    elif database_url.startswith("postgresql://"):
        database_url = "postgresql+asyncpg://" + database_url[len("postgresql://"):]
    config.set_main_option("sqlalchemy.url", database_url)

target_metadata = Base.metadata


def include_object(object_, name, type_, reflected, compare_to):
    """Ignore tables owned by other applications in a shared database.

    NeonBuild migrations own only tables present in Base.metadata. Without
    this guard, Alembic autogenerate proposes destructive drops for unrelated
    schemas/tables such as other local services using the same PostgreSQL DB.
    """
    if type_ == "table" and reflected and compare_to is None:
        return name in target_metadata.tables
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_async_migrations())
