"""Microsoft SQL Server implementations of authentication repositories."""

import json
from datetime import datetime, timezone
from typing import Any

from backend.models.auth import (
    Group,
    Role,
    Session,
    User,
    UserGroupMembership,
    UserRoleMembership,
)
from backend.repositories.auth.mssql.database import AuthMSSQLDatabase


def _utc_naive(value: datetime | None = None) -> datetime:
    resolved = value or datetime.now(timezone.utc)
    if resolved.tzinfo is None:
        return resolved
    return resolved.astimezone(timezone.utc).replace(tzinfo=None)


def _utc_aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _rows(cursor: Any) -> list[dict[str, Any]]:
    names = [str(column[0]).lower() for column in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def _row(cursor: Any) -> dict[str, Any] | None:
    names = [str(column[0]).lower() for column in cursor.description]
    value = cursor.fetchone()
    return dict(zip(names, value)) if value is not None else None


class MSSQLUserRepository:
    def __init__(self, database: AuthMSSQLDatabase) -> None:
        self._database = database

    def create(self, user: User, password_hash: str) -> User:
        if not password_hash.startswith("$argon2id$"):
            raise ValueError("Only encoded Argon2id password hashes may be stored.")
        with self._database.connect() as connection:
            connection.cursor().execute(
                """
                INSERT INTO auth.Users
                    (Id, Username, DisplayName, PasswordHash, Active, CreatedAt)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                user.id,
                user.username,
                user.display_name,
                password_hash,
                user.active,
                _utc_naive(),
            )
        return user

    def get_by_id(self, user_id: str) -> User | None:
        return self._get("SELECT * FROM auth.Users WHERE Id = ?", user_id)

    def get_by_username(self, username: str) -> User | None:
        return self._get("SELECT * FROM auth.Users WHERE Username = ?", username)

    def get_password_hash(self, user_id: str) -> str | None:
        with self._database.connect() as connection:
            cursor = connection.cursor()
            cursor.execute("SELECT PasswordHash FROM auth.Users WHERE Id = ?", user_id)
            row = _row(cursor)
        return str(row["passwordhash"]) if row else None

    def count(self) -> int:
        with self._database.connect() as connection:
            cursor = connection.cursor()
            cursor.execute("SELECT COUNT(*) AS Total FROM auth.Users")
            row = _row(cursor)
        return int(row["total"]) if row else 0

    def _get(self, sql: str, value: str) -> User | None:
        with self._database.connect() as connection:
            cursor = connection.cursor()
            cursor.execute(sql, value)
            row = _row(cursor)
        if not row:
            return None
        return User(
            str(row["id"]),
            str(row["username"]),
            str(row["displayname"]),
            bool(row["active"]),
        )


class MSSQLGroupRepository:
    def __init__(self, database: AuthMSSQLDatabase) -> None:
        self._database = database

    def create(self, group: Group) -> Group:
        with self._database.connect() as connection:
            connection.cursor().execute(
                """
                INSERT INTO auth.Groups(Id, Name, Description, CreatedAt)
                VALUES (?, ?, ?, ?)
                """,
                group.id,
                group.name,
                group.description,
                _utc_naive(),
            )
        return group

    def list_for_user(self, user_id: str) -> tuple[Group, ...]:
        with self._database.connect() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT groups.* FROM auth.Groups AS groups
                JOIN auth.UserGroupMemberships AS membership
                  ON membership.GroupId = groups.Id
                WHERE membership.UserId = ? ORDER BY groups.Name
                """,
                user_id,
            )
            rows = _rows(cursor)
        return tuple(
            Group(str(row["id"]), str(row["name"]), str(row["description"]))
            for row in rows
        )


class MSSQLRoleRepository:
    def __init__(self, database: AuthMSSQLDatabase) -> None:
        self._database = database

    def create(self, role: Role) -> Role:
        with self._database.connect() as connection:
            connection.cursor().execute(
                """
                INSERT INTO auth.Roles
                    (Id, Name, PermissionsJson, Description, CreatedAt)
                VALUES (?, ?, ?, ?, ?)
                """,
                role.id,
                role.name,
                json.dumps(role.permissions),
                role.description,
                _utc_naive(),
            )
        return role

    def get_by_name(self, name: str) -> Role | None:
        with self._database.connect() as connection:
            cursor = connection.cursor()
            cursor.execute("SELECT * FROM auth.Roles WHERE Name = ?", name)
            row = _row(cursor)
        return self._to_role(row) if row else None

    def list_for_user(self, user_id: str) -> tuple[Role, ...]:
        with self._database.connect() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT DISTINCT roles.* FROM auth.Roles AS roles
                JOIN auth.UserRoleMemberships AS membership
                  ON membership.RoleId = roles.Id
                WHERE membership.UserId = ? ORDER BY roles.Name
                """,
                user_id,
            )
            rows = _rows(cursor)
        return tuple(self._to_role(row) for row in rows)

    @staticmethod
    def _to_role(row: dict[str, Any]) -> Role:
        return Role(
            str(row["id"]),
            str(row["name"]),
            tuple(json.loads(row["permissionsjson"])),
            str(row["description"]),
        )


class MSSQLMembershipRepository:
    def __init__(self, database: AuthMSSQLDatabase) -> None:
        self._database = database

    def add_group_membership(self, membership: UserGroupMembership) -> UserGroupMembership:
        with self._database.connect() as connection:
            connection.cursor().execute(
                """
                INSERT INTO auth.UserGroupMemberships(UserId, GroupId, CreatedAt)
                VALUES (?, ?, ?)
                """,
                membership.user_id,
                membership.group_id,
                _utc_naive(membership.created_at),
            )
        return membership

    def add_role_membership(self, membership: UserRoleMembership) -> UserRoleMembership:
        with self._database.connect() as connection:
            connection.cursor().execute(
                """
                INSERT INTO auth.UserRoleMemberships(UserId, RoleId, Scope, CreatedAt)
                VALUES (?, ?, ?, ?)
                """,
                membership.user_id,
                membership.role_id,
                membership.scope or "",
                _utc_naive(membership.created_at),
            )
        return membership

    def list_group_memberships(self, user_id: str) -> tuple[UserGroupMembership, ...]:
        with self._database.connect() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT * FROM auth.UserGroupMemberships
                WHERE UserId = ? ORDER BY GroupId
                """,
                user_id,
            )
            rows = _rows(cursor)
        return tuple(
            UserGroupMembership(
                str(row["userid"]),
                str(row["groupid"]),
                _utc_aware(row["createdat"]),
            )
            for row in rows
        )

    def list_role_memberships(self, user_id: str) -> tuple[UserRoleMembership, ...]:
        with self._database.connect() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT * FROM auth.UserRoleMemberships
                WHERE UserId = ? ORDER BY RoleId, Scope
                """,
                user_id,
            )
            rows = _rows(cursor)
        return tuple(
            UserRoleMembership(
                str(row["userid"]),
                str(row["roleid"]),
                str(row["scope"]) or None,
                _utc_aware(row["createdat"]),
            )
            for row in rows
        )


class MSSQLSessionRepository:
    def __init__(self, database: AuthMSSQLDatabase) -> None:
        self._database = database

    def create(self, session: Session, token_digest: str) -> Session:
        if len(token_digest) != 64 or any(character not in "0123456789abcdef" for character in token_digest):
            raise ValueError("Session token digest must be a lowercase SHA-256 digest.")
        with self._database.connect() as connection:
            connection.cursor().execute(
                """
                INSERT INTO auth.Sessions
                    (Id, UserId, TokenDigest, CreatedAt, ExpiresAt,
                     RevokedAt, Viewer, MetadataJson)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                session.id,
                session.user_id,
                token_digest,
                _utc_naive(session.created_at),
                _utc_naive(session.expires_at),
                _utc_naive(session.revoked_at) if session.revoked_at else None,
                session.viewer,
                json.dumps(session.metadata),
            )
        return session

    def get_by_token_digest(self, token_digest: str) -> Session | None:
        with self._database.connect() as connection:
            cursor = connection.cursor()
            cursor.execute(
                "SELECT * FROM auth.Sessions WHERE TokenDigest = ?",
                token_digest,
            )
            row = _row(cursor)
        if not row:
            return None
        return Session(
            str(row["id"]),
            str(row["userid"]),
            _utc_aware(row["createdat"]),  # type: ignore[arg-type]
            _utc_aware(row["expiresat"]),  # type: ignore[arg-type]
            _utc_aware(row["revokedat"]),
            bool(row["viewer"]),
            dict(json.loads(row["metadatajson"])),
        )

    def revoke(self, session_id: str, revoked_at: datetime) -> bool:
        with self._database.connect() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                UPDATE auth.Sessions SET RevokedAt = ?
                WHERE Id = ? AND RevokedAt IS NULL
                """,
                _utc_naive(revoked_at),
                session_id,
            )
            affected = cursor.rowcount
        return affected == 1
