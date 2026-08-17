import json
import unittest

from backend.domain.engineering_review import (
    DecisionAction, DecisionKind, EngineeringReviewConcurrencyError,
    EngineeringReviewError, ReviewStatus,
)
from backend.repositories.engineering_review_memory import InMemoryEngineeringReviewRepository
from backend.services.engineering_review_service import EngineeringReviewService
from tests.test_engineering_extraction import quotation_payload, manual_payload


class EngineeringReviewTests(unittest.TestCase):
    def setUp(self): self.repo=InMemoryEngineeringReviewRepository(); self.service=EngineeringReviewService(self.repo)
    def create_run(self,sha="a"*64,extractor="v1",schema="s1",snapshot=None,resource="QUO_ABC"):
        return self.service.persist_extraction(snapshot or quotation_payload(),source_document_id="KM_1",source_sha256=sha,extractor_version=extractor,schema_version=schema,source_resource_id=resource,source_resource_version=2)

    def test_extraction_identity_idempotency_and_revisions(self):
        first=self.create_run(); same=self.create_run(); changed_sha=self.create_run("b"*64); changed_extractor=self.create_run(extractor="v2"); changed_schema=self.create_run(schema="s2")
        self.assertTrue(first.extraction_run_id.startswith("EXR_")); self.assertEqual(first.extraction_run_id,same.extraction_run_id)
        self.assertEqual(len({first.extraction_run_id,changed_sha.extraction_run_id,changed_extractor.extraction_run_id,changed_schema.extraction_run_id}),4)

    def test_snapshot_is_immutable_and_preserves_evidence_parties_candidates(self):
        snapshot=quotation_payload(); snapshot["quotation"]["issuer_supplier"]["candidates"]=[{"resource_id":"SUP_1","active_version":7}]
        run=self.create_run(snapshot=snapshot); snapshot["quotation"]["issuer_supplier"]["tax_id"]["value"]="changed"
        stored=run.snapshot
        self.assertEqual(stored["quotation"]["issuer_supplier"]["tax_id"]["value"],"001-02-003")
        self.assertEqual(stored["quotation"]["customer_buyer"]["company_name"]["value"],"CUSTOMER FACTORY")
        self.assertEqual(stored["quotation"]["issuer_supplier"]["candidates"][0]["active_version"],7)
        self.assertTrue(stored["classification"]["evidence"])

    def test_review_decisions_concurrency_cancel_and_finalization(self):
        review=self.service.create_review(self.create_run().extraction_run_id)
        decisions=[{"target_ref":"supplier","kind":"supplier","action":"use_existing","canonical_id":"SUP_1","expected_canonical_version":"7"},
                   {"target_ref":"contact-1","kind":"contact","action":"propose_new"},
                   {"target_ref":"line-2","kind":"equipment_part","action":"not_equipment_part"}]
        updated=self.service.update(review.review_id,decisions,[],review.concurrency_token)
        self.assertEqual(updated.status,ReviewStatus.IN_REVIEW)
        with self.assertRaises(EngineeringReviewConcurrencyError):self.service.update(review.review_id,decisions,[],review.concurrency_token)
        cancelled=self.service.cancel(updated.review_id,updated.concurrency_token); self.assertEqual(cancelled.status,ReviewStatus.CANCELLED)
        with self.assertRaises(EngineeringReviewError):self.service.update(cancelled.review_id,[],[],cancelled.concurrency_token)

    def test_confirm_generates_ready_idempotent_logical_commands_and_no_duplicates(self):
        review=self.service.create_review(self.create_run().extraction_run_id)
        decisions=[{"target_ref":"supplier","kind":"supplier","action":"use_existing","canonical_id":"SUP_1","expected_canonical_version":"7"},
                   {"target_ref":"contact-1","kind":"contact","action":"ignore"},
                   {"target_ref":"line-1-ept","kind":"equipment_part","action":"use_existing","canonical_id":"EPT_1"},
                   {"target_ref":"line-2","kind":"equipment_part","action":"not_equipment_part"}]
        updated=self.service.update(review.review_id,decisions,["LP2/MIX/Tag"],review.concurrency_token)
        confirmed,commands=self.service.confirm(updated.review_id,updated.concurrency_token)
        again,duplicates=self.service.confirm(updated.review_id,confirmed.concurrency_token)
        self.assertEqual(confirmed.status,ReviewStatus.CONFIRMED); self.assertEqual([x.command_id for x in commands],[x.command_id for x in duplicates])
        self.assertTrue(all(x.command_id.startswith("CMD_") and x.status.value=="ready" and x.attempts==0 for x in commands))
        types={x.command_type for x in commands}; self.assertIn("LinkResourceToSupplier",types); self.assertIn("LinkResourceToEquipmentPart",types); self.assertIn("LinkEquipmentPartToTag",types)
        self.assertFalse(any("line-2" in x.payload_json for x in commands)); self.assertNotIn("D:\\",json.dumps([x.payload for x in commands]))
        with self.assertRaises(EngineeringReviewError):self.service.update(confirmed.review_id,[],[],confirmed.concurrency_token)

    def test_supplier_contact_ept_decision_variants_and_manual_intent(self):
        run=self.create_run(snapshot=manual_payload(),resource="MAN_ABC"); review=self.service.create_review(run.extraction_run_id)
        decisions=[{"target_ref":"supplier","kind":"supplier","action":"propose_new"},{"target_ref":"contact","kind":"contact","action":"propose_new"},{"target_ref":"manual-ept","kind":"manual_equipment_part","action":"use_existing","canonical_id":"EPT_9"}]
        updated=self.service.update(review.review_id,decisions,[],review.concurrency_token); _,commands=self.service.confirm(updated.review_id,updated.concurrency_token)
        types={x.command_type for x in commands}; self.assertEqual({"ProposeCreateSupplier","ProposeCreateContact","UseExistingEquipmentPart","LinkResourceToEquipmentPart"},types)


if __name__=="__main__":unittest.main()
