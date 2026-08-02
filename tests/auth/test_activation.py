"""Tests for safe temporary FastAPI authentication activation."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI

from backend.config.auth import AuthSettings
from backend.config.mssql import MSSQLSettings
from backend.services.auth.composition import AuthDatabaseStatus
from backend.repositories.auth.sqlite import AuthSQLiteDatabase
from backend.routers.auth import auth_status, register_auth_router


class AuthActivationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self._temporary_directory.name) / "auth.sqlite3"

    def tearDown(self) -> None:
        self._temporary_directory.cleanup()

    @staticmethod
    def _route_methods(app: FastAPI) -> set[tuple[str, str]]:
        return {
            (method.upper(), path)
            for path, operations in app.openapi()["paths"].items()
            for method in operations
        }

    def test_disabled_router_registers_no_temporary_or_active_paths(self) -> None:
        app = FastAPI()

        registered = register_auth_router(app, AuthSettings())
        paths = {path for _, path in self._route_methods(app)}

        self.assertFalse(registered)
        self.assertFalse(any(path.startswith("/api/auth-v2") for path in paths))
        self.assertTrue(
            {"/api/login", "/api/login/viewer", "/api/logout", "/api/me"}
            .isdisjoint(paths)
        )

    def test_enabled_router_uses_only_the_temporary_prefix(self) -> None:
        app = FastAPI()
        settings = AuthSettings(
            fastapi_enabled=True,
            mssql=MSSQLSettings("server", "database", "user", "password"),
        )

        registered = register_auth_router(app, settings)
        routes = self._route_methods(app)

        self.assertTrue(registered)
        self.assertTrue(
            {
                ("POST", "/api/auth-v2/login"),
                ("POST", "/api/auth-v2/login/viewer"),
                ("POST", "/api/auth-v2/logout"),
                ("GET", "/api/auth-v2/me"),
                ("GET", "/api/auth-v2/status"),
            }.issubset(routes)
        )
        self.assertTrue(
            {"/api/login", "/api/login/viewer", "/api/logout", "/api/me"}
            .isdisjoint({path for _, path in routes})
        )
        self.assertEqual(app.state.auth_settings, settings)

    @patch("backend.routers.auth.inspect_auth_database")
    def test_status_reports_enabled_reachable_initialized_schema(self, inspect) -> None:
        settings = AuthSettings(fastapi_enabled=True)
        inspect.return_value = AuthDatabaseStatus(True, True)
        result = auth_status(settings)

        self.assertEqual(
            result,
            {
                "enabled": True,
                "database_reachable": True,
                "schema_initialized": True,
            },
        )

    @patch("backend.routers.auth.inspect_auth_database")
    def test_status_reports_unreachable_without_sensitive_values(self, inspect) -> None:
        settings = AuthSettings(fastapi_enabled=True)
        inspect.return_value = AuthDatabaseStatus(False, False)
        result = auth_status(settings)

        self.assertEqual(
            result,
            {
                "enabled": True,
                "database_reachable": False,
                "schema_initialized": False,
            },
        )
        self.assertNotIn("password", str(result).lower())


if __name__ == "__main__":
    unittest.main()
