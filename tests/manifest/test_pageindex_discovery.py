"""Pure PageIndex discovery tests using mock Manifest persistence."""

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
from backend.repositories.manifest import ManifestConcurrencyError
from backend.services.pageindex.discovery import (
    DiscoveryReason,
    PageIndexDiscoveryService,
)


NOW = datetime(2026, 8, 17, tzinfo=timezone.utc)


def item(name: str, state: PageIndexState, **changes: object) -> ManifestRecord:
    values: dict[str, object] = {
        "stable_document_id": StableDocumentId(f"doc-{name}"),
        "document_version_id": DocumentVersionId(f"ver-{name}"),
        "relative_locator": f"Packing/{name}.md",
        "source_filename": f"{name}.pptx",
        "content_sha256": (name[0].lower() if name[0].lower() in "abcdef" else "a") * 64,
        "document_type": DocumentType.MARKDOWN,
        "artifact_role": ArtifactRole.DETAIL_MARKDOWN,
        "training_state": TrainingState.TRAINED,
        "lifecycle_state": LifecycleState.ACTIVE,
        "pageindex_state": state,
        "created_at": NOW,
        "updated_at": NOW,
        "concurrency_token": f"token-{name}".encode(),
    }
    values.update(changes)
    return ManifestRecord(**values)  # type: ignore[arg-type]


class FakeManifestRepository:
    def __init__(self, records: tuple[ManifestRecord, ...], missing: tuple[str, ...] = ()) -> None:
        self.records = {str(value.document_version_id): value for value in records}
        self.missing = set(missing)
        self.attempts: list[str] = []
        self.conflict_ids: set[str] = set()

    def list_active_trained_markdown(self):
        return tuple(self.records.values())

    def list_missing_workspace_mapping(self):
        return tuple(self.records[value] for value in self.missing)

    def mark_indexing_attempt(self, document_version_id: str, expected_token: bytes):
        current = self.records[document_version_id]
        if document_version_id in self.conflict_ids or current.concurrency_token != expected_token:
            raise ManifestConcurrencyError("stale")
        updated = replace(
            current,
            pageindex_state=PageIndexState.PENDING,
            attempt_count=current.attempt_count + 1,
            last_error=None,
            concurrency_token=expected_token + b"-next",
        )
        self.records[document_version_id] = updated
        self.attempts.append(document_version_id)
        return updated


class PageIndexDiscoveryTests(unittest.TestCase):
    def test_scan_classifies_new_failed_pending_and_missing_mapping(self) -> None:
        records = (
            item("new", PageIndexState.NOT_INDEXED),
            item("failed", PageIndexState.FAILED, last_error="failure"),
            item("pending", PageIndexState.PENDING, attempt_count=1),
            item("missing", PageIndexState.INDEXED, workspace_document_id=None),
            item("complete", PageIndexState.INDEXED, workspace_document_id="current"),
        )
        repository = FakeManifestRepository(records, missing=("ver-missing",))
        candidates = PageIndexDiscoveryService(repository).scan()  # type: ignore[arg-type]
        reasons = {str(value.record.document_version_id): value.reason for value in candidates}
        self.assertEqual(reasons["ver-new"], DiscoveryReason.NEW_OR_CHANGED)
        self.assertEqual(reasons["ver-failed"], DiscoveryReason.RETRY_FAILED)
        self.assertEqual(reasons["ver-pending"], DiscoveryReason.RESUME_PENDING)
        self.assertEqual(reasons["ver-missing"], DiscoveryReason.MISSING_WORKSPACE_MAPPING)
        self.assertNotIn("ver-complete", reasons)

    def test_prepare_marks_new_failed_and_missing_pending_once(self) -> None:
        records = (
            item("new", PageIndexState.NOT_INDEXED),
            item("failed", PageIndexState.FAILED, last_error="failure"),
            item("pending", PageIndexState.PENDING, attempt_count=2),
            item("missing", PageIndexState.INDEXED, workspace_document_id=None),
        )
        repository = FakeManifestRepository(records, missing=("ver-missing",))
        result = PageIndexDiscoveryService(repository).prepare()  # type: ignore[arg-type]
        self.assertEqual(set(repository.attempts), {"ver-new", "ver-failed", "ver-missing"})
        resumed = next(value for value in result.ready if str(value.document_version_id) == "ver-pending")
        self.assertEqual(resumed.attempt_count, 2)
        self.assertTrue(all(value.pageindex_state is PageIndexState.PENDING for value in result.ready))

    def test_retired_untrained_and_original_sources_are_excluded(self) -> None:
        retired = item(
            "retired", PageIndexState.RETIRED,
            lifecycle_state=LifecycleState.RETIRED,
        )
        untrained = item("untrained", PageIndexState.NOT_INDEXED, training_state=TrainingState.NOT_TRAINED)
        original = item("original", PageIndexState.NOT_INDEXED, artifact_role=ArtifactRole.ORIGINAL_SOURCE)
        repository = FakeManifestRepository((retired, untrained, original))
        self.assertEqual(PageIndexDiscoveryService(repository).scan(), ())  # type: ignore[arg-type]

    def test_duplicate_repository_rows_are_deduplicated_by_version_identity(self) -> None:
        value = item("same", PageIndexState.NOT_INDEXED)

        class DuplicateRepository(FakeManifestRepository):
            def list_active_trained_markdown(self):
                return (value, value)

        candidates = PageIndexDiscoveryService(DuplicateRepository((value,))).scan()  # type: ignore[arg-type]
        self.assertEqual(len(candidates), 1)

    def test_stale_rowversion_is_reported_without_overwrite(self) -> None:
        value = item("conflict", PageIndexState.FAILED, last_error="failure")
        repository = FakeManifestRepository((value,))
        repository.conflict_ids.add("ver-conflict")
        result = PageIndexDiscoveryService(repository).prepare()  # type: ignore[arg-type]
        self.assertEqual(result.ready, ())
        self.assertEqual(result.conflicts, ("ver-conflict",))
        self.assertEqual(repository.records["ver-conflict"].pageindex_state, PageIndexState.FAILED)

    def test_missing_concurrency_token_is_not_mutated(self) -> None:
        value = item("notoken", PageIndexState.NOT_INDEXED, concurrency_token=None)
        repository = FakeManifestRepository((value,))
        result = PageIndexDiscoveryService(repository).prepare()  # type: ignore[arg-type]
        self.assertEqual(result.conflicts, ("ver-notoken",))
        self.assertEqual(repository.attempts, [])


if __name__ == "__main__":
    unittest.main()
