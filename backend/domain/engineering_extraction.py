"""Persistence-neutral engineering document extraction and review contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class ExtractionContractError(ValueError):
    """Raised when AI or integration data violates the draft contract."""


class EngineeringDocumentType(str, Enum):
    QUOTATION = "quotation"
    MANUAL = "manual"
    DRAWING = "drawing"
    DATASHEET = "datasheet"
    CATALOG = "catalog"
    GENERAL_DOCUMENT = "general_document"
    UNKNOWN = "unknown"


class CommercialLineType(str, Enum):
    EQUIPMENT_PART_CANDIDATE = "equipment_part_candidate"
    SERVICE = "service"
    FREIGHT = "freight"
    INSTALLATION = "installation"
    ENGINEERING = "engineering"
    CALIBRATION = "calibration"
    OTHER = "other"


@dataclass(frozen=True)
class SourceEvidence:
    artifact: str
    location: str
    excerpt: str = ""

    @classmethod
    def parse(cls, value: Any) -> "SourceEvidence":
        if not isinstance(value, dict) or not isinstance(value.get("artifact"), str) or not isinstance(value.get("location"), str):
            raise ExtractionContractError("Evidence must identify an artifact and location.")
        return cls(value["artifact"].strip(), value["location"].strip(), str(value.get("excerpt", "")).strip())


@dataclass(frozen=True)
class ExtractedValue:
    value: Any
    confidence: float
    evidence: tuple[SourceEvidence, ...]

    @classmethod
    def parse(cls, value: Any) -> "ExtractedValue":
        if not isinstance(value, dict) or "value" not in value or not isinstance(value.get("confidence"), (int, float)):
            raise ExtractionContractError("Extracted values require value and confidence.")
        confidence = float(value["confidence"])
        if not 0 <= confidence <= 1: raise ExtractionContractError("Extraction confidence must be between 0 and 1.")
        evidence = value.get("evidence", [])
        if not isinstance(evidence, list): raise ExtractionContractError("Extraction evidence must be a list.")
        return cls(value["value"], confidence, tuple(SourceEvidence.parse(item) for item in evidence))


def _fields(value: Any, allowed: set[str]) -> dict[str, ExtractedValue]:
    if value is None: return {}
    if not isinstance(value, dict) or set(value) - allowed: raise ExtractionContractError("Extraction contains unsupported fields.")
    return {key: ExtractedValue.parse(item) for key, item in value.items()}


SUPPLIER_FIELDS = {"supplier_name", "company_name", "supplier_code", "tax_id", "address", "phone", "website", "email"}
CONTACT_FIELDS = {"name", "department", "role_title", "phone", "mobile", "email", "contact_type"}
EPT_FIELDS = {"description", "manufacturer", "brand", "model", "part_number", "material_code"}
QUOTE_FIELDS = {"quotation_number", "quotation_date", "validity", "currency", "subtotal", "discount", "vat_tax", "grand_total", "payment_terms", "delivery_terms", "delivery_lead_time", "notes"}
MANUAL_FIELDS = {"title", "manufacturer", "brand", "model", "part_number", "document_number", "revision_version", "equipment_product_family", "description"}
LINE_FIELDS = {"line_number", "description", "manufacturer", "brand", "model", "part_number", "material_code", "quantity", "uom", "unit_price", "amount", "notes"}


@dataclass
class Candidate:
    canonical_id: str
    metadata: dict[str, Any]
    match_evidence: list[dict[str, Any]]


@dataclass
class SupplierDraft:
    fields: dict[str, ExtractedValue]
    candidates: list[Candidate] = field(default_factory=list)
    provisional_candidate_id: str | None = None


@dataclass
class ContactDraft:
    draft_id: str
    fields: dict[str, ExtractedValue]
    candidates: list[Candidate] = field(default_factory=list)
    provisional_candidate_id: str | None = None


@dataclass
class EquipmentPartDraft:
    draft_id: str
    fields: dict[str, ExtractedValue]
    candidates: list[Candidate] = field(default_factory=list)
    provisional_candidate_id: str | None = None


@dataclass
class QuotationLineDraft:
    draft_id: str
    line_type: CommercialLineType
    fields: dict[str, ExtractedValue]
    equipment_part: EquipmentPartDraft | None = None


@dataclass
class QuotationDraft:
    fields: dict[str, ExtractedValue]
    issuer_supplier: SupplierDraft | None
    customer_buyer: dict[str, ExtractedValue]
    supplier_contacts: list[ContactDraft]
    lines: list[QuotationLineDraft]


@dataclass
class ManualDraft:
    fields: dict[str, ExtractedValue]
    equipment_part: EquipmentPartDraft | None


@dataclass(frozen=True)
class DocumentClassification:
    document_type: EngineeringDocumentType
    confidence: float
    reason: str
    evidence: tuple[SourceEvidence, ...]


@dataclass
class EngineeringExtractionDraft:
    source_document_id: str
    source_content_sha256: str
    source_file: str
    extractor_version: str
    schema_version: str
    classification: DocumentClassification
    quotation: QuotationDraft | None = None
    manual: ManualDraft | None = None
    state: str = "extracted"
    integration_errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def parse_ai(cls, *, source_document_id: str, source_content_sha256: str, source_file: str,
                 extractor_version: str, schema_version: str, payload: Any) -> "EngineeringExtractionDraft":
        if not isinstance(payload, dict) or not isinstance(payload.get("classification"), dict):
            raise ExtractionContractError("AI extraction response is missing classification.")
        raw_class = payload["classification"]
        try: document_type = EngineeringDocumentType(raw_class.get("document_type"))
        except ValueError as error: raise ExtractionContractError("AI returned an unsupported document type.") from error
        confidence = raw_class.get("confidence")
        if not isinstance(confidence, (int, float)) or not 0 <= float(confidence) <= 1: raise ExtractionContractError("Classification confidence is invalid.")
        classification = DocumentClassification(document_type, float(confidence), str(raw_class.get("reason", "")).strip(), tuple(SourceEvidence.parse(item) for item in raw_class.get("evidence", [])))
        quotation = _parse_quotation(payload.get("quotation")) if document_type is EngineeringDocumentType.QUOTATION else None
        manual = _parse_manual(payload.get("manual")) if document_type is EngineeringDocumentType.MANUAL else None
        return cls(source_document_id, source_content_sha256, source_file, extractor_version, schema_version, classification, quotation, manual)


def _parse_supplier(value: Any) -> SupplierDraft | None:
    return None if value is None else SupplierDraft(_fields(value, SUPPLIER_FIELDS))


def _parse_ept(value: Any, draft_id: str) -> EquipmentPartDraft | None:
    return None if value is None else EquipmentPartDraft(draft_id, _fields(value, EPT_FIELDS))


def _parse_quotation(value: Any) -> QuotationDraft:
    if not isinstance(value, dict): raise ExtractionContractError("Quotation extraction is required for a quotation.")
    contacts = value.get("supplier_contacts", []); lines = value.get("lines", [])
    if not isinstance(contacts, list) or not isinstance(lines, list): raise ExtractionContractError("Quotation contacts and lines must be lists.")
    parsed_contacts = [ContactDraft(f"contact-{index}", _fields(item, CONTACT_FIELDS)) for index, item in enumerate(contacts, 1)]
    parsed_lines = []
    for index, item in enumerate(lines, 1):
        if not isinstance(item, dict): raise ExtractionContractError("Quotation line must be an object.")
        try: line_type = CommercialLineType(item.get("line_type"))
        except ValueError as error: raise ExtractionContractError("Quotation line type is invalid.") from error
        ept = _parse_ept(item.get("equipment_part"), f"line-{index}-ept") if line_type is CommercialLineType.EQUIPMENT_PART_CANDIDATE else None
        parsed_lines.append(QuotationLineDraft(f"line-{index}", line_type, _fields(item.get("fields"), LINE_FIELDS), ept))
    return QuotationDraft(_fields(value.get("fields"), QUOTE_FIELDS), _parse_supplier(value.get("issuer_supplier")),
                          _fields(value.get("customer_buyer"), SUPPLIER_FIELDS), parsed_contacts, parsed_lines)


def _parse_manual(value: Any) -> ManualDraft:
    if not isinstance(value, dict): raise ExtractionContractError("Manual extraction is required for a manual.")
    return ManualDraft(_fields(value.get("fields"), MANUAL_FIELDS), _parse_ept(value.get("equipment_part"), "manual-ept"))
