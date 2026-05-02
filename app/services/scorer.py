from __future__ import annotations

from dataclasses import dataclass
from app.services.matcher import MatchLevel


@dataclass
class ScoringCounters:
    organic_strong: int = 0
    organic_near: int = 0
    organic_partial: int = 0
    organic_commercial: int = 0
    ads_count: int = 0
    ads_strong: int = 0
    ads_near: int = 0
    weighted_competition: float = 0.0


# Base text-match scores (multiplied by intent weight × geo multiplier)
SEO_TITLE = {"STRONG": 6.0, "NEAR": 3.0, "PARTIAL": 1.0, "NONE": 0.0}
SEO_DESC = {"STRONG": 2.0, "NEAR": 1.0, "PARTIAL": 0.5, "NONE": 0.0}
ADS_TITLE = {"STRONG": 3.0, "NEAR": 1.5, "PARTIAL": 0.5, "NONE": 0.0}
ADS_DESC = {"STRONG": 1.0, "NEAR": 0.5, "PARTIAL": 0.2, "NONE": 0.0}

# Contribution of each text level to the weighted_competition pressure score
TEXT_PRESSURE = {"STRONG": 2.0, "NEAR": 1.0, "PARTIAL": 0.3, "NONE": 0.0}


def organic_item_score(
    title_level: MatchLevel,
    desc_level: MatchLevel,
    competitive_weight: float,
    geo_multiplier: float,
) -> float:
    """Three-layer score: text-match × intent weight × geo multiplier."""
    base = SEO_TITLE[title_level] + SEO_DESC[desc_level]
    return round(base * competitive_weight * geo_multiplier, 3)


def ads_item_score(
    title_level: MatchLevel,
    desc_level: MatchLevel,
    competitive_weight: float,
    geo_multiplier: float,
) -> float:
    base = ADS_TITLE[title_level] + ADS_DESC[desc_level]
    return round(base * competitive_weight * geo_multiplier, 3)


def total_score(seo_score: float, ads_score: float) -> float:
    return round((seo_score * 0.8) + (ads_score * 0.2), 2)


# ── SERP mix ──────────────────────────────────────────────────────────────────

SERP_MIX_LABEL_RU: dict[str, str] = {
    "HOMOGENEOUS": "Однородная выдача",
    "MIXED": "Смешанная выдача",
    "STRONGLY_MIXED": "Сильно смешанная выдача",
}


def compute_serp_mix(intent_types: list[str], top_n: int = 10) -> tuple[str, dict[str, int], str]:
    """
    Оценивает однородность типов страниц в выдаче.

    HOMOGENEOUS    — ≥60% одного типа в топ-N
    STRONGLY_MIXED — ≥3 разных типа в топ-N
    MIXED          — иначе

    По умолчанию считается по топ-10 органики (top_n=10).
    """
    # Считаем именно по top_n позициям выдачи
    top_slice = intent_types[:top_n]
    if not top_slice:
        return "MIXED", {}, "Нет данных по выдаче"

    breakdown: dict[str, int] = {}
    for t in top_slice:
        breakdown[t] = breakdown.get(t, 0) + 1

    total = len(top_slice)
    top_type, top_count = max(breakdown.items(), key=lambda kv: kv[1])
    distinct_types = len(breakdown)

    if top_count / total >= 0.6:
        label = "HOMOGENEOUS"
        explanation = (
            f"≥60% результатов одного типа ({top_type}: {top_count}/{total}) — "
            "выдача однородная, заходить сложнее"
        )
    elif distinct_types >= 3:
        label = "STRONGLY_MIXED"
        explanation = (
            f"В топе {distinct_types} разных типа страниц — Яндекс ещё не определился "
            "с интентом, есть шанс занять нишу"
        )
    else:
        label = "MIXED"
        explanation = (
            f"Смешанная выдача ({distinct_types} типов, лидер {top_type}: "
            f"{top_count}/{total}) — стандартная конкурентная ситуация"
        )

    return label, breakdown, explanation


# ── Page-analysis weight adjustment ──────────────────────────────────────────

def adjust_weight_for_page_analysis(
    base_weight: float,
    competitor_level: str,
    intent_coverage: str,
) -> tuple[float, str]:
    """
    Корректирует competitive_weight на основе углублённого анализа страницы.

    Усиливает вес для прямых конкурентов с сильным закрытием интента,
    ослабляет для не-конкурентов / страниц без покрытия интента.
    Не вызывается при deep_analysis=False — поведение совместимо с базовым SERP-layer.
    """
    if competitor_level == "UNKNOWN":
        return base_weight, ""

    new_weight = base_weight
    note = ""
    if competitor_level == "DIRECT" and intent_coverage == "STRONG":
        new_weight = max(base_weight, 0.95)
        if new_weight > base_weight:
            note = f"deep: прямой конкурент + сильный интент → вес поднят с {base_weight:.2f} до {new_weight:.2f}"
    elif competitor_level == "NOT_COMPETITOR" or intent_coverage == "NONE":
        new_weight = min(base_weight, 0.1)
        if new_weight < base_weight:
            note = f"deep: не конкурент / нулевой интент → вес снижен с {base_weight:.2f} до {new_weight:.2f}"
    elif competitor_level == "DIRECT" and intent_coverage == "PARTIAL":
        new_weight = max(base_weight, 0.85)
        if new_weight > base_weight:
            note = f"deep: прямой конкурент + частичный интент → вес поднят до {new_weight:.2f}"
    elif competitor_level == "CLOSE" and intent_coverage in ("STRONG", "PARTIAL"):
        new_weight = max(base_weight, 0.7)
        if new_weight > base_weight:
            note = f"deep: близкий конкурент → вес поднят до {new_weight:.2f}"
    elif competitor_level == "INDIRECT" and intent_coverage in ("WEAK", "NONE"):
        new_weight = min(base_weight, 0.25)
        if new_weight < base_weight:
            note = f"deep: непрямой конкурент со слабым интентом → вес снижен до {new_weight:.2f}"

    return round(new_weight, 3), note
