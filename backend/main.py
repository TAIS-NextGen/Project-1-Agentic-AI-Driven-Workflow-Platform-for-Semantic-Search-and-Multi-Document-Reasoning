from __future__ import annotations

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api import nodes, workflows, documents
from backend.settings import settings

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(nodes.router)
app.include_router(workflows.router)
app.include_router(documents.router)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
    }


if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
    )
