import pathlib

from pydantic_settings import BaseSettings, SettingsConfigDict


class GlobalSettings(BaseSettings):
    BASE_URL: str = "http://localhost:8000"
    DATA_PATH: pathlib.Path = pathlib.Path("./data")
    FRONTEND_BINARY_PATH: str | None = None
    ALEMBIC_INI_PATH: str = "alembic.ini"

    model_config = SettingsConfigDict(env_prefix="STATUSPAGE_", env_file=".env")


global_settings = GlobalSettings()
