"""Compatibility facade for Folder Search context building."""

from backend.config.search import SearchSettings
from backend.models.search import SearchRequest
from backend.services.pageindex.adapter import PageIndexAdapter
from backend.services.prompt_builder import PromptBuilder
from backend.services.search.policy import SearchPolicy, create_search_policy


class SearchService:
    """Build the existing Folder Search context through normalized results."""

    def __init__(
        self,
        km_root: str | None = None,
        *,
        settings: SearchSettings | None = None,
        pageindex_adapter: PageIndexAdapter | None = None,
    ) -> None:
        self._settings = settings or SearchSettings.from_environment()
        self._policy: SearchPolicy = create_search_policy(km_root, pageindex_adapter)

    def build_context(
        self, mode: str | None = None, folder: str = "", query: str = ""
    ) -> str:
        """Return the legacy prompt context for the current Folder Search flow."""
        request = SearchRequest(
            query=query, mode=mode or self._settings.mode, folder=folder
        )
        result = self._policy.select(request).search(request)
        return PromptBuilder.build_context(result)
