"""
Intent classifier for SERP results.

Eight page types — from direct commercial competitor down to irrelevant:

  AGGREGATOR      – агрегатор / каталог (avito, cian, маркетплейс…)       w=1.0  прямой конкурент
  DEVELOPER_CARD  – карточка ЖК / застройщика / объекта                   w=1.0  прямой конкурент
  TOOL_SERVICE    – онлайн-инструмент / SaaS / конвертер                  w=0.9  прямой конкурент
  COMMERCIAL      – общая коммерческая страница (купить, аренда, услуга)   w=0.9  прямой конкурент
  COMMERCIAL_INFO – коммерческо-информационный материал                    w=0.35 НЕ прямой
  INFORMATIONAL   – информационная статья / обзор / советы                 w=0.2  НЕ прямой
  GOVERNMENT      – государственный / справочный ресурс                    w=0.05 НЕ прямой
  IRRELEVANT      – нерелевантный / неопределённый                         w=0.05 НЕ прямой
"""
from __future__ import annotations

import re

COMPETITIVE_WEIGHT: dict[str, float] = {
    "AGGREGATOR": 1.0,
    "DEVELOPER_CARD": 1.0,
    "TOOL_SERVICE": 0.9,
    "COMMERCIAL": 0.9,
    "COMMERCIAL_INFO": 0.35,
    "INFORMATIONAL": 0.2,
    "GOVERNMENT": 0.05,
    "IRRELEVANT": 0.05,
}

IS_DIRECT_COMPETITOR: dict[str, bool] = {
    "AGGREGATOR": True,
    "DEVELOPER_CARD": True,
    "TOOL_SERVICE": True,
    "COMMERCIAL": True,
    "COMMERCIAL_INFO": False,
    "INFORMATIONAL": False,
    "GOVERNMENT": False,
    "IRRELEVANT": False,
}

INTENT_LABEL_RU: dict[str, str] = {
    "AGGREGATOR": "Агрегатор / каталог",
    "DEVELOPER_CARD": "Карточка объекта / застройщик",
    "TOOL_SERVICE": "Онлайн-инструмент / сервис",
    "COMMERCIAL": "Коммерческая страница",
    "COMMERCIAL_INFO": "Коммерческо-информационный",
    "INFORMATIONAL": "Информационная статья",
    "GOVERNMENT": "Государственный / справочный",
    "IRRELEVANT": "Нерелевантный результат",
}

# ── Domain lists ─────────────────────────────────────────────────────────────

_AGGREGATOR_DOMAINS: set[str] = {
    "avito.ru", "cian.ru", "domclick.ru",
    "realty.yandex.ru", "realty.mail.ru",
    "irr.ru", "youla.ru", "bazarestate.ru",
    "ozon.ru", "wildberries.ru", "lamoda.ru",
    "mvideo.ru", "eldorado.ru", "dns-shop.ru",
    "booking.com", "airbnb.com", "sutochno.ru", "ostrovok.ru",
    "auto.ru", "drom.ru", "am.ru",
    "hh.ru", "superjob.ru", "zarplata.ru",
    "delivery-club.ru", "eda.yandex.ru",
}

_GOVERNMENT_DOMAINS: set[str] = {
    "gosuslugi.ru", "mos.ru", "gov.ru", "pfr.gov.ru",
    "nalog.gov.ru", "rosreestr.gov.ru", "minstroyrf.gov.ru",
    "admtyumen.ru", "мфц.рф",
}

_INFORMATIONAL_DOMAINS: set[str] = {
    "dzen.ru", "zen.yandex.ru",
    "vc.ru", "habr.com", "pikabu.ru",
    "wikipedia.org", "ru.wikipedia.org", "wikihow.com",
    "lifehacker.ru", "the-village.ru", "adme.ru",
    "meduza.io", "lenta.ru", "ria.ru",
    "kommersant.ru", "rbc.ru", "forbes.ru",
    "gazeta.ru", "fontanka.ru", "kp.ru", "aif.ru",
    "pravda.ru", "vesti.ru",
}

# Известные онлайн-инструменты / SaaS / транскрибаторы / конвертеры
_TOOL_SERVICE_DOMAINS: set[str] = {
    "speechpad.ru", "speechtexter.com", "smodin.io",
    "otter.ai", "sonix.ai", "happyscribe.com",
    "amberscript.com", "rev.com", "trint.com",
    "vocalmatic.com", "audext.com", "transcribetube.com",
    "pdf2go.com", "convertio.co", "online-convert.com",
    "ilovepdf.com", "smallpdf.com", "cloudconvert.com",
    "canva.com", "figma.com", "remove.bg",
    "deepl.com", "translate.google.com",
    "chatgpt.com", "openai.com", "claude.ai",
    "gigachat.ru", "gpt-chatbot.ru",
}

# ── Token sets ────────────────────────────────────────────────────────────────

_AGGREGATOR_TOKENS: set[str] = {
    "каталог", "агрегатор", "маркетплейс",
    "объявления", "объявление",
    "база данных", "все предложения",
}

_DEVELOPER_TOKENS: set[str] = {
    "жк", "жилой комплекс", "жилого комплекса",
    "застройщик", "застройщика", "от застройщика",
    "новостройка", "новостройки", "квартал",
    "жилой район", "микрорайон",
}

_COMMERCIAL_TOKENS: set[str] = {
    "купить", "покупка", "приобрести",
    "продать", "продажа",
    "заказать", "заказ",
    "аренда", "арендовать", "снять", "сдать",
    "цена", "стоимость", "прайс", "тариф",
    "магазин", "интернет-магазин",
    "скидка", "акция", "распродажа",
    "доставка",
    "подбор", "подобрать", "выбрать",
    "услуга", "услуги",
}

# Глаголы / существительные, обозначающие онлайн-операцию над данными
_TOOL_ACTION_TOKENS: set[str] = {
    "конвертировать", "конвертер", "конвертация",
    "преобразовать", "преобразование",
    "транскрибировать", "транскрибация", "транскрипция",
    "распознать", "распознавание", "расшифровать", "расшифровка",
    "перевести", "переводчик", "переводить",
    "сгенерировать", "генератор", "генерация",
    "сжать", "сжатие", "обрезать", "обрезка",
    "редактор", "редактировать",
    "анализатор", "проверить", "проверка",
    "convert", "converter", "transcribe", "transcription",
    "recognize", "recognition", "translator", "translate",
    "generator", "editor", "checker",
}

# Признаки SaaS / онлайн-сервиса (часто без коммерческих токенов)
_TOOL_CONTEXT_TOKENS: set[str] = {
    "онлайн", "online",
    "бесплатно", "бесплатный", "бесплатная", "free",
    "сервис", "service", "saas",
    "инструмент", "tool",
    "программа", "приложение", "app",
    "нейросеть", "нейронка", "ai", "gpt", "ии",
    "загрузить", "загрузка", "upload",
    "попробовать", "try", "start",
    "веб", "web",
}

_INFORMATIONAL_TOKENS: set[str] = {
    "как", "почему", "зачем", "когда",
    "обзор", "рейтинг", "топ", "лучших", "лучшие",
    "виды", "типы", "история", "гайд", "руководство",
    "советы", "рекомендации", "инструкция",
    "интерьер", "дизайн", "декор", "стиль", "планировка",
    "льготы", "льгота", "пособие", "пособия",
    "субсидия", "субсидии", "маткапитал",
    "ипотека", "закон", "законодательство",
    "нормы", "правила", "право", "юридический",
    "многодетный", "многодетных",
    "новости", "статья", "публикация", "материал",
    "фото", "галерея", "видео", "подборка",
    "справка", "документ", "мфц",
    "аналитика", "исследование", "тренды",
    "отзыв", "отзывы", "форум",
}


def _root(domain: str) -> str:
    parts = domain.lower().lstrip("www.").split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else domain


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[а-яёa-z]+", text.lower()))


def _has_phrase(text: str, phrases: set[str]) -> bool:
    t = text.lower()
    return any(p in t for p in phrases)


def classify_intent(
    title: str,
    description: str,
    domain: str,
) -> tuple[str, bool, float, str]:
    """
    Returns (intent_type, is_direct_competitor, competitive_weight, explanation_ru).
    """
    full_host = domain.lower().lstrip("www.") if domain else ""
    root = _root(domain)
    combined = title + " " + description

    def _domain_hit(known: set[str]) -> str | None:
        # Match по полному хосту (cloud.yandex.ru) или по корневому домену (yandex.ru)
        if full_host in known:
            return full_host
        if root in known:
            return root
        return None

    # ── 1. Domain-level hard rules ─────────────────────────────────────────
    if root in _GOVERNMENT_DOMAINS or root.endswith(".gov.ru"):
        return _result("GOVERNMENT", f"Государственный или официальный справочный ресурс ({root})")

    if hit := _domain_hit(_INFORMATIONAL_DOMAINS):
        return _result("INFORMATIONAL", f"Известный медийный/информационный ресурс: {hit}")

    if hit := _domain_hit(_AGGREGATOR_DOMAINS):
        return _result("AGGREGATOR", f"Известная коммерческая площадка-агрегатор: {hit}")

    if hit := _domain_hit(_TOOL_SERVICE_DOMAINS):
        return _result("TOOL_SERVICE", f"Известный онлайн-инструмент / SaaS: {hit}")

    # ── 2. Title/description phrase detection ─────────────────────────────
    # Check developer/card signals first (most specific)
    if _has_phrase(combined, _DEVELOPER_TOKENS):
        sample = [t for t in _DEVELOPER_TOKENS if t in combined.lower()][:2]
        return _result("DEVELOPER_CARD", f"Карточка объекта/застройщика — маркеры: «{', '.join(sample)}»")

    # Check aggregator tokens
    if _has_phrase(combined, _AGGREGATOR_TOKENS):
        sample = [t for t in _AGGREGATOR_TOKENS if t in combined.lower()][:2]
        return _result("AGGREGATOR", f"Агрегатор/каталог — маркеры: «{', '.join(sample)}»")

    # ── 2b. TOOL/SERVICE detection ────────────────────────────────────────
    tok_all = _tokens(combined)
    title_tok_set = _tokens(title)
    action_matches = tok_all & _TOOL_ACTION_TOKENS
    context_matches = tok_all & _TOOL_CONTEXT_TOKENS
    # Сильный сигнал: action-токен (конвертировать/распознать/...) + любой контекст-токен,
    # либо action-токен в самом заголовке.
    is_tool = (
        (action_matches and context_matches)
        or (title_tok_set & _TOOL_ACTION_TOKENS)
        or len(context_matches) >= 3
    )
    if is_tool:
        sample = sorted(action_matches | context_matches)[:3]
        return _result("TOOL_SERVICE", f"Онлайн-инструмент / сервис — маркеры: «{', '.join(sample)}»")

    # ── 3. Token-level scoring ────────────────────────────────────────────
    tok = _tokens(combined)
    title_tok = _tokens(title)

    comm_matches = tok & _COMMERCIAL_TOKENS
    info_matches = tok & _INFORMATIONAL_TOKENS

    comm_score = len(comm_matches) + 2 * len(title_tok & _COMMERCIAL_TOKENS)
    info_score = len(info_matches) + 2 * len(title_tok & _INFORMATIONAL_TOKENS)

    diff = comm_score - info_score

    if comm_score == 0 and info_score == 0:
        return _result("IRRELEVANT", "Тип страницы не определён — учитывается с минимальным весом")

    if diff >= 3:
        sample = sorted(comm_matches)[:3]
        return _result("COMMERCIAL", f"Коммерческая страница — маркеры: «{', '.join(sample)}»")

    if diff <= -3:
        sample = sorted(info_matches)[:3]
        return _result("INFORMATIONAL", f"Информационный материал — маркеры: «{', '.join(sample)}»")

    # Close diff → mixed; lean toward the winner
    if diff > 0:
        comm_s = sorted(comm_matches)[:2]
        info_s = sorted(info_matches)[:2]
        explanation = "Коммерческо-информационный контент"
        if comm_s:
            explanation += f" — коммерческие маркеры: «{', '.join(comm_s)}»"
        if info_s:
            explanation += f"; информационные: «{', '.join(info_s)}»"
        return _result("COMMERCIAL_INFO", explanation)

    info_s = sorted(info_matches)[:2]
    comm_s = sorted(comm_matches)[:2]
    explanation = "Информационный материал с коммерческими элементами"
    if info_s:
        explanation += f" — информационные маркеры: «{', '.join(info_s)}»"
    if comm_s:
        explanation += f"; коммерческие: «{', '.join(comm_s)}»"
    return _result("INFORMATIONAL", explanation)


def _result(intent: str, explanation: str) -> tuple[str, bool, float, str]:
    return (
        intent,
        IS_DIRECT_COMPETITOR[intent],
        COMPETITIVE_WEIGHT[intent],
        explanation,
    )
