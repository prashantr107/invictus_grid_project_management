from logging.config import fileConfig
import os

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

from app.db.session import Base
from app import models  # noqa: F401

config = context.config
if config.config_file_name is not None:
    # Keep existing application loggers enabled: running migrations in-process
    # (e.g. a combined start script) must not silence `app.*` structured logs.
    fileConfig(config.config_file_name, disable_existing_loggers=False)
# Load backend/.env if present without overriding the real environment, then require an explicit URL.
# No credentials are hardcoded — DATABASE_URL must be provided via the environment or backend/.env.
load_dotenv()
database_url = os.getenv("DATABASE_URL")
if not database_url:
    raise RuntimeError("DATABASE_URL is not set. Export it, or add it to backend/.env, before running Alembic.")
config.set_main_option("sqlalchemy.url", database_url)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
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
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
