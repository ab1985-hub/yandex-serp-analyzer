"""
Адаптер маппинга регионов для Yandex Search API и Wordstat API.

Yandex Search API использует числовой region (lr-код),
Wordstat API использует числовой regionId (тот же формат).

Функция resolve_region_id() принимает любой идентификатор региона
(строку-название, числовой id, или стандартные псевдонимы) и возвращает int.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Базовая карта часто используемых регионов (расширяется через GetRegionsTree)
_FALLBACK_MAP: dict[str, int] = {
    # Россия
    "russia": 225,
    "россия": 225,

    # Москва и МО
    "moscow": 213,
    "москва": 213,
    "москва и московская область": 1,
    "moscow and moscow region": 1,

    # Санкт-Петербург
    "saint petersburg": 2,
    "санкт-петербург": 2,
    "спб": 2,
    "st. petersburg": 2,

    # Прочие крупные города
    "novosibirsk": 65,
    "новосибирск": 65,
    "yekaterinburg": 54,
    "екатеринбург": 54,
    "kazan": 43,
    "казань": 43,
    "nizhny novgorod": 47,
    "нижний новгород": 47,
    "chelyabinsk": 56,
    "челябинск": 56,
    "samara": 51,
    "самара": 51,
    "ufa": 172,
    "уфа": 172,
    "rostov-on-don": 39,
    "ростов-на-дону": 39,
    "krasnoyarsk": 62,
    "красноярск": 62,
    "perm": 50,
    "пермь": 50,
    "voronezh": 193,
    "воронеж": 193,
    "volgograd": 38,
    "волгоград": 38,
    "krasnodar": 35,
    "краснодар": 35,
    "saratov": 194,
    "саратов": 194,
    "tyumen": 55,
    "тюмень": 55,
    "omsk": 66,
    "омск": 66,
    "tolyatti": 242,
    "тольятти": 242,
    "barnaul": 197,
    "барнаул": 197,
    "irkutsk": 63,
    "иркутск": 63,
    "vladivostok": 75,
    "владивосток": 75,
    "khabarovsk": 76,
    "хабаровск": 76,
    "yaroslavl": 16,
    "ярославль": 16,
    "makhachkala": 28,
    "махачкала": 28,
    "tomsk": 67,
    "томск": 67,
}

# Кэш дерева регионов (заполняется при первом обращении к GetRegionsTree)
_regions_cache: dict[str, int] = {}


def resolve_region_id(name_or_id: str | int, default: int = 213) -> int:
    """
    Преобразует название или id региона в числовой lr-код.
    Приоритет: числовой id → кэш GetRegionsTree → fallback map → default (Москва).
    """
    if isinstance(name_or_id, int):
        return name_or_id

    text = str(name_or_id).strip()

    # Уже числовое значение в виде строки
    if text.isdigit():
        return int(text)

    key = text.lower()

    # Кэш дерева (если уже загружен)
    if key in _regions_cache:
        return _regions_cache[key]

    # Fallback map
    if key in _FALLBACK_MAP:
        return _FALLBACK_MAP[key]

    # Попытка найти частичное совпадение в fallback
    for map_key, map_id in _FALLBACK_MAP.items():
        if map_key in key or key in map_key:
            logger.debug("[region] частичное совпадение '%s' → '%s' (%d)", key, map_key, map_id)
            return map_id

    logger.warning("[region] не найден регион '%s', используем default=%d", text, default)
    return default


def populate_regions_cache(regions_tree: list[dict]) -> None:
    """
    Заполняет кэш регионов из дерева GetRegionsTree.
    Вызывается один раз при старте или первом обращении.
    """
    def walk(node: dict) -> None:
        name = (node.get("name") or "").strip().lower()
        region_id = node.get("id") or 0
        if name and region_id:
            _regions_cache[name] = region_id
        for child in node.get("children") or []:
            walk(child)

    for root_node in regions_tree:
        walk(root_node)

    logger.info("[region_cache] загружено %d регионов из дерева", len(_regions_cache))


def get_cached_regions() -> dict[str, int]:
    return dict(_regions_cache)
