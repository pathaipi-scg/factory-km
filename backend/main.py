"""FastAPI application entry point for the Factory KM backend."""

from pathlib import Path
import logging

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.routers.admin import router as admin_router
from backend.routers.auth import register_auth_router
from backend.routers.chat import router as chat_router
from backend.routers.pageindex import router as pageindex_router
from backend.routers.upload import router as upload_router
from backend.routers.wiki import router as wiki_router
from backend.config.vault import VaultConfigurationError, get_vault_settings


app = FastAPI(title="factory-km")
register_auth_router(app)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIRECTORY = PROJECT_ROOT / "assets"
logger = logging.getLogger("factory-km")


@app.on_event("startup")
def validate_vault_configuration() -> None:
    """Refuse startup when the configured local/UNC Vault is unavailable."""
    settings = get_vault_settings()
    settings.require_readable()
    app.state.vault_settings = settings
    logger.info("KM Vault root: %s", settings.root)

app.mount("/assets", StaticFiles(directory=ASSETS_DIRECTORY), name="assets")
app.include_router(chat_router, prefix="/api")
app.include_router(upload_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(wiki_router, prefix="/api")
app.include_router(pageindex_router, prefix="/api")


@app.get("/", include_in_schema=False)
@app.get("/index.html", include_in_schema=False)
def index() -> FileResponse:
    """Serve the existing application shell without changing its contents."""
    return FileResponse(PROJECT_ROOT / "index.html")


@app.get("/login", include_in_schema=False)
@app.get("/login.html", include_in_schema=False)
def login() -> FileResponse:
    """Serve the existing login page without changing its contents."""
    return FileResponse(PROJECT_ROOT / "login.html")


@app.get("/api/status")
def status() -> dict[str, str]:
    """Return the service status."""
    return {"status": "ok", "service": "factory-km"}


@app.get("/health", response_model=None)
def health() -> dict[str, str] | JSONResponse:
    """Return the health status."""
    try:
        settings = getattr(app.state, "vault_settings", None) or get_vault_settings()
        settings.require_readable()
    except VaultConfigurationError as error:
        return JSONResponse(status_code=503, content={"health": "error", "error": str(error)})
    return {"health": "ok", "vaultRoot": str(settings.root)}
