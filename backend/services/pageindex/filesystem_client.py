"""Read-only filesystem client for a pre-generated local PageIndex workspace."""

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any


class FilesystemLocalPageIndexClient:
    """Load one or more pre-generated document directories without mutation."""

    def __init__(self, workspace_path: str | Path) -> None:
        self._workspace_path = Path(workspace_path)

    def get_document(self, doc_id: str) -> str:
        """Return validated document metadata as JSON text."""
        document = self._load_json(doc_id, "document.json")
        if not isinstance(document, Mapping):
            raise ValueError("PageIndex document metadata must be an object.")
        if document.get("doc_id") != doc_id:
            raise ValueError("PageIndex document metadata has an invalid doc_id.")
        return json.dumps(document, ensure_ascii=False)

    def get_document_structure(self, doc_id: str) -> str:
        """Return the document tree as JSON text."""
        structure = self._load_json(doc_id, "structure.json")
        if not isinstance(structure, list):
            raise ValueError("PageIndex document structure must be an array.")
        return json.dumps(structure, ensure_ascii=False)

    def get_page_content(self, doc_id: str, pages: str) -> str:
        """Return the inclusive page range from pre-generated content."""
        match = re.fullmatch(r"([1-9]\d*)-([1-9]\d*)", pages)
        if not match:
            raise ValueError("PageIndex page range is invalid.")
        start_index, end_index = (int(value) for value in match.groups())
        if start_index > end_index:
            raise ValueError("PageIndex page range is invalid.")

        content = self._load_json(doc_id, "pages.json")
        if not isinstance(content, list):
            raise ValueError("PageIndex page content must be an array.")

        selected: list[Mapping[str, Any]] = []
        for item in content:
            if not isinstance(item, Mapping):
                raise ValueError("PageIndex page content item must be an object.")
            page = item.get("page")
            text = item.get("content")
            if isinstance(page, bool) or not isinstance(page, int):
                raise ValueError("PageIndex page number must be an integer.")
            if not isinstance(text, str):
                raise ValueError("PageIndex page content must be a string.")
            if start_index <= page <= end_index:
                selected.append(item)
        return json.dumps(selected, ensure_ascii=False)

    def _load_json(self, doc_id: str, filename: str) -> Any:
        document_directory = self._document_directory(doc_id)
        with (document_directory / filename).open(encoding="utf-8") as file:
            return json.load(file)

    def _document_directory(self, doc_id: str) -> Path:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", doc_id):
            raise ValueError("PageIndex document ID is invalid.")
        return self._workspace_path / "documents" / doc_id
