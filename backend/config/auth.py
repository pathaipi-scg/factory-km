"""Environment-backed configuration for experimental authentication."""

from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv

from backend.config.mssql import MSSQLSettings


@dataclass(frozen=True)
class AuthSettings:
    """Auth behavior plus the project's shared SQL Server settings."""

    fastapi_enabled: bool = False
    session_max_age_seconds: int = 86400
    mssql: MSSQLSettings | None = None

    @classmethod
    def from_environment(cls) -> "AuthSettings":
        """Load feature state and shared SQL Server settings."""
        project_root = Path(__file__).resolve().parents[2]
        load_dotenv(project_root / ".env", override=False)
        enabled_value = os.environ.get("AUTH_FASTAPI_ENABLED", "false").strip().lower()
        if enabled_value not in {"true", "false"}:
            raise ValueError("AUTH_FASTAPI_ENABLED must be 'true' or 'false'")
        return cls(
            fastapi_enabled=enabled_value == "true",
            session_max_age_seconds=86400,
            mssql=MSSQLSettings.from_environment() if enabled_value == "true" else None,
        )
