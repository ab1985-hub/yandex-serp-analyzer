"""
Классификатор страниц на основе HTML-признаков (после page_fetcher).

Возвращает три измерения:
  - page_type_html : структурный тип страницы
  - competitor_level : насколько это прямой конкурент по запросу
  - intent_coverage  : насколько хорошо страница закрывает интент
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.page_fetcher import PageFetchResult
from app.services.text_processor import extract_significant_lemmas, lemmatize_tokens

# Локальные действие/контекст-токены — должны коррелировать с intent_classifier.
_ACTION_TOKENS = {
    "конвертировать", "конвертер", "преобразовать", "транскрибировать",
    "транскрипция", "распознать", "распознавание", "расшифровать",
    "расшифровка", "перевести", "переводчик", "генератор",
    "convert", "converter", "transcribe", "transcription",
    "recognize", "recognition", "translator",
}
_TOOL_CONTEXT_TOKENS = {
    "онлайн", "online", "бесплатно", "free", "сервис", "service",
    "инструмент", "tool", "приложение", "app", "saas",
    "нейросеть", "ai", "gpt",
}

# Признаки статьи / блога
_ARTICLE_DOMAIN_RE = re.compile(r"(/blog/|/article|/articles/|/post|/news/|/journal/|/wiki/)", re.I)
_REVIEW_TITLE_RE = re.compile(
    r"(топ[- ]?\d+|лучших|лучшие|обзор|сравнен|подборк|рейтинг)",
    re.I,
)
_DOCS_URL_RE = re.compile(r"(/docs?/|/documentation|/help/|/support/|/manual|/api/|/reference)", re.I)
_FORUM_DOMAIN_RE = re.compile(r"(forum|otvet|otvety|reddit|stackexchange|stackoverflow|qna)", re.I)
_MARKETPLACE_DOMAIN_RE = re.compile(
    r"(ozon|wildberries|avito|youla|aliexpress|lamoda|market\.yandex)",
    re.I,
)


PAGE_TYPE_LABEL_RU: dict[str, str] = {
    "TOOL_SERVICE": "Онлайн-инструмент / сервис",
    "SAAS": "SaaS / web-app",
    "CONVERTER": "Конвертер / транскрибатор",
    "LANDING": "Лендинг продукта",
    "ARTICLE": "Информационная статья",
    "REVIEW_LIST": "Обзор / подборка",
    "DOCS": "Документация / help",
    "MARKETPLACE": "Маркетплейс / каталог",
    "FORUM": "Форум / UGC",
    "IRRELEVANT": "Нерелевантный / неопределён",
    "UNKNOWN": "Не определено",
}

COMPETITOR_LABEL_RU: dict[str, str] = {
    "DIRECT": "Прямой конкурент",
    "CLOSE": "Близкий конкурент",
    "INDIRECT": "Непрямой конкурент",
    "NOT_COMPETITOR": "Не конкурент",
    "UNKNOWN": "Не определено",
}

INTENT_COVERAGE_LABEL_RU: dict[str, str] = {
    "STRONG": "Сильно закрывает интент",
    "PARTIAL": "Частично закрывает",
    "WEAK": "Слабо закрывает",
    "NONE": "Не закрывает",
}


@dataclass
class PageClassification:
    page_type_html: str
    competitor_level: str
    intent_coverage: str
    explanation: str
    # Niche-aware extended fields (populated by classify_page_with_niche)
    page_type_domain: str | None = None
    domain_rule_applied: bool = False
    html_status: str = ""
    final_page_type: str = ""
    final_competitor_level: str = ""
    final_intent_coverage: str = ""
    classification_source: str = ""
    classification_comment: str = ""


def _tokens_lower(text: str) -> set[str]:
    return set(re.findall(r"[а-яёa-z]+", text.lower()))


def _key_in_text_ratio(key_lemmas: list[str], text: str) -> float:
    if not key_lemmas or not text:
        return 0.0
    txt_lemmas = set(lemmatize_tokens(text))
    if not txt_lemmas:
        return 0.0
    matched = sum(1 for k in key_lemmas if k in txt_lemmas)
    return matched / len(key_lemmas)


def _classify_page_type(page: PageFetchResult, key_lemmas: list[str]) -> tuple[str, str]:
    url = (page.final_url or page.url).lower()
    title_l = page.title.lower()
    h1_l = page.h1.lower()
    body_l = page.body_text.lower()
    combined_short = f"{title_l} {h1_l}"
    all_tokens = _tokens_lower(f"{combined_short} {body_l[:1500]}")

    # Маркеты / форумы — по URL
    if _MARKETPLACE_DOMAIN_RE.search(url):
        return "MARKETPLACE", "Маркетплейс по URL"
    if _FORUM_DOMAIN_RE.search(url):
        return "FORUM", "Форум / UGC по URL"

    # Документация — URL + структура
    if _DOCS_URL_RE.search(url):
        return "DOCS", "Документация / help по URL"

    # Обзор / подборка — по заголовку
    if _REVIEW_TITLE_RE.search(combined_short):
        return "REVIEW_LIST", "Обзор / подборка по заголовку"

    action_hits = all_tokens & _ACTION_TOKENS
    context_hits = all_tokens & _TOOL_CONTEXT_TOKENS

    # Сильные сервис-признаки: форма загрузки + action-токены или CTA-кнопки
    if page.has_upload_form and (action_hits or page.cta_signals):
        return "CONVERTER", f"upload-форма + действие ({', '.join(sorted(action_hits)[:2]) or 'CTA'})"

    # SaaS / TOOL_SERVICE — много CTA + регистрация / pricing
    has_signup_cta = any(c in page.cta_signals for c in ("sign up", "регистрация", "зарегистрироваться", "start free", "try free", "try now", "get started"))
    if has_signup_cta and page.has_pricing:
        return "SAAS", "регистрация + pricing"
    if has_signup_cta and (action_hits or context_hits):
        return "SAAS", "регистрация + action/context"

    # TOOL_SERVICE — есть action-токены и CTA или контекст-токены
    if action_hits and (page.cta_signals or context_hits):
        return "TOOL_SERVICE", f"действие ({', '.join(sorted(action_hits)[:2])}) + CTA/онлайн"

    # Лендинг — есть CTA, есть pricing, нет признаков статьи
    if page.cta_signals and (page.has_pricing or page.has_form):
        return "LANDING", "CTA + pricing/форма"

    # Статья — длинный текст и информационные сигналы
    is_article_url = bool(_ARTICLE_DOMAIN_RE.search(url))
    if is_article_url or page.text_length >= 1500:
        return "ARTICLE", "длинный текстовый материал" if not is_article_url else "URL содержит /blog|/article"

    # Если есть какие-то action-токены, но без CTA — слабый сигнал TOOL_SERVICE
    if action_hits or context_hits:
        return "TOOL_SERVICE", f"маркеры онлайн-сервиса: «{', '.join(sorted(action_hits | context_hits)[:3])}»"

    return "IRRELEVANT", "недостаточно признаков"


def _competitor_level_from_type(
    page_type: str,
    title_ratio: float,
    h1_ratio: float,
) -> str:
    """
    DIRECT: tool/saas/converter/marketplace + хорошее покрытие ключа в title/h1
    CLOSE:  тот же тип, но слабое покрытие
    INDIRECT: review_list / landing / docs
    NOT_COMPETITOR: article / forum / irrelevant
    """
    direct_types = {"TOOL_SERVICE", "SAAS", "CONVERTER", "MARKETPLACE"}
    close_types = {"LANDING", "REVIEW_LIST"}
    indirect_types = {"DOCS"}
    non_competitor_types = {"ARTICLE", "FORUM", "IRRELEVANT", "UNKNOWN"}

    if page_type in direct_types:
        if max(title_ratio, h1_ratio) >= 0.6:
            return "DIRECT"
        return "CLOSE"
    if page_type in close_types:
        if max(title_ratio, h1_ratio) >= 0.5:
            return "CLOSE"
        return "INDIRECT"
    if page_type in indirect_types:
        return "INDIRECT"
    if page_type in non_competitor_types:
        return "NOT_COMPETITOR"
    return "INDIRECT"


def _intent_coverage(
    page: PageFetchResult,
    page_type: str,
    title_ratio: float,
    h1_ratio: float,
) -> str:
    """
    STRONG : сервис/инструмент закрывает задачу + ключ в h1/title.
    PARTIAL: сервис, но ключ слабо упомянут; либо лендинг с темой.
    WEAK   : статья / docs со слабым упоминанием.
    NONE   : нерелевантно.
    """
    has_tool_func = page.has_upload_form or any(
        c in page.cta_signals
        for c in ("конвертировать", "преобразовать", "распознать", "расшифровать",
                  "транскрибировать", "перевести", "convert", "transcribe", "recognize",
                  "загрузить", "upload", "выбрать файл")
    )
    direct_like = page_type in {"TOOL_SERVICE", "SAAS", "CONVERTER"}

    if direct_like and has_tool_func and max(title_ratio, h1_ratio) >= 0.6:
        return "STRONG"
    if direct_like and (has_tool_func or max(title_ratio, h1_ratio) >= 0.5):
        return "PARTIAL"
    if page_type in {"LANDING", "MARKETPLACE"} and max(title_ratio, h1_ratio) >= 0.5:
        return "PARTIAL"
    if page_type in {"REVIEW_LIST", "ARTICLE"} and max(title_ratio, h1_ratio) >= 0.5:
        return "WEAK"
    if page_type in {"DOCS", "FORUM"}:
        return "WEAK"
    if page_type == "IRRELEVANT":
        return "NONE"
    if max(title_ratio, h1_ratio) >= 0.4:
        return "PARTIAL"
    return "WEAK"


def classify_page(page: PageFetchResult, keyword: str) -> PageClassification:
    if not page.fetch_ok:
        return PageClassification(
            page_type_html="UNKNOWN",
            competitor_level="UNKNOWN",
            intent_coverage="NONE",
            explanation=f"Страница не загружена: {page.error or 'unknown error'}",
        )

    key_lemmas = extract_significant_lemmas(keyword)
    page_type, type_explanation = _classify_page_type(page, key_lemmas)
    title_ratio = _key_in_text_ratio(key_lemmas, page.title)
    h1_ratio = _key_in_text_ratio(key_lemmas, page.h1)
    competitor_level = _competitor_level_from_type(page_type, title_ratio, h1_ratio)
    coverage = _intent_coverage(page, page_type, title_ratio, h1_ratio)

    explanation = (
        f"Тип: {PAGE_TYPE_LABEL_RU.get(page_type, page_type)} "
        f"({type_explanation}); ключ в title={title_ratio:.0%}, h1={h1_ratio:.0%}"
    )
    return PageClassification(
        page_type_html=page_type,
        competitor_level=competitor_level,
        intent_coverage=coverage,
        explanation=explanation,
    )


def classify_page_with_niche(
    page: PageFetchResult,
    keyword: str,
    domain: str,
    text_match_level: str,
    niche: str,
) -> PageClassification:
    """
    Niche-aware classification that layers domain rules on top of HTML analysis.

    When HTML is not loaded (fetch_ok=False):
      - Applies domain rule if domain is known → competitor_level from domain rule
      - Falls back to UNKNOWN only for truly unknown domains

    When HTML is loaded (fetch_ok=True):
      - HTML analysis is primary
      - Domain rule can upgrade (but never downgrade) competitor_level
      - final_competitor_level = max(html_level, domain_level)
    """
    from app.services.niche_profiles import classify_by_domain, merge_competitor_levels

    html_status = "OK" if page.fetch_ok else (page.error or "Не загружено")

    # ── HTML classification ────────────────────────────────────────────────
    html_cls = classify_page(page, keyword)

    # ── Domain classification ──────────────────────────────────────────────
    page_type_domain, domain_level, domain_rule_applied, domain_comment = classify_by_domain(
        domain=domain,
        text_match_level=text_match_level,
        niche=niche,
    )

    # ── Merge into final values ────────────────────────────────────────────
    if page.fetch_ok:
        # HTML is authoritative; domain can only upgrade
        final_competitor_level = merge_competitor_levels(
            html_cls.competitor_level, domain_level if domain_rule_applied else "UNKNOWN"
        )
        final_page_type = html_cls.page_type_html
        final_intent_coverage = html_cls.intent_coverage
        if domain_rule_applied and final_competitor_level != html_cls.competitor_level:
            classification_source = "html+domain"
            classification_comment = (
                f"{html_cls.explanation}. "
                f"Доменное правило повысило уровень: {html_cls.competitor_level}→{final_competitor_level}. "
                f"{domain_comment}"
            )
        else:
            classification_source = "html"
            classification_comment = html_cls.explanation
    else:
        # HTML not loaded — rely on domain rule
        if domain_rule_applied:
            final_competitor_level = domain_level
            final_page_type = page_type_domain or "UNKNOWN"
            final_intent_coverage = "PARTIAL" if text_match_level in ("STRONG", "NEAR") else "NONE"
            classification_source = "domain+serp"
            classification_comment = (
                f"HTML не загружен: {html_status}. "
                f"Применено доменное правило. {domain_comment}"
            )
        else:
            final_competitor_level = "UNKNOWN"
            final_page_type = "UNKNOWN"
            final_intent_coverage = "NONE"
            classification_source = "none"
            classification_comment = (
                f"HTML не загружен: {html_status}. "
                f"Домен '{domain}' не входит в список известных доменов ниши «{niche}»."
            )

    return PageClassification(
        page_type_html=html_cls.page_type_html,
        competitor_level=html_cls.competitor_level,
        intent_coverage=html_cls.intent_coverage,
        explanation=html_cls.explanation,
        page_type_domain=page_type_domain,
        domain_rule_applied=domain_rule_applied,
        html_status=html_status,
        final_page_type=final_page_type,
        final_competitor_level=final_competitor_level,
        final_intent_coverage=final_intent_coverage,
        classification_source=classification_source,
        classification_comment=classification_comment,
    )
