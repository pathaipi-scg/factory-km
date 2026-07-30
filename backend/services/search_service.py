"""Compatibility facade for Folder Search context building."""

from backend.models.search import SearchRequest, SearchResult
from backend.services.repositories.km_vault_repository import KmVaultRepository
from backend.services.search.folder_strategy import FolderSearchStrategy


class SearchService:
    """Build the existing Folder Search context through normalized results."""

    def __init__(self, km_root: str | None = None) -> None:
        self._repository = KmVaultRepository(km_root)
        self._folder_strategy = FolderSearchStrategy(self._repository)

    def build_context(self, mode: str = "folder", folder: str = "") -> str:
        """Return the legacy prompt context for the current Folder Search flow."""
        if mode != "folder":
            raise NotImplementedError(f"Search mode is not implemented: {mode}")

        result = self._folder_strategy.search(
            SearchRequest(query="", mode=mode, folder=folder)
        )
        return self._format_context(result)

    @staticmethod
    def _format_context(result: SearchResult) -> str:
        candidates = []
        for index, hit in enumerate(result.hits, start=1):
            metadata = hit.document.metadata
            kind = (
                "สรุป (summary)"
                if metadata.get("kind") == "summary"
                else "เอกสารเทรน (ฉบับเต็ม)"
            )
            header = (
                f"=== เอกสารที่ {index} ===\n"
                f"Source_File: {metadata.get('source_file') or '-'} | "
                f"ประเภท: {kind}\n"
                f"Category: {metadata.get('category') or '-'} | "
                f"Machine: {metadata.get('machine') or '-'} | "
                f"KM_ID: {metadata.get('km_id') or '-'}"
            )
            candidates.append(f"{header}\n\n{hit.document.content}")

        return "\n\n---\n\n".join(candidates)
