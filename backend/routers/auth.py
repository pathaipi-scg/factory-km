"""Disabled, unregistered Node-compatible FastAPI authentication endpoints."""

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import JSONResponse

from backend.config.auth import AuthSettings
from backend.dependencies.auth import get_auth_runtime, get_auth_settings
from backend.models.auth import AuthenticatedUser
from backend.services.auth.composition import (
    AuthRuntime,
    inspect_auth_database,
)

router = APIRouter()


def register_auth_router(
    app: FastAPI, settings: AuthSettings | None = None
) -> bool:
    """Register the isolated auth surface only when explicitly enabled."""
    resolved_settings = settings or AuthSettings.from_environment()
    if not resolved_settings.fastapi_enabled:
        return False
    app.state.auth_settings = resolved_settings
    app.include_router(router, prefix="/api/auth-v2")
    return True


def _login_response(
    *,
    token: str,
    role: str,
    name: str,
    settings: AuthSettings,
) -> JSONResponse:
    response = JSONResponse(
        content={"success": True, "role": role, "name": name}
    )
    response.set_cookie(
        key="km_session",
        value=token,
        max_age=settings.session_max_age_seconds,
        path="/",
        httponly=True,
        samesite="lax",
    )
    return response


@router.post("/login")
async def login(
    request: Request,
    runtime: AuthRuntime = Depends(get_auth_runtime),
    settings: AuthSettings = Depends(get_auth_settings),
) -> JSONResponse:
    """Authenticate credentials using the existing Node response contract."""
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    username = payload.get("username", "") if isinstance(payload, dict) else ""
    password = payload.get("password", "") if isinstance(payload, dict) else ""
    username = username if isinstance(username, str) else ""
    password = password if isinstance(password, str) else ""
    user = runtime.authentication.authenticate(username, password)
    if not user:
        return JSONResponse(
            status_code=401,
            content={
                "success": False,
                "error": "username หรือ password ไม่ถูกต้อง",
            },
        )
    _, token = runtime.sessions.create(user)
    current_user = runtime.current_users.resolve(token)
    role = _legacy_role(current_user) if current_user else user.username
    return _login_response(
        token=token,
        role=role,
        name=user.display_name,
        settings=settings,
    )


@router.post("/login/viewer")
def login_viewer(
    runtime: AuthRuntime = Depends(get_auth_runtime),
    settings: AuthSettings = Depends(get_auth_settings),
) -> JSONResponse:
    """Create a passwordless read-only viewer session."""
    user = runtime.authentication.authenticate_viewer()
    _, token = runtime.sessions.create(user, viewer=True)
    return _login_response(
        token=token,
        role="viewer",
        name=user.display_name,
        settings=settings,
    )


@router.post("/logout")
def logout(
    request: Request,
    runtime: AuthRuntime = Depends(get_auth_runtime),
) -> JSONResponse:
    """Revoke the current session and clear the compatibility cookie."""
    token = request.cookies.get("km_session", "")
    runtime.sessions.revoke(token)
    return JSONResponse(
        content={"success": True},
        headers={"Set-Cookie": "km_session=; HttpOnly; Path=/; Max-Age=0"},
    )


@router.get("/me")
def current_user(
    request: Request,
    runtime: AuthRuntime = Depends(get_auth_runtime),
) -> JSONResponse:
    """Return the existing current-user response shape."""
    token = request.cookies.get("km_session", "")
    resolved = runtime.current_users.resolve(token)
    if not resolved:
        return JSONResponse(status_code=401, content={"loggedIn": False})
    return JSONResponse(
        content={
            "loggedIn": True,
            "username": resolved.user.username,
            "role": _legacy_role(resolved),
            "name": resolved.user.display_name,
        }
    )


@router.get("/status")
def auth_status(
    settings: AuthSettings = Depends(get_auth_settings),
) -> dict[str, bool]:
    """Report only enablement, database reachability, and schema state."""
    database = inspect_auth_database(settings)
    return {
        "enabled": settings.fastapi_enabled,
        "database_reachable": database.reachable,
        "schema_initialized": database.schema_initialized,
    }


def _legacy_role(current_user: AuthenticatedUser) -> str:
    if current_user.metadata.get("viewer") == "true":
        return "viewer"
    return current_user.roles[0].name if current_user.roles else current_user.user.username
