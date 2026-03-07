import pathlib

from pydantic_settings import BaseSettings, SettingsConfigDict


class GlobalSettings(BaseSettings):
    BASE_URL: str = "http://localhost:8000"
    DATA_PATH: pathlib.Path = pathlib.Path("./data")
    FRONTEND_BINARY_PATH: str | None = None
    ALEMBIC_INI_PATH: str = "alembic.ini"
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str | None = None
    OIDC_ISSUER_URL: str | None = None
    OIDC_CLIENT_ID: str | None = None
    OIDC_CLIENT_SECRET: str | None = None
    OIDC_PROVIDER_NAME: str = "Keycloak"

    model_config = SettingsConfigDict(env_prefix="STATUSPAGE_", env_file=".env")


global_settings = GlobalSettings()
