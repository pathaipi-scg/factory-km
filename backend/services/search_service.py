"""Compatibility facade for Folder Search context building."""

from backend.models.search import SearchRequest
from backend.services.prompt_builder import PromptBuilder
from backend.services.search.policy import SearchPolicy, create_folder_search_policy


class SearchService:
    """Build the existing Folder Search context through normalized results."""

    def __init__(self, km_root: str | None = None) -> None:
        self._policy: SearchPolicy = create_folder_search_policy(km_root)

    def build_context(self, mode: str = "folder", folder: str = "") -> str:
        """Return the legacy prompt context for the current Folder Search flow."""
        request = SearchRequest(query="", mode=mode, folder=folder)
        result = self._policy.select(request).search(request)
        return PromptBuilder.build_context(result)
