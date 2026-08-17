import hashlib
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from backend.config.engineering_execution import EngineeringExecutionSettings
from backend.domain.engineering_review import CommandStatus
from backend.repositories.engineering_review_memory import InMemoryEngineeringReviewRepository
from backend.services.engineering_execution_service import EngineeringExecutionDisabledError, EngineeringExecutionService
from backend.services.engineering_review_service import EngineeringReviewService
from backend.services.opc_tag_manager_client import OpcTagManagerClientError
from backend.services.source_document_provider import InMemorySourceDocumentProvider


class FakeOpc:
    def __init__(self):
        self.states={};self.tags=[];self.mutations=[];self.create_result=None;self.fail_link=None
    def get_canonical_state(self,value):return self.states.get(value,{"exists":False,"canonical_id":value})
    def search_opc_tags(self,*_):return self.tags
    def create_canonical_resource(self,**values):
        self.mutations.append(("create",values));return self.create_result or {"status":"created","resource_id":"QUO_NEW","canonical_revision":"v1:abc","active_version":1}
    def link_resource_relationship(self,source,target):
        self.mutations.append(("relationship",source,target))
        if self.fail_link:raise self.fail_link
        return {"status":"already_linked","source_resource_id":source,"target_resource_id":target}
    def link_tag_resource(self,path,resource):self.mutations.append(("tag",path,resource));return {"status":"already_linked"}


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.repo=InMemoryEngineeringReviewRepository();self.review_service=EngineeringReviewService(self.repo);self.opc=FakeOpc();self.content=b"reviewed-document"
        self.provider=InMemorySourceDocumentProvider({"KM_1":("quote.pdf",self.content)})
    def confirmed(self,document_type="quotation",decisions=(),paths=(),resource=None):
        snapshot={"classification":{"document_type":document_type}}
        run=self.review_service.persist_extraction(snapshot,source_document_id="KM_1",source_sha256=hashlib.sha256(self.content).hexdigest(),extractor_version="v1",schema_version="s1",source_resource_id=resource)
        review=self.review_service.create_review(run.extraction_run_id)
        if decisions or paths:review=self.review_service.update(review.review_id,list(decisions),list(paths),review.concurrency_token)
        return self.review_service.confirm(review.review_id,review.concurrency_token)[0]
    def executor(self,enabled=False):return EngineeringExecutionService(self.repo,self.opc,self.provider,EngineeringExecutionSettings(enabled,60))

    def test_gate_blocks_execute_but_dry_run_is_available_and_mutation_free(self):
        review=self.confirmed();dry=self.executor().dry_run(review.review_id)
        self.assertTrue(dry["clean"]);self.assertFalse(dry["write_enabled"]);self.assertEqual(self.opc.mutations,[])
        with self.assertRaises(EngineeringExecutionDisabledError):self.executor().execute(review.review_id)

    def test_document_canonicalization_all_types_sha_and_similarity(self):
        for kind,prefix in (("quotation","QUO_"),("manual","MAN_"),("drawing","DWG_"),("general_document","DOC_")):
            with self.subTest(kind=kind):
                self.setUp();review=self.confirmed(kind);self.opc.create_result={"status":"created","resource_id":prefix+"NEW","canonical_revision":"v1:abc","active_version":1}
                result=self.executor(True).execute(review.review_id);self.assertEqual(result["commands"][0]["status"],"succeeded");self.assertEqual(self.opc.mutations[0][1]["content"],self.content)
        self.setUp();review=self.confirmed();self.opc.create_result={"status":"similar_resource_found","candidates":[{"resource_id":"QUO_OLD"}]}
        result=self.executor(True).execute(review.review_id);self.assertEqual(result["commands"][0]["failure_code"],"resource_similarity_decision_required")
        self.setUp();review=self.confirmed();self.provider=InMemorySourceDocumentProvider({"KM_1":("quote.pdf",b"changed")})
        self.assertEqual(self.executor().dry_run(review.review_id)["results"][0]["code"],"source_sha_mismatch")

    def test_revision_contact_and_tag_preflight(self):
        decisions=[{"target_ref":"supplier","kind":"supplier","action":"use_existing","canonical_id":"SUP_1","expected_canonical_version":"v2:ok"}]
        review=self.confirmed(decisions=decisions,resource="QUO_1");self.opc.states={"SUP_1":{"exists":True,"canonical_revision":"v3:stale"},"QUO_1":{"exists":True,"canonical_revision":"v1:q"}}
        result=self.executor().dry_run(review.review_id);self.assertTrue(any(x["code"]=="canonical_revision_mismatch" for x in result["results"]))
        self.setUp();decisions=[{"target_ref":"contact","kind":"contact","action":"use_existing","canonical_id":"CNT_1","expected_canonical_version":"v1:supplier"}]
        review=self.confirmed(decisions=decisions,resource="QUO_1");self.opc.states={"CNT_1":{"exists":True,"supplier_canonical_revision":"v2:supplier"}}
        self.assertEqual(self.executor().dry_run(review.review_id)["results"][0]["outcome"],"CONFLICT")
        self.setUp();decisions=[{"target_ref":"ept","kind":"equipment_part","action":"use_existing","canonical_id":"EPT_1","expected_canonical_version":"v1:e"}]
        review=self.confirmed(decisions=decisions,paths=("LP2/MIX/Tag",),resource="MAN_1");self.opc.states={"EPT_1":{"exists":True,"canonical_revision":"v1:e"},"MAN_1":{"exists":True,"canonical_revision":"v1:m"}}
        self.opc.tags=[{"kepware_path":"LP2/MIX/Tag","is_active":False}]
        self.assertTrue(any(x["code"]=="kepware_path_missing_or_inactive" for x in self.executor().dry_run(review.review_id)["results"]))
        self.opc.tags[0]["is_active"]=True;self.assertFalse(any(x["outcome"]!="PASS" for x in self.executor().dry_run(review.review_id)["results"]))

    def test_relationships_idempotency_blocked_commands_and_partial_retry(self):
        decisions=[{"target_ref":"supplier","kind":"supplier","action":"use_existing","canonical_id":"SUP_1","expected_canonical_version":"v1:s"}]
        review=self.confirmed(decisions=decisions,resource="QUO_1");self.opc.states={"SUP_1":{"exists":True,"canonical_revision":"v1:s"},"QUO_1":{"exists":True,"canonical_revision":"v1:q"}}
        result=self.executor(True).execute(review.review_id);self.assertTrue(all(x["status"]=="succeeded" for x in result["commands"]));self.assertIn(("relationship","SUP_1","QUO_1"),self.opc.mutations)
        self.setUp();review=self.confirmed(decisions=[{"target_ref":"supplier","kind":"supplier","action":"propose_new"}]);dry=self.executor().dry_run(review.review_id);self.assertEqual(dry["results"][-1]["outcome"],"BLOCKED");executed=self.executor(True).execute(review.review_id);self.assertEqual(executed["commands"][-1]["status"],"blocked");self.assertEqual(self.opc.mutations,[])
        self.setUp();review=self.confirmed(decisions=decisions,resource="QUO_1");self.opc.states={"SUP_1":{"exists":True,"canonical_revision":"v1:s"},"QUO_1":{"exists":True,"canonical_revision":"v1:q"}};self.opc.fail_link=OpcTagManagerClientError("timeout",retriable=True)
        first=self.executor(True).execute(review.review_id);self.assertEqual([x["status"] for x in first["commands"]],["succeeded","failed"]);self.opc.fail_link=None
        second=self.executor(True).execute(review.review_id);self.assertEqual([x["status"] for x in second["commands"]],["succeeded","succeeded"]);self.assertEqual(second["commands"][0]["attempts"],1)

    def test_claim_is_atomic_lease_recoverable_and_attempts_increment(self):
        review=self.confirmed();command=self.repo.list_commands(review.review_id)[0];now=datetime.now(timezone.utc)
        first=self.repo.claim_command(command.command_id,"lease-1",now+timedelta(minutes=1),now);self.assertEqual(first.attempts,1)
        self.assertIsNone(self.repo.claim_command(command.command_id,"lease-2",now+timedelta(minutes=1),now))
        recovered=self.repo.claim_command(command.command_id,"lease-3",now+timedelta(minutes=2),now+timedelta(minutes=1,seconds=1));self.assertEqual(recovered.attempts,2)

if __name__=="__main__":unittest.main()
