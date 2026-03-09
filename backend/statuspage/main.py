import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware

from statuspage.config import global_settings
from statuspage.routers import api, auth, frontend

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def perform_db_upgrade():
    alembic_cfg = Config(global_settings.ALEMBIC_INI_PATH)
    alembic_cfg.set_main_option(
        "script_location",
        os.path.join(os.path.dirname(os.path.abspath(global_settings.ALEMBIC_INI_PATH)), "alembic"),
    )
    from statuspage.database.connection import get_db_url

    alembic_cfg.set_main_option("sqlalchemy.url", get_db_url())
    logger.info("running database migrations")
    command.upgrade(alembic_cfg, "head")
    logger.info("database migrations complete")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- startup ---
    try:
        logger.info("starting up")
        perform_db_upgrade()
        logging.basicConfig(
            force=True,
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        )

        from statuspage.database.connection import create_sqlalchemy_engine

        app.state.db_engine = create_sqlalchemy_engine()
        import statuspage.main as _self

        from statuspage import auth as _auth

        _auth.init(
            global_settings.ADMIN_USERNAME,
            global_settings.ADMIN_PASSWORD,
            global_settings.DATA_PATH,
            db_engine=app.state.db_engine,
        )
        _self.db_engine = app.state.db_engine
        from statuspage import notifier as _notifier
        _notifier._db_engine = app.state.db_engine

        logger.info("starting frontend")
        await frontend.frontend.run()
        logger.info("frontend started at %s", global_settings.BASE_URL)

        from statuspage import checker as _checker

        asyncio.create_task(
            _checker.warmup_command_checks(app.state.db_engine),
            name="warmup-command-checks",
        )
        _checker_task = asyncio.create_task(
            _checker.health_check_loop(app.state.db_engine, global_settings.CHECK_INTERVAL_SECONDS)
        )
        _purge_task = asyncio.create_task(_session_purge_loop())
    except Exception:
        import traceback

        traceback.print_exc()
        raise

    # --- hand control back to the server ---
    yield

    # --- shutdown ---
    _purge_task.cancel()
    try:
        await _purge_task
    except asyncio.CancelledError:
        pass
    _checker_task.cancel()
    try:
        await _checker_task
    except asyncio.CancelledError:
        pass

    logger.info("stopping frontend")
    await frontend.frontend.stop()
    logger.info("frontend stopped")


app = FastAPI(
    title="Statuspage API",
    description="Backend API for the status page tool",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(GZipMiddleware, minimum_size=1000, compresslevel=5)

app.include_router(auth.router, prefix="/auth")
app.include_router(api.router, prefix="/api")
app.include_router(frontend.router)  # catch-all — must be last


# module-level reference populated during lifespan; used by get_db()
db_engine = None


async def _session_purge_loop() -> None:
    """Purge expired sessions from the DB once per hour."""
    while True:
        try:
            await asyncio.sleep(3600)
            from statuspage import auth as _auth

            count = _auth.purge_expired_sessions()
            if count:
                logger.info("purged %d expired session(s)", count)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("error purging expired sessions")


def main():
    import uvicorn

    host = os.environ.get("UVICORN_HOST", "127.0.0.1")
    port = int(os.environ.get("UVICORN_PORT", "8000"))
    reload = "--reload" in sys.argv

    uvicorn.run(
        "statuspage.main:app",
        host=host,
        port=port,
        reload=reload,
    )


if __name__ == "__main__":
    main()
