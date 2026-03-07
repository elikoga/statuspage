import datetime
import secrets
from typing import Any

SESSION_DURATION = datetime.timedelta(days=7)
COOKIE_NAME = "session-token"

# token -> {username, expires_at}
_sessions: dict[str, dict[str, Any]] = {}

# Set during lifespan startup; never None after that.
_password: str | None = None
_username: str = "admin"


def init(username: str, password: str | None) -> None:
    global _password, _username
    _username = username
    if password:
        _password = password
    else:
        _password = secrets.token_urlsafe(16)
        import logging

        logging.getLogger(__name__).warning(
            "STATUSPAGE_ADMIN_PASSWORD not set — generated password: %s", _password
        )


def verify(username: str, password: str) -> bool:
    return username == _username and _password is not None and password == _password


def create_session(username: str) -> str:
    token = secrets.token_urlsafe(32)
    _sessions[token] = {
        "username": username,
        "expires_at": datetime.datetime.utcnow() + SESSION_DURATION,
    }
    return token


def get_session(token: str) -> dict[str, Any] | None:
    entry = _sessions.get(token)
    if entry is None:
        return None
    if datetime.datetime.utcnow() > entry["expires_at"]:
        del _sessions[token]
        return None
    return entry


def delete_session(token: str) -> None:
    _sessions.pop(token, None)
