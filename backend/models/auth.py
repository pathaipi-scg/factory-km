"""Framework-neutral authentication and authorization domain models."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class User:
    """Persistent identity independent from authentication credentials."""

    id: str
    username: str
    display_name: str
    active: bool = True


@dataclass(frozen=True)
class Group:
    """Named collection of users used for organizational authorization."""

    id: str
    name: str
    description: str = ""


@dataclass(frozen=True)
class Role:
    """Named authorization role with explicit permissions."""

    id: str
    name: str
    permissions: tuple[str, ...] = ()
    description: str = ""


@dataclass(frozen=True)
class UserGroupMembership:
    """Direct relationship between a user and a group."""

    user_id: str
    group_id: str
    created_at: datetime | None = None


@dataclass(frozen=True)
class UserRoleMembership:
    """Direct relationship between a user and a role."""

    user_id: str
    role_id: str
    scope: str | None = None
    created_at: datetime | None = None


@dataclass(frozen=True)
class AuthenticatedUser:
    """Resolved user identity and authorization context for one request."""

    user: User
    groups: tuple[Group, ...] = ()
    roles: tuple[Role, ...] = ()
    scopes: tuple[str, ...] = ()
    session_id: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    def has_role(self, role: str) -> bool:
        """Return whether a resolved role matches by ID or name."""
        return any(item.id == role or item.name == role for item in self.roles)

    def has_permission(self, permission: str) -> bool:
        """Return whether any resolved role grants a permission."""
        return any(permission in role.permissions for role in self.roles)

    def has_scope(self, scope: str) -> bool:
        """Return whether the request identity includes a scope."""
        return scope in self.scopes


CurrentUser = AuthenticatedUser


@dataclass(frozen=True)
class Session:
    """Server-side session identity without exposing its secret token."""

    id: str
    user_id: str
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None
    viewer: bool = False
    metadata: dict[str, str] = field(default_factory=dict)

    def is_active(self, now: datetime) -> bool:
        """Return whether the session is usable at the supplied time."""
        return self.revoked_at is None and now < self.expires_at
