"""Concrete authentication, session, and current-user services."""

import hashlib
import re
import secrets
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Protocol
from uuid import uuid4

from backend.models.auth import AuthenticatedUser, Session, User
from backend.repositories.auth import (
    GroupRepository,
    MembershipRepository,
    RoleRepository,
    SessionRepository,
    UserRepository,
)
from backend.services.auth.passwords import PasswordHasher


class CredentialUserRepository(UserRepository, Protocol):
    """User lookup contract extended with password-hash access."""

    def get_password_hash(self, user_id: str) -> str | None: ...


class SQLiteAuthenticationService:
    """Authenticate active SQLite-backed users with Argon2id hashes."""

    def __init__(
        self,
        users: CredentialUserRepository,
        password_hasher: PasswordHasher | None = None,
    ) -> None:
        self._users = users
        self._password_hasher = password_hasher or PasswordHasher()

    def authenticate(self, username: str, password: str) -> User | None:
        normalized_username = username.strip()
        if not normalized_username or not password:
            return None
        user = self._users.get_by_username(normalized_username)
        if not user or not user.active:
            return None
        password_hash = self._users.get_password_hash(user.id)
        if not password_hash or not self._password_hasher.verify(password_hash, password):
            return None
        return user

    def authenticate_viewer(self) -> User:
        viewer = self._users.get_by_username("viewer")
        if not viewer or not viewer.active:
            raise RuntimeError("The viewer identity is not configured.")
        return viewer


class SQLiteSessionService:
    """Create and validate Node-compatible opaque session tokens."""

    TOKEN_PATTERN = re.compile(r"^[0-9a-f]{48}$")

    def __init__(
        self,
        sessions: SessionRepository,
        *,
        max_age_seconds: int = 86400,
        clock: Callable[[], datetime] | None = None,
        token_factory: Callable[[], str] | None = None,
    ) -> None:
        if max_age_seconds <= 0:
            raise ValueError("Session max age must be positive.")
        self._sessions = sessions
        self._max_age_seconds = max_age_seconds
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._token_factory = token_factory or (lambda: secrets.token_hex(24))

    def create(self, user: User, *, viewer: bool = False) -> tuple[Session, str]:
        token = self._token_factory()
        if not self.is_well_formed(token):
            raise ValueError("Session token factory returned an invalid token.")
        now = self._clock()
        session = Session(
            id=str(uuid4()),
            user_id=user.id,
            created_at=now,
            expires_at=now + timedelta(seconds=self._max_age_seconds),
            viewer=viewer,
        )
        self._sessions.create(session, self.token_digest(token))
        return session, token

    def validate(self, token: str) -> Session | None:
        if not self.is_well_formed(token):
            return None
        session = self._sessions.get_by_token_digest(self.token_digest(token))
        if not session or not session.is_active(self._clock()):
            return None
        return session

    def revoke(self, token: str) -> bool:
        if not self.is_well_formed(token):
            return False
        session = self._sessions.get_by_token_digest(self.token_digest(token))
        if not session:
            return False
        return self._sessions.revoke(session.id, self._clock())

    @classmethod
    def is_well_formed(cls, token: str) -> bool:
        return isinstance(token, str) and bool(cls.TOKEN_PATTERN.fullmatch(token))

    @staticmethod
    def token_digest(token: str) -> str:
        return hashlib.sha256(token.encode("ascii")).hexdigest()


class SQLiteCurrentUserService:
    """Resolve sessions into users, groups, roles, and authorization scopes."""

    def __init__(
        self,
        sessions: SQLiteSessionService,
        users: UserRepository,
        groups: GroupRepository,
        roles: RoleRepository,
        memberships: MembershipRepository,
    ) -> None:
        self._sessions = sessions
        self._users = users
        self._groups = groups
        self._roles = roles
        self._memberships = memberships

    def resolve(self, token: str) -> AuthenticatedUser | None:
        session = self._sessions.validate(token)
        if not session:
            return None
        user = self._users.get_by_id(session.user_id)
        if not user or not user.active:
            return None
        memberships = self._memberships.list_role_memberships(user.id)
        scopes = tuple(
            dict.fromkeys(
                membership.scope
                for membership in memberships
                if membership.scope
            )
        )
        return AuthenticatedUser(
            user=user,
            groups=self._groups.list_for_user(user.id),
            roles=self._roles.list_for_user(user.id),
            scopes=scopes,
            session_id=session.id,
            metadata={"viewer": "true" if session.viewer else "false"},
        )
