"""
Нишевые профили для классификации SERP.

Каждый профиль описывает список известных доменов с их типами страниц
и правила доменной fallback-классификации конкурентного уровня.
"""
from __future__ import annotations

from dataclasses import dataclass, field

NICHE_REAL_ESTATE = "real_estate"
NICHE_UNIVERSAL = "universal"

NICHE_NAMES_RU: dict[str, str] = {
    NICHE_REAL_ESTATE: "Недвижимость",
    NICHE_UNIVERSAL: "Универсальная",
}


@dataclass
class NicheProfile:
    id: str
    name_ru: str
    # domain → page_type_domain (bare domain, no www)
    domain_page_types: dict[str, str] = field(default_factory=dict)
    # domains guaranteed at minimum CLOSE competitor level
    min_close_domains: set[str] = field(default_factory=set)


# ---------------------------------------------------------------------------
# Real Estate profile
# ---------------------------------------------------------------------------

_RE_AGGREGATORS: dict[str, str] = {
    "cian.ru": "REAL_ESTATE_AGGREGATOR",
    "avito.ru": "CLASSIFIEDS",
    "realty.yandex.ru": "REAL_ESTATE_AGGREGATOR",
    "domclick.ru": "REAL_ESTATE_AGGREGATOR",
    "novostroy.ru": "REAL_ESTATE_AGGREGATOR",
    "novostroev.ru": "REAL_ESTATE_AGGREGATOR",
    "move.ru": "REAL_ESTATE_AGGREGATOR",
    "m2.ru": "REAL_ESTATE_AGGREGATOR",
    "bn.ru": "REAL_ESTATE_AGGREGATOR",
    "mirkvartir.ru": "REAL_ESTATE_AGGREGATOR",
    "n1.ru": "REAL_ESTATE_AGGREGATOR",
    "etagi.com": "REAL_ESTATE_AGGREGATOR",
    "domofond.ru": "REAL_ESTATE_AGGREGATOR",
    "kvartus.ru": "REAL_ESTATE_AGGREGATOR",
    "emls.ru": "REAL_ESTATE_AGGREGATOR",
    "restate.ru": "REAL_ESTATE_AGGREGATOR",
    "sob.ru": "REAL_ESTATE_AGGREGATOR",
    "avaho.ru": "REAL_ESTATE_AGGREGATOR",
    "vbr.ru": "REAL_ESTATE_AGGREGATOR",
    "novostroika.ru": "REAL_ESTATE_AGGREGATOR",
    "mskguru.ru": "REAL_ESTATE_AGGREGATOR",
    "gk-a101.ru": "REAL_ESTATE_AGGREGATOR",
}

_RE_DEVELOPERS: dict[str, str] = {
    "samolot.ru": "DEVELOPER_SITE",
    "pik.ru": "DEVELOPER_SITE",
    "donstroy.com": "DEVELOPER_SITE",
    "level.ru": "DEVELOPER_SITE",
    "mr-group.ru": "DEVELOPER_SITE",
    "ingrad.ru": "DEVELOPER_SITE",
    "afi-development.com": "DEVELOPER_SITE",
    "forma.ru": "DEVELOPER_SITE",
    "dogma.ru": "DEVELOPER_SITE",
    "brusnika.ru": "DEVELOPER_SITE",
    "a101.ru": "DEVELOPER_SITE",
    "setl-group.ru": "DEVELOPER_SITE",
    "lsr.ru": "DEVELOPER_SITE",
    "rbi.ru": "DEVELOPER_SITE",
    "granel.ru": "DEVELOPER_SITE",
    "pik-comfort.ru": "DEVELOPER_SITE",
    "zhkpik.ru": "DEVELOPER_SITE",
    "kz.ru": "DEVELOPER_SITE",
    "kortros.ru": "DEVELOPER_SITE",
    "kkpk.ru": "DEVELOPER_SITE",
    "novostroev.ru": "DEVELOPER_SITE",
}

_RE_BANKS: dict[str, str] = {
    "sberbank.ru": "BANK_MORTGAGE_PAGE",
    "vtb.ru": "BANK_MORTGAGE_PAGE",
    "alfabank.ru": "BANK_MORTGAGE_PAGE",
    "gazprombank.ru": "BANK_MORTGAGE_PAGE",
    "raiffeisen.ru": "BANK_MORTGAGE_PAGE",
    "rosbank.ru": "BANK_MORTGAGE_PAGE",
    "tinkoff.ru": "BANK_MORTGAGE_PAGE",
    "dom.rf": "BANK_MORTGAGE_PAGE",
    "sovcombank.ru": "BANK_MORTGAGE_PAGE",
    "rshb.ru": "BANK_MORTGAGE_PAGE",
    "open.ru": "BANK_MORTGAGE_PAGE",
    "psbank.ru": "BANK_MORTGAGE_PAGE",
}

REAL_ESTATE_PROFILE = NicheProfile(
    id=NICHE_REAL_ESTATE,
    name_ru="Недвижимость",
    domain_page_types={**_RE_AGGREGATORS, **_RE_DEVELOPERS, **_RE_BANKS},
    min_close_domains=set(_RE_AGGREGATORS.keys()) | set(_RE_DEVELOPERS.keys()),
)

UNIVERSAL_PROFILE = NicheProfile(
    id=NICHE_UNIVERSAL,
    name_ru="Универсальная",
    domain_page_types={},
    min_close_domains=set(),
)

PROFILES: dict[str, NicheProfile] = {
    NICHE_REAL_ESTATE: REAL_ESTATE_PROFILE,
    NICHE_UNIVERSAL: UNIVERSAL_PROFILE,
}


def get_profile(niche: str) -> NicheProfile:
    return PROFILES.get(niche, UNIVERSAL_PROFILE)


def _competitor_level_for_type(
    page_type_domain: str,
    is_strong_match: bool,
    in_min_close: bool,
) -> str:
    if page_type_domain in ("REAL_ESTATE_AGGREGATOR", "CLASSIFIEDS", "DEVELOPER_SITE"):
        return "DIRECT" if is_strong_match else "CLOSE"
    if page_type_domain == "BANK_MORTGAGE_PAGE":
        return "DIRECT" if is_strong_match else "INDIRECT"
    if page_type_domain in ("ARTICLE", "NEWS"):
        return "CLOSE" if is_strong_match else "INDIRECT"
    # Generic fallback
    if in_min_close:
        return "DIRECT" if is_strong_match else "CLOSE"
    return "CLOSE" if is_strong_match else "INDIRECT"


def classify_by_domain(
    domain: str,
    text_match_level: str,
    niche: str,
) -> tuple[str | None, str, bool, str]:
    """
    Domain-based classification (fallback or supplement).

    Returns:
        (page_type_domain, final_competitor_level, domain_rule_applied, comment)
        page_type_domain is None if no matching domain rule found.
    """
    profile = get_profile(niche)
    bare = domain.lower().removeprefix("www.")

    page_type_domain: str | None = None
    matched_domain: str = bare
    in_min_close = False

    # Exact match first
    if bare in profile.domain_page_types:
        page_type_domain = profile.domain_page_types[bare]
        matched_domain = bare
        in_min_close = bare in profile.min_close_domains
    else:
        # Subdomain match (e.g. mytishchi.cian.ru → cian.ru)
        for known_domain, ptype in profile.domain_page_types.items():
            if bare.endswith("." + known_domain):
                page_type_domain = ptype
                matched_domain = known_domain
                in_min_close = known_domain in profile.min_close_domains
                break

    if page_type_domain is None:
        return None, "UNKNOWN", False, ""

    is_strong_match = text_match_level in ("STRONG", "NEAR")
    final_level = _competitor_level_for_type(page_type_domain, is_strong_match, in_min_close)

    comment = (
        f"Доменное правило: {matched_domain} → {page_type_domain}. "
        f"SERP-совпадение: {text_match_level} → {final_level}."
    )
    return page_type_domain, final_level, True, comment


_LEVEL_RANK: dict[str, int] = {
    "NOT_COMPETITOR": 0,
    "INDIRECT": 1,
    "CLOSE": 2,
    "DIRECT": 3,
    "UNKNOWN": -1,
}


def merge_competitor_levels(html_level: str, domain_level: str) -> str:
    """Take the higher (stricter) competitor level from the two sources."""
    h = _LEVEL_RANK.get(html_level, -1)
    d = _LEVEL_RANK.get(domain_level, -1)
    if h >= d:
        return html_level
    return domain_level
