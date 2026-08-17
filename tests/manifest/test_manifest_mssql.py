"""Mocked SQL Server migration and Manifest repository tests."""

import unittest
from contextlib import contextmanager
from datetime import datetime, timezone

from backend.db.manifest_mssql_migrations import (
    MANIFEST_MSSQL_MIGRATIONS,
    apply_manifest_mssql_migrations,
)
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
from backend.repositories.manifest import ManifestRepository
from backend.repositories.manifest.mssql.repository import (
    MSSQLManifestRepository,
    ManifestConcurrencyError,
)


class FakeCursor:
    def __init__(self, result_sets=None) -> None:
        self.result_sets = list(result_sets or [])
        self.executions: list[tuple[str, tuple[object, ...]]] = []
        self.description = [("Value",)]
        self._current = []

    def execute(self, sql: str, *params: object):
        self.executions.append((sql, params))
        self._current = self.result_sets.pop(0) if self.result_sets else []
        return self

    def fetchall(self):
        return self._current

    def fetchone(self):
        return self._current[0] if self._current else None


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self.value = cursor

    def cursor(self) -> FakeCursor:
        return self.value


class FakeDatabase:
    def __init__(self, *connections: FakeConnection) -> None:
        self.connections = list(connections)

    @contextmanager
    def connect(self):
        yield self.connections.pop(0)


def fixture() -> ManifestRecord:
    now = datetime(2026, 8, 17, tzinfo=timezone.utc)
    return ManifestRecord(
        StableDocumentId("doc-1"), DocumentVersionId("ver-1"),
        "Packing/KM_1.md", "source.pptx", "a" * 64,
        DocumentType.MARKDOWN, ArtifactRole.DETAIL_MARKDOWN,
        TrainingState.TRAINED, LifecycleState.ACTIVE,
        PageIndexState.NOT_INDEXED, now, now,
    )


class ManifestMSSQLTests(unittest.TestCase):
    def test_migration_uses_dedicated_schema_rowversion_and_constraints(self) -> None:
        sql = "\n".join(value for _, value in MANIFEST_MSSQL_MIGRATIONS)
        self.assertIn("manifest.Documents", sql)
        self.assertIn("manifest.DocumentVersions", sql)
        self.assertIn("ROWVERSION", sql)
        self.assertIn("UX_manifest_Versions_ContentDiscovery", sql)
        self.assertIn("UX_manifest_Versions_SourceVersion", sql)
        self.assertIn("UX_manifest_Versions_OneActive", sql)
        self.assertIn("SourceResourceId, ArtifactRole", sql)
        self.assertNotIn("REFERENCES auth.", sql)

    def test_migration_is_idempotent_when_version_recorded(self) -> None:
        cursor = FakeCursor(result_sets=[[], [(1,)]])
        apply_manifest_mssql_migrations(FakeConnection(cursor))
        statements = "\n".join(sql for sql, _ in cursor.executions)
        self.assertIn("manifest.SchemaMigrations", statements)
        self.assertNotIn("CREATE TABLE manifest.Documents", statements)

    def test_repository_satisfies_discovery_contract(self) -> None:
        repository = MSSQLManifestRepository(FakeDatabase())  # type: ignore[arg-type]
        self.assertIsInstance(repository, ManifestRepository)

    def test_discover_inserts_document_and_version_transactionally(self) -> None:
        cursor = FakeCursor(result_sets=[[], [], [], [(b"12345678",)]])
        repository = MSSQLManifestRepository(  # type: ignore[arg-type]
            FakeDatabase(FakeConnection(cursor))
        )
        created = repository.discover(fixture())
        statements = "\n".join(sql for sql, _ in cursor.executions)
        self.assertIn("INSERT INTO manifest.Documents", statements)
        self.assertIn("INSERT INTO manifest.DocumentVersions", statements)
        self.assertIn("LifecycleState = 'retired'", statements)
        self.assertEqual(created.concurrency_token, b"12345678")

    def test_discover_checks_sha_and_source_version_before_insert(self) -> None:
        cursor = FakeCursor(result_sets=[[]])
        repository = MSSQLManifestRepository(  # type: ignore[arg-type]
            FakeDatabase(FakeConnection(cursor))
        )
        with self.assertRaises(TypeError):
            # No insert result is supplied; execution reaches the mocked boundary.
            repository.discover(fixture())
        first_sql, parameters = cursor.executions[0]
        self.assertIn("UPDLOCK, HOLDLOCK", first_sql)
        self.assertIn("v.ContentSha256 = ?", first_sql)
        self.assertIn("v.SourceResourceVersion", first_sql)
        self.assertIn("a" * 64, parameters)

    def test_state_change_uses_rowversion_and_detects_conflict(self) -> None:
        cursor = FakeCursor(result_sets=[[]])
        repository = MSSQLManifestRepository(  # type: ignore[arg-type]
            FakeDatabase(FakeConnection(cursor))
        )
        with self.assertRaises(ManifestConcurrencyError):
            repository.mark_indexing_attempt("ver-1", b"oldtoken")
        sql, parameters = cursor.executions[0]
        self.assertIn("RowVersion = ?", sql)
        self.assertIn("AttemptCount = AttemptCount + 1", sql)
        self.assertEqual(parameters[-1], b"oldtoken")

    def test_discovery_queries_cover_active_pending_failed_and_missing_mapping(self) -> None:
        cursors = [FakeCursor(result_sets=[[]]) for _ in range(3)]
        repository = MSSQLManifestRepository(  # type: ignore[arg-type]
            FakeDatabase(*(FakeConnection(cursor) for cursor in cursors))
        )
        self.assertEqual(repository.list_active_trained_markdown(), ())
        self.assertEqual(
            repository.list_by_pageindex_states(PageIndexState.PENDING, PageIndexState.FAILED),
            (),
        )
        self.assertEqual(repository.list_missing_workspace_mapping(), ())
        self.assertIn("TrainingState = 'Trained'", cursors[0].executions[0][0])
        self.assertIn("PageIndexState IN", cursors[1].executions[0][0])
        self.assertIn("WorkspaceDocumentId IS NULL", cursors[2].executions[0][0])


if __name__ == "__main__":
    unittest.main()
