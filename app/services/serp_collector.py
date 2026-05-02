"""
SERP Collector — orchestrates fetch + parse + normalise.

Priority:
  1. yandex_direct — прямой HTTP-съём из Replit (yandex_fetcher + yandex_parser)
  2. error_result  — если съём не удался: fetch_failed=True, данные пустые

Важно: никаких тихих подстановок. Если съём не удался — в serp_data['fetch_failed']
ставится True и в serp_data['fetch_error'] лежит причина. Reporter прокидывает это
в DebugInfo.fetch_status, а UI показывает пользователю честный статус.
"""
from __future__ import annotations

import hashlib
import logging
import os

from app.services.text_processor import extract_significant_lemmas
from app.services.yandex_fetcher import FetchResult, fetch_serp
from app.services.yandex_parser import ParseResult, parse_serp
from app.services.yandex_region_map import resolve_lr

logger = logging.getLogger(__name__)


class SerpCollector:
    def __init__(self) -> None:
        pass

    # -----------------------------------------------------------------------
    # Main entry-point
    # -----------------------------------------------------------------------

    async def collect(self, keyword: str, location_name: str, depth: int) -> dict:
        lr = resolve_lr(location_name)

        # --- 1. Direct Yandex ---
        fetch: FetchResult = await fetch_serp(keyword, lr=lr, depth=depth)
        if fetch.success:
            parse: ParseResult = parse_serp(fetch.html, keyword=keyword, debug=True)
            organic = parse.organic[:depth]
            ads = parse.ads
            if organic or ads:
                logger.info(
                    "[REAL/direct] '%s' → органика=%d реклама=%d стратегия=%s",
                    keyword, len(organic), len(ads), parse.debug.get("strategy"),
                )
                return {
                    "organic": organic,
                    "ads": ads,
                    "is_fallback": False,
                    "source": "yandex_direct",
                    "fetch_failed": False,
                    "fetch_error": "",
                    "fetch_debug": {
                        "success": True,
                        "captcha": False,
                        "blocked": False,
                        "url_fetched": fetch.url_fetched,
                        "html_length": len(fetch.html),
                        "attempts": fetch.attempts,
                        "proxy_used": fetch.proxy_used,
                        "parse_strategy": parse.debug.get("strategy", ""),
                        "organic_found": len(organic),
                        "ads_found": len(ads),
                    },
                }
            # Fetch succeeded but parser found nothing
            logger.warning("[direct] Парсер не нашёл результатов для '%s' (lr=%s)", keyword, lr)
            fetch_debug = {
                "success": False,
                "captcha": False,
                "blocked": False,
                "url_fetched": fetch.url_fetched,
                "html_length": len(fetch.html),
                "attempts": fetch.attempts,
                "proxy_used": fetch.proxy_used,
                "parse_strategy": parse.debug.get("strategy", ""),
                "organic_found": 0,
                "ads_found": 0,
            }
            return self._error_result(
                source="yandex_direct",
                error="Страница получена, но парсер не нашёл результатов. "
                      "Возможно, Яндекс изменил HTML-структуру SERP.",
                fetch_debug=fetch_debug,
            )

        # --- Fetch failed ---
        logger.warning("[direct] Съём не удался для '%s': %s", keyword, fetch.error)
        fetch_debug = {
            "success": False,
            "captcha": fetch.captcha,
            "blocked": fetch.blocked,
            "url_fetched": fetch.url_fetched,
            "html_length": len(fetch.html),
            "attempts": fetch.attempts,
            "proxy_used": fetch.proxy_used,
            "parse_strategy": "",
            "organic_found": 0,
            "ads_found": 0,
        }

        # --- 2. Честный результат ошибки (без тихих подстановок) ---
        return self._error_result(
            source="yandex_direct",
            error=fetch.error,
            fetch_debug=fetch_debug,
        )

    # -----------------------------------------------------------------------
    # Extended debug collect (for /api/parse-debug endpoint)
    # -----------------------------------------------------------------------

    async def collect_with_debug(self, keyword: str, location_name: str, depth: int) -> dict:
        lr = resolve_lr(location_name)
        fetch = await fetch_serp(keyword, lr=lr, depth=depth)

        result: dict = {
            "keyword": keyword,
            "location_name": location_name,
            "lr": lr,
            "fetch": {
                "success": fetch.success,
                "status_code": fetch.status_code,
                "captcha": fetch.captcha,
                "blocked": fetch.blocked,
                "empty": fetch.empty,
                "error": fetch.error,
                "html_length": len(fetch.html),
                "url_fetched": fetch.url_fetched,
                "proxy_used": fetch.proxy_used,
                "session_warmup": fetch.session_warmup,
                "attempts": fetch.attempts,
                **fetch.debug,
            },
            "parse": {},
            "organic": [],
            "ads": [],
        }

        if fetch.success:
            parse = parse_serp(fetch.html, keyword=keyword, debug=True)
            result["parse"] = {
                **parse.debug,
                "organic_count": len(parse.organic),
                "ads_count": len(parse.ads),
                "organic_sample": parse.organic[:3],
                "ads_sample": parse.ads[:3],
            }
            result["organic"] = parse.organic[:depth]
            result["ads"] = parse.ads

        return result

    # -----------------------------------------------------------------------
    # Error result (no organic/ads, fetch_failed=True, NO mock substitution)
    # -----------------------------------------------------------------------

    @staticmethod
    def _error_result(source: str, error: str, fetch_debug: dict) -> dict:
        return {
            "organic": [],
            "ads": [],
            "is_fallback": False,
            "source": source,
            "fetch_failed": True,
            "fetch_error": error,
            "fetch_debug": fetch_debug,
        }

    # -----------------------------------------------------------------------
    # Explicit mock (only called from debug/test flows)
    # -----------------------------------------------------------------------

    def get_mock(self, keyword: str) -> dict:
        """Explicit mock — only for dev/debug. Never called automatically."""
        logger.info("[MOCK/explicit] Мок для '%s'", keyword)
        h = int(hashlib.md5(keyword.encode()).hexdigest(), 16)
        key_lemmas = extract_significant_lemmas(keyword)
        n_lemmas = len(key_lemmas) if key_lemmas else 1
        GENERIC = [
            ("Популярные предложения", "Подборка лучших вариантов."),
            ("Официальный сайт", "Проверенная информация."),
            ("Рейтинг лучших вариантов", "Независимый рейтинг."),
            ("Сравнение и анализ", "Сравните по параметрам."),
            ("Агрегатор объявлений", "Все объявления на одной странице."),
            ("Справочник", "Характеристики и советы."),
            ("Блог", "Аналитика и обзоры."),
            ("Форум и отзывы", "Обсуждения и реальные отзывы."),
            ("Гид по выбору", "Пошаговые инструкции."),
            ("Новости рынка", "Актуальные тенденции."),
        ]

        def pick(pos: int) -> list[str]:
            s = (h >> (pos * 4)) & 0xFF
            count = 0 if s % 10 < 3 else (max(1, n_lemmas // 3) if s % 10 < 6 else n_lemmas)
            pool = list(key_lemmas)
            out: list[str] = []
            for _ in range(count):
                if not pool:
                    break
                out.append(pool.pop((h + len(out) * 13) % len(pool)))
            return out

        organic = []
        for i in range(10):
            idx = (h + i * 17) % len(GENERIC)
            t, d = GENERIC[idx]
            lm = pick(i)
            organic.append({
                "position": i + 1,
                "title": f"{' '.join(lm).capitalize()} — {t.lower()}" if lm else t,
                "description": d,
                "url": f"https://mock-site-{idx+1}.ru/{i+1}",
                "domain": f"mock-site-{idx+1}.ru",
            })
        return {
            "organic": organic,
            "ads": [],
            "is_fallback": True,
            "source": "mock",
            "fetch_failed": False,
            "fetch_error": "",
            "fetch_debug": {
                "success": False,
                "captcha": False,
                "blocked": False,
                "url_fetched": "",
                "html_length": 0,
                "attempts": 0,
                "proxy_used": False,
                "parse_strategy": "mock",
                "organic_found": 10,
                "ads_found": 0,
            },
        }
