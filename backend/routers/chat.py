from fastapi import APIRouter
from fastapi import Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from backend.dependencies.search import create_search_service
from backend.services.chat_service import ChatService
from backend.services.llm_service import AzureOpenAIError, LLMService


router = APIRouter()


def get_chat_service() -> ChatService:
    """Create the Ask-KM service only when the endpoint is requested."""
    return ChatService(create_search_service(), LLMService())


@router.post("/ask_km")
async def ask_km(
    request: Request,
) -> JSONResponse:
    """Handle the existing Ask-KM frontend payload."""
    try:
        payload = await request.json()
    except Exception as error:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(error)},
        )

    question = payload.get("question") if isinstance(payload, dict) else None
    question = question.strip() if isinstance(question, str) else ""
    if not question:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "Missing question"},
        )

    folder = payload.get("folder") if isinstance(payload, dict) else ""
    history = payload.get("history") if isinstance(payload, dict) else None
    flow = payload.get("flow") if isinstance(payload, dict) else None

    try:
        chat_service = get_chat_service()
        response = await run_in_threadpool(
            chat_service.ask_km,
            question=question,
            folder=folder,
            history=history,
            flow=flow,
        )
    except (AzureOpenAIError, ValueError) as error:
        return JSONResponse(
            status_code=502,
            content={"success": False, "error": str(error)},
        )

    return JSONResponse(content=response)
