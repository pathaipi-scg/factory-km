"""Disabled-by-default SQL Server composition for FastAPI authentication."""

from dataclasses import dataclass

from backend.config.auth import AuthSettings
from backend.db.auth_mssql_migrations import AUTH_MSSQL_MIGRATIONS
from backend.db.mssql import MSSQLConnectionFactory
from backend.repositories.auth.mssql import (
    AuthMSSQLDatabase,
    MSSQLGroupRepository,
    MSSQLMembershipRepository,
    MSSQLRoleRepository,
    MSSQLSessionRepository,
    MSSQLUserRepository,
)
from backend.services.auth.services import (
    RepositoryAuthenticationService,
    RepositoryCurrentUserService,
    RepositorySessionService,
)


@dataclass(frozen=True)
class AuthRuntime:
    """Concrete services used by the disabled compatibility router."""

    authentication: RepositoryAuthenticationService
    sessions: RepositorySessionService
    current_users: RepositoryCurrentUserService


@dataclass(frozen=True)
class AuthDatabaseStatus:
    """Non-sensitive reachability and migration state."""

    reachable: bool
    schema_initialized: bool


def create_auth_runtime(settings: AuthSettings) -> AuthRuntime:
    """Compose SQL Server auth services only when explicitly enabled."""
    if not settings.fastapi_enabled:
        raise RuntimeError("FastAPI authentication is disabled.")
    if settings.mssql is None:
        raise RuntimeError("Shared SQL Server settings are not configured.")
    database = AuthMSSQLDatabase(MSSQLConnectionFactory(settings.mssql))
    database.initialize()
    users = MSSQLUserRepository(database)
    groups = MSSQLGroupRepository(database)
    roles = MSSQLRoleRepository(database)
    memberships = MSSQLMembershipRepository(database)
    sessions = RepositorySessionService(
        MSSQLSessionRepository(database),
        max_age_seconds=settings.session_max_age_seconds,
    )
    return AuthRuntime(
        authentication=RepositoryAuthenticationService(users),
        sessions=sessions,
        current_users=RepositoryCurrentUserService(
            sessions,
            users,
            groups,
            roles,
            memberships,
        ),
    )


def inspect_auth_database(settings: AuthSettings) -> AuthDatabaseStatus:
    """Inspect database availability without initializing or migrating it."""
    if settings.mssql is None:
        return AuthDatabaseStatus(False, False)
    database = AuthMSSQLDatabase(MSSQLConnectionFactory(settings.mssql))
    try:
        with database.connect() as connection:
            cursor = connection.cursor()
            cursor.execute("SELECT 1").fetchone()
            cursor.execute("SELECT OBJECT_ID(N'auth.SchemaMigrations', N'U')")
            migration_table = cursor.fetchone()[0]
            if not migration_table:
                return AuthDatabaseStatus(True, False)
            latest_version = max(version for version, _ in AUTH_MSSQL_MIGRATIONS)
            cursor.execute(
                """
                SELECT 1 FROM auth.SchemaMigrations
                WHERE Component = ? AND Version = ?
                """,
                "auth",
                latest_version,
            )
            migration = cursor.fetchone()
            cursor.execute(
                """
                SELECT COUNT(*) FROM sys.tables AS tables
                JOIN sys.schemas AS schemas ON schemas.schema_id = tables.schema_id
                WHERE schemas.name = N'auth' AND tables.name IN
                    (N'Users', N'Groups', N'Roles', N'UserGroupMemberships',
                     N'UserRoleMemberships', N'Sessions')
                """
            )
            table_count = int(cursor.fetchone()[0])
            return AuthDatabaseStatus(
                True,
                migration is not None and table_count == 6,
            )
    except Exception:
        return AuthDatabaseStatus(False, False)
