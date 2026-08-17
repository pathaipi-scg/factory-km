"""Idempotent SQL Server migrations for the central Manifest domain."""

from datetime import datetime, timezone
from typing import Any


MANIFEST_MSSQL_MIGRATIONS: tuple[tuple[int, str], ...] = (
    (
        1,
        """
        IF OBJECT_ID(N'manifest.Documents', N'U') IS NULL
        BEGIN
            CREATE TABLE manifest.Documents (
                StableDocumentId NVARCHAR(128) NOT NULL
                    CONSTRAINT PK_manifest_Documents PRIMARY KEY,
                DocumentType NVARCHAR(32) NOT NULL,
                ArtifactRole NVARCHAR(32) NOT NULL,
                SourceFilename NVARCHAR(512) NOT NULL,
                SourceResourceId NVARCHAR(64) NULL,
                FactoryId NVARCHAR(128) NULL,
                PlantId NVARCHAR(128) NULL,
                DepartmentId NVARCHAR(128) NULL,
                ProcessId NVARCHAR(128) NULL,
                MachineId NVARCHAR(128) NULL,
                KepwarePath NVARCHAR(1024) NULL,
                TaskId NVARCHAR(128) NULL,
                SupplierResourceIdsJson NVARCHAR(MAX) NOT NULL
                    CONSTRAINT DF_manifest_Documents_Suppliers DEFAULT N'[]',
                ContactIdsJson NVARCHAR(MAX) NOT NULL
                    CONSTRAINT DF_manifest_Documents_Contacts DEFAULT N'[]',
                EquipmentPartResourceIdsJson NVARCHAR(MAX) NOT NULL
                    CONSTRAINT DF_manifest_Documents_EquipmentParts DEFAULT N'[]',
                CreatedAt DATETIME2(7) NOT NULL,
                UpdatedAt DATETIME2(7) NOT NULL,
                RowVersion ROWVERSION NOT NULL,
                CONSTRAINT CK_manifest_Documents_SuppliersJson
                    CHECK (ISJSON(SupplierResourceIdsJson) = 1),
                CONSTRAINT CK_manifest_Documents_ContactsJson
                    CHECK (ISJSON(ContactIdsJson) = 1),
                CONSTRAINT CK_manifest_Documents_EquipmentPartsJson
                    CHECK (ISJSON(EquipmentPartResourceIdsJson) = 1)
            );
            CREATE UNIQUE INDEX UX_manifest_Documents_SourceResource
                ON manifest.Documents(SourceResourceId, ArtifactRole)
                WHERE SourceResourceId IS NOT NULL;
        END;

        IF OBJECT_ID(N'manifest.DocumentVersions', N'U') IS NULL
        BEGIN
            CREATE TABLE manifest.DocumentVersions (
                DocumentVersionId NVARCHAR(128) NOT NULL
                    CONSTRAINT PK_manifest_DocumentVersions PRIMARY KEY,
                StableDocumentId NVARCHAR(128) NOT NULL,
                SourceResourceVersion INT NULL,
                RelativeLocator NVARCHAR(2048) NOT NULL,
                ContentSha256 CHAR(64) NOT NULL,
                ArtifactRole NVARCHAR(32) NOT NULL,
                TrainingState NVARCHAR(32) NOT NULL,
                LifecycleState NVARCHAR(16) NOT NULL,
                PageIndexState NVARCHAR(32) NOT NULL,
                WorkspaceDocumentId NVARCHAR(256) NULL,
                AttemptCount INT NOT NULL
                    CONSTRAINT DF_manifest_Versions_Attempts DEFAULT 0,
                LastError NVARCHAR(4000) NULL,
                CreatedAt DATETIME2(7) NOT NULL,
                UpdatedAt DATETIME2(7) NOT NULL,
                IndexedAt DATETIME2(7) NULL,
                RowVersion ROWVERSION NOT NULL,
                CONSTRAINT FK_manifest_Versions_Document FOREIGN KEY (StableDocumentId)
                    REFERENCES manifest.Documents(StableDocumentId),
                CONSTRAINT CK_manifest_Versions_SHA256 CHECK (
                    LEN(ContentSha256) = 64
                    AND ContentSha256 NOT LIKE '%[^0-9a-f]%'
                ),
                CONSTRAINT CK_manifest_Versions_Attempts CHECK (AttemptCount >= 0),
                CONSTRAINT CK_manifest_Versions_SourceVersion CHECK (
                    SourceResourceVersion IS NULL OR SourceResourceVersion > 0
                ),
                CONSTRAINT CK_manifest_Versions_Lifecycle CHECK (
                    LifecycleState IN ('active', 'retired')
                ),
                CONSTRAINT CK_manifest_Versions_PageIndexState CHECK (
                    PageIndexState IN ('not_indexed','pending','indexed','failed','retired')
                )
            );
            CREATE UNIQUE INDEX UX_manifest_Versions_ContentDiscovery
                ON manifest.DocumentVersions(
                    StableDocumentId, ArtifactRole, SourceResourceVersion, ContentSha256
                );
            CREATE UNIQUE INDEX UX_manifest_Versions_SourceVersion
                ON manifest.DocumentVersions(
                    StableDocumentId, ArtifactRole, SourceResourceVersion, ContentSha256
                )
                WHERE SourceResourceVersion IS NOT NULL;
            CREATE UNIQUE INDEX UX_manifest_Versions_OneActive
                ON manifest.DocumentVersions(StableDocumentId)
                WHERE LifecycleState = 'active';
            CREATE INDEX IX_manifest_Versions_Discovery
                ON manifest.DocumentVersions(LifecycleState, TrainingState, ArtifactRole, PageIndexState);
            CREATE INDEX IX_manifest_Versions_Workspace
                ON manifest.DocumentVersions(WorkspaceDocumentId);
        END;
        """,
    ),
)


def apply_manifest_mssql_migrations(connection: Any) -> None:
    """Apply Manifest migrations once inside the caller's transaction."""
    cursor = connection.cursor()
    cursor.execute(
        """
        IF SCHEMA_ID(N'manifest') IS NULL EXEC(N'CREATE SCHEMA manifest');
        IF OBJECT_ID(N'manifest.SchemaMigrations', N'U') IS NULL
        BEGIN
            CREATE TABLE manifest.SchemaMigrations (
                Version INT NOT NULL CONSTRAINT PK_manifest_SchemaMigrations PRIMARY KEY,
                AppliedAt DATETIME2(7) NOT NULL
                    CONSTRAINT DF_manifest_Migrations_AppliedAt DEFAULT SYSUTCDATETIME()
            );
        END;
        """
    )
    cursor.execute("SELECT Version FROM manifest.SchemaMigrations")
    applied = {int(row[0]) for row in cursor.fetchall()}
    for version, sql in MANIFEST_MSSQL_MIGRATIONS:
        if version in applied:
            continue
        cursor.execute(sql)
        cursor.execute(
            "INSERT INTO manifest.SchemaMigrations(Version, AppliedAt) VALUES (?, ?)",
            version,
            datetime.now(timezone.utc).replace(tzinfo=None),
        )
