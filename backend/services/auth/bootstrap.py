"""Explicit first-admin bootstrap for authentication persistence."""

from dataclasses import dataclass
import secrets
from uuid import NAMESPACE_URL, uuid5

from backend.config.auth import AuthSettings
from backend.db.mssql import MSSQLConnectionFactory
from backend.models.auth import Role, User, UserRoleMembership
from backend.repositories.auth.mssql import (
    AuthMSSQLDatabase,
    MSSQLMembershipRepository,
    MSSQLRoleRepository,
    MSSQLUserRepository,
)
from backend.services.auth.passwords import PasswordHasher


ADMIN_PERMISSIONS = (
    "auth.admin",
    "vault.list",
    "vault.create_folder",
    "vault.upload",
    "vault.rename",
    "vault.move",
    "vault.edit",
    "vault.soft_delete",
    "vault.restore",
)


@dataclass(frozen=True)
class BootstrapResult:
    """Identity created by one successful explicit bootstrap."""

    user: User
    role: Role


def bootstrap_first_admin(
    settings: AuthSettings,
    *,
    username: str,
    password: str,
    display_name: str,
    password_hasher: PasswordHasher | None = None,
) -> BootstrapResult:
    """Initialize exactly one first admin when explicitly called."""
    normalized_username = username.strip()
    if not normalized_username:
        raise ValueError("Admin username is required.")
    if len(password) < 12:
        raise ValueError("Admin password must contain at least 12 characters.")
    if not display_name.strip():
        raise ValueError("Admin display name is required.")

    if settings.mssql is None:
        raise RuntimeError("Shared SQL Server settings are not configured.")
    database = AuthMSSQLDatabase(MSSQLConnectionFactory(settings.mssql))
    database.initialize()
    users = MSSQLUserRepository(database)
    if users.count() != 0:
        raise RuntimeError("Admin bootstrap is disabled after the first user exists.")

    user = User(
        id=str(uuid5(NAMESPACE_URL, f"factory-km:auth:user:{normalized_username.lower()}")),
        username=normalized_username,
        display_name=display_name.strip(),
    )
    role = Role(
        id=str(uuid5(NAMESPACE_URL, "factory-km:auth:role:admin")),
        name="admin",
        permissions=ADMIN_PERMISSIONS,
        description="Factory-KM administrator",
    )
    hasher = password_hasher or PasswordHasher()
    users.create(user, hasher.hash(password))
    viewer = User(
        id=str(uuid5(NAMESPACE_URL, "factory-km:auth:user:viewer")),
        username="viewer",
        display_name="ผู้ชม (Viewer)",
    )
    users.create(viewer, hasher.hash(secrets.token_urlsafe(48)))
    MSSQLRoleRepository(database).create(role)
    MSSQLMembershipRepository(database).add_role_membership(
        UserRoleMembership(user.id, role.id)
    )
    return BootstrapResult(user=user, role=role)
