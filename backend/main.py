"""FastAPI application entry point for the Factory KM backend."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.routers.admin import router as admin_router
from backend.routers.auth import register_auth_router
from backend.routers.chat import router as chat_router
from backend.routers.pageindex import router as pageindex_router
from backend.routers.upload import router as upload_router
from backend.routers.wiki import router as wiki_router


app = FastAPI(title="factory-km")
register_auth_router(app)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIRECTORY = PROJECT_ROOT / "assets"

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


@app.get("/health")
def health() -> dict[str, str]:
    """Return the health status."""
    return {"health": "ok"}
