"""Focused tests for SQLite authentication persistence."""

import hashlib
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from backend.config.auth import AuthSettings
from backend.models.auth import (
    Group,
    Role,
    Session,
    User,
    UserGroupMembership,
    UserRoleMembership,
)
from backend.repositories.auth import (
    GroupRepository,
    MembershipRepository,
    RoleRepository,
    SessionRepository,
    UserRepository,
)
from backend.repositories.auth.sqlite import (
    AuthSQLiteDatabase,
    SQLiteGroupRepository,
    SQLiteMembershipRepository,
    SQLiteRoleRepository,
    SQLiteSessionRepository,
    SQLiteUserRepository,
)
from backend.services.auth.bootstrap import bootstrap_first_admin
from backend.services.auth.passwords import PasswordHasher


class SQLiteAuthPersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self._temporary_directory.name) / "auth.sqlite3"
        self.database = AuthSQLiteDatabase(self.database_path)
        self.database.initialize()

    def tearDown(self) -> None:
        self._temporary_directory.cleanup()

    def test_schema_contains_all_auth_tables_and_migration_record(self) -> None:
        with self.database.connect() as connection:
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            migration = connection.execute(
                """
                SELECT version FROM schema_migrations
                WHERE component = 'auth'
                """
            ).fetchone()

        self.assertTrue(
            {
                "users",
                "groups",
                "roles",
                "user_group_memberships",
                "user_role_memberships",
                "sessions",
            }.issubset(tables)
        )
        self.assertEqual(migration["version"], 1)

    def test_repositories_satisfy_existing_protocols(self) -> None:
        self.assertIsInstance(SQLiteUserRepository(self.database), UserRepository)
        self.assertIsInstance(SQLiteGroupRepository(self.database), GroupRepository)
        self.assertIsInstance(SQLiteRoleRepository(self.database), RoleRepository)
        self.assertIsInstance(
            SQLiteMembershipRepository(self.database), MembershipRepository
        )
        self.assertIsInstance(SQLiteSessionRepository(self.database), SessionRepository)

    def test_users_groups_roles_and_memberships_round_trip(self) -> None:
        users = SQLiteUserRepository(self.database)
        groups = SQLiteGroupRepository(self.database)
        roles = SQLiteRoleRepository(self.database)
        memberships = SQLiteMembershipRepository(self.database)
        password_hash = PasswordHasher().hash("correct horse battery staple")
        user = User("user-1", "factory", "Factory Operator")
        group = Group("group-1", "Packing")
        role = Role("role-1", "editor", ("vault.list", "vault.edit"))

        users.create(user, password_hash)
        groups.create(group)
        roles.create(role)
        memberships.add_group_membership(UserGroupMembership(user.id, group.id))
        memberships.add_role_membership(
            UserRoleMembership(user.id, role.id, "factory:cb")
        )

        self.assertEqual(users.get_by_username("FACTORY"), user)
        self.assertEqual(groups.list_for_user(user.id), (group,))
        self.assertEqual(roles.list_for_user(user.id), (role,))
        self.assertEqual(
            memberships.list_role_memberships(user.id)[0].scope,
            "factory:cb",
        )

    def test_database_constraints_reject_duplicates_and_dangling_memberships(self) -> None:
        users = SQLiteUserRepository(self.database)
        password_hash = PasswordHasher().hash("correct horse battery staple")
        users.create(User("user-1", "factory", "Factory"), password_hash)

        with self.assertRaises(sqlite3.IntegrityError):
            users.create(User("user-2", "FACTORY", "Duplicate"), password_hash)
        with self.assertRaises(sqlite3.IntegrityError):
            SQLiteMembershipRepository(self.database).add_group_membership(
                UserGroupMembership("missing-user", "missing-group")
            )

    def test_password_hashing_uses_argon2id_and_never_stores_plaintext(self) -> None:
        password = "correct horse battery staple"
        hasher = PasswordHasher()
        password_hash = hasher.hash(password)
        users = SQLiteUserRepository(self.database)
        users.create(User("user-1", "factory", "Factory"), password_hash)

        stored_hash = users.get_password_hash("user-1")

        self.assertIsNotNone(stored_hash)
        self.assertTrue(stored_hash.startswith("$argon2id$"))
        self.assertNotIn(password, stored_hash)
        self.assertTrue(hasher.verify(stored_hash, password))
        self.assertFalse(hasher.verify(stored_hash, "wrong password"))
        with self.assertRaises(ValueError):
            users.create(User("user-2", "unsafe", "Unsafe"), password)

    def test_session_repository_stores_digest_and_supports_revocation(self) -> None:
        users = SQLiteUserRepository(self.database)
        users.create(
            User("user-1", "factory", "Factory"),
            PasswordHasher().hash("correct horse battery staple"),
        )
        now = datetime.now(timezone.utc)
        session = Session(
            "session-1",
            "user-1",
            now,
            now + timedelta(hours=24),
            metadata={"source": "test"},
        )
        token = "opaque-secret-token"
        token_digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        sessions = SQLiteSessionRepository(self.database)

        sessions.create(session, token_digest)
        stored = sessions.get_by_token_digest(token_digest)

        self.assertEqual(stored, session)
        self.assertTrue(sessions.revoke(session.id, now))
        self.assertIsNotNone(
            sessions.get_by_token_digest(token_digest).revoked_at  # type: ignore[union-attr]
        )
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT token_digest FROM sessions WHERE id = ?", (session.id,)
            ).fetchone()
        self.assertEqual(row["token_digest"], token_digest)
        self.assertNotEqual(row["token_digest"], token)

    def test_admin_bootstrap_is_explicit_and_single_use(self) -> None:
        fresh_path = Path(self._temporary_directory.name) / "bootstrap.sqlite3"
        settings = AuthSettings(fresh_path)

        result = bootstrap_first_admin(
            settings,
            username="admin",
            password="a strong bootstrap password",
            display_name="Administrator",
        )

        self.assertEqual(result.user.username, "admin")
        self.assertEqual(result.role.name, "admin")
        database = AuthSQLiteDatabase(fresh_path)
        stored_hash = SQLiteUserRepository(database).get_password_hash(result.user.id)
        self.assertTrue(PasswordHasher().verify(stored_hash, "a strong bootstrap password"))
        with self.assertRaises(RuntimeError):
            bootstrap_first_admin(
                settings,
                username="second-admin",
                password="another strong password",
                display_name="Second Administrator",
            )

    def test_auth_database_path_is_environment_configurable(self) -> None:
        configured = Path(self._temporary_directory.name) / "configured.sqlite3"
        with patch.dict(
            os.environ,
            {"AUTH_SQLITE_PATH": str(configured)},
            clear=True,
        ):
            settings = AuthSettings.from_environment()

        self.assertEqual(settings.sqlite_path, configured)
        self.assertFalse(configured.exists())


if __name__ == "__main__":
    unittest.main()
