"""Transactional SQL Server Manifest repository."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

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
from backend.repositories.manifest.mssql.database import ManifestMSSQLDatabase
from backend.repositories.manifest.protocols import ManifestConcurrencyError


def _utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _utc_aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _row(cursor: Any) -> dict[str, Any] | None:
    names = [str(column[0]).lower() for column in cursor.description]
    value = cursor.fetchone()
    return dict(zip(names, value)) if value is not None else None


def _rows(cursor: Any) -> list[dict[str, Any]]:
    names = [str(column[0]).lower() for column in cursor.description]
    return [dict(zip(names, value)) for value in cursor.fetchall()]


_SELECT = """
SELECT
    d.StableDocumentId, v.DocumentVersionId, v.RelativeLocator,
    d.SourceFilename, v.ContentSha256, d.DocumentType, v.ArtifactRole,
    v.TrainingState, v.LifecycleState, v.PageIndexState,
    d.CreatedAt AS DocumentCreatedAt, v.CreatedAt, v.UpdatedAt,
    d.SourceResourceId, v.SourceResourceVersion, v.WorkspaceDocumentId,
    v.AttemptCount, v.LastError, v.IndexedAt, d.FactoryId, d.PlantId,
    d.DepartmentId, d.ProcessId, d.MachineId, d.KepwarePath,
    d.SupplierResourceIdsJson, d.ContactIdsJson,
    d.EquipmentPartResourceIdsJson, d.TaskId, v.RowVersion
FROM manifest.DocumentVersions AS v
JOIN manifest.Documents AS d ON d.StableDocumentId = v.StableDocumentId
"""


class MSSQLManifestRepository:
    def __init__(self, database: ManifestMSSQLDatabase) -> None:
        self._database = database

    def discover(self, record: ManifestRecord) -> ManifestRecord:
        """Create a version or return its existing SHA/source-version match."""
        with self._database.connect() as connection:
            cursor = connection.cursor()
            cursor.execute(
                _SELECT.replace(
                    "FROM manifest.DocumentVersions AS v",
                    "FROM manifest.DocumentVersions AS v WITH (UPDLOCK, HOLDLOCK)",
                )
                + """ WHERE v.StableDocumentId = ? AND v.ArtifactRole = ?
                      AND v.ContentSha256 = ?
                      AND ((v.SourceResourceVersion = ?) OR
                           (v.SourceResourceVersion IS NULL AND ? IS NULL))""",
                str(record.stable_document_id),
                record.artifact_role.value,
                record.content_sha256,
                record.source_resource_version,
                record.source_resource_version,
            )
            existing = _row(cursor)
            if existing:
                return self._to_record(existing)

            cursor.execute(
                """
                IF EXISTS (
                    SELECT 1 FROM manifest.Documents
                    WHERE StableDocumentId = ? AND (
                        ArtifactRole <> ? OR DocumentType <> ? OR
                        ISNULL(SourceResourceId, N'') <> ISNULL(?, N'')
                    )
                )
                    THROW 50001, 'StableDocumentId metadata conflict.', 1;
                IF NOT EXISTS (
                    SELECT 1 FROM manifest.Documents WHERE StableDocumentId = ?
                )
                INSERT INTO manifest.Documents (
                    StableDocumentId, DocumentType, ArtifactRole, SourceFilename,
                    SourceResourceId, FactoryId, PlantId, DepartmentId,
                    ProcessId, MachineId, KepwarePath, TaskId,
                    SupplierResourceIdsJson, ContactIdsJson,
                    EquipmentPartResourceIdsJson, CreatedAt, UpdatedAt
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                str(record.stable_document_id),
                record.artifact_role.value,
                record.document_type.value,
                record.source_resource_id,
                str(record.stable_document_id),
                str(record.stable_document_id),
                record.document_type.value,
                record.artifact_role.value,
                record.source_filename,
                record.source_resource_id,
                record.factory_id,
                record.plant_id,
                record.department_id,
                record.process_id,
                record.machine_id,
                record.kepware_path,
                record.task_id,
                json.dumps(record.supplier_resource_ids),
                json.dumps(record.contact_ids),
                json.dumps(record.equipment_part_resource_ids),
                _utc_naive(record.created_at),
                _utc_naive(record.updated_at),
            )
            cursor.execute(
                """UPDATE manifest.DocumentVersions
                   SET LifecycleState = 'retired', PageIndexState = 'retired',
                       WorkspaceDocumentId = NULL, UpdatedAt = SYSUTCDATETIME()
                   WHERE StableDocumentId = ? AND LifecycleState = 'active'""",
                str(record.stable_document_id),
            )
            cursor.execute(
                """
                INSERT INTO manifest.DocumentVersions (
                    DocumentVersionId, StableDocumentId, SourceResourceVersion,
                    RelativeLocator, ContentSha256, ArtifactRole, TrainingState,
                    LifecycleState, PageIndexState, WorkspaceDocumentId,
                    AttemptCount, LastError, CreatedAt, UpdatedAt, IndexedAt
                )
                OUTPUT inserted.RowVersion
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                str(record.document_version_id),
                str(record.stable_document_id),
                record.source_resource_version,
                record.relative_locator,
                record.content_sha256,
                record.artifact_role.value,
                record.training_state.value,
                record.lifecycle_state.value,
                record.pageindex_state.value,
                record.workspace_document_id,
                record.attempt_count,
                record.last_error,
                _utc_naive(record.created_at),
                _utc_naive(record.updated_at),
                _utc_naive(record.indexed_at) if record.indexed_at else None,
            )
            inserted = cursor.fetchone()
            return record.with_concurrency_token(bytes(inserted[0]))

    def get_version(self, document_version_id: str) -> ManifestRecord | None:
        with self._database.connect() as connection:
            cursor = connection.cursor()
            cursor.execute(_SELECT + " WHERE v.DocumentVersionId = ?", document_version_id)
            row = _row(cursor)
        return self._to_record(row) if row else None

    def list_active_trained_markdown(self) -> tuple[ManifestRecord, ...]:
        roles = tuple(role.value for role in ArtifactRole if role is not ArtifactRole.ORIGINAL_SOURCE)
        placeholders = ",".join("?" for _ in roles)
        sql = _SELECT + f""" WHERE v.LifecycleState = 'active'
            AND v.TrainingState = 'Trained'
            AND v.ArtifactRole IN ({placeholders})
            AND v.PageIndexState <> 'retired'
            ORDER BY v.CreatedAt, v.DocumentVersionId"""
        return self._list(sql, *roles)

    def list_by_pageindex_states(self, *states: PageIndexState) -> tuple[ManifestRecord, ...]:
        if not states:
            return ()
        placeholders = ",".join("?" for _ in states)
        return self._list(
            _SELECT + f" WHERE v.PageIndexState IN ({placeholders}) ORDER BY v.UpdatedAt",
            *(state.value for state in states),
        )

    def list_missing_workspace_mapping(self) -> tuple[ManifestRecord, ...]:
        return self._list(
            _SELECT
            + """ WHERE v.LifecycleState = 'active'
                  AND v.TrainingState = 'Trained'
                  AND v.ArtifactRole <> 'original_source'
                  AND v.WorkspaceDocumentId IS NULL
                  ORDER BY v.UpdatedAt"""
        )

    def mark_training_state(self, document_version_id: str, state: TrainingState, expected_token: bytes) -> ManifestRecord:
        return self._transition(
            document_version_id,
            expected_token,
            "TrainingState = ?",
            state.value,
        )

    def mark_indexing_attempt(self, document_version_id: str, expected_token: bytes) -> ManifestRecord:
        return self._transition(
            document_version_id,
            expected_token,
            "PageIndexState = 'pending', AttemptCount = AttemptCount + 1, LastError = NULL",
        )

    def mark_indexed(self, document_version_id: str, workspace_document_id: str, expected_token: bytes) -> ManifestRecord:
        if not workspace_document_id.strip():
            raise ValueError("workspace document ID must not be empty")
        return self._transition(
            document_version_id,
            expected_token,
            "PageIndexState = 'indexed', WorkspaceDocumentId = ?, IndexedAt = SYSUTCDATETIME(), LastError = NULL",
            workspace_document_id,
        )

    def mark_failed(self, document_version_id: str, error: str, expected_token: bytes) -> ManifestRecord:
        if not error.strip():
            raise ValueError("index error must not be empty")
        return self._transition(
            document_version_id,
            expected_token,
            "PageIndexState = 'failed', LastError = ?",
            error[:4000],
        )

    def mark_retired(self, document_version_id: str, expected_token: bytes) -> ManifestRecord:
        return self._transition(
            document_version_id,
            expected_token,
            "LifecycleState = 'retired', PageIndexState = 'retired', WorkspaceDocumentId = NULL",
        )

    def _transition(self, document_version_id: str, expected_token: bytes, assignment: str, *values: object) -> ManifestRecord:
        with self._database.connect() as connection:
            cursor = connection.cursor()
            cursor.execute(
                f"""UPDATE manifest.DocumentVersions
                    SET {assignment}, UpdatedAt = SYSUTCDATETIME()
                    OUTPUT inserted.RowVersion
                    WHERE DocumentVersionId = ? AND RowVersion = ?""",
                *values,
                document_version_id,
                expected_token,
            )
            if cursor.fetchone() is None:
                raise ManifestConcurrencyError("Manifest record was modified concurrently.")
        updated = self.get_version(document_version_id)
        if updated is None:
            raise ManifestConcurrencyError("Manifest record no longer exists.")
        return updated

    def _list(self, sql: str, *parameters: object) -> tuple[ManifestRecord, ...]:
        with self._database.connect() as connection:
            cursor = connection.cursor()
            cursor.execute(sql, *parameters)
            rows = _rows(cursor)
        return tuple(self._to_record(row) for row in rows)

    @staticmethod
    def _to_record(row: dict[str, Any]) -> ManifestRecord:
        def array(name: str) -> tuple[str, ...]:
            value = json.loads(str(row[name]))
            return tuple(str(item) for item in value)

        return ManifestRecord(
            stable_document_id=StableDocumentId(str(row["stabledocumentid"])),
            document_version_id=DocumentVersionId(str(row["documentversionid"])),
            relative_locator=str(row["relativelocator"]),
            source_filename=str(row["sourcefilename"]),
            content_sha256=str(row["contentsha256"]),
            document_type=DocumentType(str(row["documenttype"])),
            artifact_role=ArtifactRole(str(row["artifactrole"])),
            training_state=TrainingState(str(row["trainingstate"])),
            lifecycle_state=LifecycleState(str(row["lifecyclestate"])),
            pageindex_state=PageIndexState(str(row["pageindexstate"])),
            created_at=_utc_aware(row["createdat"]),
            updated_at=_utc_aware(row["updatedat"]),
            source_resource_id=row["sourceresourceid"],
            source_resource_version=row["sourceresourceversion"],
            workspace_document_id=row["workspacedocumentid"],
            attempt_count=int(row["attemptcount"]),
            last_error=row["lasterror"],
            indexed_at=_utc_aware(row["indexedat"]),
            factory_id=row["factoryid"], plant_id=row["plantid"],
            department_id=row["departmentid"], process_id=row["processid"],
            machine_id=row["machineid"], kepware_path=row["kepwarepath"],
            supplier_resource_ids=array("supplierresourceidsjson"),
            contact_ids=array("contactidsjson"),
            equipment_part_resource_ids=array("equipmentpartresourceidsjson"),
            task_id=row["taskid"], concurrency_token=bytes(row["rowversion"]),
        )
