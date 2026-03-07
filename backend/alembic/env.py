from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

from statuspage.database.models import Base  # noqa: E402

target_metadata = Base.metadata


def _get_url() -> str:
    # When called from main.py via alembic.command.upgrade, sqlalchemy.url is
    # already injected. When invoked from the CLI we derive it from settings.
    url = config.get_main_option("sqlalchemy.url")
    if not url:
        from statuspage.database.connection import get_db_url
        url = get_db_url()
    return url


def run_migrations_offline() -> None:
    context.configure(
        url=_get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    cfg = config.get_section(config.config_ini_section, {})
    cfg.setdefault("sqlalchemy.url", _get_url())
    connectable = engine_from_config(cfg, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
