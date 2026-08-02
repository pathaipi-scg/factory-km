"""Environment-backed configuration for authentication persistence."""

from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class AuthSettings:
    """SQLite persistence settings for the isolated authentication module."""

    sqlite_path: Path
    fastapi_enabled: bool = False
    session_max_age_seconds: int = 86400

    @classmethod
    def from_environment(cls) -> "AuthSettings":
        """Load the auth database path without initializing the database."""
        project_root = Path(__file__).resolve().parents[2]
        load_dotenv(project_root / ".env", override=False)
        configured_path = os.environ.get("AUTH_SQLITE_PATH", "").strip()
        sqlite_path = (
            Path(configured_path)
            if configured_path
            else project_root / "data" / "auth.sqlite3"
        )
        enabled_value = os.environ.get("AUTH_FASTAPI_ENABLED", "false").strip().lower()
        if enabled_value not in {"true", "false"}:
            raise ValueError("AUTH_FASTAPI_ENABLED must be 'true' or 'false'")
        return cls(
            sqlite_path=sqlite_path,
            fastapi_enabled=enabled_value == "true",
            session_max_age_seconds=86400,
        )
