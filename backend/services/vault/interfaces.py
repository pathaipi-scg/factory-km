"""Framework-neutral authorization and orchestration contracts for the Vault."""

from typing import Protocol, runtime_checkable

from backend.models.auth import CurrentUser
from backend.models.vault import (
    FileEntry,
    VaultEntry,
    VaultOperation,
    VaultOperationResult,
    VaultPath,
)


@runtime_checkable
class VaultAuthorizationService(Protocol):
    """Evaluate one action against user grants and source/destination paths."""

    def is_allowed(
        self,
        current_user: CurrentUser,
        action: VaultOperation,
        source_path: VaultPath,
        destination_path: VaultPath | None = None,
    ) -> bool: ...


@runtime_checkable
class VaultService(Protocol):
    """Orchestrate authorized Vault operations without transport coupling."""

    def list_entries(
        self, current_user: CurrentUser, path: VaultPath
    ) -> tuple[VaultEntry, ...]: ...

    def create_folder(
        self, current_user: CurrentUser, path: VaultPath
    ) -> VaultOperationResult: ...

    def upload(
        self, current_user: CurrentUser, path: VaultPath, content: bytes
    ) -> VaultOperationResult: ...

    def rename(
        self,
        current_user: CurrentUser,
        source_path: VaultPath,
        destination_path: VaultPath,
    ) -> VaultOperationResult: ...

    def move(
        self,
        current_user: CurrentUser,
        source_path: VaultPath,
        destination_path: VaultPath,
    ) -> VaultOperationResult: ...

    def edit(
        self, current_user: CurrentUser, path: VaultPath, content: bytes
    ) -> VaultOperationResult: ...

    def soft_delete(
        self, current_user: CurrentUser, path: VaultPath
    ) -> VaultOperationResult: ...

    def restore(
        self,
        current_user: CurrentUser,
        recycle_id: str,
        destination_path: VaultPath | None = None,
    ) -> VaultOperationResult: ...

    def read_metadata(
        self, current_user: CurrentUser, path: VaultPath
    ) -> VaultEntry | FileEntry | None: ...
