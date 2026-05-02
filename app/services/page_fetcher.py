"""
Async HTTP fetcher для углублённого анализа реальных страниц из топа.

Без headless-браузера: только httpx + bs4. Медленно, но достаточно
для большинства SEO-страниц (статьи, лендинги, инструменты), у которых
полезный контент уже в server-rendered HTML.
"""
from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Iterable

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

_TIMEOUT = httpx.Timeout(connect=5.0, read=8.0, write=5.0, pool=5.0)
_MAX_BODY_BYTES = 1_500_000  # 1.5 MB
_BODY_TEXT_LIMIT = 3000

# CTA / триггерные слова, которые ищем в тексте кнопок и ссылок
_CTA_PATTERNS: list[str] = [
    "попробовать", "попробуйте", "начать", "начните",
    "загрузить", "загрузите", "выбрать файл",
    "конвертировать", "преобразовать", "распознать", "расшифровать",
    "транскрибировать", "перевести",
    "перетащите", "drag",
    "upload", "convert", "transcribe", "recognize",
    "try free", "try now", "start free", "get started",
    "sign up", "регистрация", "зарегистрироваться",
    "скачать", "download",
]

# Признаки pricing-блока в тексте
_PRICING_RE = re.compile(
    r"(тариф|подписк|стоимост|цен[аыу]|price|pricing|/мес|/мо|руб[\.\s/]|₽)",
    re.IGNORECASE,
)


@dataclass
class PageFetchResult:
    url: str                                 # исходный URL
    final_url: str = ""                      # после редиректов
    fetch_ok: bool = False
    status_code: int = 0
    error: str = ""
    title: str = ""
    meta_description: str = ""
    h1: str = ""
    body_text: str = ""                      # первые 3000 символов
    cta_signals: list[str] = field(default_factory=list)
    has_form: bool = False
    has_upload_form: bool = False            # <input type="file"> или dropzone
    has_pricing: bool = False
    text_length: int = 0
    html_length: int = 0


def _safe_text(node) -> str:
    if node is None:
        return ""
    try:
        return node.get_text(" ", strip=True)
    except Exception:
        return ""


def _extract(html: str) -> dict:
    """Парсим HTML и извлекаем интересующие нас фрагменты."""
    soup = BeautifulSoup(html, "lxml")

    title = _safe_text(soup.find("title"))[:300]

    meta_desc = ""
    meta_node = soup.find("meta", attrs={"name": "description"})
    if meta_node and meta_node.get("content"):
        meta_desc = str(meta_node["content"]).strip()[:500]
    if not meta_desc:
        og = soup.find("meta", attrs={"property": "og:description"})
        if og and og.get("content"):
            meta_desc = str(og["content"]).strip()[:500]

    h1 = _safe_text(soup.find("h1"))[:300]

    # Удаляем шум, чтобы текст был чище
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
        tag.decompose()

    body_text = _safe_text(soup.body or soup)[:_BODY_TEXT_LIMIT]

    # CTA по тексту кнопок и ссылок
    cta: set[str] = set()
    for el in soup.find_all(["button", "a"]):
        txt = _safe_text(el).lower()
        if not txt or len(txt) > 80:
            continue
        for pat in _CTA_PATTERNS:
            if pat in txt:
                cta.add(pat)
                break

    has_form = bool(soup.find("form"))
    has_upload = bool(
        soup.find("input", attrs={"type": "file"})
        or soup.find(attrs={"class": re.compile(r"(dropzone|drag|upload)", re.I)})
    )
    has_pricing = bool(_PRICING_RE.search(body_text))

    return {
        "title": title,
        "meta_description": meta_desc,
        "h1": h1,
        "body_text": body_text,
        "cta_signals": sorted(cta),
        "has_form": has_form,
        "has_upload_form": has_upload,
        "has_pricing": has_pricing,
        "text_length": len(body_text),
    }


async def _fetch_one(client: httpx.AsyncClient, url: str) -> PageFetchResult:
    res = PageFetchResult(url=url)
    try:
        # один retry на сетевые ошибки
        last_exc: Exception | None = None
        for attempt in range(2):
            try:
                resp = await client.get(url)
                break
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError) as exc:
                last_exc = exc
                if attempt == 1:
                    raise
                await asyncio.sleep(0.3)
        else:  # pragma: no cover
            raise last_exc or RuntimeError("fetch failed")

        res.status_code = resp.status_code
        res.final_url = str(resp.url)

        if resp.status_code >= 400:
            res.error = f"HTTP {resp.status_code}"
            return res

        ctype = resp.headers.get("content-type", "").lower()
        if "html" not in ctype:
            res.error = f"non-html ({ctype or 'unknown'})"
            return res

        html_bytes = resp.content[:_MAX_BODY_BYTES]
        try:
            html = html_bytes.decode(resp.encoding or "utf-8", errors="replace")
        except Exception:
            html = html_bytes.decode("utf-8", errors="replace")

        res.html_length = len(html_bytes)
        parsed = _extract(html)
        for key, value in parsed.items():
            setattr(res, key, value)
        res.fetch_ok = True
        return res

    except httpx.HTTPError as exc:
        res.error = f"{type(exc).__name__}: {exc}"[:200]
    except Exception as exc:  # noqa: BLE001
        res.error = f"{type(exc).__name__}: {exc}"[:200]
    return res


async def fetch_pages(urls: Iterable[str], concurrency: int = 5) -> list[PageFetchResult]:
    """Параллельно загружает HTML страниц. Никогда не падает: на ошибке возвращает fetch_ok=False."""
    url_list = [u for u in urls if u]
    if not url_list:
        return []

    headers = {
        "User-Agent": _USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru,en-US;q=0.9,en;q=0.8",
    }
    limits = httpx.Limits(max_keepalive_connections=concurrency, max_connections=concurrency)
    async with httpx.AsyncClient(
        timeout=_TIMEOUT,
        follow_redirects=True,
        max_redirects=5,
        headers=headers,
        limits=limits,
        verify=True,  # secure-by-default: невалидный TLS → fetch_ok=False с понятной ошибкой
    ) as client:
        sem = asyncio.Semaphore(concurrency)

        async def _bound(u: str) -> PageFetchResult:
            async with sem:
                return await _fetch_one(client, u)

        results = await asyncio.gather(*[_bound(u) for u in url_list], return_exceptions=False)

    ok = sum(1 for r in results if r.fetch_ok)
    logger.info("[page_fetcher] fetched %d/%d pages OK", ok, len(results))
    return list(results)
