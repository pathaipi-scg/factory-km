"""Tests for Vault repository, service, authorization, and router contracts."""

import unittest
from datetime import datetime

from backend.models.auth import AuthenticatedUser, User
from backend.models.vault import (
    AuditEvent,
    FileEntry,
    FolderEntry,
    ManifestEvent,
    VaultEntry,
    VaultOperation,
    VaultOperationResult,
    VaultPath,
)
from backend.repositories.vault import (
    AuditRepository,
    ManifestEventPublisher,
    RecycleBinRepository,
    VaultListingRepository,
    VaultMetadataRepository,
    VaultMutationRepository,
)
from backend.routers.vault import router
from backend.services.vault import VaultAuthorizationService, VaultService


class FakeVaultBackend:
    def list_entries(self, path: VaultPath) -> tuple[VaultEntry, ...]:
        return ()

    def get_entry(self, path: VaultPath) -> VaultEntry | None:
        return None

    def create_folder(self, path: VaultPath) -> FolderEntry:
        return FolderEntry(path, path.name)

    def upload(self, path: VaultPath, content: bytes) -> FileEntry:
        return FileEntry(path, path.name, size_bytes=len(content))

    def rename(self, source: VaultPath, destination: VaultPath) -> VaultEntry:
        return FileEntry(destination, destination.name)

    def move(self, source: VaultPath, destination: VaultPath) -> VaultEntry:
        return FileEntry(destination, destination.name)

    def edit(self, path: VaultPath, content: bytes) -> FileEntry:
        return FileEntry(path, path.name, size_bytes=len(content))

    def soft_delete(self, path: VaultPath) -> VaultOperationResult:
        return VaultOperationResult(VaultOperation.SOFT_DELETE, True, path)

    def restore(
        self, recycle_id: str, destination: VaultPath | None = None
    ) -> VaultOperationResult:
        return VaultOperationResult(
            VaultOperation.RESTORE,
            True,
            destination or VaultPath(),
        )

    def append(self, event: AuditEvent) -> None:
        return None

    def publish(self, event: ManifestEvent) -> None:
        return None


class FakeAuthorizationService:
    def is_allowed(
        self,
        current_user: AuthenticatedUser,
        action: VaultOperation,
        source_path: VaultPath,
        destination_path: VaultPath | None = None,
    ) -> bool:
        del current_user, action, source_path, destination_path
        return True


class FakeVaultService:
    def list_entries(
        self, current_user: AuthenticatedUser, path: VaultPath
    ) -> tuple[VaultEntry, ...]:
        return ()

    def create_folder(self, current_user: AuthenticatedUser, path: VaultPath) -> VaultOperationResult:
        return VaultOperationResult(VaultOperation.CREATE_FOLDER, True, path)

    def upload(self, current_user: AuthenticatedUser, path: VaultPath, content: bytes) -> VaultOperationResult:
        return VaultOperationResult(VaultOperation.UPLOAD, True, path)

    def rename(self, current_user: AuthenticatedUser, source_path: VaultPath, destination_path: VaultPath) -> VaultOperationResult:
        return VaultOperationResult(VaultOperation.RENAME, True, source_path, destination_path)

    def move(self, current_user: AuthenticatedUser, source_path: VaultPath, destination_path: VaultPath) -> VaultOperationResult:
        return VaultOperationResult(VaultOperation.MOVE, True, source_path, destination_path)

    def edit(self, current_user: AuthenticatedUser, path: VaultPath, content: bytes) -> VaultOperationResult:
        return VaultOperationResult(VaultOperation.EDIT, True, path)

    def soft_delete(self, current_user: AuthenticatedUser, path: VaultPath) -> VaultOperationResult:
        return VaultOperationResult(VaultOperation.SOFT_DELETE, True, path)

    def restore(self, current_user: AuthenticatedUser, recycle_id: str, destination_path: VaultPath | None = None) -> VaultOperationResult:
        return VaultOperationResult(VaultOperation.RESTORE, True, destination_path or VaultPath())

    def read_metadata(self, current_user: AuthenticatedUser, path: VaultPath) -> VaultEntry | None:
        return None


class VaultContractTests(unittest.TestCase):
    def test_repository_protocols_accept_structural_implementation(self) -> None:
        backend = FakeVaultBackend()

        self.assertIsInstance(backend, VaultListingRepository)
        self.assertIsInstance(backend, VaultMetadataRepository)
        self.assertIsInstance(backend, VaultMutationRepository)
        self.assertIsInstance(backend, RecycleBinRepository)
        self.assertIsInstance(backend, AuditRepository)
        self.assertIsInstance(backend, ManifestEventPublisher)

    def test_service_protocols_accept_structural_implementations(self) -> None:
        self.assertIsInstance(FakeAuthorizationService(), VaultAuthorizationService)
        self.assertIsInstance(FakeVaultService(), VaultService)

    def test_authorization_contract_receives_user_action_and_paths(self) -> None:
        authorization = FakeAuthorizationService()
        user = AuthenticatedUser(User("user-1", "factory", "Factory Operator"))

        self.assertTrue(
            authorization.is_allowed(
                user,
                VaultOperation.MOVE,
                VaultPath("Packing/manual.md"),
                VaultPath("Packing/Archive/manual.md"),
            )
        )

    def test_router_reserves_all_operation_routes(self) -> None:
        routes = {
            (method, route.path)
            for route in router.routes
            for method in route.methods
        }

        self.assertEqual(
            routes,
            {
                ("GET", "/vault/entries"),
                ("POST", "/vault/folders"),
                ("POST", "/vault/files"),
                ("POST", "/vault/rename"),
                ("POST", "/vault/move"),
                ("PUT", "/vault/files"),
                ("POST", "/vault/soft-delete"),
                ("POST", "/vault/restore"),
            },
        )


if __name__ == "__main__":
    unittest.main()
