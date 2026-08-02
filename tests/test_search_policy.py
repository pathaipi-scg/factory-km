"""Focused tests for production search strategy composition."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.config.search import SearchSettings
from backend.models.search import (
    SearchDocument,
    SearchHit,
    SearchRequest,
    SearchResult,
    SearchWarning,
)
from backend.services.search.policy import create_search_policy
from backend.services.search_service import SearchService


class StubPageIndexAdapter:
    def __init__(self, result: SearchResult) -> None:
        self.result = result
        self.requests: list[SearchRequest] = []

    def retrieve(self, request: SearchRequest) -> SearchResult:
        self.requests.append(request)
        return self.result


class RaisingPageIndexAdapter:
    def retrieve(self, request: SearchRequest) -> SearchResult:
        raise RuntimeError("PageIndex unavailable")


class SearchPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary_directory = tempfile.TemporaryDirectory()
        self.km_root = Path(self._temporary_directory.name)
        (self.km_root / "KM_20260802_120000.md").write_text(
            """# KM Information
KM_ID : KM_20260802_120000
Source_File : legacy.md
Category : Packing
Machine : Packer
Training_Status : Trained

# Slide Analysis

Legacy folder content.
""",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self._temporary_directory.cleanup()

    def test_folder_is_the_default_configuration(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(SearchSettings.from_environment().mode, "folder")

    def test_pageindex_mode_selects_pageindex_when_it_has_hits(self) -> None:
        pageindex_result = SearchResult(
            hits=(
                SearchHit(
                    document=SearchDocument(
                        id="pageindex-hit",
                        content="PageIndex content.",
                        source_type="pageindex_local",
                    ),
                    strategy="pageindex",
                ),
            ),
            strategy="pageindex",
            total_hits=1,
        )
        adapter = StubPageIndexAdapter(pageindex_result)
        policy = create_search_policy(str(self.km_root), adapter)
        request = SearchRequest(query="packer", mode="pageindex")

        result = policy.select(request).search(request)

        self.assertEqual(result.strategy, "pageindex")
        self.assertEqual(result.hits[0].document.id, "pageindex-hit")
        self.assertEqual(adapter.requests, [request])

    def test_pageindex_warning_falls_back_to_folder(self) -> None:
        adapter = StubPageIndexAdapter(
            SearchResult(
                warnings=(
                    SearchWarning(
                        code="pageindex_not_configured",
                        message="PageIndex is not configured.",
                        strategy="pageindex",
                    ),
                ),
                strategy="pageindex",
                total_hits=0,
            )
        )
        policy = create_search_policy(str(self.km_root), adapter)

        result = policy.select(
            SearchRequest(query="packer", mode="pageindex")
        ).search(SearchRequest(query="packer", mode="pageindex"))

        self.assertEqual(result.strategy, "folder")
        self.assertEqual(result.hits[0].document.id, "KM_20260802_120000")
        self.assertEqual(result.warnings[0].code, "search_fallback")
        self.assertEqual(result.metadata["fallback_from"], "pageindex")

    def test_pageindex_exception_falls_back_to_folder(self) -> None:
        policy = create_search_policy(str(self.km_root), RaisingPageIndexAdapter())
        request = SearchRequest(query="packer", mode="pageindex")

        result = policy.select(request).search(request)

        self.assertEqual(result.strategy, "folder")
        self.assertEqual(result.total_hits, 1)
        self.assertIn("PageIndex unavailable", result.warnings[0].message)

    def test_search_service_default_preserves_folder_context_format(self) -> None:
        service = SearchService(
            str(self.km_root), settings=SearchSettings(mode="folder")
        )

        context = service.build_context(folder="")

        self.assertIn("Source_File: legacy.md", context)
        self.assertIn("Legacy folder content.", context)

    def test_search_service_uses_configured_pageindex_mode(self) -> None:
        adapter = StubPageIndexAdapter(
            SearchResult(
                hits=(
                    SearchHit(
                        document=SearchDocument(
                            id="configured-hit",
                            content="Configured PageIndex content.",
                            source_type="pageindex_local",
                        ),
                        strategy="pageindex",
                    ),
                ),
                strategy="pageindex",
                total_hits=1,
            )
        )
        service = SearchService(
            str(self.km_root),
            settings=SearchSettings(mode="pageindex"),
            pageindex_adapter=adapter,
        )

        context = service.build_context(folder="Packing")

        self.assertIn("Configured PageIndex content.", context)
        self.assertEqual(adapter.requests[0].mode, "pageindex")
        self.assertEqual(adapter.requests[0].folder, "Packing")


if __name__ == "__main__":
    unittest.main()
