"""Local PageIndex search strategy."""

from backend.models.search import SearchRequest, SearchResult
from backend.services.pageindex.adapter import PageIndexAdapter


class PageIndexSearchStrategy:
    """Delegate normalized PageIndex retrieval to a local adapter."""

    def __init__(self, adapter: PageIndexAdapter) -> None:
        self._adapter = adapter

    def search(self, request: SearchRequest) -> SearchResult:
        """Return the adapter result without transformation."""
        return self._adapter.retrieve(request)
