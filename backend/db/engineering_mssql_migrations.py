"""Idempotent central SQL Server migrations for engineering review state."""

from datetime import datetime, timezone
from typing import Any


ENGINEERING_MSSQL_MIGRATIONS = ((1, """
IF OBJECT_ID(N'engineering.ExtractionRuns', N'U') IS NULL BEGIN
 CREATE TABLE engineering.ExtractionRuns(
  ExtractionRunId NVARCHAR(36) NOT NULL CONSTRAINT PK_engineering_ExtractionRuns PRIMARY KEY,
  StableDocumentId NVARCHAR(128) NULL, DocumentVersionId NVARCHAR(128) NULL,
  SourceDocumentId NVARCHAR(128) NOT NULL, SourceResourceId NVARCHAR(64) NULL,
  SourceResourceVersion INT NULL, SourceSha256 CHAR(64) NOT NULL,
  DocumentType NVARCHAR(32) NOT NULL, ExtractorVersion NVARCHAR(128) NOT NULL,
  SchemaVersion NVARCHAR(128) NOT NULL, IdempotencyKey CHAR(64) NOT NULL,
  SnapshotJson NVARCHAR(MAX) NOT NULL, Status NVARCHAR(32) NOT NULL, CreatedAt DATETIME2(7) NOT NULL,
  CONSTRAINT CK_engineering_ExtractionSnapshotJson CHECK(ISJSON(SnapshotJson)=1),
  CONSTRAINT CK_engineering_ExtractionSha CHECK(LEN(SourceSha256)=64 AND SourceSha256 NOT LIKE '%[^0-9a-f]%'),
  CONSTRAINT CK_engineering_ExtractionStatus CHECK(Status IN('created','reviewing','confirmed','cancelled'))
 );
 CREATE UNIQUE INDEX UX_engineering_ExtractionRuns_Idempotency ON engineering.ExtractionRuns(IdempotencyKey);
 CREATE INDEX IX_engineering_ExtractionRuns_Source ON engineering.ExtractionRuns(StableDocumentId,DocumentVersionId,SourceResourceId,CreatedAt);
END;
IF OBJECT_ID(N'engineering.Reviews', N'U') IS NULL BEGIN
 CREATE TABLE engineering.Reviews(
  ReviewId NVARCHAR(36) NOT NULL CONSTRAINT PK_engineering_Reviews PRIMARY KEY,
  ExtractionRunId NVARCHAR(36) NOT NULL, Status NVARCHAR(32) NOT NULL,
  DecisionsJson NVARCHAR(MAX) NOT NULL CONSTRAINT DF_engineering_Reviews_Decisions DEFAULT N'[]',
  KepwarePathsJson NVARCHAR(MAX) NOT NULL CONSTRAINT DF_engineering_Reviews_Kepware DEFAULT N'[]',
  ActorId NVARCHAR(256) NULL, Source NVARCHAR(128) NOT NULL,
  CreatedAt DATETIME2(7) NOT NULL, UpdatedAt DATETIME2(7) NOT NULL, RowVersion ROWVERSION NOT NULL,
  CONSTRAINT FK_engineering_Reviews_Run FOREIGN KEY(ExtractionRunId) REFERENCES engineering.ExtractionRuns(ExtractionRunId),
  CONSTRAINT CK_engineering_Reviews_Status CHECK(Status IN('draft','in_review','confirmed','cancelled')),
  CONSTRAINT CK_engineering_Reviews_Decisions CHECK(ISJSON(DecisionsJson)=1),
  CONSTRAINT CK_engineering_Reviews_Kepware CHECK(ISJSON(KepwarePathsJson)=1)
 );
 CREATE INDEX IX_engineering_Reviews_Run ON engineering.Reviews(ExtractionRunId,UpdatedAt);
END;
IF OBJECT_ID(N'engineering.Commands', N'U') IS NULL BEGIN
 CREATE TABLE engineering.Commands(
  CommandId NVARCHAR(36) NOT NULL CONSTRAINT PK_engineering_Commands PRIMARY KEY,
  ReviewId NVARCHAR(36) NOT NULL, CommandType NVARCHAR(128) NOT NULL, PayloadJson NVARCHAR(MAX) NOT NULL,
  IdempotencyKey CHAR(64) NOT NULL, ExpectedCanonicalVersion NVARCHAR(256) NULL,
  Status NVARCHAR(32) NOT NULL, Attempts INT NOT NULL CONSTRAINT DF_engineering_Commands_Attempts DEFAULT 0,
  LastError NVARCHAR(4000) NULL, CreatedAt DATETIME2(7) NOT NULL, UpdatedAt DATETIME2(7) NOT NULL,
  RowVersion ROWVERSION NOT NULL,
  CONSTRAINT FK_engineering_Commands_Review FOREIGN KEY(ReviewId) REFERENCES engineering.Reviews(ReviewId),
  CONSTRAINT CK_engineering_Commands_Payload CHECK(ISJSON(PayloadJson)=1),
  CONSTRAINT CK_engineering_Commands_Status CHECK(Status IN('ready','executing','succeeded','failed','conflict','cancelled')),
  CONSTRAINT CK_engineering_Commands_Attempts CHECK(Attempts>=0)
 );
 CREATE UNIQUE INDEX UX_engineering_Commands_Idempotency ON engineering.Commands(IdempotencyKey);
 CREATE INDEX IX_engineering_Commands_Ready ON engineering.Commands(Status,CreatedAt);
END;
IF OBJECT_ID(N'engineering.ReviewEvents', N'U') IS NULL BEGIN
 CREATE TABLE engineering.ReviewEvents(
  ReviewEventId BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_engineering_ReviewEvents PRIMARY KEY,
  ReviewId NVARCHAR(36) NOT NULL, ActionAt DATETIME2(7) NOT NULL, ActorId NVARCHAR(256) NULL,
  Source NVARCHAR(128) NOT NULL, PreviousState NVARCHAR(32) NULL, NewState NVARCHAR(32) NOT NULL,
  CONSTRAINT FK_engineering_ReviewEvents_Review FOREIGN KEY(ReviewId) REFERENCES engineering.Reviews(ReviewId)
 );
 CREATE INDEX IX_engineering_ReviewEvents_Review ON engineering.ReviewEvents(ReviewId,ActionAt);
END;
"""),)


def apply_engineering_mssql_migrations(connection: Any) -> None:
    cursor=connection.cursor(); cursor.execute("""IF SCHEMA_ID(N'engineering') IS NULL EXEC(N'CREATE SCHEMA engineering');
IF OBJECT_ID(N'engineering.SchemaMigrations',N'U') IS NULL CREATE TABLE engineering.SchemaMigrations(Version INT NOT NULL CONSTRAINT PK_engineering_SchemaMigrations PRIMARY KEY,AppliedAt DATETIME2(7) NOT NULL);""")
    cursor.execute("SELECT Version FROM engineering.SchemaMigrations"); applied={int(row[0]) for row in cursor.fetchall()}
    for version,sql in ENGINEERING_MSSQL_MIGRATIONS:
        if version in applied: continue
        cursor.execute(sql); cursor.execute("INSERT INTO engineering.SchemaMigrations(Version,AppliedAt) VALUES(?,?)",version,datetime.now(timezone.utc).replace(tzinfo=None))
