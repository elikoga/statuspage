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
    CHECK_INTERVAL_SECONDS: int = 30

    # ── Telegram notifications ────────────────────────────────────────────────
    TELEGRAM_BOT_TOKEN: str | None = None
    TELEGRAM_CHAT_ID: str | None = None

    # ── Email (SMTP) notifications ───────────────────────────────────────────
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM: str | None = None   # defaults to SMTP_USER if unset
    SMTP_TO: str | None = None     # recipient; enables email when set
    SMTP_USE_STARTTLS: bool = True  # set False for port-465 SSL or plain relay

    model_config = SettingsConfigDict(env_prefix="STATUSPAGE_", env_file=".env")


global_settings = GlobalSettings()
