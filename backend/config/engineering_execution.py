"""Safety configuration for controlled engineering canonical execution."""

from dataclasses import dataclass
import os
from pathlib import Path
from dotenv import load_dotenv


@dataclass(frozen=True)
class EngineeringExecutionSettings:
    write_enabled: bool = False
    lease_seconds: int = 300

    @classmethod
    def from_environment(cls) -> "EngineeringExecutionSettings":
        load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
        enabled = os.environ.get("ENGINEERING_CANONICAL_WRITE_ENABLED", "false").strip().casefold() == "true"
        lease = int(os.environ.get("ENGINEERING_COMMAND_LEASE_SECONDS", "300"))
        if not 30 <= lease <= 3600: raise ValueError("ENGINEERING_COMMAND_LEASE_SECONDS must be between 30 and 3600.")
        return cls(enabled, lease)
