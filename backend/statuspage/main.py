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
    from statuspage.database.connection import get_db_url

    alembic_cfg.set_main_option("sqlalchemy.url", get_db_url())
    logger.info("running database migrations")
    command.upgrade(alembic_cfg, "head")
    logger.info("database migrations complete")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("starting up")
    perform_db_upgrade()

    from statuspage import auth as _auth

    _auth.init(global_settings.ADMIN_USERNAME, global_settings.ADMIN_PASSWORD)
    # expose the engine on the app state so get_db() can reach it
    from statuspage.database.connection import create_sqlalchemy_engine

    app.state.db_engine = create_sqlalchemy_engine()
    import statuspage.main as _self

    _self.db_engine = app.state.db_engine

    logger.info("starting frontend")
    await frontend.frontend.run()
    logger.info("frontend started at %s", global_settings.BASE_URL)

    yield

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
