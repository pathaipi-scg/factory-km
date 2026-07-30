"""API router registration."""

from fastapi import APIRouter

from . import admin, chat, pageindex, upload, wiki


api_router = APIRouter(prefix="/api")
api_router.include_router(chat.router)
api_router.include_router(upload.router)
api_router.include_router(admin.router)
api_router.include_router(wiki.router)
api_router.include_router(pageindex.router)
