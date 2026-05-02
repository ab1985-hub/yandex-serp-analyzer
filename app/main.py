from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
