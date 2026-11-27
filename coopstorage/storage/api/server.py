"""
Env-driven entry point for hosted deployments (uvicorn --factory).

Every route except /health and /auth/* requires a Google sign-in whose verified
email is in ALLOWED_EMAILS. The session cookie holds only the email.

Required env: GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, SESSION_SECRET, ALLOWED_EMAILS
(comma-separated). Optional: DATABASE_URL (mounts /v2 layouts on Postgres),
COOPSTORAGE_BUILD_VERSION, SESSION_HTTPS_ONLY (default true), LOG_LEVEL (default INFO).
"""
import logging
import os
from typing import FrozenSet

from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from starlette.middleware.sessions import SessionMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from coopstorage.storage.api.api_factory import storage_api_factory
from coopstorage.storage.layout_manager import postgres_layout_manager

logger = logging.getLogger(__name__)

GOOGLE_METADATA_URL = "https://accounts.google.com/.well-known/openid-configuration"
SESSION_MAX_AGE_SECONDS = 14 * 24 * 3600
HOME_PATH = "/static/index.html"


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} must be set to run the hosted server")
    return value


def _allowed_emails() -> FrozenSet[str]:
    emails = frozenset(e.strip().lower() for e in _required_env("ALLOWED_EMAILS").split(",") if e.strip())
    if not emails:
        raise RuntimeError("ALLOWED_EMAILS must list at least one email")
    return emails


class RequireAllowedUser:
    """
    Pure ASGI gate (not BaseHTTPMiddleware, so SSE streams pass through untouched).
    Must sit inside SessionMiddleware, which populates scope["session"].
    """

    def __init__(self, app: ASGIApp, allowed_emails: FrozenSet[str]):
        self.app = app
        self.allowed_emails = allowed_emails

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http" or scope["path"] == "/health" or scope["path"].startswith("/auth/"):
            await self.app(scope, receive, send)
            return

        if scope.get("session", {}).get("email") in self.allowed_emails:
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        if request.method == "GET" and "text/html" in request.headers.get("accept", ""):
            response: Response = RedirectResponse("/auth/login", status_code=303)
        else:
            response = JSONResponse({"code": "not_signed_in", "message": "Sign in to continue."}, status_code=401)
        await response(scope, receive, send)


def auth_router(client_id: str, client_secret: str, allowed_emails: FrozenSet[str]) -> APIRouter:
    router = APIRouter(prefix="/auth")
    oauth = OAuth()
    oauth.register(
        name="google",
        server_metadata_url=GOOGLE_METADATA_URL,
        client_id=client_id,
        client_secret=client_secret,
        client_kwargs={"scope": "openid email"},
    )

    @router.get("/login")
    async def login(request: Request) -> Response:
        return await oauth.google.authorize_redirect(request, str(request.url_for("auth_callback")))

    @router.get("/callback", name="auth_callback")
    async def callback(request: Request) -> Response:
        try:
            token = await oauth.google.authorize_access_token(request)
        except OAuthError as exc:
            logger.warning("google sign-in failed: %s", exc.error)
            return JSONResponse({"code": "login_failed", "message": "Google sign-in failed."}, status_code=401)
        info = token.get("userinfo") or {}
        email = str(info.get("email", "")).lower()
        request.session.clear()
        if not info.get("email_verified") or email not in allowed_emails:
            logger.warning("sign-in refused for an account not on the allowlist")
            return JSONResponse({"code": "login_denied", "message": "This account is not allowed."}, status_code=403)
        request.session["email"] = email
        return RedirectResponse(HOME_PATH, status_code=303)

    @router.post("/logout", status_code=204)
    async def logout(request: Request) -> None:
        request.session.clear()

    return router


def create_app() -> FastAPI:
    # uvicorn configures only its own loggers; without this, app and Alembic INFO lines never reach stdout.
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO").upper(),
                        format="%(levelname)s %(name)s: %(message)s")
    allowed_emails = _allowed_emails()
    client_id = _required_env("GOOGLE_CLIENT_ID")
    client_secret = _required_env("GOOGLE_CLIENT_SECRET")
    session_secret = _required_env("SESSION_SECRET")
    https_only = os.environ.get("SESSION_HTTPS_ONLY", "true").lower() != "false"

    layout_manager = postgres_layout_manager() if os.environ.get("DATABASE_URL") else None
    app = storage_api_factory(layout_manager=layout_manager)
    version = os.environ.get("COOPSTORAGE_BUILD_VERSION", "unknown")

    @app.get("/health")
    def health():
        return {"status": "ok", "version": version}

    app.include_router(auth_router(client_id, client_secret, allowed_emails))

    # add_middleware wraps outward: the gate is added first so SessionMiddleware runs before it.
    app.add_middleware(RequireAllowedUser, allowed_emails=allowed_emails)
    app.add_middleware(
        SessionMiddleware,
        secret_key=session_secret,
        session_cookie="coopstorage_session",
        max_age=SESSION_MAX_AGE_SECONDS,
        same_site="lax",
        https_only=https_only,
    )
    return app
