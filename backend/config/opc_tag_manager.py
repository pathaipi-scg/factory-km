"""Environment-backed OpcTagManager integration configuration."""

from dataclasses import dataclass
import os
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv


@dataclass(frozen=True)
class OpcTagManagerSettings:
    base_url: str
    timeout_seconds: float = 5.0

    @classmethod
    def from_environment(cls) -> "OpcTagManagerSettings":
        load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
        value = os.environ.get("OPC_TAG_MANAGER_BASE_URL", "").strip().rstrip("/")
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.path not in {"", "/"}:
            raise ValueError("OPC_TAG_MANAGER_BASE_URL must be an HTTP(S) origin.")
        return cls(value, float(os.environ.get("OPC_TAG_MANAGER_TIMEOUT_SECONDS", "5")))
