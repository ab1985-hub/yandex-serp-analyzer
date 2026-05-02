"""
YandexSearchClient — клиент Yandex Search API и Wordstat API.

Env vars:
  YANDEX_API_KEY    — API-ключ сервисного аккаунта Yandex Cloud
  YANDEX_FOLDER_ID  — идентификатор каталога (b1g...)

Оба API (Search + Wordstat) работают через один хост:
  https://searchapi.api.cloud.yandex.net/v2

  Search:  POST /web/search
  Wordstat: POST /wordstat/getTop, /wordstat/getRegionsTree

Пресеты:
  manual-serp-check: sync, xml  — точечная проверка SERP
  bulk-analysis:     async, xml  — массовый анализ (polling)
"""
from __future__ import annotations

import asyncio
import base64
import logging
import os
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

import httpx

logger = logging.getLogger(__name__)

_SEARCH_API_BASE = "https://searchapi.api.cloud.yandex.net/v2"
_WORDSTAT_API_BASE = _SEARCH_API_BASE
_TIMEOUT = 30
_POLL_INTERVAL = 2.0
_POLL_MAX_ATTEMPTS = 30


def _api_key() -> str:
    key = os.getenv("YANDEX_API_KEY", "")
    if not key:
        raise RuntimeError("YANDEX_API_KEY не задан в Secrets")
    return key


def _folder_id() -> str:
    fid = os.getenv("YANDEX_FOLDER_ID", "")
    if not fid:
        raise RuntimeError("YANDEX_FOLDER_ID не задан в Secrets")
    return fid


def _auth_headers() -> dict:
    return {"Authorization": f"Api-Key {_api_key()}"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _decode_raw_data(raw: str) -> str:
    try:
        return base64.b64decode(raw).decode("utf-8", errors="replace")
    except Exception as exc:
        raise ValueError(f"Ошибка декодирования rawData: {exc}") from exc


def _parse_xml_serp(xml_text: str, depth: int = 10) -> dict:
    """Парсит XML Yandex Search API → organic + ads."""
    organic: list[dict] = []
    ads: list[dict] = []
    try:
        root = ET.fromstring(xml_text)
        for group in root.iter("group"):
            for doc in group.findall("doc"):
                title_el = doc.find("title")
                url_el = doc.find("url")
                domain_el = doc.find("domain")
                passages = doc.findall(".//passage")

                title = "".join(title_el.itertext()).strip() if title_el is not None else ""
                description = " ".join(
                    "".join(p.itertext()).strip() for p in passages
                ).strip()
                url = url_el.text.strip() if url_el is not None and url_el.text else ""
                domain = domain_el.text.strip() if domain_el is not None and domain_el.text else ""
                if not domain and url:
                    domain = urlparse(url).netloc.lstrip("www.")

                organic.append({
                    "position": len(organic) + 1,
                    "title": title,
                    "description": description,
                    "url": url,
                    "domain": domain,
                })
                if len(organic) >= depth:
                    break
            if len(organic) >= depth:
                break
    except ET.ParseError as exc:
        logger.warning("[xml_parser] ParseError: %s | snippet: %s", exc, xml_text[:200])
    return {"organic": organic, "ads": ads}


# ---------------------------------------------------------------------------
# SerpResult container
# ---------------------------------------------------------------------------

class SerpResult:
    def __init__(self, organic: list[dict], ads: list[dict],
                 source: str, raw_text: str = "", error: str = ""):
        self.organic = organic
        self.ads = ads
        self.source = source
        self.raw_text = raw_text
        self.error = error
        self.success = not bool(error)

    def to_collector_dict(self) -> dict:
        ok = not self.error
        return {
            "organic": self.organic,
            "ads": self.ads,
            "is_fallback": False,
            "source": self.source,
            "fetch_failed": not ok,
            "fetch_error": self.error,
            "fetch_debug": {
                "success": ok,
                "captcha": False,
                "blocked": False,
                "url_fetched": "",
                "html_length": len(self.raw_text),
                "attempts": 1,
                "proxy_used": False,
                "parse_strategy": "search_api_xml",
                "organic_found": len(self.organic),
                "ads_found": len(self.ads),
            },
        }


# ---------------------------------------------------------------------------
# Preset constants
# ---------------------------------------------------------------------------

PRESET_MANUAL_CHECK = "manual-serp-check"
PRESET_BULK_ANALYSIS = "bulk-analysis"


# ---------------------------------------------------------------------------
# Shared request builder
# ---------------------------------------------------------------------------

def _build_search_payload(keyword: str, folder_id: str, region_id: int, depth: int) -> dict:
    return {
        "folderId": folder_id,
        "query": {
            "searchType": "SEARCH_TYPE_RU",
            "queryText": keyword,
            "groupsOnPage": min(depth, 20),
            "region": region_id,
        },
        "sortSpec": {"sortType": "SORT_TYPE_RELEVANCE"},
        "maxPassages": 2,
    }


# ---------------------------------------------------------------------------
# A. Sync Search API (manual-serp-check)
# ---------------------------------------------------------------------------

async def web_search_sync_html(
    keyword: str,
    region_id: int = 213,
    depth: int = 10,
) -> SerpResult:
    """
    Sync Search API → XML ответ (используется для точечной проверки).
    Note: API всегда возвращает XML rawData; HTML недоступен в данном эндпоинте.
    """
    folder_id = _folder_id()
    payload = _build_search_payload(keyword, folder_id, region_id, depth)
    url = f"{_SEARCH_API_BASE}/web/search"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(url, json=payload, headers=_auth_headers())
            if resp.status_code != 200:
                err = f"Search API HTTP {resp.status_code}: {resp.text[:400]}"
                logger.error("[sync] %s", err)
                return SerpResult([], [], "search_api", error=err)
            data = resp.json()

        raw = data.get("rawData", "")
        if not raw:
            return SerpResult([], [], "search_api", error="Search API: rawData пуст")

        xml_text = _decode_raw_data(raw)
        parsed = _parse_xml_serp(xml_text, depth=depth)
        logger.info("[sync] '%s' → organic=%d", keyword, len(parsed["organic"]))
        return SerpResult(parsed["organic"], parsed["ads"], "search_api", raw_text=xml_text)

    except Exception as exc:
        err = f"Ошибка Search API (sync): {exc}"
        logger.exception("[sync] %s", err)
        return SerpResult([], [], "search_api", error=err)


# ---------------------------------------------------------------------------
# B. Async Search API (bulk-analysis)
# ---------------------------------------------------------------------------

async def web_search_async_xml(
    keyword: str,
    region_id: int = 213,
    depth: int = 10,
) -> SerpResult:
    """
    Async Search API → XML ответ (для массового анализа).
    Отправка → polling → декодирование XML.
    """
    folder_id = _folder_id()
    payload = _build_search_payload(keyword, folder_id, region_id, depth)
    create_url = f"{_SEARCH_API_BASE}/web/searchAsync"

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(create_url, json=payload, headers=_auth_headers())
            if resp.status_code not in (200, 202):
                err = f"Search API (async create) HTTP {resp.status_code}: {resp.text[:400]}"
                logger.error("[async] %s", err)
                return SerpResult([], [], "search_api_async", error=err)
            op_data = resp.json()

        operation_id = op_data.get("id") or op_data.get("operationId")
        if not operation_id:
            # Some sync responses return rawData directly
            raw = op_data.get("rawData", "") or (op_data.get("response") or {}).get("rawData", "")
            if raw:
                xml_text = _decode_raw_data(raw)
                parsed = _parse_xml_serp(xml_text, depth=depth)
                return SerpResult(parsed["organic"], parsed["ads"],
                                  "search_api_async", raw_text=xml_text)
            err = f"Search API: нет operationId и нет rawData: {list(op_data.keys())}"
            return SerpResult([], [], "search_api_async", error=err)

        logger.info("[async] операция '%s' для '%s'", operation_id, keyword)
        poll_url = f"{_SEARCH_API_BASE}/operations/{operation_id}"

        for attempt in range(_POLL_MAX_ATTEMPTS):
            await asyncio.sleep(_POLL_INTERVAL)
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                pr = await client.get(poll_url, headers=_auth_headers())
                if pr.status_code != 200:
                    continue
                poll_data = pr.json()

            if not poll_data.get("done", False):
                logger.debug("[async] ожидание %d/%d для '%s'", attempt + 1, _POLL_MAX_ATTEMPTS, keyword)
                continue

            if poll_data.get("error"):
                err = f"Search API: операция завершилась ошибкой: {poll_data['error']}"
                return SerpResult([], [], "search_api_async", error=err)

            raw = (poll_data.get("response") or {}).get("rawData", "")
            if not raw:
                err = "Search API: операция завершена, rawData пуст"
                return SerpResult([], [], "search_api_async", error=err)

            xml_text = _decode_raw_data(raw)
            parsed = _parse_xml_serp(xml_text, depth=depth)
            logger.info("[async] '%s' → organic=%d", keyword, len(parsed["organic"]))
            return SerpResult(parsed["organic"], parsed["ads"],
                              "search_api_async", raw_text=xml_text)

        err = f"Search API: таймаут ({_POLL_MAX_ATTEMPTS * _POLL_INTERVAL}s)"
        return SerpResult([], [], "search_api_async", error=err)

    except Exception as exc:
        err = f"Ошибка Search API (async): {exc}"
        logger.exception("[async] %s", err)
        return SerpResult([], [], "search_api_async", error=err)


# ---------------------------------------------------------------------------
# C. Wordstat API  (searchapi.api.cloud.yandex.net/v2/wordstat/...)
#
# Реальные REST-пути из официального proto (cloudapi GitHub):
#   GetTop               → POST /v2/wordstat/topRequests
#   GetDynamics          → POST /v2/wordstat/dynamics
#   GetRegionsDistrib.   → POST /v2/wordstat/regions
#   GetRegionsTree       → POST /v2/wordstat/getRegionsTree
# ---------------------------------------------------------------------------

async def wordstat_get_top(
    keyword: str,
    region_id: int = 213,
    limit: int = 100,
) -> list[dict]:
    """
    Wordstat GetTop → список ключей с частотностью.
    Raises RuntimeError если API недоступен.
    """
    folder_id = _folder_id()
    payload = {
        "folderId": folder_id,
        "phrase": keyword,
        "numPhrases": min(limit, 2000),
        "regions": [str(region_id)],
    }
    url = f"{_WORDSTAT_API_BASE}/wordstat/topRequests"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(url, json=payload, headers=_auth_headers())
            if resp.status_code != 200:
                raise RuntimeError(
                    f"Wordstat API HTTP {resp.status_code}: {resp.text[:400]}")
            data = resp.json()

        # Используем ТОЛЬКО results (вкладка «Популярные» в Wordstat UI).
        # associations — ассоциативные запросы из отдельного столбца «Что искали со словом»,
        # они намеренно не смешиваются с основным списком.
        raw_results: list[dict] = []
        for item in (data.get("results") or []):
            kw = (item.get("phrase") or "").strip()
            freq = int(item.get("count") or 0)
            if kw:
                raw_results.append({"keyword": kw, "frequency": freq})

        # Дедупликация (в API не должно быть дублей, но на всякий случай)
        seen: set[str] = set()
        unique: list[dict] = []
        for r in raw_results:
            k = r["keyword"].lower()
            if k not in seen:
                seen.add(k)
                unique.append(r)

        logger.info("[wordstat] '%s' → %d results (без associations)", keyword, len(unique))
        return unique[:limit]

    except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
        raise RuntimeError(f"Wordstat API недоступен: {exc}") from exc
    except Exception as exc:
        logger.exception("[wordstat] %s", exc)
        raise


async def wordstat_get_regions_tree() -> list[dict]:
    """
    Wordstat GetRegionsTree → иерархия регионов.
    Raises RuntimeError если API недоступен.
    """
    folder_id = _folder_id()
    url = f"{_WORDSTAT_API_BASE}/wordstat/getRegionsTree"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json={"folderId": folder_id},
                                     headers=_auth_headers())
            if resp.status_code != 200:
                raise RuntimeError(
                    f"Wordstat GetRegionsTree HTTP {resp.status_code}: {resp.text[:400]}")
            data = resp.json()

        def normalize(node: dict) -> dict:
            return {
                "id": int(node.get("id") or node.get("regionId") or 0),
                "name": node.get("label") or node.get("name") or node.get("regionName") or "",
                "parentId": node.get("parentId"),
                "children": [normalize(c) for c in (node.get("children") or [])],
            }

        regions = data.get("regions") or data.get("result") or []
        return [normalize(r) for r in regions]

    except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
        raise RuntimeError(f"Wordstat GetRegionsTree недоступен: {exc}") from exc
    except Exception as exc:
        logger.exception("[regions_tree] %s", exc)
        raise


# ---------------------------------------------------------------------------
# Stubs for future
# ---------------------------------------------------------------------------

async def wordstat_get_dynamics(keyword: str, region_id: int = 213) -> list[dict]:
    raise NotImplementedError("wordstat_get_dynamics не реализован")


async def wordstat_get_regions_distribution(keyword: str) -> list[dict]:
    raise NotImplementedError("wordstat_get_regions_distribution не реализован")


async def get_async_operation_result(operation_id: str) -> dict:
    url = f"{_SEARCH_API_BASE}/operations/{operation_id}"
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(url, headers=_auth_headers())
        resp.raise_for_status()
        return resp.json()
