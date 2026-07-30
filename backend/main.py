"""FastAPI application entry point for the Factory KM backend."""

from fastapi import FastAPI


app = FastAPI(title="factory-km")


@app.get("/")
def root() -> dict[str, str]:
    """Return the service status."""
    return {"status": "ok", "service": "factory-km"}


@app.get("/health")
def health() -> dict[str, str]:
    """Return the health status."""
    return {"health": "ok"}
