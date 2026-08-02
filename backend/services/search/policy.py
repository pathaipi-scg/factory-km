"""Search strategy selection policy."""

from collections.abc import Mapping

from backend.models.search import SearchRequest
from backend.models.search import SearchResult, SearchWarning
from backend.services.pageindex.adapter import (
    NotConfiguredPageIndexAdapter,
    PageIndexAdapter,
)
from backend.services.repositories.km_vault_repository import KmVaultRepository
from backend.services.search.folder_strategy import FolderSearchStrategy
from backend.services.search.pageindex_strategy import PageIndexSearchStrategy
from backend.services.search.strategy import SearchStrategy


class SearchPolicy:
    """Select a configured search strategy for a normalized request."""

    def __init__(self, strategies: Mapping[str, SearchStrategy]) -> None:
        self._strategies = dict(strategies)

    def select(self, request: SearchRequest) -> SearchStrategy:
        """Return the strategy configured for the requested search mode."""
        try:
            return self._strategies[request.mode]
        except KeyError as error:
            raise NotImplementedError(
                f"Search mode is not implemented: {request.mode}"
            ) from error


class FallbackSearchStrategy:
    """Use a fallback strategy when the primary cannot return usable hits."""

    def __init__(
        self, primary: SearchStrategy, fallback: SearchStrategy, *, primary_name: str
    ) -> None:
        self._primary = primary
        self._fallback = fallback
        self._primary_name = primary_name

    def search(self, request: SearchRequest) -> SearchResult:
        """Return primary hits, or safely retry through the fallback strategy."""
        try:
            primary_result = self._primary.search(request)
        except Exception as error:
            return self._fallback_result(request, str(error))

        if primary_result.hits:
            return primary_result

        reason = (
            primary_result.warnings[0].message
            if primary_result.warnings
            else f"{self._primary_name} returned no results."
        )
        return self._fallback_result(request, reason)

    def _fallback_result(self, request: SearchRequest, reason: str) -> SearchResult:
        fallback_request = SearchRequest(
            query=request.query,
            mode="folder",
            folder=request.folder,
            filters=request.filters,
            request_context=request.request_context,
        )
        result = self._fallback.search(fallback_request)
        warning = SearchWarning(
            code="search_fallback",
            message=f"{self._primary_name} fallback: {reason}",
            source=self._primary_name,
            strategy=result.strategy,
        )
        return SearchResult(
            hits=result.hits,
            warnings=(warning, *result.warnings),
            strategy=result.strategy,
            total_hits=result.total_hits,
            metadata={
                **result.metadata,
                "requested_mode": request.mode,
                "fallback_from": self._primary_name,
            },
        )


def create_folder_search_policy(km_root: str | None = None) -> SearchPolicy:
    """Compose the current Folder Search strategy for compatibility callers."""
    repository = KmVaultRepository(km_root)
    return SearchPolicy({"folder": FolderSearchStrategy(repository)})


def create_search_policy(
    km_root: str | None = None,
    pageindex_adapter: PageIndexAdapter | None = None,
) -> SearchPolicy:
    """Compose production search modes with Folder Search as the fallback."""
    repository = KmVaultRepository(km_root)
    folder_strategy = FolderSearchStrategy(repository)
    pageindex_strategy = PageIndexSearchStrategy(
        pageindex_adapter or NotConfiguredPageIndexAdapter()
    )
    return SearchPolicy(
        {
            "folder": folder_strategy,
            "pageindex": FallbackSearchStrategy(
                pageindex_strategy,
                folder_strategy,
                primary_name="pageindex",
            ),
        }
    )
