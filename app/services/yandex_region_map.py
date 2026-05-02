"""
Yandex region (lr) codes — maps human-readable location names to Yandex lr parameters.

Yandex search uses the `lr` query parameter to localise results.
Full reference: https://yandex.ru/dev/xml/doc/dg/reference/regions.html

Usage:
    from app.services.yandex_region_map import resolve_lr
    lr = resolve_lr("Moscow,Moscow,Russia")   # → 213
    lr = resolve_lr("Россия > Санкт-Петербург")  # → 2
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Primary mapping: lowercase English/Russian city/region tokens → lr code
# ---------------------------------------------------------------------------
_TOKEN_TO_LR: dict[str, int] = {
    # Russia federal + largest cities
    "russia": 225, "россия": 225, "рф": 225,
    # Moscow
    "moscow": 213, "москва": 213, "мск": 213,
    # Saint Petersburg
    "saint petersburg": 2, "st. petersburg": 2, "st petersburg": 2,
    "санкт-петербург": 2, "петербург": 2, "спб": 2,
    # Novosibirsk
    "novosibirsk": 65, "новосибирск": 65, "нск": 65,
    # Yekaterinburg
    "yekaterinburg": 54, "ekaterinburg": 54, "екатеринбург": 54,
    # Nizhny Novgorod
    "nizhny novgorod": 47, "nizhny": 47, "нижний новгород": 47, "нижний": 47,
    # Kazan
    "kazan": 43, "казань": 43,
    # Chelyabinsk
    "chelyabinsk": 74, "челябинск": 74,
    # Omsk
    "omsk": 66, "омск": 66,
    # Samara
    "samara": 63, "самара": 63,
    # Rostov-on-Don
    "rostov-on-don": 39, "rostov on don": 39, "ростов-на-дону": 39, "ростов": 39,
    # Ufa
    "ufa": 172, "уфа": 172,
    # Krasnodar
    "krasnodar": 35, "краснодар": 35,
    # Voronezh
    "voronezh": 193, "воронеж": 193,
    # Perm
    "perm": 50, "пермь": 50,
    # Volgograd
    "volgograd": 38, "волгоград": 38,
    # Krasnoyarsk
    "krasnoyarsk": 62, "красноярск": 62,
    # Saratov
    "saratov": 194, "саратов": 194,
    # Tyumen
    "tyumen": 55, "тюмень": 55,
    # Izhevsk
    "izhevsk": 44, "ижевск": 44,
    # Barnaul
    "barnaul": 197, "барнаул": 197,
    # Ulyanovsk
    "ulyanovsk": 195, "ульяновск": 195,
    # Vladivostok
    "vladivostok": 75, "владивосток": 75,
    # Irkutsk
    "irkutsk": 63, "иркутск": 63,
    # Habarovsk
    "khabarovsk": 76, "хабаровск": 76,
    # Yaroslavl
    "yaroslavl": 16, "ярославль": 16,
    # Orenburg
    "orenburg": 51, "оренбург": 51,
    # Tomsk
    "tomsk": 67, "томск": 67,
    # Kemerovo
    "kemerovo": 64, "кемерово": 64,
    # Novokuznetsk
    "novokuznetsk": 237, "новокузнецк": 237,
    # Astrakhan
    "astrakhan": 37, "астрахань": 37,
    # Ryazan
    "ryazan": 10, "рязань": 10,
    # Penza
    "penza": 49, "пенза": 49,
    # Lipetsk
    "lipetsk": 9, "липецк": 9,
    # Tula
    "tula": 15, "тула": 15,
    # Kirov
    "kirov": 46, "киров": 46,
    # Cheboksary
    "cheboksary": 45, "чебоксары": 45,
    # Kaliningrad
    "kaliningrad": 22, "калининград": 22,
    # Bryansk
    "bryansk": 191, "брянск": 191,
    # Ivanovo
    "ivanovo": 5, "иваново": 5,
    # Kursk
    "kursk": 8, "курск": 8,
    # Tver
    "tver": 14, "тверь": 14,
    # Stavropol
    "stavropol": 36, "ставрополь": 36,
    # Sochi
    "sochi": 239, "сочи": 239,
}

DEFAULT_LR = 225  # Russia


def resolve_lr(location_name: str) -> int:
    """
    Convert a location_name string (any format) to a Yandex lr code.

    Handles inputs like:
      - "Moscow,Moscow,Russia"
      - "Россия > Москва"
      - "Saint Petersburg,Saint Petersburg,Russia"
      - "Russia"
    """
    if not location_name:
        return DEFAULT_LR

    # Split on commas, ">" and normalize tokens
    raw_tokens = location_name.replace(">", ",").replace("—", ",").split(",")
    tokens = [t.strip().lower() for t in raw_tokens if t.strip()]

    # Try each token from most-specific (first) to least-specific
    for token in tokens:
        if token in _TOKEN_TO_LR:
            return _TOKEN_TO_LR[token]
        # Partial match: check if the token starts with a known key
        for key, lr in _TOKEN_TO_LR.items():
            if token.startswith(key) or key.startswith(token):
                return lr

    return DEFAULT_LR
