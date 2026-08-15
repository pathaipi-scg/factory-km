"""Authoritative filesystem Vault configuration for Factory-KM."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import tempfile

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_VAULT_ROOT = Path(r"D:\KM\Vault")


class VaultConfigurationError(ValueError):
    """The configured Vault is missing or cannot satisfy an operation."""


@dataclass(frozen=True)
class VaultSettings:
    """Resolved Vault location shared by Python runtime components."""

    root: Path
    explicitly_configured: bool

    @classmethod
    def from_environment(cls) -> "VaultSettings":
        load_dotenv(PROJECT_ROOT / ".env", override=False)
        configured = "KM_VAULT_ROOT" in os.environ
        raw_root = os.environ.get("KM_VAULT_ROOT") if configured else str(DEFAULT_VAULT_ROOT)
        if raw_root is None or not raw_root.strip():
            raise VaultConfigurationError("KM_VAULT_ROOT is configured but empty.")
        root = Path(os.path.abspath(os.path.normpath(raw_root.strip())))
        return cls(root=root, explicitly_configured=configured)

    def require_readable(self) -> Path:
        if not self.root.exists():
            raise VaultConfigurationError(f"KM Vault is unavailable: {self.root}")
        if not self.root.is_dir():
            raise VaultConfigurationError(f"KM Vault is not a directory: {self.root}")
        try:
            with os.scandir(self.root):
                pass
        except OSError as error:
            raise VaultConfigurationError(f"KM Vault is not readable: {self.root}") from error
        return self.root

    def require_writable(self) -> Path:
        self.require_readable()
        try:
            descriptor, probe = tempfile.mkstemp(prefix=".factory-km-write-", dir=self.root)
            os.close(descriptor)
            os.unlink(probe)
        except OSError as error:
            raise VaultConfigurationError(f"KM Vault is not writable: {self.root}") from error
        return self.root


def get_vault_settings() -> VaultSettings:
    """Resolve Vault settings at the caller's configuration boundary."""
    return VaultSettings.from_environment()
