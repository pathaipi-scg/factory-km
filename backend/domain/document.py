"""Shared document identity and aggregate models.

These models deliberately do not depend on FastAPI, persistence libraries,
filesystem paths, PageIndex identifiers, or authentication models.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


_OPAQUE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")


def _validate_opaque_id(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not _OPAQUE_ID_PATTERN.fullmatch(value):
        raise ValueError(
            f"{field_name} must be a non-empty opaque identifier containing "
            "only letters, numbers, '.', '_' or '-'"
        )


def _validate_non_empty(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must not be empty")


@dataclass(frozen=True, order=True)
class StableDocumentId:
    """Canonical document identity, independent of location and index data."""

    value: str

    def __post_init__(self) -> None:
        _validate_opaque_id(self.value, "document ID")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, order=True)
class FolderId:
    """Stable folder identity that does not encode a filesystem path."""

    value: str

    def __post_init__(self) -> None:
        _validate_opaque_id(self.value, "folder ID")

    def __str__(self) -> str:
        return self.value


class ActorKind(str, Enum):
    USER = "user"
    SERVICE = "service"
    SYSTEM = "system"


@dataclass(frozen=True)
class AuditActor:
    """Portable actor snapshot for attribution without an auth dependency."""

    kind: ActorKind
    actor_id: str
    display_name: str

    def __post_init__(self) -> None:
        _validate_opaque_id(self.actor_id, "actor ID")
        _validate_non_empty(self.display_name, "actor display name")


class OwnershipKind(str, Enum):
    USER = "user"
    GROUP = "group"
    DEPARTMENT = "department"
    SYSTEM = "system"


@dataclass(frozen=True)
class Ownership:
    """Responsibility assignment only; it grants no access or permission."""

    kind: OwnershipKind
    owner_id: str

    def __post_init__(self) -> None:
        _validate_opaque_id(self.owner_id, "owner ID")


class DocumentKind(str, Enum):
    ORIGINAL = "original"
    KM_DETAIL = "km_detail"
    KM_SUMMARY = "km_summary"


class DocumentStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    RETIRED = "retired"


@dataclass(frozen=True)
class DocumentVersion:
    """An immutable version entity belonging to one Document aggregate."""

    version_id: str
    document_id: StableDocumentId
    sequence: int
    content_sha256: str
    storage_reference: str
    media_type: str
    created_at: datetime
    created_by: AuditActor
    size_bytes: int | None = None

    def __post_init__(self) -> None:
        _validate_opaque_id(self.version_id, "version ID")
        if self.sequence < 1:
            raise ValueError("version sequence must be at least 1")
        if not _SHA256_PATTERN.fullmatch(self.content_sha256):
            raise ValueError("content SHA-256 must contain exactly 64 hex characters")
        _validate_non_empty(self.storage_reference, "storage reference")
        _validate_non_empty(self.media_type, "media type")
        if self.size_bytes is not None and self.size_bytes < 0:
            raise ValueError("size in bytes must not be negative")
        object.__setattr__(self, "content_sha256", self.content_sha256.lower())


@dataclass(frozen=True)
class Document:
    """Aggregate root for one original, detail, or summary document."""

    document_id: StableDocumentId
    kind: DocumentKind
    title: str
    folder_id: FolderId
    ownership: Ownership
    versions: tuple[DocumentVersion, ...]
    current_version_id: str
    created_at: datetime
    updated_at: datetime
    status: DocumentStatus = DocumentStatus.ACTIVE
    derived_from_document_id: StableDocumentId | None = None
    plant_id: str | None = None
    department_id: str | None = None
    process_id: str | None = None
    machine_id: str | None = None

    def __post_init__(self) -> None:
        _validate_non_empty(self.title, "document title")
        _validate_opaque_id(self.current_version_id, "current version ID")
        if not self.versions:
            raise ValueError("document must contain at least one version")
        if self.updated_at < self.created_at:
            raise ValueError("document update time must not precede creation time")
        if self.derived_from_document_id == self.document_id:
            raise ValueError("document cannot be derived from itself")

        version_ids = [version.version_id for version in self.versions]
        sequences = [version.sequence for version in self.versions]
        if len(version_ids) != len(set(version_ids)):
            raise ValueError("document version IDs must be unique")
        if len(sequences) != len(set(sequences)):
            raise ValueError("document version sequences must be unique")
        if self.current_version_id not in version_ids:
            raise ValueError("current version must belong to the document")
        if any(version.document_id != self.document_id for version in self.versions):
            raise ValueError("all versions must belong to the document")

        for field_name in (
            "plant_id",
            "department_id",
            "process_id",
            "machine_id",
        ):
            value = getattr(self, field_name)
            if value is not None:
                _validate_opaque_id(value, field_name.replace("_", " "))

    @property
    def current_version(self) -> DocumentVersion:
        """Return the version selected as current by the aggregate."""

        return next(
            version
            for version in self.versions
            if version.version_id == self.current_version_id
        )
