# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app import infrastructure  # noqa: F401
from app.infrastructure.config import settings
from app.infrastructure.database import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support

target_metadata = Base.metadata

_IGNORED_SCHEMAS: frozenset[str] = frozenset(
    {
        "tiger",
        "tiger_data",
        "topology",
        "context",
        "keycloak",
        "n8n",
        "mattermost",
    }
)

_IGNORED_EXTENSION_TABLES: frozenset[str] = frozenset(
    {
        "alembic_version",
        "spatial_ref_sys",
        "geography_columns",
        "geometry_columns",
        "raster_columns",
        "raster_overviews",
        "layer",
        "topology",
        "addr",
        "addrfeat",
        "bg",
        "county",
        "county_lookup",
        "countysub_lookup",
        "cousub",
        "direction_lookup",
        "edges",
        "faces",
        "featnames",
        "geocode_settings",
        "geocode_settings_default",
        "loader_lookuptables",
        "loader_platform",
        "loader_variables",
        "pagc_gaz",
        "pagc_lex",
        "pagc_rules",
        "place",
        "place_lookup",
        "secondary_unit_lookup",
        "state",
        "state_lookup",
        "street_type_lookup",
        "tabblock",
        "tabblock20",
        "tract",
        "zcta5",
        "zip_lookup",
        "zip_lookup_all",
        "zip_lookup_base",
        "zip_state",
        "zip_state_loc",
    }
)


def include_object(object_, name, type_, reflected, compare_to) -> bool:
    """Ignore PostGIS / Tiger Geocoder / Topology system tables & non-public schemas."""
    obj_schema = getattr(object_, "schema", None)
    if obj_schema is not None and obj_schema != "public":
        return False
    if obj_schema in _IGNORED_SCHEMAS:
        return False

    if type_ == "table" and name in _IGNORED_EXTENSION_TABLES:
        return False

    parent_table = getattr(object_, "table", None)
    parent_schema = getattr(parent_table, "schema", None)
    parent_name = getattr(parent_table, "name", None)
    if parent_schema is not None and parent_schema != "public":
        return False
    if parent_name in _IGNORED_EXTENSION_TABLES:
        return False

    return True


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = settings.DATABASE_URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """In this scenario we need to create an Engine
    and associate a connection with the context.

    """

    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = settings.DATABASE_URL
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
