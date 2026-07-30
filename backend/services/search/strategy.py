"""Framework-neutral search strategy contract."""

from typing import Protocol, runtime_checkable

from backend.models.search import SearchRequest, SearchResult


@runtime_checkable
class SearchStrategy(Protocol):
    """Contract implemented by synchronous search strategies."""

    def search(self, request: SearchRequest) -> SearchResult:
        """Return normalized search results for a request."""
        ...
