"""Alembic env.py — Configurado para Dona (lee DATABASE_URL de .env)."""

import os
from logging.config import fileConfig
from dotenv import load_dotenv

from sqlalchemy import engine_from_config, pool
from alembic import context

load_dotenv()

config = context.config

# Usar DATABASE_URL de .env en lugar de alembic.ini
db_url = os.getenv("DATABASE_URL", "sqlite:///./dona.db")
# Alembic usa sync drivers
if db_url.startswith("postgresql+asyncpg://"):
    db_url = db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
elif db_url.startswith("postgresql://"):
    pass  # ya es sync
config.set_main_option("sqlalchemy.url", db_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Importar los modelos para autogenerate
from agent.memory import Base
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
