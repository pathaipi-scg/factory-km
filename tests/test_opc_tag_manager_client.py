import json
import unittest
from urllib.error import URLError

from backend.config.opc_tag_manager import OpcTagManagerSettings
from backend.services.opc_tag_manager_client import OpcTagManagerClient, OpcTagManagerClientError


class Response:
    def __init__(self, payload): self.payload = payload
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def read(self): return json.dumps(self.payload).encode()


class ClientTests(unittest.TestCase):
    def client(self, payloads):
        calls = []
        def open_request(request, timeout):
            calls.append((request.full_url, request.get_method(), timeout)); value = payloads.pop(0)
            if isinstance(value, Exception): raise value
            return Response(value)
        return OpcTagManagerClient(OpcTagManagerSettings("http://opc.example", 2), open_request), calls

    def test_all_contracts_are_get_only_and_never_write(self):
        client, calls = self.client([{"success": True, "candidates": [{"resource_id": "SUP_1"}]}, {"success": True, "candidates": [{"contact_id": "CNT_1"}]}, {"success": True, "candidates": [{"resource_id": "EPT_1"}]}, {"success": True, "equipment_parts": [{"resource_id": "EPT_1"}]}, {"success": True, "relationships": [{"target_resource_id": "QUO_1"}]}])
        client.supplier_candidates(tax_id="001-2"); client.contact_candidates(supplier_resource_id="SUP_1", email="a@example.com"); client.equipment_part_candidates(material_code="0001"); client.supplier_equipment_parts("SUP_1"); client.resource_relationships("EPT_1")
        self.assertTrue(all(method == "GET" for _, method, _ in calls)); self.assertFalse(any("/link" in url or "/unlink" in url for url, _, _ in calls))

    def test_ambiguity_is_preserved(self):
        client, _ = self.client([{"success": True, "candidates": [{"resource_id": "SUP_1"}, {"resource_id": "SUP_2"}]}])
        self.assertEqual([item["resource_id"] for item in client.supplier_candidates(name="ABC")], ["SUP_1", "SUP_2"])

    def test_timeout_malformed_and_physical_path_fail_safely(self):
        for payload in (URLError("timeout"), {"success": True, "wrong": []}, {"success": True, "candidates": [{"resource_id": "SUP_1", "filesystem_path": "D:\\KM\\Vault"}]}):
            with self.subTest(payload=payload):
                client, _ = self.client([payload])
                with self.assertRaises(OpcTagManagerClientError): client.supplier_candidates(name="ABC")

    def test_phase_410_read_and_allowlisted_write_contracts(self):
        client,calls=self.client([
            {"success":True,"state":{"exists":True,"canonical_id":"SUP_1","canonical_revision":"v1:abc"}},
            {"success":True,"tags":[{"kepware_path":"LP2/MIX/Tag","tag_name":"Tag","levels":["LP2","MIX"],"is_active":True}]},
            {"success":True,"status":"created","resource_id":"QUO_1","canonical_revision":"v1:def","active_version":1},
            {"success":True,"status":"already_linked","resource":{"active_file":"quote.pdf"}},
            {"success":True,"references":{"resource":{"active_file":"ept.md"}}},
        ])
        self.assertEqual(client.get_canonical_state("SUP_1")["canonical_revision"],"v1:abc")
        self.assertEqual(client.search_opc_tags("LP2/MIX/Tag")[0]["tag_name"],"Tag")
        created=client.create_canonical_resource(resource_type="Quotation",display_name="Quote",source_sha256="a"*64,source_document_id="KM_1",original_filename="quote.pdf",content=b"bytes")
        self.assertEqual(created["resource_id"],"QUO_1")
        self.assertNotIn("active_file",json.dumps(client.link_resource_relationship("SUP_1","QUO_1")))
        self.assertNotIn("active_file",json.dumps(client.link_tag_resource("LP2/MIX/Tag","EPT_1")))
        self.assertEqual([method for _,method,_ in calls],["GET","GET","POST","POST","POST"])
        self.assertTrue(all(url.startswith("http://opc.example/api/") for url,_,_ in calls))


if __name__ == "__main__": unittest.main()
