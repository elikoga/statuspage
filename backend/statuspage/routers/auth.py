import datetime
import logging

import httpx
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from statuspage import auth as _auth
from statuspage.config import global_settings

router = APIRouter(tags=["auth"])
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Discovery document cache (refreshed after 1 hour)
# ---------------------------------------------------------------------------

_discovery_doc: dict | None = None
_discovery_fetched_at: datetime.datetime | None = None
_DISCOVERY_TTL = datetime.timedelta(hours=1)


async def _get_discovery_doc() -> dict:
    global _discovery_doc, _discovery_fetched_at
    now = datetime.datetime.utcnow()
    if (
        _discovery_doc is None
        or _discovery_fetched_at is None
        or now - _discovery_fetched_at > _DISCOVERY_TTL
    ):
        issuer = global_settings.OIDC_ISSUER_URL
        url = f"{issuer.rstrip('/')}/.well-known/openid-configuration"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=10)
            resp.raise_for_status()
        _discovery_doc = resp.json()
        _discovery_fetched_at = now
        logger.info("OIDC discovery document fetched from %s", url)
    return _discovery_doc


# ---------------------------------------------------------------------------
# Password login
# ---------------------------------------------------------------------------


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(body: LoginRequest):
    if not _auth.verify(body.username, body.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = _auth.create_session(body.username)
    # Return token in body; the SvelteKit action sets the cookie so it
    # reaches the browser (Set-Cookie on a proxied fetch doesn't propagate).
    return {"token": token, "ok": True}


@router.post("/logout")
def logout(request: Request, response: Response):
    token = request.cookies.get(_auth.COOKIE_NAME)
    if token:
        _auth.delete_session(token)
    response.delete_cookie(_auth.COOKIE_NAME)
    return {"ok": True}


@router.get("/me")
def me(request: Request):
    token = request.cookies.get(_auth.COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    session = _auth.get_session(token)
    if not session:
        raise HTTPException(status_code=401, detail="Session expired")
    return {"username": session["username"]}


# ---------------------------------------------------------------------------
# Auth configuration (used by the frontend login page)
# ---------------------------------------------------------------------------


@router.get("/config")
def auth_config():
    return {
        "oidc_enabled": global_settings.OIDC_ISSUER_URL is not None,
        "oidc_provider_name": global_settings.OIDC_PROVIDER_NAME,
    }


# ---------------------------------------------------------------------------
# OIDC – Authorization Code Flow
# ---------------------------------------------------------------------------


def _oidc_redirect_uri() -> str:
    return f"{global_settings.BASE_URL.rstrip('/')}/auth/oidc/callback"


def _require_oidc() -> None:
    if (
        not global_settings.OIDC_ISSUER_URL
        or not global_settings.OIDC_CLIENT_ID
        or not global_settings.OIDC_CLIENT_SECRET
    ):
        raise HTTPException(status_code=404, detail="OIDC not configured")


@router.get("/oidc/login")
async def oidc_login(next: str = "/admin"):
    _require_oidc()
    discovery = await _get_discovery_doc()
    state, nonce = _auth.create_oidc_state(next)
    auth_endpoint = discovery["authorization_endpoint"]
    params = (
        f"response_type=code"
        f"&client_id={global_settings.OIDC_CLIENT_ID}"
        f"&redirect_uri={_oidc_redirect_uri()}"
        f"&scope=openid+profile+email"
        f"&state={state}"
        f"&nonce={nonce}"
    )
    return RedirectResponse(url=f"{auth_endpoint}?{params}", status_code=302)


@router.get("/oidc/callback")
async def oidc_callback(code: str = "", state: str = "", error: str = ""):
    _require_oidc()

    if error:
        logger.warning("OIDC provider returned error: %s", error)
        return RedirectResponse(url="/login?error=oidc_denied", status_code=302)

    if not code or not state:
        return RedirectResponse(url="/login?error=oidc_invalid", status_code=302)

    state_data = _auth.consume_oidc_state(state)
    if state_data is None:
        logger.warning("OIDC callback received unknown or expired state")
        return RedirectResponse(url="/login?error=oidc_invalid", status_code=302)

    next_url = state_data.get("next", "/admin")

    try:
        discovery = await _get_discovery_doc()

        async with httpx.AsyncClient() as client:
            # Exchange code for tokens
            token_resp = await client.post(
                discovery["token_endpoint"],
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": _oidc_redirect_uri(),
                    "client_id": global_settings.OIDC_CLIENT_ID,
                    "client_secret": global_settings.OIDC_CLIENT_SECRET,
                },
                timeout=10,
            )
            token_resp.raise_for_status()
            access_token = token_resp.json()["access_token"]

            # Fetch user info from the provider (avoids JWT sig validation)
            userinfo_resp = await client.get(
                discovery["userinfo_endpoint"],
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10,
            )
            userinfo_resp.raise_for_status()
            userinfo = userinfo_resp.json()

    except Exception:
        logger.exception("OIDC token exchange / userinfo failed")
        return RedirectResponse(url="/login?error=oidc_failed", status_code=302)

    # Prefer preferred_username, fall back to email, then sub
    username = (
        userinfo.get("preferred_username")
        or userinfo.get("email")
        or userinfo.get("sub")
    )
    if not username:
        logger.error("OIDC userinfo contained no usable identifier: %s", userinfo)
        return RedirectResponse(url="/login?error=oidc_failed", status_code=302)

    token = _auth.create_session(username)
    logger.info("OIDC login: created session for %r", username)

    # The callback is a direct browser request (not a proxied SSR fetch),
    # so Set-Cookie propagates to the browser correctly here.
    response = RedirectResponse(url=next_url, status_code=302)
    response.set_cookie(
        key=_auth.COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 7,
        path="/",
    )
    return response
