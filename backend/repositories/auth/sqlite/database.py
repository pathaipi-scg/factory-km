"""SQLite connection and migration boundary for authentication persistence."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from backend.db.auth_migrations import apply_auth_migrations


class AuthSQLiteDatabase:
    """Open configured SQLite connections with auth integrity settings."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def initialize(self) -> None:
        """Create the parent directory and apply pending schema migrations."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            apply_auth_migrations(connection)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """Yield and always close a foreign-key-enforcing connection."""
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
