"""Framework-neutral Manifest identity and lifecycle models."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum
from pathlib import PureWindowsPath

from backend.domain.document import StableDocumentId


_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")
_RESOURCE_ID = re.compile(r"^(MAN|DWG|SUP|QUO|PUR|PHO|DOC|EPT)_[0-9A-F]{32}$")
_SUPPLIER_ID = re.compile(r"^SUP_[0-9A-F]{32}$")
_CONTACT_ID = re.compile(r"^CNT_[0-9A-F]{32}$")
_EQUIPMENT_ID = re.compile(r"^EPT_[0-9A-F]{32}$")


def _opaque(value: str, name: str) -> None:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError(f"{name} must be a valid opaque identifier")


def _optional_text(value: str | None, name: str) -> None:
    if value is not None and (not isinstance(value, str) or not value.strip()):
        raise ValueError(f"{name} must be omitted or non-empty")


def _ids(values: tuple[str, ...], pattern: re.Pattern[str], name: str) -> None:
    if len(values) != len(set(values)) or any(not pattern.fullmatch(v) for v in values):
        raise ValueError(f"{name} must contain unique valid logical identities")


@dataclass(frozen=True, order=True)
class DocumentVersionId:
    value: str

    def __post_init__(self) -> None:
        _opaque(self.value, "document version ID")

    def __str__(self) -> str:
        return self.value


class DocumentType(str, Enum):
    OFFICE = "office"
    PDF = "pdf"
    IMAGE = "image"
    MARKDOWN = "markdown"
    TAG_KNOWLEDGE = "tag_knowledge"
    SHARED_RESOURCE = "shared_resource"
    PROFILE = "profile"


class ArtifactRole(str, Enum):
    ORIGINAL_SOURCE = "original_source"
    DETAIL_MARKDOWN = "detail_markdown"
    SUMMARY_MARKDOWN = "summary_markdown"
    EXTRACTED_MARKDOWN = "extracted_markdown"
    CURATED_MARKDOWN = "curated_markdown"


class TrainingState(str, Enum):
    NOT_APPLICABLE = "NotApplicable"
    NOT_TRAINED = "NotTrained"
    TRAINED = "Trained"
    ERROR = "TrainingError"


class LifecycleState(str, Enum):
    ACTIVE = "active"
    RETIRED = "retired"


class PageIndexState(str, Enum):
    NOT_INDEXED = "not_indexed"
    PENDING = "pending"
    INDEXED = "indexed"
    FAILED = "failed"
    RETIRED = "retired"


@dataclass(frozen=True)
class ManifestRecord:
    stable_document_id: StableDocumentId
    document_version_id: DocumentVersionId
    relative_locator: str
    source_filename: str
    content_sha256: str
    document_type: DocumentType
    artifact_role: ArtifactRole
    training_state: TrainingState
    lifecycle_state: LifecycleState
    pageindex_state: PageIndexState
    created_at: datetime
    updated_at: datetime
    source_resource_id: str | None = None
    source_resource_version: int | None = None
    workspace_document_id: str | None = None
    attempt_count: int = 0
    last_error: str | None = None
    indexed_at: datetime | None = None
    factory_id: str | None = None
    plant_id: str | None = None
    department_id: str | None = None
    process_id: str | None = None
    machine_id: str | None = None
    kepware_path: str | None = None
    supplier_resource_ids: tuple[str, ...] = ()
    contact_ids: tuple[str, ...] = ()
    equipment_part_resource_ids: tuple[str, ...] = ()
    task_id: str | None = None
    concurrency_token: bytes | None = None

    def __post_init__(self) -> None:
        locator = PureWindowsPath(self.relative_locator)
        if (
            not self.relative_locator.strip()
            or locator.is_absolute()
            or locator.drive
            or locator.root
            or ".." in locator.parts
        ):
            raise ValueError("relative locator must be safe and path-independent")
        if not self.source_filename.strip() or PureWindowsPath(self.source_filename).name != self.source_filename:
            raise ValueError("source filename must be a filename, not a path")
        if not _SHA256.fullmatch(self.content_sha256):
            raise ValueError("content SHA-256 must contain exactly 64 hex characters")
        object.__setattr__(self, "content_sha256", self.content_sha256.lower())
        if self.source_resource_id is not None and not _RESOURCE_ID.fullmatch(self.source_resource_id):
            raise ValueError("source ResourceId is invalid")
        if self.source_resource_version is not None and self.source_resource_version < 1:
            raise ValueError("source resource version must be positive")
        if self.source_resource_version is not None and self.source_resource_id is None:
            raise ValueError("source resource version requires SourceResourceId")
        if self.updated_at < self.created_at:
            raise ValueError("updated time must not precede creation time")
        if self.attempt_count < 0:
            raise ValueError("attempt count must not be negative")
        if self.lifecycle_state is LifecycleState.RETIRED and self.pageindex_state is not PageIndexState.RETIRED:
            raise ValueError("retired records require retired PageIndex state")
        _ids(self.supplier_resource_ids, _SUPPLIER_ID, "Supplier ResourceIds")
        _ids(self.contact_ids, _CONTACT_ID, "ContactIds")
        _ids(self.equipment_part_resource_ids, _EQUIPMENT_ID, "EquipmentPart ResourceIds")
        for name in ("workspace_document_id", "factory_id", "plant_id", "department_id", "process_id", "machine_id", "kepware_path", "task_id"):
            _optional_text(getattr(self, name), name)

    @property
    def eligible_for_pageindex(self) -> bool:
        return (
            self.lifecycle_state is LifecycleState.ACTIVE
            and self.training_state is TrainingState.TRAINED
            and self.artifact_role
            in {
                ArtifactRole.DETAIL_MARKDOWN,
                ArtifactRole.SUMMARY_MARKDOWN,
                ArtifactRole.EXTRACTED_MARKDOWN,
                ArtifactRole.CURATED_MARKDOWN,
            }
            and self.pageindex_state is not PageIndexState.RETIRED
        )

    def with_concurrency_token(self, token: bytes) -> "ManifestRecord":
        return replace(self, concurrency_token=token)
