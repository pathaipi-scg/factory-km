"""Pure Manifest domain and cross-project compatibility tests."""

import unittest
from dataclasses import replace
from datetime import datetime, timezone

from backend.domain.document import StableDocumentId
from backend.domain.manifest import (
    ArtifactRole,
    DocumentType,
    DocumentVersionId,
    LifecycleState,
    ManifestRecord,
    PageIndexState,
    TrainingState,
)


NOW = datetime(2026, 8, 17, tzinfo=timezone.utc)
HEX = "A" * 32


def record(**changes: object) -> ManifestRecord:
    values: dict[str, object] = {
        "stable_document_id": StableDocumentId("doc-pptx-detail"),
        "document_version_id": DocumentVersionId("ver-pptx-detail-1"),
        "relative_locator": "Packing/KM_20260817_120000.md",
        "source_filename": "Packer Training.pptx",
        "content_sha256": "a" * 64,
        "document_type": DocumentType.MARKDOWN,
        "artifact_role": ArtifactRole.DETAIL_MARKDOWN,
        "training_state": TrainingState.TRAINED,
        "lifecycle_state": LifecycleState.ACTIVE,
        "pageindex_state": PageIndexState.NOT_INDEXED,
        "created_at": NOW,
        "updated_at": NOW,
        "plant_id": "LP2",
    }
    values.update(changes)
    return ManifestRecord(**values)  # type: ignore[arg-type]


class ManifestDomainTests(unittest.TestCase):
    def test_stable_and_version_identity_are_distinct_and_path_independent(self) -> None:
        item = record()
        self.assertNotEqual(str(item.stable_document_id), str(item.document_version_id))
        self.assertTrue(item.eligible_for_pageindex)

    def test_absolute_parent_and_drive_locators_are_rejected(self) -> None:
        for locator in (r"D:\KM\Vault\file.md", r"..\file.md", r"\server\share\file.md"):
            with self.subTest(locator=locator), self.assertRaises(ValueError):
                record(relative_locator=locator)

    def test_factory_upload_detail_and_summary_are_independent_artifacts(self) -> None:
        detail = record()
        summary = record(
            stable_document_id=StableDocumentId("doc-pptx-summary"),
            document_version_id=DocumentVersionId("ver-pptx-summary-1"),
            relative_locator="Packing/KM_20260817_120000_summary.md",
            artifact_role=ArtifactRole.SUMMARY_MARKDOWN,
        )
        self.assertNotEqual(detail.stable_document_id, summary.stable_document_id)
        self.assertTrue(detail.eligible_for_pageindex and summary.eligible_for_pageindex)

    def test_office_pdf_docx_xlsx_originals_are_not_index_eligible(self) -> None:
        for name in ("source.xlsx", "source.pdf", "source.docx", "source.pptx"):
            item = record(
                relative_locator=f"Sources/{name}", source_filename=name,
                document_type=DocumentType.OFFICE if name != "source.pdf" else DocumentType.PDF,
                artifact_role=ArtifactRole.ORIGINAL_SOURCE,
                training_state=TrainingState.NOT_TRAINED,
            )
            self.assertFalse(item.eligible_for_pageindex)

    def test_tag_knowledge_uses_kepware_path_without_domain_logic(self) -> None:
        item = record(
            document_type=DocumentType.TAG_KNOWLEDGE,
            artifact_role=ArtifactRole.CURATED_MARKDOWN,
            kepware_path="LP2.MIX.Cement_FML",
        )
        self.assertEqual(item.kepware_path, "LP2.MIX.Cement_FML")

    def test_manual_supplier_and_equipment_resources_are_representable(self) -> None:
        for prefix, version in (("MAN", 2), ("SUP", 1), ("EPT", 1)):
            item = record(
                stable_document_id=StableDocumentId(f"doc-{prefix.lower()}"),
                document_version_id=DocumentVersionId(f"ver-{prefix.lower()}-1"),
                source_resource_id=f"{prefix}_{HEX}",
                source_resource_version=version,
            )
            self.assertEqual(item.source_resource_version, version)

    def test_cross_module_reference_collections_validate_prefixes(self) -> None:
        item = record(
            supplier_resource_ids=(f"SUP_{HEX}",),
            contact_ids=(f"CNT_{HEX}",),
            equipment_part_resource_ids=(f"EPT_{HEX}",),
            task_id="FKM-20260817-0041",
        )
        self.assertEqual(len(item.contact_ids), 1)
        with self.assertRaises(ValueError):
            record(contact_ids=(f"SUP_{HEX}",))

    def test_training_and_pageindex_states_are_explicit(self) -> None:
        pending = record(pageindex_state=PageIndexState.PENDING, attempt_count=1)
        failed = replace(pending, pageindex_state=PageIndexState.FAILED, last_error="reason")
        indexed = replace(
            failed, pageindex_state=PageIndexState.INDEXED,
            workspace_document_id="workspace-doc-1", indexed_at=NOW,
        )
        self.assertEqual(pending.training_state.value, "Trained")
        self.assertEqual(failed.pageindex_state.value, "failed")
        self.assertTrue(indexed.eligible_for_pageindex)

    def test_retired_history_is_retained_but_not_eligible(self) -> None:
        retired = record(
            lifecycle_state=LifecycleState.RETIRED,
            pageindex_state=PageIndexState.RETIRED,
        )
        self.assertEqual(retired.relative_locator, "Packing/KM_20260817_120000.md")
        self.assertFalse(retired.eligible_for_pageindex)

    def test_changed_sha_or_source_version_can_have_new_version_identity(self) -> None:
        first = record(source_resource_id=f"MAN_{HEX}", source_resource_version=1)
        changed_sha = record(
            document_version_id=DocumentVersionId("ver-pptx-detail-2"),
            content_sha256="b" * 64,
            source_resource_id=f"MAN_{HEX}", source_resource_version=1,
        )
        changed_source_version = replace(
            changed_sha,
            document_version_id=DocumentVersionId("ver-pptx-detail-3"),
            source_resource_version=2,
        )
        self.assertNotEqual(first.content_sha256, changed_sha.content_sha256)
        self.assertNotEqual(changed_sha.source_resource_version, changed_source_version.source_resource_version)

    def test_same_logical_version_and_sha_is_stable_idempotency_key(self) -> None:
        first = record()
        duplicate = record()
        self.assertEqual(first.document_version_id, duplicate.document_version_id)
        self.assertEqual(first.content_sha256, duplicate.content_sha256)


if __name__ == "__main__":
    unittest.main()
