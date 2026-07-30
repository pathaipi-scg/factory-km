"""Chat use-case orchestration."""

from backend.services.llm_service import LLMService
from backend.services.search_service import SearchService


class ChatService:
    """Coordinate Folder Search context retrieval and LLM generation."""

    def __init__(self, search_service: SearchService, llm_service: LLMService) -> None:
        self._search_service = search_service
        self._llm_service = llm_service

    def ask_km(
        self,
        *,
        question: str,
        folder: str = "",
        history: str | None = None,
        flow: str | None = None,
    ) -> dict[str, str]:
        """Answer an existing Folder Search request using the current contract."""
        del history, flow
        context = self._search_service.build_context(mode="folder", folder=folder)
        text = self._llm_service.generate(context=context, question=question)
        return {"text": text}
