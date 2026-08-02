"""Runtime composition for the configured Ask-KM search service."""

from backend.config.search import SearchSettings
from backend.services.pageindex.filesystem_client import (
    FilesystemLocalPageIndexClient,
)
from backend.services.pageindex.local_adapter import LocalPageIndexAdapter
from backend.services.pageindex.local_reasoner import (
    DeterministicLocalPageIndexReasoner,
    OpenAICompatibleLocalReasoner,
)
from backend.services.search_service import SearchService


def create_search_service(
    settings: SearchSettings | None = None,
    *,
    km_root: str | None = None,
) -> SearchService:
    """Compose Folder Search and the optional local PageIndex runtime."""
    resolved_settings = settings or SearchSettings.from_environment()
    if resolved_settings.mode != "pageindex":
        return SearchService(km_root, settings=resolved_settings)

    workspace_path = resolved_settings.pageindex_workspace_path
    document_id = resolved_settings.pageindex_document_id
    if not workspace_path or not document_id:
        return SearchService(km_root, settings=resolved_settings)

    if resolved_settings.pageindex_reasoner_endpoint:
        reasoner = OpenAICompatibleLocalReasoner(
            endpoint=resolved_settings.pageindex_reasoner_endpoint,
            model=resolved_settings.pageindex_reasoner_model,
            timeout=resolved_settings.pageindex_reasoner_timeout_seconds,
            maximum_results=3,
            approved_hosts=resolved_settings.pageindex_reasoner_allowed_hosts,
        )
    else:
        reasoner = DeterministicLocalPageIndexReasoner()

    adapter = LocalPageIndexAdapter(
        FilesystemLocalPageIndexClient(workspace_path),
        reasoner,
        pageindex_document_id=document_id,
        stable_document_id=(
            resolved_settings.pageindex_stable_document_id or document_id
        ),
    )
    return SearchService(
        km_root,
        settings=resolved_settings,
        pageindex_adapter=adapter,
    )
