"""Tests for framework-neutral Vault Management models."""

import unittest
from datetime import datetime, timezone

from backend.models.vault import (
    AuditEvent,
    FileEntry,
    FolderEntry,
    ManifestEvent,
    VaultOperation,
    VaultOperationResult,
    VaultPath,
    VaultScope,
)


class VaultModelTests(unittest.TestCase):
    def test_vault_path_normalizes_relative_paths(self) -> None:
        path = VaultPath(r"Packing\Trouble_Shooting\manual.md")

        self.assertEqual(path.value, "Packing/Trouble_Shooting/manual.md")
        self.assertEqual(path.name, "manual.md")
        self.assertEqual(
            VaultPath("Packing").child("Manuals").value,
            "Packing/Manuals",
        )

    def test_vault_path_rejects_absolute_and_traversal_paths(self) -> None:
        invalid_paths = (
            "/etc/passwd",
            r"D:\KM\Vault",
            "Packing/../Secrets",
            r"\\server\share",
        )

        for value in invalid_paths:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    VaultPath(value)

    def test_supported_operations_are_explicit(self) -> None:
        self.assertEqual(
            {operation.value for operation in VaultOperation},
            {
                "list",
                "create_folder",
                "upload",
                "rename",
                "move",
                "edit",
                "soft_delete",
                "restore",
            },
        )

    def test_entries_scope_results_and_events_preserve_context(self) -> None:
        now = datetime.now(timezone.utc)
        source = VaultPath("Packing/manual.md")
        destination = VaultPath("Packing/Archive/manual.md")
        file_entry = FileEntry(source, "manual.md", size_bytes=128)
        folder_entry = FolderEntry(VaultPath("Packing"), "Packing", child_count=1)
        scope = VaultScope(
            "scope-1",
            VaultPath("Packing"),
            (VaultOperation.LIST, VaultOperation.MOVE),
        )
        result = VaultOperationResult(
            VaultOperation.MOVE,
            True,
            source,
            destination_path=destination,
            entry=file_entry,
        )
        audit = AuditEvent(
            "audit-1",
            "user-1",
            VaultOperation.MOVE,
            source,
            now,
            True,
            destination_path=destination,
        )
        manifest = ManifestEvent(
            "manifest-1",
            VaultOperation.MOVE,
            source,
            now,
            destination_path=destination,
        )

        self.assertEqual(folder_entry.child_count, 1)
        self.assertIn(VaultOperation.MOVE, scope.operations)
        self.assertEqual(result.destination_path, destination)
        self.assertEqual(audit.actor_user_id, "user-1")
        self.assertEqual(manifest.destination_path, destination)


if __name__ == "__main__":
    unittest.main()
