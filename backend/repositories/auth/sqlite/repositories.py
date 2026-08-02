"""Concrete SQLite repositories for authentication persistence."""

import json
from datetime import datetime, timezone

from backend.models.auth import (
    Group,
    Role,
    Session,
    User,
    UserGroupMembership,
    UserRoleMembership,
)
from backend.repositories.auth.sqlite.database import AuthSQLiteDatabase


def _timestamp(value: datetime | None = None) -> str:
    return (value or datetime.now(timezone.utc)).isoformat()


def _datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


class SQLiteUserRepository:
    """Persist users and their Argon2 password hashes."""

    def __init__(self, database: AuthSQLiteDatabase) -> None:
        self._database = database

    def create(self, user: User, password_hash: str) -> User:
        if not password_hash.startswith("$argon2id$"):
            raise ValueError("Only encoded Argon2id password hashes may be stored.")
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO users(
                    id, username, display_name, password_hash, active, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    user.id,
                    user.username,
                    user.display_name,
                    password_hash,
                    int(user.active),
                    _timestamp(),
                ),
            )
        return user

    def get_by_id(self, user_id: str) -> User | None:
        return self._get("SELECT * FROM users WHERE id = ?", user_id)

    def get_by_username(self, username: str) -> User | None:
        return self._get("SELECT * FROM users WHERE username = ?", username)

    def get_password_hash(self, user_id: str) -> str | None:
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT password_hash FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        return str(row["password_hash"]) if row else None

    def count(self) -> int:
        with self._database.connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS total FROM users").fetchone()
        return int(row["total"])

    def _get(self, sql: str, value: str) -> User | None:
        with self._database.connect() as connection:
            row = connection.execute(sql, (value,)).fetchone()
        return (
            User(
                id=str(row["id"]),
                username=str(row["username"]),
                display_name=str(row["display_name"]),
                active=bool(row["active"]),
            )
            if row
            else None
        )


class SQLiteGroupRepository:
    """Persist groups and resolve a user's group collection."""

    def __init__(self, database: AuthSQLiteDatabase) -> None:
        self._database = database

    def create(self, group: Group) -> Group:
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO groups(id, name, description, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (group.id, group.name, group.description, _timestamp()),
            )
        return group

    def list_for_user(self, user_id: str) -> tuple[Group, ...]:
        with self._database.connect() as connection:
            rows = connection.execute(
                """
                SELECT groups.* FROM groups
                JOIN user_group_memberships membership
                  ON membership.group_id = groups.id
                WHERE membership.user_id = ?
                ORDER BY groups.name
                """,
                (user_id,),
            ).fetchall()
        return tuple(
            Group(str(row["id"]), str(row["name"]), str(row["description"]))
            for row in rows
        )


class SQLiteRoleRepository:
    """Persist roles and resolve a user's role collection."""

    def __init__(self, database: AuthSQLiteDatabase) -> None:
        self._database = database

    def create(self, role: Role) -> Role:
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO roles(
                    id, name, permissions_json, description, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    role.id,
                    role.name,
                    json.dumps(role.permissions),
                    role.description,
                    _timestamp(),
                ),
            )
        return role

    def get_by_name(self, name: str) -> Role | None:
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM roles WHERE name = ?", (name,)
            ).fetchone()
        return self._to_role(row) if row else None

    def list_for_user(self, user_id: str) -> tuple[Role, ...]:
        with self._database.connect() as connection:
            rows = connection.execute(
                """
                SELECT DISTINCT roles.* FROM roles
                JOIN user_role_memberships membership
                  ON membership.role_id = roles.id
                WHERE membership.user_id = ?
                ORDER BY roles.name
                """,
                (user_id,),
            ).fetchall()
        return tuple(self._to_role(row) for row in rows)

    @staticmethod
    def _to_role(row: object) -> Role:
        return Role(
            id=str(row["id"]),  # type: ignore[index]
            name=str(row["name"]),  # type: ignore[index]
            permissions=tuple(json.loads(row["permissions_json"])),  # type: ignore[index]
            description=str(row["description"]),  # type: ignore[index]
        )


class SQLiteMembershipRepository:
    """Persist and query direct group and role memberships."""

    def __init__(self, database: AuthSQLiteDatabase) -> None:
        self._database = database

    def add_group_membership(
        self, membership: UserGroupMembership
    ) -> UserGroupMembership:
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO user_group_memberships(user_id, group_id, created_at)
                VALUES (?, ?, ?)
                """,
                (
                    membership.user_id,
                    membership.group_id,
                    _timestamp(membership.created_at),
                ),
            )
        return membership

    def add_role_membership(
        self, membership: UserRoleMembership
    ) -> UserRoleMembership:
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO user_role_memberships(
                    user_id, role_id, scope, created_at
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    membership.user_id,
                    membership.role_id,
                    membership.scope or "",
                    _timestamp(membership.created_at),
                ),
            )
        return membership

    def list_group_memberships(
        self, user_id: str
    ) -> tuple[UserGroupMembership, ...]:
        with self._database.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM user_group_memberships
                WHERE user_id = ? ORDER BY group_id
                """,
                (user_id,),
            ).fetchall()
        return tuple(
            UserGroupMembership(
                str(row["user_id"]),
                str(row["group_id"]),
                _datetime(row["created_at"]),
            )
            for row in rows
        )

    def list_role_memberships(
        self, user_id: str
    ) -> tuple[UserRoleMembership, ...]:
        with self._database.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM user_role_memberships
                WHERE user_id = ? ORDER BY role_id, scope
                """,
                (user_id,),
            ).fetchall()
        return tuple(
            UserRoleMembership(
                str(row["user_id"]),
                str(row["role_id"]),
                str(row["scope"]) or None,
                _datetime(row["created_at"]),
            )
            for row in rows
        )


class SQLiteSessionRepository:
    """Persist opaque-session digests and lifecycle state."""

    def __init__(self, database: AuthSQLiteDatabase) -> None:
        self._database = database

    def create(self, session: Session, token_digest: str) -> Session:
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO sessions(
                    id, user_id, token_digest, created_at, expires_at,
                    revoked_at, viewer, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session.id,
                    session.user_id,
                    token_digest,
                    _timestamp(session.created_at),
                    _timestamp(session.expires_at),
                    _timestamp(session.revoked_at) if session.revoked_at else None,
                    int(session.viewer),
                    json.dumps(session.metadata),
                ),
            )
        return session

    def get_by_token_digest(self, token_digest: str) -> Session | None:
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM sessions WHERE token_digest = ?", (token_digest,)
            ).fetchone()
        if not row:
            return None
        return Session(
            id=str(row["id"]),
            user_id=str(row["user_id"]),
            created_at=_datetime(row["created_at"]),  # type: ignore[arg-type]
            expires_at=_datetime(row["expires_at"]),  # type: ignore[arg-type]
            revoked_at=_datetime(row["revoked_at"]),
            viewer=bool(row["viewer"]),
            metadata=dict(json.loads(row["metadata_json"])),
        )

    def revoke(self, session_id: str, revoked_at: datetime) -> bool:
        with self._database.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE sessions SET revoked_at = ?
                WHERE id = ? AND revoked_at IS NULL
                """,
                (_timestamp(revoked_at), session_id),
            )
        return cursor.rowcount == 1
