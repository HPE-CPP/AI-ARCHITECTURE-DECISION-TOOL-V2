import sys
from pathlib import Path
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# Make backend root importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import settings
from app.db.base import Base
import app.db.models  # noqa: F401 — register all models

config = context.config

# Override sqlalchemy.url from our settings (ignore alembic.ini value).
# Alembic stores this in a ConfigParser, which treats '%' as interpolation
# syntax. URLs with percent-encoded characters (e.g. a password containing
# '%40' for '@') would raise "invalid interpolation syntax" and silently skip
# migrations. Escape '%' as '%%' so ConfigParser round-trips it back to the
# literal URL when read by engine_from_config / get_main_option.
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL.replace("%", "%%"))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (no live DB connection)."""
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
    """Run migrations in 'online' mode (live DB connection)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
