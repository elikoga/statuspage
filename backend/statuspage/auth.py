import datetime
import logging
import pathlib
import secrets
from typing import Any

_log = logging.getLogger(__name__)

SESSION_DURATION = datetime.timedelta(days=7)
COOKIE_NAME = "session-token"

# token -> {username, expires_at}
_sessions: dict[str, dict[str, Any]] = {}

# Set during lifespan startup; never None after that.
_password: str | None = None
_username: str = "admin"


def init(username: str, password: str | None, data_path: pathlib.Path) -> None:
    global _password, _username
    _username = username
    if password:
        _password = password
        return

    password_file = data_path / "admin-password"
    if password_file.exists():
        _password = password_file.read_text().strip()
        _log.info("loaded admin password from %s", password_file)
        return

    # First run: generate, persist, announce.
    data_path.mkdir(parents=True, exist_ok=True)
    _password = secrets.token_urlsafe(32)
    password_file.write_text(_password)
    password_file.chmod(0o600)
    _log.warning(
        "STATUSPAGE_ADMIN_PASSWORD not set — generated password written to %s: %s",
        password_file,
        _password,
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



# ---------------------------------------------------------------------------
# OIDC state store (short-lived; state token -> payload)
# ---------------------------------------------------------------------------

_OIDC_STATE_TTL = datetime.timedelta(minutes=10)
_oidc_states: dict[str, dict] = {}


def create_oidc_state(next_url: str) -> tuple[str, str]:
    """Return (state, nonce) and persist them for the duration of the OAuth flow."""
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    _oidc_states[state] = {
        "nonce": nonce,
        "next": next_url,
        "expires_at": datetime.datetime.utcnow() + _OIDC_STATE_TTL,
    }
    return state, nonce


def consume_oidc_state(state: str) -> dict | None:
    """Pop and return the state payload, or None if missing/expired."""
    entry = _oidc_states.pop(state, None)
    if entry is None:
        return None
    if datetime.datetime.utcnow() > entry["expires_at"]:
        return None
    return entry