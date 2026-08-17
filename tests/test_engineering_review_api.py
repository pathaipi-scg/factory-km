import asyncio
import json
import unittest
from types import SimpleNamespace

from backend.main import app
from backend.repositories.engineering_review_memory import InMemoryEngineeringReviewRepository
from backend.routers.engineering import create_review, update_review, confirm_review, cancel_review, get_commands, dry_run_execution, execute_review, get_execution
from backend.config.engineering_execution import EngineeringExecutionSettings
from backend.services.engineering_execution_service import EngineeringExecutionService
from backend.services.source_document_provider import InMemorySourceDocumentProvider
from tests.test_engineering_execution import FakeOpc
from backend.services.engineering_review_service import EngineeringReviewService
from tests.test_engineering_extraction import quotation_payload


class Request:
    def __init__(self,service,payload=None,execution=None):
        self.app=SimpleNamespace(state=SimpleNamespace(engineering_review_service=service,engineering_execution_service=execution));self._payload=payload
    async def json(self):return self._payload


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.service=EngineeringReviewService(InMemoryEngineeringReviewRepository());self.run=self.service.persist_extraction(quotation_payload(),source_document_id="KM_1",source_sha256="a"*64,extractor_version="v1",schema_version="s1",source_resource_id="QUO_1")

    def body(self,response):return json.loads(response.body) if hasattr(response,"body") else response

    def test_save_concurrency_confirm_command_display_and_no_execute_api(self):
        created=self.body(asyncio.run(create_review(self.run.extraction_run_id,Request(self.service,{}),"factory")));review=created["review"]
        payload={"concurrency_token":review["concurrency_token"],"decisions":[{"target_ref":"supplier","kind":"supplier","action":"use_existing","canonical_id":"SUP_1"}],"intended_kepware_paths":[]}
        saved=self.body(asyncio.run(update_review(review["review_id"],Request(self.service,payload),"factory")))["review"]
        conflict=asyncio.run(update_review(review["review_id"],Request(self.service,payload),"factory"));self.assertEqual(conflict.status_code,409)
        confirmed=self.body(asyncio.run(confirm_review(review["review_id"],Request(self.service,{"concurrency_token":saved["concurrency_token"]}),"factory")))
        self.assertEqual(confirmed["review"]["status"],"confirmed");self.assertTrue(confirmed["review"]["commands"]);self.assertIn("not executed",confirmed["notice"].lower())
        commands=self.body(get_commands(review["review_id"],Request(self.service)));
        self.assertFalse(commands["execution_available"]);self.assertTrue(all(item["status"]=="ready" for item in commands["commands"]))
        paths={getattr(route,"path","") for route in app.routes};self.assertFalse(any("execute" in path for path in paths))

    def test_cancel_api(self):
        review=self.body(asyncio.run(create_review(self.run.extraction_run_id,Request(self.service,{}),"factory")))["review"]
        cancelled=self.body(asyncio.run(cancel_review(review["review_id"],Request(self.service,{"concurrency_token":review["concurrency_token"]}),"factory")))
        self.assertEqual(cancelled["review"]["status"],"cancelled")

    def test_execution_api_requires_confirmed_review_and_gate(self):
        review=self.body(asyncio.run(create_review(self.run.extraction_run_id,Request(self.service,{}),"factory")))["review"]
        saved=self.body(asyncio.run(update_review(review["review_id"],Request(self.service,{"concurrency_token":review["concurrency_token"],"decisions":[],"intended_kepware_paths":[]}),"factory")))["review"]
        confirmed=self.body(asyncio.run(confirm_review(review["review_id"],Request(self.service,{"concurrency_token":saved["concurrency_token"]}),"factory")))["review"]
        execution=EngineeringExecutionService(self.service.repository,FakeOpc(),InMemorySourceDocumentProvider({}),EngineeringExecutionSettings(False,60))
        request=Request(self.service,execution=execution)
        self.assertTrue(self.body(dry_run_execution(confirmed["review_id"],request,"factory"))["success"])
        denied=execute_review(confirmed["review_id"],request,"factory");self.assertEqual(denied.status_code,403)
        self.assertTrue(self.body(get_execution(confirmed["review_id"],request))["success"])


if __name__=="__main__":unittest.main()
