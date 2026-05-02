"""
Geo-relevance checker for SERP results.

Given the target region and a result's title/description/domain, determines
how geo-relevant the result is to the search region.

  RELEVANT    – mentions the target region           (multiplier 1.0)
  NEUTRAL     – no city/region signals found         (multiplier 0.7)
  IRRELEVANT  – mentions a DIFFERENT city/region     (multiplier 0.3)
"""
from __future__ import annotations

import re

GEO_MULTIPLIER: dict[str, float] = {
    "RELEVANT": 1.0,
    "NEUTRAL": 0.7,
    "IRRELEVANT": 0.3,
}

GEO_LABEL_RU: dict[str, str] = {
    "RELEVANT": "Гео-релевантен",
    "NEUTRAL": "Гео-нейтрален",
    "IRRELEVANT": "Гео-нерелевантен",
}

# English location_name prefix → set of lowercase Russian city tokens
_LOC_NAME_MAP: dict[str, set[str]] = {
    "moscow": {"москва", "московск", "подмосковь"},
    "saint petersburg": {"петербург", "санкт-петербург", "питер", "ленинград"},
    "novosibirsk": {"новосибирск"},
    "yekaterinburg": {"екатеринбург"},
    "kazan": {"казань"},
    "nizhny novgorod": {"нижний новгород", "нижнем новгороде"},
    "omsk": {"омск"},
    "samara": {"самара"},
    "chelyabinsk": {"челябинск"},
    "rostov-on-don": {"ростов-на-дону", "ростов"},
    "ufa": {"уфа"},
    "krasnodar": {"краснодар"},
    "sochi": {"сочи"},
    "voronezh": {"воронеж"},
    "perm": {"пермь"},
    "volgograd": {"волгоград"},
    "krasnoyarsk": {"красноярск"},
    "tyumen": {"тюмень"},
    "barnaul": {"барнаул"},
    "vladivostok": {"владивосток"},
    "irkutsk": {"иркутск"},
    "yaroslavl": {"ярославль"},
    "khabarovsk": {"хабаровск"},
}

# All known Russian city tokens → display name (for alien-city detection)
_ALL_CITY_TOKENS: dict[str, str] = {
    "москва": "Москва", "московск": "Москва", "подмосковь": "Московская область",
    "петербург": "Санкт-Петербург", "санкт-петербург": "Санкт-Петербург",
    "питер": "Санкт-Петербург", "ленинград": "Санкт-Петербург",
    "новосибирск": "Новосибирск",
    "екатеринбург": "Екатеринбург",
    "казань": "Казань",
    "нижний новгород": "Нижний Новгород",
    "нижнем новгороде": "Нижний Новгород",
    "омск": "Омск",
    "самара": "Самара",
    "челябинск": "Челябинск",
    "ростов": "Ростов-на-Дону",
    "ростов-на-дону": "Ростов-на-Дону",
    "уфа": "Уфа",
    "краснодар": "Краснодар",
    "сочи": "Сочи",
    "новороссийск": "Новороссийск",
    "мариуполь": "Мариуполь",
    "тюмень": "Тюмень",
    "барнаул": "Барнаул",
    "ярославль": "Ярославль",
    "иркутск": "Иркутск",
    "хабаровск": "Хабаровск",
    "воронеж": "Воронеж",
    "красноярск": "Красноярск",
    "владивосток": "Владивосток",
    "саратов": "Саратов",
    "тольятти": "Тольятти",
    "ульяновск": "Ульяновск",
    "пермь": "Пермь",
    "волгоград": "Волгоград",
    "рязань": "Рязань",
    "астрахань": "Астрахань",
    "кемерово": "Кемерово",
    "новокузнецк": "Новокузнецк",
    "иваново": "Иваново",
    "брянск": "Брянск",
    "липецк": "Липецк",
    "тула": "Тула",
    "ставрополь": "Ставрополь",
    "курск": "Курск",
    "смоленск": "Смоленск",
    "пенза": "Пенза",
    "чебоксары": "Чебоксары",
    "белгород": "Белгород",
    "оренбург": "Оренбург",
    "калуга": "Калуга",
    "тверь": "Тверь",
    "калининград": "Калининград",
    "томск": "Томск",
    "магнитогорск": "Магнитогорск",
    "набережные челны": "Набережные Челны",
}


def _target_tokens(location_name: str, region_display: str) -> set[str]:
    """
    Derive the set of lowercase Russian city tokens that represent the target region.
    First tries the API location_name (English), then falls back to the display path.
    """
    loc = location_name.lower()
    for key, tokens in _LOC_NAME_MAP.items():
        if key in loc:
            return tokens

    # Fall back to display path: "Россия > Москва" or "Россия > Северо-Западный ФО > Санкт-Петербург"
    parts = [p.strip().lower() for p in re.split(r"[>\\/]", region_display)]
    for part in reversed(parts):
        for token in _ALL_CITY_TOKENS:
            if token in part:
                return {token}

    return set()


def check_geo_relevance(
    title: str,
    description: str,
    domain: str,
    location_name: str,
    region_display: str,
) -> tuple[str, float, str]:
    """
    Returns (geo_relevance, geo_multiplier, explanation_ru).
    """
    target = _target_tokens(location_name, region_display)

    if not target:
        return (
            "NEUTRAL",
            GEO_MULTIPLIER["NEUTRAL"],
            "Регион анализа не определён точно — гео-вес нейтральный",
        )

    combined = (title + " " + description + " " + domain).lower()

    # Check if target city is mentioned
    for t in target:
        if t in combined:
            city_name = _ALL_CITY_TOKENS.get(t, t.capitalize())
            return (
                "RELEVANT",
                GEO_MULTIPLIER["RELEVANT"],
                f"Упоминает целевой регион: {city_name}",
            )

    # Check for mentions of OTHER cities
    alien_cities: list[str] = []
    for token, city_name in _ALL_CITY_TOKENS.items():
        if token in target:
            continue
        if token in combined:
            alien_cities.append(city_name)
            if len(alien_cities) >= 2:
                break

    if alien_cities:
        unique = list(dict.fromkeys(alien_cities))[:2]
        return (
            "IRRELEVANT",
            GEO_MULTIPLIER["IRRELEVANT"],
            f"Упоминает другой регион: {', '.join(unique)} — вес снижен",
        )

    return (
        "NEUTRAL",
        GEO_MULTIPLIER["NEUTRAL"],
        "Без явных гео-маркеров — вероятно, федеральный охват",
    )
