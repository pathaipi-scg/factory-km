"""Idempotent Microsoft SQL Server migrations for authentication."""

from datetime import datetime, timezone
from typing import Any


AUTH_MSSQL_MIGRATIONS: tuple[tuple[int, str], ...] = (
    (
        1,
        """
        IF OBJECT_ID(N'auth.Users', N'U') IS NULL
        BEGIN
            CREATE TABLE auth.Users (
                Id NVARCHAR(128) NOT NULL CONSTRAINT PK_auth_Users PRIMARY KEY,
                Username NVARCHAR(255) COLLATE Latin1_General_100_CI_AS NOT NULL,
                DisplayName NVARCHAR(255) NOT NULL,
                PasswordHash NVARCHAR(512) NOT NULL,
                Active BIT NOT NULL CONSTRAINT DF_auth_Users_Active DEFAULT 1,
                CreatedAt DATETIME2(7) NOT NULL
                    CONSTRAINT DF_auth_Users_CreatedAt DEFAULT SYSUTCDATETIME(),
                CONSTRAINT UQ_auth_Users_Username UNIQUE (Username),
                CONSTRAINT CK_auth_Users_Argon2id
                    CHECK (PasswordHash LIKE '$argon2id$%')
            );
        END;

        IF OBJECT_ID(N'auth.Groups', N'U') IS NULL
        BEGIN
            CREATE TABLE auth.Groups (
                Id NVARCHAR(128) NOT NULL CONSTRAINT PK_auth_Groups PRIMARY KEY,
                Name NVARCHAR(255) COLLATE Latin1_General_100_CI_AS NOT NULL,
                Description NVARCHAR(1000) NOT NULL
                    CONSTRAINT DF_auth_Groups_Description DEFAULT N'',
                CreatedAt DATETIME2(7) NOT NULL
                    CONSTRAINT DF_auth_Groups_CreatedAt DEFAULT SYSUTCDATETIME(),
                CONSTRAINT UQ_auth_Groups_Name UNIQUE (Name)
            );
        END;

        IF OBJECT_ID(N'auth.Roles', N'U') IS NULL
        BEGIN
            CREATE TABLE auth.Roles (
                Id NVARCHAR(128) NOT NULL CONSTRAINT PK_auth_Roles PRIMARY KEY,
                Name NVARCHAR(255) COLLATE Latin1_General_100_CI_AS NOT NULL,
                PermissionsJson NVARCHAR(MAX) NOT NULL
                    CONSTRAINT DF_auth_Roles_Permissions DEFAULT N'[]',
                Description NVARCHAR(1000) NOT NULL
                    CONSTRAINT DF_auth_Roles_Description DEFAULT N'',
                CreatedAt DATETIME2(7) NOT NULL
                    CONSTRAINT DF_auth_Roles_CreatedAt DEFAULT SYSUTCDATETIME(),
                CONSTRAINT UQ_auth_Roles_Name UNIQUE (Name),
                CONSTRAINT CK_auth_Roles_PermissionsJson CHECK (ISJSON(PermissionsJson) = 1)
            );
        END;

        IF OBJECT_ID(N'auth.UserGroupMemberships', N'U') IS NULL
        BEGIN
            CREATE TABLE auth.UserGroupMemberships (
                UserId NVARCHAR(128) NOT NULL,
                GroupId NVARCHAR(128) NOT NULL,
                CreatedAt DATETIME2(7) NOT NULL
                    CONSTRAINT DF_auth_UserGroups_CreatedAt DEFAULT SYSUTCDATETIME(),
                CONSTRAINT PK_auth_UserGroupMemberships PRIMARY KEY (UserId, GroupId),
                CONSTRAINT FK_auth_UserGroups_User FOREIGN KEY (UserId)
                    REFERENCES auth.Users(Id) ON DELETE CASCADE,
                CONSTRAINT FK_auth_UserGroups_Group FOREIGN KEY (GroupId)
                    REFERENCES auth.Groups(Id) ON DELETE CASCADE
            );
        END;

        IF OBJECT_ID(N'auth.UserRoleMemberships', N'U') IS NULL
        BEGIN
            CREATE TABLE auth.UserRoleMemberships (
                UserId NVARCHAR(128) NOT NULL,
                RoleId NVARCHAR(128) NOT NULL,
                Scope NVARCHAR(512) NOT NULL
                    CONSTRAINT DF_auth_UserRoles_Scope DEFAULT N'',
                CreatedAt DATETIME2(7) NOT NULL
                    CONSTRAINT DF_auth_UserRoles_CreatedAt DEFAULT SYSUTCDATETIME(),
                CONSTRAINT PK_auth_UserRoleMemberships PRIMARY KEY (UserId, RoleId, Scope),
                CONSTRAINT FK_auth_UserRoles_User FOREIGN KEY (UserId)
                    REFERENCES auth.Users(Id) ON DELETE CASCADE,
                CONSTRAINT FK_auth_UserRoles_Role FOREIGN KEY (RoleId)
                    REFERENCES auth.Roles(Id) ON DELETE CASCADE
            );
        END;

        IF OBJECT_ID(N'auth.Sessions', N'U') IS NULL
        BEGIN
            CREATE TABLE auth.Sessions (
                Id NVARCHAR(128) NOT NULL CONSTRAINT PK_auth_Sessions PRIMARY KEY,
                UserId NVARCHAR(128) NOT NULL,
                TokenDigest CHAR(64) NOT NULL,
                CreatedAt DATETIME2(7) NOT NULL,
                ExpiresAt DATETIME2(7) NOT NULL,
                RevokedAt DATETIME2(7) NULL,
                Viewer BIT NOT NULL CONSTRAINT DF_auth_Sessions_Viewer DEFAULT 0,
                MetadataJson NVARCHAR(MAX) NOT NULL
                    CONSTRAINT DF_auth_Sessions_Metadata DEFAULT N'{}',
                CONSTRAINT UQ_auth_Sessions_TokenDigest UNIQUE (TokenDigest),
                CONSTRAINT FK_auth_Sessions_User FOREIGN KEY (UserId)
                    REFERENCES auth.Users(Id) ON DELETE CASCADE,
                CONSTRAINT CK_auth_Sessions_TokenDigest
                    CHECK (LEN(TokenDigest) = 64 AND TokenDigest NOT LIKE '%[^0-9a-f]%'),
                CONSTRAINT CK_auth_Sessions_MetadataJson CHECK (ISJSON(MetadataJson) = 1),
                CONSTRAINT CK_auth_Sessions_Expiry CHECK (ExpiresAt > CreatedAt)
            );
            CREATE INDEX IX_auth_Sessions_UserId ON auth.Sessions(UserId);
            CREATE INDEX IX_auth_Sessions_ExpiresAt ON auth.Sessions(ExpiresAt);
        END;
        """,
    ),
)


def apply_auth_mssql_migrations(connection: Any) -> None:
    """Apply each auth migration once inside the caller's transaction."""
    cursor = connection.cursor()
    cursor.execute(
        """
        IF SCHEMA_ID(N'auth') IS NULL EXEC(N'CREATE SCHEMA auth');
        IF OBJECT_ID(N'auth.SchemaMigrations', N'U') IS NULL
        BEGIN
            CREATE TABLE auth.SchemaMigrations (
                Component NVARCHAR(64) NOT NULL,
                Version INT NOT NULL,
                AppliedAt DATETIME2(7) NOT NULL
                    CONSTRAINT DF_auth_Migrations_AppliedAt DEFAULT SYSUTCDATETIME(),
                CONSTRAINT PK_auth_SchemaMigrations PRIMARY KEY (Component, Version)
            );
        END;
        """
    )
    cursor.execute(
        "SELECT Version FROM auth.SchemaMigrations WHERE Component = ?",
        "auth",
    )
    applied = {int(row[0]) for row in cursor.fetchall()}
    for version, sql in AUTH_MSSQL_MIGRATIONS:
        if version in applied:
            continue
        cursor.execute(sql)
        cursor.execute(
            """
            INSERT INTO auth.SchemaMigrations(Component, Version, AppliedAt)
            VALUES (?, ?, ?)
            """,
            "auth",
            version,
            datetime.now(timezone.utc).replace(tzinfo=None),
        )
