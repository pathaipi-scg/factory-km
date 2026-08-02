"""SQL Server database boundary for authentication persistence."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from backend.db.auth_mssql_migrations import apply_auth_mssql_migrations
from backend.db.mssql import MSSQLConnectionFactory


class AuthMSSQLDatabase:
    def __init__(self, connection_factory: MSSQLConnectionFactory) -> None:
        self.connection_factory = connection_factory

    def initialize(self) -> None:
        with self.connect() as connection:
            apply_auth_mssql_migrations(connection)

    @contextmanager
    def connect(self) -> Iterator[Any]:
        with self.connection_factory.connect() as connection:
            yield connection
