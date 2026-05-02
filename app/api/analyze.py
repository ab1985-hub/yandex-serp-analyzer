from __future__ import annotations

import io
import logging
import os
import re

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.models.schemas import AnalyzeRequest, AnalyzeResponse
from app.services.keyword_normalizer import (
    apply_minus_phrases,
    normalize_keywords,
    parse_keywords_from_text,
)
from app.services.region_adapter import populate_regions_cache, resolve_region_id
from app.services.reporter import build_keyword_report
from app.services.yandex_client import (
    PRESET_BULK_ANALYSIS,
    PRESET_MANUAL_CHECK,
    SerpResult,
    web_search_async_xml,
    web_search_sync_html,
    wordstat_get_regions_tree,
    wordstat_get_top,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["analyze"])

_regions_loaded = False


async def _ensure_regions() -> None:
    global _regions_loaded
    if _regions_loaded:
        return
    try:
        tree = await wordstat_get_regions_tree()
        populate_regions_cache(tree)
        _regions_loaded = True
    except Exception as exc:
        logger.warning("[regions] Не удалось загрузить дерево регионов: %s", exc)


# ---------------------------------------------------------------------------
# Status endpoint
# ---------------------------------------------------------------------------

@router.get("/status")
async def status() -> dict:
    api_key_ok = bool(os.getenv("YANDEX_API_KEY"))
    folder_id_ok = bool(os.getenv("YANDEX_FOLDER_ID"))
    ready = api_key_ok and folder_id_ok
    return {
        "mode": "api" if ready else "unconfigured",
        "source": "yandex_search_api",
        "api_configured": ready,
        "message": (
            "Yandex Search API · Wordstat API · готов"
            if ready
            else "⚠ Не заданы YANDEX_API_KEY / YANDEX_FOLDER_ID в Secrets"
        ),
    }


# ---------------------------------------------------------------------------
# Regions tree endpoint
# ---------------------------------------------------------------------------

_FALLBACK_REGIONS = [
    {"id": 225, "name": "Россия", "children": [
        {"id": 1, "name": "Москва и Московская область", "children": [
            {"id": 213, "name": "Москва", "children": []},
        ]},
        {"id": 2, "name": "Санкт-Петербург", "children": []},
        {"id": 65, "name": "Новосибирск", "children": []},
        {"id": 54, "name": "Екатеринбург", "children": []},
        {"id": 43, "name": "Казань", "children": []},
        {"id": 47, "name": "Нижний Новгород", "children": []},
        {"id": 56, "name": "Челябинск", "children": []},
        {"id": 51, "name": "Самара", "children": []},
        {"id": 172, "name": "Уфа", "children": []},
        {"id": 39, "name": "Ростов-на-Дону", "children": []},
        {"id": 62, "name": "Красноярск", "children": []},
        {"id": 50, "name": "Пермь", "children": []},
        {"id": 35, "name": "Краснодар", "children": []},
        {"id": 194, "name": "Саратов", "children": []},
        {"id": 55, "name": "Тюмень", "children": []},
        {"id": 66, "name": "Омск", "children": []},
        {"id": 75, "name": "Владивосток", "children": []},
        {"id": 76, "name": "Хабаровск", "children": []},
        {"id": 63, "name": "Иркутск", "children": []},
    ]},
]


@router.get("/regions")
async def get_regions() -> dict:
    """
    Возвращает дерево регионов. Пробует Wordstat API,
    при недоступности возвращает встроенный fallback-список.
    """
    try:
        tree = await wordstat_get_regions_tree()
        populate_regions_cache(tree)
        global _regions_loaded
        _regions_loaded = True
        return {"regions": tree, "source": "wordstat_api"}
    except Exception as exc:
        logger.warning("[regions] Wordstat недоступен, используем fallback: %s", exc)
        return {"regions": _FALLBACK_REGIONS, "source": "fallback"}


# ---------------------------------------------------------------------------
# Wordstat — GetTop
# ---------------------------------------------------------------------------

class WordstatRequest(BaseModel):
    seed_keyword: str = Field(..., description="Тема / стартовый ключ")
    region_id: int = Field(default=213, description="ID региона (lr-код)")
    limit: int = Field(default=100, ge=1, le=1000)
    minus_phrases: list[str] = Field(default_factory=list)
    min_frequency: int = Field(default=0, ge=0, description="Минимальная частотность (0 = не фильтровать)")


@router.post("/wordstat/top")
async def wordstat_top(request: WordstatRequest) -> dict:
    """
    Собирает ключевые слова через Wordstat GetTop.
    Pipeline: fetch → minus_phrases → min_frequency → limit.
    Фильтр по частотности применяется ДО обрезки лимитом.
    """
    try:
        # Когда задан порог частотности — запрашиваем больше у API,
        # чтобы после фильтрации осталось до limit строк.
        fetch_limit = min(request.limit * 5, 2000) if request.min_frequency > 0 else request.limit

        raw_results = await wordstat_get_top(
            keyword=request.seed_keyword,
            region_id=request.region_id,
            limit=fetch_limit,
        )

        # 1. Минус-фразы
        allowed_kws = set(apply_minus_phrases(
            [r["keyword"] for r in raw_results],
            request.minus_phrases,
        ))
        filtered = [r for r in raw_results if r["keyword"] in allowed_kws]

        # 2. Минимальная частотность — ДО лимита
        if request.min_frequency > 0:
            before = len(filtered)
            filtered = [r for r in filtered if r["frequency"] >= request.min_frequency]
            logger.info(
                "[wordstat] min_frequency=%d: %d → %d ключей",
                request.min_frequency, before, len(filtered),
            )

        # 3. Лимит — ПОСЛЕ всех фильтров
        filtered = filtered[:request.limit]

        result = [{"keyword": r["keyword"], "frequency": r["frequency"]} for r in filtered]
        return {"keywords": result, "total": len(result)}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Ошибка Wordstat API: {exc}") from exc


# ---------------------------------------------------------------------------
# File upload — extract keywords
# ---------------------------------------------------------------------------

@router.post("/keywords/upload")
async def upload_keywords(file: UploadFile = File(...)) -> dict:
    """
    Загружает файл (.txt, .csv, .xlsx) и возвращает нормализованный список ключей.
    """
    filename = (file.filename or "").lower()
    try:
        content_bytes = await file.read()

        if filename.endswith(".xlsx"):
            try:
                import openpyxl
                _XLSX_HEADERS = {"keyword", "key", "ключ", "слово", "phrase", "запрос"}
                wb = openpyxl.load_workbook(io.BytesIO(content_bytes))
                ws = wb.active
                raw_lines = []
                for row in ws.iter_rows():
                    if not row[0].value:
                        continue
                    cell = str(row[0].value).strip()
                    if cell.lower() in _XLSX_HEADERS:
                        continue
                    raw_lines.append(cell)
            except ImportError:
                raise HTTPException(
                    status_code=422,
                    detail="Для загрузки .xlsx установите openpyxl (pip install openpyxl)",
                )
        else:
            text = content_bytes.decode("utf-8", errors="replace")
            if filename.endswith(".csv"):
                import csv as csv_mod
                reader = csv_mod.reader(text.splitlines())
                raw_lines = []
                for row in reader:
                    if not row:
                        continue
                    cell = row[0].strip()
                    if cell.lower() in ("keyword", "key", "ключ", "слово", "phrase", "запрос"):
                        continue
                    raw_lines.append(cell)
            else:
                raw_lines = text.splitlines()

        keywords = normalize_keywords(raw_lines)
        return {"keywords": keywords, "total": len(keywords)}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Ошибка разбора файла: {exc}") from exc


# ---------------------------------------------------------------------------
# Main analyze endpoint (Search API)
# ---------------------------------------------------------------------------

class KeywordInput(BaseModel):
    """Ключ с необязательной частотностью (из Wordstat)."""
    keyword: str
    frequency: int | None = None


class SearchAnalyzeRequest(BaseModel):
    keywords: list[str | KeywordInput] = Field(..., description="Список ключей (строки или объекты с frequency)")
    region_id: int = Field(default=213, description="ID региона (lr-код)")
    region_name: str = Field(default="Москва", description="Название региона для отображения")
    country: str = Field(default="Россия")
    minus_phrases: list[str] = Field(default_factory=list)
    depth: int = Field(default=10, ge=1, le=20)
    preset: str = Field(default=PRESET_BULK_ANALYSIS,
                        description=f"'{PRESET_MANUAL_CHECK}' или '{PRESET_BULK_ANALYSIS}'")
    deep_analysis: bool = Field(
        default=True,
        description="Углублённый анализ: HTTP-загрузка top-10 страниц для анализа реального содержимого",
    )
    niche: str = Field(
        default="real_estate",
        description="Ниша анализа: 'real_estate' | 'universal'",
    )


def _parse_keyword_items(raw: list[str | KeywordInput]) -> list[tuple[str, int | None]]:
    """Нормализует входящие ключи в пары (text, frequency)."""
    pairs = []
    for item in raw:
        if isinstance(item, str):
            pairs.append((item, None))
        else:
            pairs.append((item.keyword, item.frequency))
    return pairs


@router.post("/analyze")
async def analyze(request: SearchAnalyzeRequest) -> dict:
    """
    Анализ конкурентности ключей через Yandex Search API.
    Preset bulk-analysis (async XML) — для списков.
    Preset manual-serp-check (sync HTML) — для одиночной проверки.
    """
    await _ensure_regions()

    try:
        # Нормализуем: поддерживаем и строки, и объекты {keyword, frequency}
        kw_pairs = _parse_keyword_items(request.keywords)
        kw_texts = normalize_keywords([kw for kw, _ in kw_pairs])

        # Строим карту frequency по нижнему регистру ключа (case-insensitive, первое вхождение)
        freq_map: dict[str, int | None] = {}
        for text, freq in kw_pairs:
            key = re.sub(r"\s+", " ", text).strip().lower()
            if key and key not in freq_map:
                freq_map[key] = freq

        kw_texts = apply_minus_phrases(kw_texts, request.minus_phrases)
        if not kw_texts:
            raise HTTPException(status_code=422, detail="Список ключей пуст после фильтрации")

        results = []
        for keyword in kw_texts:
            serp: SerpResult = await web_search_sync_html(
                keyword=keyword,
                region_id=request.region_id,
                depth=request.depth,
            )

            serp_data = serp.to_collector_dict()
            result_item = await build_keyword_report(
                keyword=keyword,
                serp_data=serp_data,
                country=request.country,
                region=request.region_name,
                city="",
                geo_mode="region_only",
                location_name=request.region_name,
                deep_analysis=request.deep_analysis,
                niche=request.niche,
            )
            # Attach frequency — case-insensitive lookup
            freq_key = keyword.lower()
            freq = freq_map.get(freq_key)
            result_item.частотность = freq if freq is not None else None
            results.append(result_item)

        return {"результаты": [r.model_dump() for r in results]}

    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Ошибка данных: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка анализа: {exc}") from exc


# ---------------------------------------------------------------------------
# Legacy AnalyzeRequest endpoint (kept for backward compat, wraps to Search API)
# ---------------------------------------------------------------------------

from app.services.serp_collector import SerpCollector  # noqa: E402

_legacy_collector = SerpCollector()


@router.post("/analyze/legacy", response_model=AnalyzeResponse)
async def analyze_legacy(request: AnalyzeRequest) -> AnalyzeResponse:
    """Устаревший endpoint — прямой HTML-парсинг. Оставлен для совместимости."""
    try:
        location_name = request.location_name or request.region or "Russia"
        results = []
        for keyword in request.keywords:
            serp_data = await _legacy_collector.collect(
                keyword=keyword,
                location_name=location_name,
                depth=request.depth,
            )
            result_item = await build_keyword_report(
                keyword=keyword,
                serp_data=serp_data,
                country=request.country,
                region=request.region,
                city=request.city,
                geo_mode=request.geo_mode,
                location_name=location_name,
                deep_analysis=request.deep_analysis,
            )
            results.append(result_item)
        return AnalyzeResponse(результаты=results)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Ошибка данных: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка: {exc}") from exc


# ---------------------------------------------------------------------------
# Parse-debug endpoint (kept for diagnostics)
# ---------------------------------------------------------------------------

class ParseDebugRequest(BaseModel):
    keyword: str
    location_name: str = "Moscow,Moscow,Russia"
    depth: int = 10


@router.post("/parse-debug")
async def parse_debug(request: ParseDebugRequest) -> dict:
    """Debug endpoint: тест одного ключа через sync HTML Search API."""
    try:
        region_id = resolve_region_id(request.location_name)
        serp = await web_search_sync_html(
            keyword=request.keyword,
            region_id=region_id,
            depth=request.depth,
        )
        return {
            "keyword": request.keyword,
            "source": serp.source,
            "error": serp.error,
            "fetch": {
                "success": serp.success,
                "captcha": False,
                "blocked": False,
                "html_length": len(serp.raw_text),
                "proxy_used": False,
                "parse_strategy": "search_api_html",
            },
            "organic": serp.organic[: request.depth],
            "ads": serp.ads,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
