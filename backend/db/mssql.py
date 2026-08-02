"""Shared pyodbc connection factory for Microsoft SQL Server."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, Callable

from backend.config.mssql import MSSQLSettings


class MSSQLConnectionFactory:
    """Open transactional SQL Server connections from shared settings."""

    def __init__(
        self,
        settings: MSSQLSettings,
        connect: Callable[..., Any] | None = None,
    ) -> None:
        self.settings = settings
        self._connect = connect

    def _connector(self) -> Callable[..., Any]:
        if self._connect is not None:
            return self._connect
        try:
            import pyodbc
        except ImportError as exc:  # pragma: no cover - deployment dependency
            raise RuntimeError("pyodbc is required for SQL Server persistence") from exc
        return pyodbc.connect

    @contextmanager
    def connect(self) -> Iterator[Any]:
        connection = self._connector()(
            self.settings.connection_string(),
            autocommit=False,
        )
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
