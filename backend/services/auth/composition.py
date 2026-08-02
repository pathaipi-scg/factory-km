"""Disabled-by-default runtime composition for FastAPI authentication."""

from dataclasses import dataclass
import sqlite3

from backend.config.auth import AuthSettings
from backend.db.auth_migrations import MIGRATIONS
from backend.repositories.auth.sqlite import (
    AuthSQLiteDatabase,
    SQLiteGroupRepository,
    SQLiteMembershipRepository,
    SQLiteRoleRepository,
    SQLiteSessionRepository,
    SQLiteUserRepository,
)
from backend.services.auth.services import (
    SQLiteAuthenticationService,
    SQLiteCurrentUserService,
    SQLiteSessionService,
)


@dataclass(frozen=True)
class AuthRuntime:
    """Concrete services used by the disabled compatibility router."""

    authentication: SQLiteAuthenticationService
    sessions: SQLiteSessionService
    current_users: SQLiteCurrentUserService


@dataclass(frozen=True)
class AuthDatabaseStatus:
    """Non-sensitive reachability and migration state."""

    reachable: bool
    schema_initialized: bool


def create_auth_runtime(settings: AuthSettings) -> AuthRuntime:
    """Compose SQLite auth services only when explicitly enabled."""
    if not settings.fastapi_enabled:
        raise RuntimeError("FastAPI authentication is disabled.")
    database = AuthSQLiteDatabase(settings.sqlite_path)
    database.initialize()
    users = SQLiteUserRepository(database)
    groups = SQLiteGroupRepository(database)
    roles = SQLiteRoleRepository(database)
    memberships = SQLiteMembershipRepository(database)
    sessions = SQLiteSessionService(
        SQLiteSessionRepository(database),
        max_age_seconds=settings.session_max_age_seconds,
    )
    return AuthRuntime(
        authentication=SQLiteAuthenticationService(users),
        sessions=sessions,
        current_users=SQLiteCurrentUserService(
            sessions,
            users,
            groups,
            roles,
            memberships,
        ),
    )


def inspect_auth_database(settings: AuthSettings) -> AuthDatabaseStatus:
    """Inspect database availability without initializing or migrating it."""
    database = AuthSQLiteDatabase(settings.sqlite_path)
    try:
        with database.connect() as connection:
            connection.execute("SELECT 1").fetchone()
            migration_table = connection.execute(
                """
                SELECT 1 FROM sqlite_master
                WHERE type = 'table' AND name = 'schema_migrations'
                """
            ).fetchone()
            if not migration_table:
                return AuthDatabaseStatus(True, False)
            latest_version = max(version for version, _ in MIGRATIONS)
            migration = connection.execute(
                """
                SELECT 1 FROM schema_migrations
                WHERE component = 'auth' AND version = ?
                """,
                (latest_version,),
            ).fetchone()
            required_tables = {
                "users",
                "groups",
                "roles",
                "user_group_memberships",
                "user_role_memberships",
                "sessions",
            }
            existing_tables = {
                str(row["name"])
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            return AuthDatabaseStatus(
                True,
                migration is not None and required_tables.issubset(existing_tables),
            )
    except (OSError, sqlite3.Error):
        return AuthDatabaseStatus(False, False)
