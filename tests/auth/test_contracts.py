"""Tests for auth repository, service, router, and dependency contracts."""

import asyncio
import unittest
from datetime import datetime, timezone

from fastapi import HTTPException

from backend.dependencies.auth import (
    require_permission,
    require_role,
    require_scope,
)
from backend.models.auth import AuthenticatedUser, Role, Session, User
from backend.repositories.auth import SessionRepository, UserRepository
from backend.routers.auth import router
from backend.services.auth import AuthenticationService, CurrentUserService, SessionService


class FakeAuthBackend:
    def get_by_id(self, user_id: str) -> User | None:
        return User(user_id, "factory", "Factory Operator")

    def get_by_username(self, username: str) -> User | None:
        return User("user-1", username, "Factory Operator")

    def authenticate(self, username: str, password: str) -> User | None:
        return self.get_by_username(username) if password else None

    def authenticate_viewer(self) -> User:
        return User("viewer", "viewer", "Viewer")

    def create(self, user: User, *, viewer: bool = False) -> tuple[Session, str]:
        now = datetime.now(timezone.utc)
        return Session("session-1", user.id, now, now, viewer=viewer), "token"

    def validate(self, token: str) -> Session | None:
        return None

    def revoke(self, token: str) -> bool:
        return True

    def resolve(self, token: str) -> AuthenticatedUser | None:
        return None


class FakeSessionRepository:
    def create(self, session: Session, token_digest: str) -> Session:
        return session

    def get_by_token_digest(self, token_digest: str) -> Session | None:
        return None

    def revoke(self, session_id: str, revoked_at: datetime) -> bool:
        return True


class AuthContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.current_user = AuthenticatedUser(
            user=User("user-1", "factory", "Factory Operator"),
            roles=(Role("role-1", "editor", permissions=("vault.write",)),),
            scopes=("factory:cb",),
        )

    def test_protocols_accept_structural_implementations(self) -> None:
        backend = FakeAuthBackend()

        self.assertIsInstance(backend, UserRepository)
        self.assertIsInstance(backend, AuthenticationService)
        self.assertIsInstance(backend, SessionService)
        self.assertIsInstance(backend, CurrentUserService)
        self.assertIsInstance(FakeSessionRepository(), SessionRepository)

    def test_authorization_dependencies_return_authorized_user(self) -> None:
        self.assertIs(
            asyncio.run(require_role("editor")(self.current_user)),
            self.current_user,
        )
        self.assertIs(
            asyncio.run(require_permission("vault.write")(self.current_user)),
            self.current_user,
        )
        self.assertIs(
            asyncio.run(require_scope("factory:cb")(self.current_user)),
            self.current_user,
        )

    def test_authorization_dependencies_reject_missing_grants(self) -> None:
        for dependency in (
            require_role("admin"),
            require_permission("auth.admin"),
            require_scope("factory:other"),
        ):
            with self.subTest(dependency=dependency):
                with self.assertRaises(HTTPException) as context:
                    asyncio.run(dependency(self.current_user))
                self.assertEqual(context.exception.status_code, 403)

    def test_router_reserves_legacy_compatible_paths(self) -> None:
        paths = {route.path for route in router.routes}

        self.assertEqual(
            paths,
            {"/login", "/login/viewer", "/logout", "/me", "/status"},
        )


if __name__ == "__main__":
    unittest.main()
