"""Framework-neutral authentication service interfaces."""

from typing import Protocol, runtime_checkable

from backend.models.auth import AuthenticatedUser, Session, User


@runtime_checkable
class AuthenticationService(Protocol):
    """Validate credentials without creating transport-specific responses."""

    def authenticate(self, username: str, password: str) -> User | None: ...

    def authenticate_viewer(self) -> User: ...


@runtime_checkable
class SessionService(Protocol):
    """Create, validate, and revoke opaque server-side sessions."""

    def create(self, user: User, *, viewer: bool = False) -> tuple[Session, str]: ...

    def validate(self, token: str) -> Session | None: ...

    def revoke(self, token: str) -> bool: ...


@runtime_checkable
class CurrentUserService(Protocol):
    """Resolve a validated session into request authorization context."""

    def resolve(self, token: str) -> AuthenticatedUser | None: ...
