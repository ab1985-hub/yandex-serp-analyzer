from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field, field_validator


class PageAnalysisDetail(BaseModel):
    """Результат углублённого анализа реальной страницы (deep mode)."""
    fetch_ok: bool = False
    final_url: str = ""
    page_type_html: str = "UNKNOWN"      # TOOL_SERVICE / SAAS / CONVERTER / LANDING / ARTICLE / REVIEW_LIST / DOCS / MARKETPLACE / FORUM / IRRELEVANT
    competitor_level: str = "UNKNOWN"    # DIRECT / CLOSE / INDIRECT / NOT_COMPETITOR (HTML-based)
    intent_coverage: str = "NONE"        # STRONG / PARTIAL / WEAK / NONE (HTML-based)
    h1: str = ""
    meta_description: str = ""
    cta_signals: list[str] = []
    has_upload_form: bool = False
    has_pricing: bool = False
    text_length: int = 0
    explanation: str = ""
    # Niche-aware extended fields
    niche: str = "universal"
    page_type_domain: str | None = None
    domain_rule_applied: bool = False
    html_status: str = ""
    final_page_type: str = "UNKNOWN"
    final_competitor_level: str = "UNKNOWN"
    final_intent_coverage: str = "NONE"
    classification_source: str = ""
    classification_comment: str = ""


class SerpMixInfo(BaseModel):
    """Оценка однородности типов страниц в выдаче."""
    label: str = "MIXED"                 # HOMOGENEOUS / MIXED / STRONGLY_MIXED
    breakdown: dict[str, int] = {}
    explanation: str = ""


class OrganicMatchDetail(BaseModel):
    position: int
    title: str
    description: str
    url: str
    title_coverage: float
    title_level: str
    desc_coverage: float
    desc_level: str
    intent_type: str
    is_direct_competitor: bool
    competitive_weight: float
    intent_explanation: str
    geo_relevance: str
    geo_multiplier: float
    geo_explanation: str
    final_weight: float
    seo_contribution: float
    page_analysis: PageAnalysisDetail | None = None


class AdsMatchDetail(BaseModel):
    position: int
    title: str
    description: str
    url: str
    title_coverage: float
    title_level: str
    desc_coverage: float
    desc_level: str
    intent_type: str
    is_direct_competitor: bool
    competitive_weight: float
    intent_explanation: str
    geo_relevance: str
    geo_multiplier: float
    geo_explanation: str
    final_weight: float
    ads_contribution: float


class FetchStatusInfo(BaseModel):
    source: str          # "yandex_direct" | "mock"
    success: bool
    captcha: bool = False
    blocked: bool = False
    error: str = ""
    url_fetched: str = ""
    html_length: int = 0
    organic_found: int = 0
    ads_found: int = 0
    attempts: int = 0
    proxy_used: bool = False
    parse_strategy: str = ""


class DeepStats(BaseModel):
    """Агрегированная статистика из углублённого анализа страниц top-10."""
    total_results: int = 0
    html_loaded: int = 0
    direct_count: int = 0
    close_count: int = 0
    indirect_count: int = 0
    not_competitor_count: int = 0
    unknown_count: int = 0
    strong_intent_count: int = 0
    partial_intent_count: int = 0
    tool_like_count: int = 0
    article_like_count: int = 0
    unloaded_count: int = 0
    domain_classified_count: int = 0


class DebugInfo(BaseModel):
    key_lemmas: list[str]
    using_fallback: bool
    fetch_status: FetchStatusInfo
    organic_matches: list[OrganicMatchDetail]
    ads_matches: list[AdsMatchDetail]
    seo_score_raw: float
    ads_score_raw: float
    ads_density_bonus: float
    weighted_competition: float
    serp_mix: SerpMixInfo = Field(default_factory=SerpMixInfo)
    deep_analysis_used: bool = False
    deep_stats: DeepStats = Field(default_factory=DeepStats)
    classification_adjustments: str = ""


class AnalyzeRequest(BaseModel):
    search_engine: Literal["yandex"] = "yandex"
    country: str = Field(..., description="Страна")
    region: str = Field(..., description="Отображаемый путь региона")
    city: str = Field(default="", description="Город")
    location_name: str = Field(default="", description="Название локации для SERP-запроса")
    geo_mode: Literal["strict", "region_only"] = "strict"
    depth: int = 10
    keywords: list[str] = Field(default_factory=list)
    deep_analysis: bool = False

    @field_validator("depth")
    @classmethod
    def validate_depth(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("Глубина анализа должна быть больше 0")
        return min(value, 10)

    @field_validator("keywords")
    @classmethod
    def validate_keywords(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if item and item.strip()]
        if not cleaned:
            raise ValueError("Нужно передать хотя бы один ключ")
        return cleaned


class LocationOut(BaseModel):
    страна: str
    регион: str
    город: str
    режим: str


class OrganicOut(BaseModel):
    strong: int
    near: int
    partial: int
    commercial: int


class AdsOut(BaseModel):
    количество: int
    strong: int
    near: int


class ScoreOut(BaseModel):
    seo: float
    ads: float
    итог: float


class AnalyzeResultItem(BaseModel):
    ключ: str
    частотность: int | None = None
    ниша: str = "universal"
    analysis_status: str = "success"
    локация: LocationOut
    органика: OrganicOut
    реклама: AdsOut
    оценка: ScoreOut
    класс: str
    рекомендация: str
    отладка: DebugInfo


class AnalyzeResponse(BaseModel):
    результаты: list[AnalyzeResultItem]
