"""Unregistered FastAPI Vault Management router skeleton."""

from fastapi import APIRouter, HTTPException, status


router = APIRouter(prefix="/vault")


def _not_implemented() -> None:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Vault Management is not implemented.",
    )


@router.get("/entries")
def list_entries() -> None:
    _not_implemented()


@router.post("/folders")
def create_folder() -> None:
    _not_implemented()


@router.post("/files")
def upload() -> None:
    _not_implemented()


@router.post("/rename")
def rename() -> None:
    _not_implemented()


@router.post("/move")
def move() -> None:
    _not_implemented()


@router.put("/files")
def edit() -> None:
    _not_implemented()


@router.post("/soft-delete")
def soft_delete() -> None:
    _not_implemented()


@router.post("/restore")
def restore() -> None:
    _not_implemented()
