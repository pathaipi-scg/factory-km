"""Tests for framework-neutral authentication models."""

import unittest
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

from backend.models.auth import AuthenticatedUser, Group, Role, Session, User


class AuthModelTests(unittest.TestCase):
    def test_authenticated_user_resolves_roles_permissions_and_scopes(self) -> None:
        user = AuthenticatedUser(
            user=User("user-1", "factory", "Factory Operator"),
            groups=(Group("group-1", "Packing"),),
            roles=(
                Role(
                    "role-1",
                    "vault-editor",
                    permissions=("vault.read", "vault.write"),
                ),
            ),
            scopes=("factory:cb", "department:packing"),
            session_id="session-1",
        )

        self.assertTrue(user.has_role("role-1"))
        self.assertTrue(user.has_role("vault-editor"))
        self.assertTrue(user.has_permission("vault.write"))
        self.assertTrue(user.has_scope("factory:cb"))
        self.assertFalse(user.has_permission("auth.admin"))

    def test_identity_models_are_immutable(self) -> None:
        user = User("user-1", "factory", "Factory Operator")

        with self.assertRaises(FrozenInstanceError):
            user.username = "changed"  # type: ignore[misc]

    def test_session_activity_honors_expiry_and_revocation(self) -> None:
        now = datetime.now(timezone.utc)
        active = Session("session-1", "user-1", now, now + timedelta(hours=1))
        expired = Session("session-2", "user-1", now, now)
        revoked = Session(
            "session-3",
            "user-1",
            now,
            now + timedelta(hours=1),
            revoked_at=now,
        )

        self.assertTrue(active.is_active(now))
        self.assertFalse(expired.is_active(now))
        self.assertFalse(revoked.is_active(now))


if __name__ == "__main__":
    unittest.main()
