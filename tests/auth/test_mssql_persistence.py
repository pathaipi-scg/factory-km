"""Focused mocked tests for SQL Server auth persistence."""

import os
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

from backend.config.auth import AuthSettings
from backend.config.mssql import MSSQLSettings
from backend.db.auth_mssql_migrations import apply_auth_mssql_migrations
from backend.db.mssql import MSSQLConnectionFactory
from backend.models.auth import Session, User
from backend.repositories.auth.mssql import (
    AuthMSSQLDatabase,
    MSSQLSessionRepository,
    MSSQLUserRepository,
)
from backend.services.auth.composition import create_auth_runtime
from backend.services.auth.bootstrap import bootstrap_first_admin


class FakeCursor:
    def __init__(self, result_sets: list[list[tuple[object, ...]]] | None = None) -> None:
        self.result_sets = list(result_sets or [])
        self.executions: list[tuple[str, tuple[object, ...]]] = []
        self.description = [("Value",)]
        self.rowcount = 1
        self._current: list[tuple[object, ...]] = []

    def execute(self, sql: str, *params: object) -> "FakeCursor":
        self.executions.append((sql, params))
        self._current = self.result_sets.pop(0) if self.result_sets else []
        return self

    def fetchall(self) -> list[tuple[object, ...]]:
        return self._current

    def fetchone(self) -> tuple[object, ...] | None:
        return self._current[0] if self._current else None


class FakeConnection:
    def __init__(self, cursor: FakeCursor | None = None) -> None:
        self._cursor = cursor or FakeCursor()
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self) -> FakeCursor:
        return self._cursor

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    def close(self) -> None:
        self.closed = True


class FakeDatabase:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    @contextmanager
    def connect(self):
        yield self.connection


class MSSQLPersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = MSSQLSettings("sql-host", "factory", "app-user", "secret")

    def test_shared_settings_use_existing_environment_names(self) -> None:
        environment = {
            "SQL_SERVER": "sql-host",
            "SQL_DB": "factory",
            "SQL_USER": "app-user",
            "SQL_PASS": "secret",
        }
        with patch.dict(os.environ, environment, clear=True):
            settings = MSSQLSettings.from_environment()

        self.assertEqual(settings.server, "sql-host")
        self.assertEqual(settings.driver, "ODBC Driver 18 for SQL Server")
        self.assertNotIn("AUTH_SQL", settings.connection_string())

    def test_connection_factory_commits_and_closes(self) -> None:
        connection = FakeConnection()
        connector = Mock(return_value=connection)

        with MSSQLConnectionFactory(self.settings, connector).connect():
            pass

        connector.assert_called_once()
        self.assertTrue(connection.committed)
        self.assertTrue(connection.closed)

    def test_migration_is_idempotent_when_version_is_recorded(self) -> None:
        cursor = FakeCursor(result_sets=[[], [(1,)]])
        apply_auth_mssql_migrations(FakeConnection(cursor))

        statements = "\n".join(sql for sql, _ in cursor.executions)
        self.assertIn("auth.SchemaMigrations", statements)
        self.assertNotIn("CREATE TABLE auth.Users", statements)

    def test_user_repository_rejects_non_argon2id_hashes(self) -> None:
        repository = MSSQLUserRepository(FakeDatabase(FakeConnection()))  # type: ignore[arg-type]

        with self.assertRaises(ValueError):
            repository.create(User("user-1", "factory", "Factory"), "plaintext")

    def test_session_repository_stores_only_sha256_digest(self) -> None:
        cursor = FakeCursor()
        repository = MSSQLSessionRepository(  # type: ignore[arg-type]
            FakeDatabase(FakeConnection(cursor))
        )
        now = datetime.now(timezone.utc)
        session = Session("session-1", "user-1", now, now + timedelta(hours=1))

        repository.create(session, "a" * 64)

        sql, parameters = cursor.executions[0]
        self.assertIn("TokenDigest", sql)
        self.assertIn("a" * 64, parameters)
        self.assertNotIn("km_session", str(parameters))

    @patch("backend.services.auth.composition.AuthMSSQLDatabase")
    def test_runtime_composes_sql_server_repositories(self, database_type: Mock) -> None:
        database_type.return_value = Mock()
        settings = AuthSettings(fastapi_enabled=True, mssql=self.settings)

        runtime = create_auth_runtime(settings)

        database_type.return_value.initialize.assert_called_once_with()
        self.assertIsNotNone(runtime.authentication)
        self.assertIsNotNone(runtime.sessions)

    @patch("backend.services.auth.bootstrap.PasswordHasher")
    @patch("backend.services.auth.bootstrap.MSSQLMembershipRepository")
    @patch("backend.services.auth.bootstrap.MSSQLRoleRepository")
    @patch("backend.services.auth.bootstrap.MSSQLUserRepository")
    @patch("backend.services.auth.bootstrap.AuthMSSQLDatabase")
    def test_first_admin_bootstrap_uses_sql_server_repositories(
        self,
        database_type: Mock,
        user_repository_type: Mock,
        role_repository_type: Mock,
        membership_repository_type: Mock,
        hasher_type: Mock,
    ) -> None:
        user_repository_type.return_value.count.return_value = 0
        hasher_type.return_value.hash.return_value = "$argon2id$test-hash"
        settings = AuthSettings(fastapi_enabled=True, mssql=self.settings)

        result = bootstrap_first_admin(
            settings,
            username="admin",
            password="a strong bootstrap password",
            display_name="Administrator",
        )

        database_type.return_value.initialize.assert_called_once_with()
        self.assertEqual(user_repository_type.return_value.create.call_count, 2)
        role_repository_type.return_value.create.assert_called_once()
        membership_repository_type.return_value.add_role_membership.assert_called_once()
        self.assertEqual(result.role.name, "admin")


@unittest.skipUnless(
    os.environ.get("AUTH_MSSQL_INTEGRATION_TESTS", "").lower() == "true",
    "Set AUTH_MSSQL_INTEGRATION_TESTS=true to run against configured SQL Server",
)
class MSSQLIntegrationTests(unittest.TestCase):
    def test_configured_database_accepts_idempotent_auth_migrations(self) -> None:
        database = AuthMSSQLDatabase(
            MSSQLConnectionFactory(MSSQLSettings.from_environment())
        )
        database.initialize()
        database.initialize()


if __name__ == "__main__":
    unittest.main()
