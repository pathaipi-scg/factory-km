"""Persistence-neutral repository protocols for authentication."""

from datetime import datetime
from typing import Protocol, runtime_checkable

from backend.models.auth import (
    Group,
    Role,
    Session,
    User,
    UserGroupMembership,
    UserRoleMembership,
)


@runtime_checkable
class UserRepository(Protocol):
    def get_by_id(self, user_id: str) -> User | None: ...

    def get_by_username(self, username: str) -> User | None: ...


@runtime_checkable
class GroupRepository(Protocol):
    def list_for_user(self, user_id: str) -> tuple[Group, ...]: ...


@runtime_checkable
class RoleRepository(Protocol):
    def list_for_user(self, user_id: str) -> tuple[Role, ...]: ...


@runtime_checkable
class MembershipRepository(Protocol):
    def list_group_memberships(
        self, user_id: str
    ) -> tuple[UserGroupMembership, ...]: ...

    def list_role_memberships(
        self, user_id: str
    ) -> tuple[UserRoleMembership, ...]: ...


@runtime_checkable
class SessionRepository(Protocol):
    def create(self, session: Session, token_digest: str) -> Session: ...

    def get_by_token_digest(self, token_digest: str) -> Session | None: ...

    def revoke(self, session_id: str, revoked_at: datetime) -> bool: ...
