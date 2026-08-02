"""Focused tests for core document domain phase 1."""

import unittest
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

from backend.domain import (
    ActorKind,
    AuditActor,
    Document,
    DocumentKind,
    DocumentVersion,
    FolderId,
    Ownership,
    OwnershipKind,
    StableDocumentId,
)


class DocumentDomainTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime.now(timezone.utc)
        self.actor = AuditActor(ActorKind.USER, "user-1", "Factory Admin")
        self.owner = Ownership(OwnershipKind.GROUP, "group-maintenance")

    def make_version(
        self,
        document_id: StableDocumentId,
        version_id: str = "version-1",
    ) -> DocumentVersion:
        return DocumentVersion(
            version_id=version_id,
            document_id=document_id,
            sequence=1,
            content_sha256="a" * 64,
            storage_reference="objects/ab/content.md",
            media_type="text/markdown",
            created_at=self.now,
            created_by=self.actor,
        )

    def make_document(
        self,
        document_id: StableDocumentId,
        kind: DocumentKind,
        derived_from: StableDocumentId | None = None,
    ) -> Document:
        version = self.make_version(document_id)
        return Document(
            document_id=document_id,
            kind=kind,
            title=f"{kind.value} document",
            folder_id=FolderId("folder-maintenance"),
            ownership=self.owner,
            versions=(version,),
            current_version_id=version.version_id,
            created_at=self.now,
            updated_at=self.now,
            derived_from_document_id=derived_from,
        )

    def test_document_and_folder_ids_are_opaque_and_immutable(self) -> None:
        document_id = StableDocumentId("doc-01KM")
        folder_id = FolderId("folder-maintenance")

        self.assertEqual(str(document_id), "doc-01KM")
        self.assertEqual(str(folder_id), "folder-maintenance")
        with self.assertRaises(FrozenInstanceError):
            document_id.value = "replacement"  # type: ignore[misc]

        for path in ("Manuals/pump.md", r"D:\Vault\pump.md"):
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    StableDocumentId(path)

    def test_audit_actor_does_not_depend_on_auth_session_models(self) -> None:
        service = AuditActor(ActorKind.SERVICE, "index-worker", "Index Worker")
        system = AuditActor(ActorKind.SYSTEM, "factory-km", "Factory KM")

        self.assertEqual(service.kind, ActorKind.SERVICE)
        self.assertEqual(system.actor_id, "factory-km")

    def test_ownership_expresses_responsibility_not_authorization(self) -> None:
        self.assertEqual(self.owner.owner_id, "group-maintenance")
        self.assertFalse(hasattr(self.owner, "permissions"))
        self.assertFalse(hasattr(self.owner, "is_allowed"))

    def test_detail_and_summary_are_separate_document_aggregates(self) -> None:
        source_id = StableDocumentId("doc-source")
        detail = self.make_document(
            StableDocumentId("doc-detail"),
            DocumentKind.KM_DETAIL,
            source_id,
        )
        summary = self.make_document(
            StableDocumentId("doc-summary"),
            DocumentKind.KM_SUMMARY,
            source_id,
        )

        self.assertNotEqual(detail.document_id, summary.document_id)
        self.assertEqual(detail.derived_from_document_id, source_id)
        self.assertEqual(summary.derived_from_document_id, source_id)

    def test_classification_references_are_optional(self) -> None:
        document = self.make_document(
            StableDocumentId("doc-unclassified"),
            DocumentKind.ORIGINAL,
        )

        self.assertIsNone(document.plant_id)
        self.assertIsNone(document.department_id)
        self.assertIsNone(document.process_id)
        self.assertIsNone(document.machine_id)

    def test_document_owns_versions_and_selects_current_version(self) -> None:
        document_id = StableDocumentId("doc-owned-versions")
        document = self.make_document(document_id, DocumentKind.ORIGINAL)

        self.assertEqual(document.current_version.version_id, "version-1")

        foreign_version = self.make_version(StableDocumentId("doc-foreign"))
        with self.assertRaises(ValueError):
            Document(
                document_id=document_id,
                kind=DocumentKind.ORIGINAL,
                title="Invalid aggregate",
                folder_id=FolderId("folder-one"),
                ownership=self.owner,
                versions=(foreign_version,),
                current_version_id=foreign_version.version_id,
                created_at=self.now,
                updated_at=self.now,
            )

    def test_version_validates_content_identity(self) -> None:
        with self.assertRaises(ValueError):
            DocumentVersion(
                version_id="version-1",
                document_id=StableDocumentId("doc-one"),
                sequence=1,
                content_sha256="not-a-sha256",
                storage_reference="objects/content.md",
                media_type="text/markdown",
                created_at=self.now,
                created_by=self.actor,
            )


if __name__ == "__main__":
    unittest.main()
