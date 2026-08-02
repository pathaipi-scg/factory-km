"""Shared Microsoft SQL Server configuration for Factory-KM."""

from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class MSSQLSettings:
    """Connection settings shared by all SQL Server-backed modules."""

    server: str
    database: str
    username: str
    password: str
    driver: str = "ODBC Driver 18 for SQL Server"

    @classmethod
    def from_environment(cls) -> "MSSQLSettings":
        project_root = Path(__file__).resolve().parents[2]
        load_dotenv(project_root / ".env", override=False)
        values = {
            "server": os.environ.get("SQL_SERVER", "").strip(),
            "database": os.environ.get("SQL_DB", "").strip(),
            "username": os.environ.get("SQL_USER", "").strip(),
            "password": os.environ.get("SQL_PASS", ""),
        }
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise ValueError(
                "Missing shared SQL Server configuration: " + ", ".join(missing)
            )
        return cls(**values)

    def connection_string(self) -> str:
        """Build an encrypted ODBC connection string without logging secrets."""
        def quoted(value: str) -> str:
            return "{" + value.replace("}", "}}") + "}"

        return ";".join(
            (
                f"DRIVER={quoted(self.driver)}",
                f"SERVER={quoted(self.server)}",
                f"DATABASE={quoted(self.database)}",
                f"UID={quoted(self.username)}",
                f"PWD={quoted(self.password)}",
                "Encrypt=yes",
                "TrustServerCertificate=yes",
            )
        )
