# statuspage

A lightweight status page tool. Track service health and communicate incidents.

## Stack

- **Backend**: Python / FastAPI / SQLite (via SQLAlchemy + Alembic), managed with `uv`
- **Frontend**: SvelteKit 2 / Svelte 5 / Tailwind CSS 4, built with `adapter-node`

The backend spawns the SvelteKit process as a subprocess and reverse-proxies all non-API traffic to it. SSR fetches from the frontend are rewritten to hit the backend directly over localhost.

## Getting started

```bash
cd backend
uv sync
uv run statuspage --reload
```

`--reload` starts the frontend in Vite dev mode (hot reload). Without it the backend runs `npm build && npm preview` instead.

On first run the SQLite database is created and migrations are applied automatically.

## Project structure

```
backend/
  statuspage/
    main.py          FastAPI app + lifespan
    config.py        Settings (env prefix: STATUSPAGE_)
    database/        SQLAlchemy models + engine
    routers/
      api.py         REST CRUD — /api/services, /api/incidents
      frontend.py    Subprocess manager + reverse proxy catch-all
  alembic/           Migrations
  alembic.ini

frontend/
  src/
    hooks.server.ts  Rewrites SSR /api/* fetches to PRIVATE_BASE_URL
    routes/
      +page.*        Public status page
      admin/+page.*  Admin UI (manage services and incidents)
```

## Configuration

| Env var | Default | Description |
|---|---|---|
| `STATUSPAGE_BASE_URL` | `http://localhost:8000` | Public URL of the app |
| `STATUSPAGE_DATA_PATH` | `./data` | Directory for the SQLite database |
| `STATUSPAGE_FRONTEND_BINARY_PATH` | *(none)* | Path to a prebuilt frontend binary |
| `UVICORN_HOST` | `127.0.0.1` | Host uvicorn listens on |
| `UVICORN_PORT` | `8000` | Port uvicorn listens on |
| `STATUSPAGE_ADMIN_USERNAME` | `admin` | Admin username |
| `STATUSPAGE_ADMIN_PASSWORD` | *(auto-generated)* | Admin password; logged at WARNING if unset |
| `STATUSPAGE_OIDC_ISSUER_URL` | *(none)* | Enables OIDC when set (e.g. Keycloak realm URL) |
| `STATUSPAGE_OIDC_CLIENT_ID` | *(none)* | OIDC client ID |
| `STATUSPAGE_OIDC_CLIENT_SECRET` | *(none)* | OIDC client secret |
| `STATUSPAGE_OIDC_PROVIDER_NAME` | `Keycloak` | Label shown on the SSO button |

The frontend receives `PRIVATE_BASE_URL` (derived from `UVICORN_HOST`/`UVICORN_PORT`) for SSR → backend calls, and `PUBLIC_BASE_URL` for client-side use.


## Authentication

### Password (default)

A single admin account is used. Set credentials via env vars:

```
STATUSPAGE_ADMIN_USERNAME=admin          # default: admin
STATUSPAGE_ADMIN_PASSWORD=changeme       # if unset, a random password is
                                         # generated and logged at WARNING level
```

The login form is at `/login`.

### OIDC / Keycloak

Set these four vars to enable SSO. The password form is still available as a
fallback behind a `<details>` toggle.

```
STATUSPAGE_OIDC_ISSUER_URL=https://keycloak.example.com/realms/myrealm
STATUSPAGE_OIDC_CLIENT_ID=statuspage
STATUSPAGE_OIDC_CLIENT_SECRET=<secret>
STATUSPAGE_OIDC_PROVIDER_NAME=Keycloak   # optional — changes the button label
```

**Keycloak client settings**:
- Access type: **Confidential**
- Valid redirect URI: `{BASE_URL}/auth/oidc/callback`
  (e.g. `https://status.example.com/auth/oidc/callback`)

**How it works**: `GET /auth/oidc/login` redirects to Keycloak. After the user
authenticates, Keycloak redirects back to `GET /auth/oidc/callback`. The backend
exchanges the code for an access token, fetches `/userinfo`, and creates a
session — no JWT validation needed on our side (confidential client flow).
Because the callback is a direct browser redirect (not a proxied SSR fetch),
the backend can set the session cookie directly in the response.

Username is taken from `preferred_username`, falling back to `email`, then `sub`.
## Database migrations

```bash
cd backend

# generate a new migration after model changes
uv run alembic revision --autogenerate -m "description"

# apply all pending migrations
uv run alembic upgrade head
```

## Pages

| URL | Description |
|---|---|
| `/` | Public status page — service health + active incidents |
| `/admin` | Admin UI — create/edit/delete services and incidents |
| `/private` | Private status page — same as `/` but shows all services including non-public ones (requires auth) |
| `/api/services` | REST API |
| `/api/incidents` | REST API |
| `/docs` | Auto-generated OpenAPI UI |


## Pitfalls

### Datetime serialization — always UTC-aware

`datetime.datetime.utcnow()` returns a naive `datetime` (no `tzinfo`). Pydantic serializes
naive datetimes without a timezone marker, and browsers parse timezone-naive ISO 8601
strings as **local time**, not UTC. A service checked 5 seconds ago appears "1h ago" for a
user in UTC+1.

All response models (`ServiceOut`, `IncidentOut`) carry a `field_validator` that stamps
`tzinfo=datetime.timezone.utc` on any naive datetime before serialization. Pydantic then
emits `+00:00`-suffixed strings which browsers parse correctly. Do not remove those
validators or switch back to naive datetimes.

### Alembic `script_location` must be absolute

`alembic.ini` contains `script_location = alembic` (relative). In any environment where
the working directory is not the directory containing `alembic.ini` (systemd services,
Nix store paths), alembic cannot find the migrations directory. `perform_db_upgrade()` in
`main.py` overrides `script_location` to an absolute path derived from `ALEMBIC_INI_PATH`.

### `fileConfig` in `alembic/env.py` — keep `disable_existing_loggers=False`

`logging.config.fileConfig()` defaults to `disable_existing_loggers=True`. When alembic
runs migrations during startup it silently kills all existing loggers including uvicorn's.
The call in `alembic/env.py` explicitly passes `disable_existing_loggers=False`; do not
revert that.

### `lifespan` must contain `yield` directly

`@asynccontextmanager` requires the decorated function to be an async generator — it must
contain a `yield`. Delegating to a sub-coroutine (no `yield` in the decorated function)
makes it a plain coroutine and FastAPI raises a runtime error on startup.

### `frontend_path` assert must not run for binary-path deployments

In Nix deployments `STATUSPAGE_FRONTEND_BINARY_PATH` is set and the pre-built Node binary
is executed directly. The `frontend_path.exists()` assert (which checks for the source
`frontend/` directory) must only run in the dev/build-from-source branches, never in the
binary-path branch.