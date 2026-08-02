"""Framework-neutral shared domain models."""

from .document import (
    ActorKind,
    AuditActor,
    Document,
    DocumentKind,
    DocumentStatus,
    DocumentVersion,
    FolderId,
    Ownership,
    OwnershipKind,
    StableDocumentId,
)
from .reference import (
    Department,
    DepartmentId,
    Machine,
    MachineId,
    Plant,
    PlantId,
    Process,
    ProcessId,
    ReferenceLifecycle,
)

__all__ = [
    "ActorKind",
    "AuditActor",
    "Document",
    "DocumentKind",
    "DocumentStatus",
    "DocumentVersion",
    "Department",
    "DepartmentId",
    "FolderId",
    "Machine",
    "MachineId",
    "Ownership",
    "OwnershipKind",
    "Plant",
    "PlantId",
    "Process",
    "ProcessId",
    "ReferenceLifecycle",
    "StableDocumentId",
]
