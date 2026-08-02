"""Framework-neutral Vault Management domain models."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import PurePosixPath
from typing import Any


class VaultOperation(str, Enum):
    """Supported Vault Management actions."""

    LIST = "list"
    CREATE_FOLDER = "create_folder"
    UPLOAD = "upload"
    RENAME = "rename"
    MOVE = "move"
    EDIT = "edit"
    SOFT_DELETE = "soft_delete"
    RESTORE = "restore"


@dataclass(frozen=True, order=True)
class VaultPath:
    """Normalized relative path scoped beneath the configured Vault root."""

    value: str = ""

    def __post_init__(self) -> None:
        raw = self.value.strip().replace("\\", "/")
        if raw.startswith("/"):
            raise ValueError("Vault paths must remain relative to the Vault root.")
        normalized = raw.strip("/")
        path = PurePosixPath(normalized)
        if path.is_absolute() or any(part in {".", ".."} for part in path.parts):
            raise ValueError("Vault paths must remain relative to the Vault root.")
        if path.parts and ":" in path.parts[0]:
            raise ValueError("Vault paths must not contain a drive prefix.")
        object.__setattr__(self, "value", "" if normalized == "." else str(path))

    @property
    def name(self) -> str:
        return PurePosixPath(self.value).name if self.value else ""

    def child(self, name: str) -> "VaultPath":
        """Return a validated child path."""
        if not name or "/" in name or "\\" in name:
            raise ValueError("Vault child names must contain one path segment.")
        return VaultPath(f"{self.value}/{name}" if self.value else name)


@dataclass(frozen=True)
class VaultScope:
    """Authorization scope rooted at one Vault-relative path."""

    id: str
    root: VaultPath
    operations: tuple[VaultOperation, ...]
    recursive: bool = True


@dataclass(frozen=True)
class VaultEntry:
    """Shared metadata for a Vault filesystem entry."""

    path: VaultPath
    name: str
    created_at: datetime | None = None
    modified_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FileEntry(VaultEntry):
    """Vault file metadata without file content."""

    size_bytes: int = 0
    media_type: str | None = None
    checksum: str | None = None


@dataclass(frozen=True)
class FolderEntry(VaultEntry):
    """Vault folder metadata."""

    child_count: int | None = None


@dataclass(frozen=True)
class VaultOperationResult:
    """Normalized outcome from one Vault operation."""

    operation: VaultOperation
    success: bool
    source_path: VaultPath
    destination_path: VaultPath | None = None
    entry: VaultEntry | None = None
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AuditEvent:
    """Immutable record of an attempted Vault operation."""

    id: str
    actor_user_id: str
    operation: VaultOperation
    source_path: VaultPath
    occurred_at: datetime
    success: bool
    destination_path: VaultPath | None = None
    session_id: str | None = None
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ManifestEvent:
    """Event announcing a successful Vault change to future consumers."""

    id: str
    operation: VaultOperation
    source_path: VaultPath
    occurred_at: datetime
    destination_path: VaultPath | None = None
    actor_user_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
