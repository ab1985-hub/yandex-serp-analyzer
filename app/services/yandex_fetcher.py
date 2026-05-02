"""
Yandex SERP Fetcher — максимально усиленный прямой съём из Replit.

Улучшения по сравнению с предыдущей версией:
  - Сессионный прогрев: сначала GET yandex.ru → получаем реальные куки (yandexuid, i, yp)
  - Pre-seeded cookies: если прогрев не удался, используем синтетические правдоподобные куки
  - Полный набор Sec-Ch-Ua / Sec-Fetch-* заголовков (как у Chrome)
  - Jitter с нарастающей задержкой между ретраями (exponential backoff)
  - Честная детализация ошибок: CAPTCHA / blocked / empty / error
  - Поддержка SERP_PROXY_URL из env (добавить резидентский прокси = стабильный съём)

Env vars:
  SERP_PROXY_URL — HTTP/SOCKS5 прокси, e.g. http://user:pass@host:port
"""
from __future__ import annotations

import asyncio
import base64
import logging
import os
import random
import time
import urllib.parse
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_BASE_YANDEX = "https://yandex.ru"
_SEARCH_PATH = "/search/"
_TIMEOUT_SEC = 25
_MAX_RETRIES = 2


def _proxy_url() -> str | None:
    return os.getenv("SERP_PROXY_URL") or None


def _proxy_auth_header(proxy: str) -> dict:
    """
    httpx 0.27 не всегда передаёт Proxy-Authorization для HTTP-прокси.
    Явно формируем заголовок из учётных данных в URL.
    """
    parsed = urllib.parse.urlparse(proxy)
    if parsed.username and parsed.password:
        credentials = f"{urllib.parse.unquote(parsed.username)}:{urllib.parse.unquote(parsed.password)}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return {"Proxy-Authorization": f"Basic {encoded}"}
    return {}


# ---------------------------------------------------------------------------
# User-Agent pool
# ---------------------------------------------------------------------------

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

@dataclass
class FetchResult:
    success: bool
    html: str = ""
    captcha: bool = False
    blocked: bool = False
    empty: bool = False
    error: str = ""
    status_code: int = 0
    url_fetched: str = ""
    proxy_used: bool = False
    session_warmup: bool = False
    attempts: int = 0
    debug: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def fetch_serp(keyword: str, lr: int, depth: int = 10) -> FetchResult:
    """
    Fetch Yandex SERP for keyword + region.

    Steps:
      1. Session warmup — GET https://yandex.ru to collect real cookies
      2. Search request with cookies + full browser headers
      3. Retry up to _MAX_RETRIES times with fresh UA and backoff

    If SERP_PROXY_URL is set, all requests are routed through it.
    """
    numdoc = max(10, min(depth, 20))
    proxy = _proxy_url()

    params = {
        "text": keyword,
        "lr": str(lr),
        "numdoc": str(numdoc),
        "p": "0",
        "ncrnd": str(random.randint(100000, 999999)),  # Yandex JS-injected noise param
    }
    search_url = _BASE_YANDEX + _SEARCH_PATH + "?" + urllib.parse.urlencode(params)

    last_result: FetchResult | None = None

    for attempt in range(1, _MAX_RETRIES + 1):
        ua = random.choice(_USER_AGENTS)

        # Exponential backoff: 0.4–1s on first attempt, 2–4s on retry
        delay = random.uniform(0.4, 1.0) if attempt == 1 else random.uniform(2.0, 4.0)
        await asyncio.sleep(delay)

        client_kwargs: dict = {
            "timeout": _TIMEOUT_SEC,
            "follow_redirects": True,
        }
        if proxy:
            client_kwargs["proxy"] = proxy
            proxy_headers = _proxy_auth_header(proxy)
            if proxy_headers:
                client_kwargs["headers"] = proxy_headers

        try:
            async with httpx.AsyncClient(**client_kwargs) as client:
                # -------------------------------------------------------
                # Step 1 — Session warmup: visit Yandex homepage first
                # -------------------------------------------------------
                warmup_ok = False
                try:
                    warmup_resp = await client.get(
                        _BASE_YANDEX,
                        headers=_build_headers(ua, referer=None),
                    )
                    warmup_ok = warmup_resp.status_code == 200
                    await asyncio.sleep(random.uniform(0.3, 0.7))
                except Exception:
                    pass

                # -------------------------------------------------------
                # Step 2 — Seed cookies if warmup gave us nothing
                # -------------------------------------------------------
                if "yandexuid" not in client.cookies:
                    _seed_cookies(client.cookies, ua)

                # -------------------------------------------------------
                # Step 3 — Actual search request
                # -------------------------------------------------------
                response = await client.get(
                    search_url,
                    headers=_build_headers(ua, referer=_BASE_YANDEX + "/"),
                )

            status = response.status_code
            final_url = str(response.url)
            html = response.text

            debug: dict = {
                "url_fetched": final_url,
                "status_code": status,
                "ua": ua,
                "html_length": len(html),
                "proxy": proxy or "none",
                "attempt": attempt,
                "session_warmup": warmup_ok,
            }

            # CAPTCHA
            if _is_captcha(final_url, html):
                logger.warning("[FETCH] attempt=%d CAPTCHA для '%s' (lr=%s)", attempt, keyword, lr)
                last_result = FetchResult(
                    success=False, captcha=True,
                    status_code=status, url_fetched=final_url,
                    proxy_used=bool(proxy), session_warmup=warmup_ok, attempts=attempt,
                    error=(
                        "Яндекс вернул CAPTCHA."
                        + (" Прокси не помог — попробуйте резидентский." if proxy else
                           " Добавьте SERP_PROXY_URL (резидентский прокси) в Secrets.")
                    ),
                    debug=debug,
                )
                continue

            # Explicit block
            if status in (403, 429):
                logger.warning("[FETCH] attempt=%d HTTP %s для '%s'", attempt, status, keyword)
                last_result = FetchResult(
                    success=False, blocked=True,
                    status_code=status, url_fetched=final_url,
                    proxy_used=bool(proxy), session_warmup=warmup_ok, attempts=attempt,
                    error=f"Яндекс заблокировал запрос (HTTP {status}). Нужен резидентский прокси.",
                    debug=debug,
                )
                continue

            if status != 200:
                last_result = FetchResult(
                    success=False, status_code=status, url_fetched=final_url,
                    proxy_used=bool(proxy), session_warmup=warmup_ok, attempts=attempt,
                    error=f"Неожиданный HTTP {status} от Яндекса.",
                    debug=debug,
                )
                continue

            # Too short
            if len(html) < 5_000:
                logger.warning("[FETCH] attempt=%d слишком короткий ответ (%d bytes)", attempt, len(html))
                last_result = FetchResult(
                    success=False, empty=True, html=html,
                    status_code=status, url_fetched=final_url,
                    proxy_used=bool(proxy), session_warmup=warmup_ok, attempts=attempt,
                    error=f"Яндекс вернул слишком короткую страницу ({len(html)} bytes).",
                    debug=debug,
                )
                continue

            logger.info(
                "[FETCH] OK '%s' lr=%s %d bytes (attempt %d, warmup=%s, proxy=%s)",
                keyword, lr, len(html), attempt, warmup_ok, bool(proxy),
            )
            return FetchResult(
                success=True, html=html,
                status_code=status, url_fetched=final_url,
                proxy_used=bool(proxy), session_warmup=warmup_ok, attempts=attempt,
                debug=debug,
            )

        except httpx.ProxyError as exc:
            msg = f"Ошибка прокси: {exc}"
            logger.warning("[FETCH] %s", msg)
            last_result = FetchResult(success=False, error=msg, attempts=attempt,
                                      proxy_used=bool(proxy))
        except httpx.TimeoutException:
            msg = f"Таймаут запроса ({_TIMEOUT_SEC}s)"
            logger.warning("[FETCH] attempt=%d %s", attempt, msg)
            last_result = FetchResult(success=False, error=msg, attempts=attempt)
        except Exception as exc:  # noqa: BLE001
            msg = f"HTTP ошибка: {exc}"
            logger.exception("[FETCH] %s", msg)
            last_result = FetchResult(success=False, error=msg, attempts=attempt)

    return last_result or FetchResult(success=False, error="Все попытки запроса к Яндексу исчерпаны")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_headers(ua: str, referer: str | None = None) -> dict:
    h: dict = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none" if referer is None else "same-origin",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }
    if referer:
        h["Referer"] = referer
    if "Chrome" in ua:
        h["Sec-Ch-Ua"] = '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"'
        h["Sec-Ch-Ua-Mobile"] = "?0"
        h["Sec-Ch-Ua-Platform"] = '"Windows"' if "Windows" in ua else '"macOS"'
    return h


def _seed_cookies(cookies: httpx.Cookies, ua: str) -> None:
    """
    Pre-seed realistic Yandex cookies to mimic a returning user.
    These are the cookies Yandex normally sets on first visit.
    Using plausible but synthetic values.
    """
    ts = int(time.time())
    uid = f"{random.randint(10**17, 10**18 - 1)}"
    # yandexuid — primary user identifier set by Yandex on first visit
    cookies.set("yandexuid", uid, domain=".yandex.ru")
    # i — session token
    cookies.set("i", f"{random.randint(10**30, 10**31 - 1)}", domain=".yandex.ru")
    # yp — user preferences (encoded timestamp)
    cookies.set("yp", f"{ts + 31536000}.yu.{uid}", domain=".yandex.ru")
    # is_gdpr, is_gdpr_b — EU GDPR flags
    cookies.set("is_gdpr", "0", domain=".yandex.ru")
    cookies.set("is_gdpr_b", "CK4tEA==", domain=".yandex.ru")


def _is_captcha(url: str, html: str) -> bool:
    if any(sig in url.lower() for sig in ("captcha", "showcaptcha", "checkcaptcha")):
        return True
    signals = [
        "showcaptcha", "smartcaptcha", "yandex_smart_captcha",
        "i-captcha", '"robot"', "robot-check", "checkcaptcha",
        "id=\"js-button\"",
    ]
    html_lower = html.lower()
    return any(sig in html_lower for sig in signals)
