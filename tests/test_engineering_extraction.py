import json
import unittest

from backend.domain.engineering_extraction import CommercialLineType, EngineeringDocumentType
from backend.services.engineering_extraction_service import EngineeringExtractionError, EngineeringExtractionService
from backend.services.training_service import TrainedKmInput


def ev(value, location="Slide 1", confidence=0.95):
    return {"value": value, "confidence": confidence, "evidence": [{"artifact": "detail_markdown", "location": location, "excerpt": str(value)}]}


def classification(kind, confidence=0.9):
    return {"document_type": kind, "confidence": confidence, "reason": "content structure", "evidence": [{"artifact": "detail_markdown", "location": "Slide 1", "excerpt": kind}]}


def quotation_payload():
    return {"classification": classification("quotation"), "quotation": {
        "fields": {"quotation_number": ev("QT-001"), "quotation_date": ev("2026-08-17"), "grand_total": ev("1070.00")},
        "issuer_supplier": {"supplier_name": ev("KEYENCE THAILAND"), "tax_id": ev("001-02-003", confidence=0.99), "phone": ev("+66 2000")},
        "customer_buyer": {"company_name": ev("CUSTOMER FACTORY"), "tax_id": ev("00999")},
        "supplier_contacts": [{"name": ev("Sales Person"), "email": ev("sales@keyence.example"), "contact_type": ev("Sales")}],
        "lines": [
            {"line_type": "equipment_part_candidate", "fields": {"line_number": ev("1"), "description": ev("FR-S01 Sensor"), "manufacturer": ev("KEYENCE"), "model": ev("FR-S01"), "quantity": ev("2")}, "equipment_part": {"description": ev("FR-S01 Sensor"), "manufacturer": ev("KEYENCE"), "model": ev("FR-S01")}},
            {"line_type": "freight", "fields": {"line_number": ev("2"), "description": ev("Freight"), "amount": ev("70")}, "equipment_part": {"description": ev("must be ignored")}},
        ]}, "manual": None}


def manual_payload():
    return {"classification": classification("manual"), "quotation": None, "manual": {"fields": {
        "title": ev("ACS550 User Manual"), "manufacturer": ev("ABB"), "model": ev("ACS550"), "part_number": ev("ACS550-01")},
        "equipment_part": {"description": ev("ABB ACS550"), "manufacturer": ev("ABB"), "model": ev("ACS550"), "part_number": ev("ACS550-01")}}}


class FakeProvider:
    def __init__(self, payload): self.payload = payload; self.calls = []
    def generate(self, *, context, question): self.calls.append((context, question)); return json.dumps(self.payload)


class FakeOpcClient:
    def __init__(self): self.calls = []
    def supplier_candidates(self, **signals):
        self.calls.append(("supplier", signals)); return [{"resource_id": "SUP_1", "supplier_name": "KEYENCE A", "match_evidence": [{"signal": "tax_id"}]}, {"resource_id": "SUP_2", "supplier_name": "KEYENCE B", "match_evidence": [{"signal": "name"}]}]
    def equipment_part_candidates(self, **signals):
        self.calls.append(("ept", signals)); return [{"resource_id": "EPT_1", "display_name": "FR-S01", "match_evidence": [{"signal": "manufacturer_model"}]}]
    def contact_candidates(self, **signals):
        self.calls.append(("contact", signals)); return [{"contact_id": "CNT_1", "contact_name": "Sales Person", "match_evidence": [{"signal": "email"}]}]


class EngineeringExtractionTests(unittest.TestCase):
    source = TrainedKmInput("KM_20260817_120000", "quotation.pdf", "a" * 64, "# Detail\n## Slide 1", "# Summary")

    def test_quotation_preserves_supplier_customer_tax_contact_lines_and_ambiguity(self):
        opc = FakeOpcClient(); draft = EngineeringExtractionService(FakeProvider(quotation_payload()), opc).extract(self.source)
        self.assertEqual(draft.classification.document_type, EngineeringDocumentType.QUOTATION)
        self.assertEqual(draft.quotation.fields["quotation_number"].value, "QT-001")
        self.assertEqual(draft.quotation.issuer_supplier.fields["tax_id"].value, "001-02-003")
        self.assertEqual(draft.quotation.customer_buyer["company_name"].value, "CUSTOMER FACTORY")
        self.assertEqual(draft.quotation.supplier_contacts[0].fields["email"].value, "sales@keyence.example")
        self.assertEqual(len(draft.quotation.issuer_supplier.candidates), 2); self.assertIsNone(draft.quotation.issuer_supplier.provisional_candidate_id)
        self.assertEqual(draft.quotation.lines[1].line_type, CommercialLineType.FREIGHT); self.assertIsNone(draft.quotation.lines[1].equipment_part)
        self.assertEqual([call[0] for call in opc.calls], ["supplier", "ept"]); self.assertTrue(draft.quotation.fields["quotation_date"].evidence)

    def test_manual_prepares_ept_candidates_with_evidence(self):
        opc = FakeOpcClient(); draft = EngineeringExtractionService(FakeProvider(manual_payload()), opc).extract(self.source)
        self.assertEqual(draft.classification.document_type, EngineeringDocumentType.MANUAL)
        self.assertEqual(draft.manual.fields["manufacturer"].value, "ABB"); self.assertEqual(draft.manual.equipment_part.candidates[0].canonical_id, "EPT_1")
        self.assertEqual(opc.calls[0][1]["part_no"], "ACS550-01")

    def test_unknown_ambiguous_and_no_canonical_selection(self):
        payload = {"classification": classification("unknown", 0.45), "quotation": None, "manual": None}
        draft = EngineeringExtractionService(FakeProvider(payload), FakeOpcClient()).extract(self.source)
        self.assertEqual(draft.classification.document_type, EngineeringDocumentType.UNKNOWN); self.assertEqual(draft.state, "extracted"); self.assertIsNone(draft.quotation)

    def test_contact_lookup_uses_provisional_supplier_and_remains_read_only(self):
        opc = FakeOpcClient(); service = EngineeringExtractionService(FakeProvider({}), opc)
        candidates = service.contact_candidates("SUP_1", {"name": ev("Sales Person"), "email": ev("sales@keyence.example")})
        self.assertEqual(candidates[0]["contact_id"], "CNT_1"); self.assertEqual(opc.calls[0][1]["supplier_resource_id"], "SUP_1")

    def test_malformed_ai_output_fails_safely(self):
        with self.assertRaises(EngineeringExtractionError): EngineeringExtractionService(FakeProvider({"classification": {"document_type": "quotation", "confidence": 2}}), FakeOpcClient()).extract(self.source)

    def test_source_identity_is_path_independent_and_rerun_keyed(self):
        draft = EngineeringExtractionService(FakeProvider(manual_payload()), FakeOpcClient()).extract(self.source); serialized = json.dumps(draft.to_dict())
        self.assertNotIn("D:\\", serialized); self.assertEqual(draft.source_content_sha256, "a" * 64); self.assertTrue(draft.extractor_version); self.assertTrue(draft.schema_version)


if __name__ == "__main__": unittest.main()
