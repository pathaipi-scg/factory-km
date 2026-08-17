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


if __name__ == "__main__": unittest.main()
