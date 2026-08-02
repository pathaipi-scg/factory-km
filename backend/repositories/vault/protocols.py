"""Persistence-neutral repository protocols for Vault Management."""

from typing import Protocol, runtime_checkable

from backend.models.vault import (
    AuditEvent,
    FileEntry,
    FolderEntry,
    ManifestEvent,
    VaultEntry,
    VaultOperationResult,
    VaultPath,
)


@runtime_checkable
class VaultListingRepository(Protocol):
    def list_entries(self, path: VaultPath) -> tuple[VaultEntry, ...]: ...


@runtime_checkable
class VaultMetadataRepository(Protocol):
    def get_entry(self, path: VaultPath) -> VaultEntry | None: ...


@runtime_checkable
class VaultMutationRepository(Protocol):
    def create_folder(self, path: VaultPath) -> FolderEntry: ...

    def upload(self, path: VaultPath, content: bytes) -> FileEntry: ...

    def rename(self, source: VaultPath, destination: VaultPath) -> VaultEntry: ...

    def move(self, source: VaultPath, destination: VaultPath) -> VaultEntry: ...

    def edit(self, path: VaultPath, content: bytes) -> FileEntry: ...


@runtime_checkable
class RecycleBinRepository(Protocol):
    def soft_delete(self, path: VaultPath) -> VaultOperationResult: ...

    def restore(
        self, recycle_id: str, destination: VaultPath | None = None
    ) -> VaultOperationResult: ...


@runtime_checkable
class AuditRepository(Protocol):
    def append(self, event: AuditEvent) -> None: ...


@runtime_checkable
class ManifestEventPublisher(Protocol):
    def publish(self, event: ManifestEvent) -> None: ...
