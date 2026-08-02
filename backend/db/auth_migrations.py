"""Ordered SQLite migrations for authentication persistence."""

import sqlite3


MIGRATIONS: tuple[tuple[int, str], ...] = (
    (
        1,
        """
        CREATE TABLE users (
            id TEXT PRIMARY KEY NOT NULL,
            username TEXT NOT NULL COLLATE NOCASE UNIQUE,
            display_name TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
            created_at TEXT NOT NULL
        );

        CREATE TABLE groups (
            id TEXT PRIMARY KEY NOT NULL,
            name TEXT NOT NULL COLLATE NOCASE UNIQUE,
            description TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        );

        CREATE TABLE roles (
            id TEXT PRIMARY KEY NOT NULL,
            name TEXT NOT NULL COLLATE NOCASE UNIQUE,
            permissions_json TEXT NOT NULL DEFAULT '[]',
            description TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        );

        CREATE TABLE user_group_memberships (
            user_id TEXT NOT NULL,
            group_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (user_id, group_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE
        );

        CREATE TABLE user_role_memberships (
            user_id TEXT NOT NULL,
            role_id TEXT NOT NULL,
            scope TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            PRIMARY KEY (user_id, role_id, scope),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE
        );

        CREATE TABLE sessions (
            id TEXT PRIMARY KEY NOT NULL,
            user_id TEXT NOT NULL,
            token_digest TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            revoked_at TEXT,
            viewer INTEGER NOT NULL DEFAULT 0 CHECK (viewer IN (0, 1)),
            metadata_json TEXT NOT NULL DEFAULT '{}',
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE INDEX sessions_user_id_idx ON sessions(user_id);
        CREATE INDEX sessions_expires_at_idx ON sessions(expires_at);
        """,
    ),
)


def apply_auth_migrations(connection: sqlite3.Connection) -> None:
    """Apply pending migrations atomically and in version order."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            component TEXT NOT NULL,
            version INTEGER NOT NULL,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (component, version)
        )
        """
    )
    applied = {
        row[0]
        for row in connection.execute(
            "SELECT version FROM schema_migrations WHERE component = ?",
            ("auth",),
        )
    }
    for version, sql in MIGRATIONS:
        if version in applied:
            continue
        with connection:
            connection.executescript(sql)
            connection.execute(
                "INSERT INTO schema_migrations(component, version) VALUES (?, ?)",
                ("auth", version),
            )
