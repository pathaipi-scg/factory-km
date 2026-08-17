"""Structured draft extraction from completed Factory-KM Markdown."""

from __future__ import annotations

import json
import re
from typing import Any

from backend.domain.engineering_extraction import (
    Candidate, CommercialLineType, EngineeringExtractionDraft, ExtractedValue,
    ExtractionContractError,
)
from backend.services.llm_service import LLMProvider, AzureOpenAIProvider
from backend.config.azure_openai import AzureOpenAISettings
from backend.services.opc_tag_manager_client import OpcTagManagerClient, OpcTagManagerClientError
from backend.services.training_service import TrainedKmInput


EXTRACTOR_VERSION = "engineering-extractor-1"
SCHEMA_VERSION = "engineering-extraction-draft-1"


class EngineeringExtractionError(RuntimeError):
    """Safe extraction failure."""


class EngineeringExtractionService:
    def __init__(self, ai_provider: LLMProvider | None = None,
                 opc_client: OpcTagManagerClient | None = None) -> None:
        self.ai_provider = ai_provider or AzureOpenAIProvider(AzureOpenAISettings.from_environment())
        self.opc_client = opc_client or OpcTagManagerClient()

    def extract(self, source: TrainedKmInput) -> EngineeringExtractionDraft:
        try:
            raw = self.ai_provider.generate(context=self._context(source), question=self._instructions())
            payload = json.loads(self._json_text(raw))
            draft = EngineeringExtractionDraft.parse_ai(
                source_document_id=source.source_document_id,
                source_content_sha256=source.source_content_sha256,
                source_file=source.source_file,
                extractor_version=EXTRACTOR_VERSION,
                schema_version=SCHEMA_VERSION,
                payload=payload,
            )
        except (json.JSONDecodeError, ExtractionContractError, TypeError, ValueError) as error:
            raise EngineeringExtractionError("AI returned an invalid engineering extraction draft.") from error
        self._add_candidates(draft)
        return draft

    def contact_candidates(self, supplier_resource_id: str, fields: dict[str, Any]) -> list[dict[str, Any]]:
        values = {key: self._plain(value) for key, value in fields.items() if key in {"name", "email", "phone", "mobile"}}
        phone = values.get("phone") or values.get("mobile", "")
        return self.opc_client.contact_candidates(supplier_resource_id=supplier_resource_id,
                                                  name=values.get("name", ""), email=values.get("email", ""), phone=phone)

    def _add_candidates(self, draft: EngineeringExtractionDraft) -> None:
        if draft.quotation and draft.quotation.issuer_supplier:
            supplier = draft.quotation.issuer_supplier
            fields = supplier.fields
            self._safe_lookup(draft, supplier.candidates, lambda: self.opc_client.supplier_candidates(
                tax_id=self._value(fields, "tax_id"), supplier_code=self._value(fields, "supplier_code"),
                name=self._value(fields, "company_name") or self._value(fields, "supplier_name"),
                website=self._value(fields, "website"), phone=self._value(fields, "phone"), address=self._value(fields, "address")))
            for line in draft.quotation.lines:
                if line.line_type is CommercialLineType.EQUIPMENT_PART_CANDIDATE and line.equipment_part:
                    self._match_ept(draft, line.equipment_part)
        if draft.manual and draft.manual.equipment_part: self._match_ept(draft, draft.manual.equipment_part)

    def _match_ept(self, draft: EngineeringExtractionDraft, equipment: Any) -> None:
        fields = equipment.fields
        self._safe_lookup(draft, equipment.candidates, lambda: self.opc_client.equipment_part_candidates(
            material_code=self._value(fields, "material_code"), manufacturer=self._value(fields, "manufacturer"),
            part_no=self._value(fields, "part_number"), model=self._value(fields, "model"),
            display_name=self._value(fields, "description"), alias=self._value(fields, "description")))

    @staticmethod
    def _safe_lookup(draft: EngineeringExtractionDraft, destination: list[Candidate], lookup: Any) -> None:
        try:
            for item in lookup():
                canonical_id = item.get("resource_id") or item.get("contact_id")
                destination.append(Candidate(canonical_id, {key: value for key, value in item.items() if key != "match_evidence"}, item.get("match_evidence", [])))
        except OpcTagManagerClientError as error:
            draft.integration_errors.append(str(error))

    @staticmethod
    def _value(fields: dict[str, ExtractedValue], key: str) -> str:
        return EngineeringExtractionService._plain(fields[key].value) if key in fields else ""

    @staticmethod
    def _plain(value: Any) -> str:
        if isinstance(value, dict) and "value" in value: value = value["value"]
        return str(value).strip() if value is not None else ""

    @staticmethod
    def _json_text(value: str) -> str:
        text = value.strip()
        match = re.fullmatch(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
        return match.group(1) if match else text

    @staticmethod
    def _context(source: TrainedKmInput) -> str:
        return f"SOURCE_DOCUMENT_ID: {source.source_document_id}\nSOURCE_FILE: {source.source_file}\n\nDETAIL MARKDOWN:\n{source.detail_markdown}\n\nSUMMARY MARKDOWN:\n{source.summary_markdown}"

    @staticmethod
    def _instructions() -> str:
        return """Return JSON only for schema engineering-extraction-draft-1. Classify document_type as quotation, manual, drawing, datasheet, catalog, general_document, or unknown using content evidence, not filename alone. Every value object is {\"value\":...,\"confidence\":0..1,\"evidence\":[{\"artifact\":\"detail_markdown|summary_markdown\",\"location\":\"Slide/page/section\",\"excerpt\":\"short text\"}]}. Root: {\"classification\":{\"document_type\":...,\"confidence\":...,\"reason\":...,\"evidence\":[...]},\"quotation\":null|{\"fields\":{},\"issuer_supplier\":null|{},\"customer_buyer\":{},\"supplier_contacts\":[],\"lines\":[{\"line_type\":\"equipment_part_candidate|service|freight|installation|engineering|calibration|other\",\"fields\":{},\"equipment_part\":null|{}}]},\"manual\":null|{\"fields\":{},\"equipment_part\":null|{}}}. Keep issuer supplier distinct from customer buyer. Only physical/catalog lines may use equipment_part_candidate. Never invent canonical IDs or facts."""
