"""Tests for auth services and disabled compatibility endpoints."""

import asyncio
import json
import re
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import HTTPException
from starlette.requests import Request

from backend.config.auth import AuthSettings
from backend.dependencies.auth import get_auth_runtime
from backend.models.auth import Role, Session, User, UserRoleMembership
from backend.repositories.auth.sqlite import (
    AuthSQLiteDatabase,
    SQLiteGroupRepository,
    SQLiteMembershipRepository,
    SQLiteRoleRepository,
    SQLiteSessionRepository,
    SQLiteUserRepository,
)
from backend.routers.auth import current_user, login, login_viewer, logout
from backend.services.auth.composition import AuthRuntime
from backend.services.auth.passwords import PasswordHasher
from backend.services.auth.services import (
    SQLiteAuthenticationService,
    SQLiteCurrentUserService,
    SQLiteSessionService,
)


class AuthServiceAndEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self._temporary_directory.name) / "auth.sqlite3"
        self.settings = AuthSettings(fastapi_enabled=True, session_max_age_seconds=86400)
        self.database = AuthSQLiteDatabase(self.database_path)
        self.database.initialize()
        self._seed_identities()
        users = SQLiteUserRepository(self.database)
        groups = SQLiteGroupRepository(self.database)
        roles = SQLiteRoleRepository(self.database)
        memberships = SQLiteMembershipRepository(self.database)
        sessions = SQLiteSessionService(SQLiteSessionRepository(self.database))
        self.runtime = AuthRuntime(
            SQLiteAuthenticationService(users),
            sessions,
            SQLiteCurrentUserService(sessions, users, groups, roles, memberships),
        )

    def tearDown(self) -> None:
        self._temporary_directory.cleanup()

    @staticmethod
    def _request(
        *, body: dict[str, str] | None = None, cookie: str = ""
    ) -> Request:
        encoded_body = json.dumps(body).encode("utf-8") if body is not None else b""
        headers = [(b"content-type", b"application/json")]
        if cookie:
            headers.append((b"cookie", f"km_session={cookie}".encode("ascii")))
        delivered = False

        async def receive() -> dict[str, object]:
            nonlocal delivered
            if delivered:
                return {"type": "http.disconnect"}
            delivered = True
            return {"type": "http.request", "body": encoded_body, "more_body": False}

        return Request(
            {"type": "http", "method": "POST", "path": "/", "headers": headers},
            receive,
        )

    @staticmethod
    def _json(response: object) -> dict[str, object]:
        return json.loads(response.body.decode("utf-8"))  # type: ignore[attr-defined]

    @staticmethod
    def _cookie_token(response: object) -> str:
        cookie = response.headers["set-cookie"]  # type: ignore[attr-defined]
        match = re.search(r"km_session=([0-9a-f]{48})", cookie)
        if not match:
            raise AssertionError("Response did not contain a valid km_session cookie.")
        return match.group(1)

    def _seed_identities(self) -> None:
        hasher = PasswordHasher()
        users = SQLiteUserRepository(self.database)
        roles = SQLiteRoleRepository(self.database)
        memberships = SQLiteMembershipRepository(self.database)
        factory = User("user-factory", "factory", "Factory Operator")
        viewer = User("user-viewer", "viewer", "ผู้ชม (Viewer)")
        role = Role("role-factory", "factory", ("vault.list",))
        users.create(factory, hasher.hash("factory-password"))
        users.create(viewer, hasher.hash("unusable-viewer-password"))
        roles.create(role)
        memberships.add_role_membership(UserRoleMembership(factory.id, role.id))

    def test_valid_login_preserves_response_and_cookie_contract(self) -> None:
        response = asyncio.run(
            login(
                self._request(
                    body={"username": "factory", "password": "factory-password"}
                ),
                self.runtime,
                self.settings,
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self._json(response),
            {"success": True, "role": "factory", "name": "Factory Operator"},
        )
        cookie = response.headers["set-cookie"]
        self.assertIn("km_session=", cookie)
        self.assertIn("HttpOnly", cookie)
        self.assertIn("Path=/", cookie)
        self.assertIn("SameSite=lax", cookie)
        self.assertIn("Max-Age=86400", cookie)

    def test_invalid_login_preserves_status_and_response_shape(self) -> None:
        response = asyncio.run(
            login(
                self._request(body={"username": "factory", "password": "wrong"}),
                self.runtime,
                self.settings,
            )
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            self._json(response),
            {
                "success": False,
                "error": "username หรือ password ไม่ถูกต้อง",
            },
        )
        self.assertNotIn("set-cookie", response.headers)

    def test_viewer_login_preserves_response_shape(self) -> None:
        response = login_viewer(self.runtime, self.settings)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self._json(response),
            {"success": True, "role": "viewer", "name": "ผู้ชม (Viewer)"},
        )
        self.assertIn("km_session=", response.headers["set-cookie"])

    def test_me_authenticated_and_unauthenticated_shapes(self) -> None:
        unauthenticated = current_user(self._request(), self.runtime)
        self.assertEqual(unauthenticated.status_code, 401)
        self.assertEqual(self._json(unauthenticated), {"loggedIn": False})

        login_response = asyncio.run(
            login(
                self._request(
                    body={"username": "factory", "password": "factory-password"}
                ),
                self.runtime,
                self.settings,
            )
        )
        authenticated = current_user(
            self._request(cookie=self._cookie_token(login_response)),
            self.runtime,
        )

        self.assertEqual(authenticated.status_code, 200)
        self.assertEqual(
            self._json(authenticated),
            {
                "loggedIn": True,
                "username": "factory",
                "role": "factory",
                "name": "Factory Operator",
            },
        )

    def test_malformed_cookie_is_unauthenticated(self) -> None:
        response = current_user(
            self._request(cookie="not-a-valid-token"), self.runtime
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(self._json(response), {"loggedIn": False})

    def test_logout_revokes_session_and_clears_cookie(self) -> None:
        login_response = asyncio.run(
            login(
                self._request(
                    body={"username": "factory", "password": "factory-password"}
                ),
                self.runtime,
                self.settings,
            )
        )
        token = self._cookie_token(login_response)

        response = logout(self._request(cookie=token), self.runtime)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._json(response), {"success": True})
        self.assertEqual(
            response.headers["set-cookie"],
            "km_session=; HttpOnly; Path=/; Max-Age=0",
        )
        self.assertEqual(
            current_user(self._request(cookie=token), self.runtime).status_code,
            401,
        )

    def test_expired_and_revoked_sessions_are_invalid(self) -> None:
        now = datetime.now(timezone.utc)
        current_time = [now]
        repository = SQLiteSessionRepository(self.database)
        sessions = SQLiteSessionService(
            repository,
            max_age_seconds=60,
            clock=lambda: current_time[0],
            token_factory=lambda: "a" * 48,
        )
        user = SQLiteUserRepository(self.database).get_by_id("user-factory")
        _, token = sessions.create(user)  # type: ignore[arg-type]

        current_time[0] = now + timedelta(seconds=61)
        self.assertIsNone(sessions.validate(token))

        active_session = Session(
            "revoked-session",
            "user-factory",
            now,
            now + timedelta(hours=1),
        )
        revoked_token = "b" * 48
        repository.create(
            active_session,
            SQLiteSessionService.token_digest(revoked_token),
        )
        current_time[0] = now
        self.assertTrue(sessions.revoke(revoked_token))
        self.assertIsNone(sessions.validate(revoked_token))

    def test_feature_flag_defaults_to_disabled_behavior(self) -> None:
        with self.assertRaises(HTTPException) as context:
            get_auth_runtime(AuthSettings())

        self.assertEqual(context.exception.status_code, 503)
        self.assertEqual(context.exception.detail, "FastAPI authentication is disabled.")


if __name__ == "__main__":
    unittest.main()
