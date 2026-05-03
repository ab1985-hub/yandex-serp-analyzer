from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.api.analyze import router as analyze_router
from app.utils.logger import setup_logging

setup_logging()

app = FastAPI(
    title="MVP анализа конкурентности ключевых слов",
    description="Сервис анализа Яндекс SERP по списку ключевых слов",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"статус": "ok"}


app.include_router(analyze_router)

# ── Serve built React frontend (production) ───────────────────────────────────
_STATIC_DIR = Path(__file__).parent.parent / "client" / "dist"

if _STATIC_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=str(_STATIC_DIR / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str) -> FileResponse:
        """Serve index.html for all non-API routes (SPA client-side routing)."""
        index = _STATIC_DIR / "index.html"
        return FileResponse(str(index))
