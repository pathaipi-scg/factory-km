"""Framework-neutral contract for future PageIndex retrieval."""

from typing import Protocol, runtime_checkable

from backend.models.search import SearchRequest, SearchResult, SearchWarning


@runtime_checkable
class PageIndexAdapter(Protocol):
    """Retrieve normalized search results from a PageIndex integration."""

    def retrieve(self, request: SearchRequest) -> SearchResult:
        """Return PageIndex retrieval results for a search request."""
        ...


class NotConfiguredPageIndexAdapter:
    """Safe placeholder used until a PageIndex integration is configured."""

    def retrieve(self, request: SearchRequest) -> SearchResult:
        """Return an explicit warning without performing any I/O."""
        return SearchResult(
            warnings=(
                SearchWarning(
                    code="pageindex_not_configured",
                    message="PageIndex is not configured.",
                    source="pageindex",
                    strategy="pageindex",
                ),
            ),
            strategy="pageindex",
            total_hits=0,
            metadata={"mode": request.mode},
        )
