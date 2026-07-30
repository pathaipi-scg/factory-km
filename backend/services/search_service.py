"""Compatibility facade for Folder Search context building."""

from backend.models.search import SearchRequest
from backend.services.prompt_builder import PromptBuilder
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
        return PromptBuilder.build_context(result)
