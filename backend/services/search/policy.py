"""Search strategy selection policy."""

from collections.abc import Mapping

from backend.models.search import SearchRequest
from backend.services.repositories.km_vault_repository import KmVaultRepository
from backend.services.search.folder_strategy import FolderSearchStrategy
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


def create_folder_search_policy(km_root: str | None = None) -> SearchPolicy:
    """Compose the current Folder Search strategy for compatibility callers."""
    repository = KmVaultRepository(km_root)
    return SearchPolicy({"folder": FolderSearchStrategy(repository)})
