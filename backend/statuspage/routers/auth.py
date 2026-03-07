from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from statuspage import auth as _auth

router = APIRouter(tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(body: LoginRequest):
    if not _auth.verify(body.username, body.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = _auth.create_session(body.username)
    # Return the token in the body; the SvelteKit action sets the cookie so
    # it reaches the browser (Set-Cookie on a proxied fetch doesn't propagate).
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
