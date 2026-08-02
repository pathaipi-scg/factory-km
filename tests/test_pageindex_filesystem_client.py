"""Tests for the read-only filesystem PageIndex runtime."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.config.search import SearchSettings
from backend.dependencies.search import create_search_service
from backend.services.pageindex.filesystem_client import (
    FilesystemLocalPageIndexClient,
)


class FilesystemPageIndexTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self._temporary_directory.name)
        self.workspace = self.root / "workspace"
        self.document_directory = self.workspace / "documents" / "factory-manual"
        self.document_directory.mkdir(parents=True)
        self.km_root = self.root / "vault"
        self.km_root.mkdir()
        (self.km_root / "KM_20260802_120000.md").write_text(
            """# KM Information
KM_ID : KM_20260802_120000
Source_File : fallback.md
Category : Packing
Machine : Packer
Training_Status : Trained

# Slide Analysis

Folder fallback content.
""",
            encoding="utf-8",
        )
        self._write_valid_workspace()

    def tearDown(self) -> None:
        self._temporary_directory.cleanup()

    def _write_valid_workspace(self) -> None:
        (self.document_directory / "document.json").write_text(
            json.dumps(
                {
                    "doc_id": "factory-manual",
                    "doc_name": "factory-manual.md",
                    "type": "md",
                    "status": "completed",
                }
            ),
            encoding="utf-8",
        )
        (self.document_directory / "structure.json").write_text(
            json.dumps(
                [
                    {
                        "node_id": "calibration",
                        "title": "Temperature calibration",
                        "summary": "Calibration procedure.",
                        "start_index": 2,
                        "end_index": 3,
                    }
                ]
            ),
            encoding="utf-8",
        )
        (self.document_directory / "pages.json").write_text(
            json.dumps(
                [
                    {"page": 1, "content": "Factory manual"},
                    {"page": 2, "content": "Temperature calibration"},
                    {"page": 3, "content": "Set the reference probe to 50 C."},
                ]
            ),
            encoding="utf-8",
        )

    def _settings(self, **overrides: object) -> SearchSettings:
        values = {
            "mode": "pageindex",
            "pageindex_workspace_path": str(self.workspace),
            "pageindex_document_id": "factory-manual",
            "pageindex_stable_document_id": "KM_FACTORY_MANUAL",
        }
        values.update(overrides)
        return SearchSettings(**values)

    def test_filesystem_client_loads_metadata_tree_and_page_range(self) -> None:
        client = FilesystemLocalPageIndexClient(self.workspace)

        document = json.loads(client.get_document("factory-manual"))
        structure = json.loads(client.get_document_structure("factory-manual"))
        pages = json.loads(client.get_page_content("factory-manual", "2-3"))

        self.assertEqual(document["doc_id"], "factory-manual")
        self.assertEqual(structure[0]["node_id"], "calibration")
        self.assertEqual([page["page"] for page in pages], [2, 3])

    def test_runtime_composition_uses_filesystem_pageindex(self) -> None:
        service = create_search_service(
            self._settings(), km_root=str(self.km_root)
        )

        context = service.build_context(query="temperature calibration")

        self.assertIn("Set the reference probe to 50 C.", context)
        self.assertNotIn("Folder fallback content.", context)

    def test_corrupt_workspace_falls_back_to_folder_search(self) -> None:
        (self.document_directory / "structure.json").write_text(
            "not-json", encoding="utf-8"
        )
        service = create_search_service(
            self._settings(), km_root=str(self.km_root)
        )

        context = service.build_context(query="temperature calibration")

        self.assertIn("Folder fallback content.", context)

    def test_missing_workspace_falls_back_to_folder_search(self) -> None:
        service = create_search_service(
            self._settings(
                pageindex_workspace_path=str(self.root / "missing-workspace")
            ),
            km_root=str(self.km_root),
        )

        context = service.build_context(query="temperature calibration")

        self.assertIn("Folder fallback content.", context)

    def test_environment_loads_pageindex_runtime_configuration(self) -> None:
        environment = {
            "KM_SEARCH_MODE": "pageindex",
            "PAGEINDEX_WORKSPACE_PATH": str(self.workspace),
            "PAGEINDEX_DOCUMENT_ID": "factory-manual",
            "PAGEINDEX_STABLE_DOCUMENT_ID": "stable-manual",
            "PAGEINDEX_REASONER_ENDPOINT": "http://127.0.0.1:1234/v1/chat/completions",
            "PAGEINDEX_REASONER_MODEL": "local-model",
            "PAGEINDEX_REASONER_TIMEOUT_SECONDS": "12.5",
            "PAGEINDEX_REASONER_ALLOWED_HOSTS": "192.168.1.20, reasoner.local",
        }
        with patch.dict(os.environ, environment, clear=True):
            settings = SearchSettings.from_environment()

        self.assertEqual(settings.mode, "pageindex")
        self.assertEqual(settings.pageindex_workspace_path, str(self.workspace))
        self.assertEqual(settings.pageindex_document_id, "factory-manual")
        self.assertEqual(settings.pageindex_stable_document_id, "stable-manual")
        self.assertEqual(settings.pageindex_reasoner_model, "local-model")
        self.assertEqual(settings.pageindex_reasoner_timeout_seconds, 12.5)
        self.assertEqual(
            settings.pageindex_reasoner_allowed_hosts,
            ("192.168.1.20", "reasoner.local"),
        )


if __name__ == "__main__":
    unittest.main()
