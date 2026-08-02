"""FastAPI dependency contracts for future authentication migration."""

from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status

from backend.config.auth import AuthSettings
from backend.models.auth import CurrentUser
from backend.services.auth.composition import AuthRuntime, create_auth_runtime


def get_auth_settings(request: Request) -> AuthSettings:
    """Load app-bound settings or the disabled-by-default environment values."""
    configured = getattr(request.app.state, "auth_settings", None)
    return configured if isinstance(configured, AuthSettings) else AuthSettings.from_environment()


def get_auth_runtime(
    settings: AuthSettings = Depends(get_auth_settings),
) -> AuthRuntime:
    """Compose auth services only when the migration flag is enabled."""
    if not settings.fastapi_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="FastAPI authentication is disabled.",
        )
    return create_auth_runtime(settings)


async def get_current_user(
    request: Request,
    runtime: AuthRuntime = Depends(get_auth_runtime),
) -> CurrentUser:
    """Resolve the current user from the compatibility session cookie."""
    token = request.cookies.get("km_session", "")
    current_user = runtime.current_users.resolve(token)
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return current_user


def require_role(role: str) -> Callable[..., CurrentUser]:
    """Create a dependency requiring a resolved role ID or name."""

    async def dependency(
        current_user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        if not current_user.has_role(role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required role: {role}",
            )
        return current_user

    return dependency


def require_permission(permission: str) -> Callable[..., CurrentUser]:
    """Create a dependency requiring an explicit role permission."""

    async def dependency(
        current_user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        if not current_user.has_permission(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required permission: {permission}",
            )
        return current_user

    return dependency


def require_scope(scope: str) -> Callable[..., CurrentUser]:
    """Create a dependency requiring an explicit authorization scope."""

    async def dependency(
        current_user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        if not current_user.has_scope(scope):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required scope: {scope}",
            )
        return current_user

    return dependency
