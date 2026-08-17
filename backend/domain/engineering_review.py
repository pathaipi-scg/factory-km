"""Persistence-neutral engineering extraction review and command domain."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import re
import uuid
from typing import Any


class EngineeringReviewError(ValueError): pass
class EngineeringReviewConcurrencyError(RuntimeError): pass


ID_PATTERNS = {"EXR": re.compile(r"^EXR_[0-9A-F]{32}$"), "REV": re.compile(r"^REV_[0-9A-F]{32}$"), "CMD": re.compile(r"^CMD_[0-9A-F]{32}$")}


def new_id(prefix: str) -> str: return f"{prefix}_{uuid.uuid4().hex.upper()}"
def stable_id(prefix: str, key: str) -> str: return f"{prefix}_{uuid.uuid5(uuid.NAMESPACE_URL, key).hex.upper()}"
def validate_id(value: str, prefix: str) -> str:
    if not isinstance(value, str) or not ID_PATTERNS[prefix].fullmatch(value): raise EngineeringReviewError(f"Invalid {prefix} identity.")
    return value


class ExtractionRunStatus(str, Enum): CREATED = "created"; REVIEWING = "reviewing"; CONFIRMED = "confirmed"; CANCELLED = "cancelled"
class ReviewStatus(str, Enum): DRAFT = "draft"; IN_REVIEW = "in_review"; CONFIRMED = "confirmed"; CANCELLED = "cancelled"
class DecisionAction(str, Enum): USE_EXISTING = "use_existing"; PROPOSE_NEW = "propose_new"; PROPOSE_UPDATE = "propose_update"; IGNORE = "ignore"; NOT_EQUIPMENT_PART = "not_equipment_part"; UNRESOLVED = "unresolved"
class DecisionKind(str, Enum): SUPPLIER = "supplier"; CONTACT = "contact"; EQUIPMENT_PART = "equipment_part"; MANUAL_EQUIPMENT_PART = "manual_equipment_part"
class CommandStatus(str, Enum): READY = "ready"; EXECUTING = "executing"; SUCCEEDED = "succeeded"; FAILED = "failed"; CONFLICT = "conflict"; CANCELLED = "cancelled"


@dataclass(frozen=True)
class ExtractionRun:
    extraction_run_id: str; source_document_id: str; source_sha256: str; document_type: str
    extractor_version: str; schema_version: str; snapshot_json: str; idempotency_key: str
    created_at: datetime; status: ExtractionRunStatus = ExtractionRunStatus.CREATED
    stable_document_id: str | None = None; document_version_id: str | None = None
    source_resource_id: str | None = None; source_resource_version: int | None = None

    @classmethod
    def create(cls, *, source_document_id: str, source_sha256: str, document_type: str,
               extractor_version: str, schema_version: str, snapshot: dict[str, Any],
               stable_document_id: str | None = None, document_version_id: str | None = None,
               source_resource_id: str | None = None, source_resource_version: int | None = None,
               now: datetime | None = None) -> "ExtractionRun":
        if not re.fullmatch(r"[0-9a-f]{64}", source_sha256): raise EngineeringReviewError("Source SHA-256 is invalid.")
        snapshot_json = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        _reject_paths(json.loads(snapshot_json))
        identity = "|".join([stable_document_id or source_document_id, document_version_id or "", source_resource_id or "", str(source_resource_version or ""), source_sha256, extractor_version, schema_version])
        key = hashlib.sha256(identity.encode()).hexdigest()
        return cls(stable_id("EXR", key), source_document_id, source_sha256, document_type, extractor_version,
                   schema_version, snapshot_json, key, now or datetime.now(timezone.utc),
                   stable_document_id=stable_document_id, document_version_id=document_version_id,
                   source_resource_id=source_resource_id, source_resource_version=source_resource_version)

    @property
    def snapshot(self) -> dict[str, Any]: return json.loads(self.snapshot_json)


@dataclass(frozen=True)
class ReviewerDecision:
    target_ref: str; kind: DecisionKind; action: DecisionAction; canonical_id: str | None = None
    expected_canonical_version: str | None = None; notes: str = ""

    def __post_init__(self) -> None:
        if not self.target_ref.strip(): raise EngineeringReviewError("Decision target is required.")
        expected = {DecisionKind.SUPPLIER: "SUP_", DecisionKind.CONTACT: "CNT_", DecisionKind.EQUIPMENT_PART: "EPT_", DecisionKind.MANUAL_EQUIPMENT_PART: "EPT_"}[self.kind]
        if self.action in {DecisionAction.USE_EXISTING, DecisionAction.PROPOSE_UPDATE}:
            if not self.canonical_id or not self.canonical_id.startswith(expected): raise EngineeringReviewError("Decision canonical identity is invalid.")
        elif self.canonical_id is not None: raise EngineeringReviewError("This decision action must not carry a canonical identity.")


@dataclass(frozen=True)
class EngineeringReview:
    review_id: str; extraction_run_id: str; status: ReviewStatus; decisions: tuple[ReviewerDecision, ...]
    intended_kepware_paths: tuple[str, ...]; created_at: datetime; updated_at: datetime
    actor_id: str | None = None; source: str = "factory-km-ui"; concurrency_token: bytes = b""

    @classmethod
    def create(cls, extraction_run_id: str, actor_id: str | None = None, now: datetime | None = None) -> "EngineeringReview":
        timestamp = now or datetime.now(timezone.utc)
        return cls(new_id("REV"), validate_id(extraction_run_id, "EXR"), ReviewStatus.DRAFT, (), (), timestamp, timestamp, actor_id)

    def update(self, decisions: tuple[ReviewerDecision, ...], intended_kepware_paths: tuple[str, ...], now: datetime | None = None) -> "EngineeringReview":
        if self.status in {ReviewStatus.CONFIRMED, ReviewStatus.CANCELLED}: raise EngineeringReviewError("Finalized review cannot be modified.")
        if len({item.target_ref for item in decisions}) != len(decisions): raise EngineeringReviewError("Each review target may have one decision.")
        for path in intended_kepware_paths:
            if not path.strip() or "\\" in path or "/" in path: raise EngineeringReviewError("KepwarePath is invalid.")
        return replace(self, status=ReviewStatus.IN_REVIEW, decisions=decisions, intended_kepware_paths=intended_kepware_paths, updated_at=now or datetime.now(timezone.utc))


@dataclass(frozen=True)
class ConfirmedCommand:
    command_id: str; review_id: str; command_type: str; payload_json: str; idempotency_key: str
    status: CommandStatus; attempts: int; last_error: str | None; created_at: datetime; updated_at: datetime
    expected_canonical_version: str | None = None
    @property
    def payload(self) -> dict[str, Any]: return json.loads(self.payload_json)


def prepare_commands(review: EngineeringReview, run: ExtractionRun, now: datetime | None = None) -> tuple[ConfirmedCommand, ...]:
    timestamp = now or datetime.now(timezone.utc); output = []
    for decision in review.decisions:
        mapping = {
            (DecisionKind.SUPPLIER, DecisionAction.USE_EXISTING): "UseExistingSupplier",
            (DecisionKind.SUPPLIER, DecisionAction.PROPOSE_NEW): "ProposeCreateSupplier",
            (DecisionKind.SUPPLIER, DecisionAction.PROPOSE_UPDATE): "ProposeUpdateSupplier",
            (DecisionKind.CONTACT, DecisionAction.USE_EXISTING): "UseExistingContact",
            (DecisionKind.CONTACT, DecisionAction.PROPOSE_NEW): "ProposeCreateContact",
            (DecisionKind.CONTACT, DecisionAction.PROPOSE_UPDATE): "ProposeUpdateContact",
            (DecisionKind.EQUIPMENT_PART, DecisionAction.USE_EXISTING): "UseExistingEquipmentPart",
            (DecisionKind.EQUIPMENT_PART, DecisionAction.PROPOSE_NEW): "ProposeCreateEquipmentPart",
            (DecisionKind.EQUIPMENT_PART, DecisionAction.PROPOSE_UPDATE): "ProposeUpdateEquipmentPart",
            (DecisionKind.MANUAL_EQUIPMENT_PART, DecisionAction.USE_EXISTING): "UseExistingEquipmentPart",
            (DecisionKind.MANUAL_EQUIPMENT_PART, DecisionAction.PROPOSE_NEW): "ProposeCreateEquipmentPart",
        }
        command_type = mapping.get((decision.kind, decision.action))
        if not command_type: continue
        payload = {"target_ref": decision.target_ref, **({"canonical_id": decision.canonical_id} if decision.canonical_id else {})}
        output.append(_command(review.review_id, command_type, payload, decision.expected_canonical_version, timestamp))
        if decision.canonical_id and decision.kind in {DecisionKind.EQUIPMENT_PART, DecisionKind.MANUAL_EQUIPMENT_PART}:
            if run.source_resource_id: output.append(_command(review.review_id, "LinkResourceToEquipmentPart", {"source_resource_id": run.source_resource_id, "equipment_part_id": decision.canonical_id}, decision.expected_canonical_version, timestamp))
            for path in review.intended_kepware_paths: output.append(_command(review.review_id, "LinkEquipmentPartToTag", {"equipment_part_id": decision.canonical_id, "kepware_path": path}, decision.expected_canonical_version, timestamp))
        if decision.canonical_id and decision.kind is DecisionKind.SUPPLIER and run.source_resource_id:
            output.append(_command(review.review_id, "LinkResourceToSupplier", {"source_resource_id": run.source_resource_id, "supplier_id": decision.canonical_id}, decision.expected_canonical_version, timestamp))
    return tuple(sorted({item.idempotency_key: item for item in output}.values(), key=lambda item: item.idempotency_key))


def _command(review_id: str, command_type: str, payload: dict[str, Any], version: str | None, now: datetime) -> ConfirmedCommand:
    _reject_paths(payload); payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":")); key = hashlib.sha256(f"{review_id}|{command_type}|{payload_json}".encode()).hexdigest()
    return ConfirmedCommand(stable_id("CMD", key), review_id, command_type, payload_json, key, CommandStatus.READY, 0, None, now, now, version)


def _reject_paths(value: Any) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).casefold() in {"filesystem_path", "vault_path", "absolute_path"}: raise EngineeringReviewError("Physical paths are not allowed.")
            _reject_paths(item)
    elif isinstance(value, list):
        for item in value: _reject_paths(item)
    elif isinstance(value, str) and (value.startswith("\\\\") or (len(value) > 2 and value[1:3] in {":\\", ":/"})):
        raise EngineeringReviewError("Physical paths are not allowed.")
