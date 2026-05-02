from __future__ import annotations

import logging

from app.models.schemas import (
    AdsMatchDetail,
    AdsOut,
    AnalyzeResultItem,
    DebugInfo,
    DeepStats,
    FetchStatusInfo,
    LocationOut,
    OrganicMatchDetail,
    OrganicOut,
    PageAnalysisDetail,
    ScoreOut,
    SerpMixInfo,
)
from app.services.classifier import (
    CLASS_SCORE_FLOOR,
    apply_deep_guardrails,
    competition_class,
    recommendation,
)
from app.services.geo_checker import check_geo_relevance
from app.services.intent_classifier import classify_intent
from app.services.matcher import coverage, level_by_coverage
from app.services.page_classifier import classify_page_with_niche
from app.services.page_fetcher import fetch_pages
from app.services.scorer import (
    ScoringCounters,
    TEXT_PRESSURE,
    adjust_weight_for_page_analysis,
    ads_item_score,
    compute_serp_mix,
    organic_item_score,
    total_score,
)
from app.services.text_processor import extract_significant_lemmas, lemmatize_tokens

logger = logging.getLogger(__name__)

DEEP_ANALYSIS_TOP_N = 10


async def build_keyword_report(
    keyword: str,
    serp_data: dict,
    country: str,
    region: str,
    city: str,
    geo_mode: str,
    location_name: str = "",
    deep_analysis: bool = True,
    niche: str = "universal",
) -> AnalyzeResultItem:
    is_fallback: bool = serp_data.get("is_fallback", False)
    source: str = serp_data.get("source", "unknown")
    fetch_debug: dict = serp_data.get("fetch_debug", {})
    fetch_failed: bool = serp_data.get("fetch_failed", False)

    key_lemmas = extract_significant_lemmas(keyword)
    counters = ScoringCounters()
    seo_score = 0.0
    ads_score = 0.0

    organic_items = serp_data.get("organic", [])
    total_organic = len(organic_items)

    organic_matches: list[OrganicMatchDetail] = []
    ads_matches: list[AdsMatchDetail] = []

    # ── Deep page analysis (опционально) ──────────────────────────────────
    page_analyses: dict[int, PageAnalysisDetail] = {}
    if deep_analysis and organic_items:
        top_items = organic_items[:DEEP_ANALYSIS_TOP_N]
        urls_to_fetch = [item.get("url", "") for item in top_items]

        # Pre-compute SERP text_match_level per item (needed for domain fallback)
        pre_title_levels: list[str] = []
        for item in top_items:
            t_lemmas = lemmatize_tokens(item.get("title", ""))
            t_cov = coverage(key_lemmas, t_lemmas)
            pre_title_levels.append(level_by_coverage(t_cov))

        try:
            fetch_results = await fetch_pages(urls_to_fetch)
            for idx, fr in enumerate(fetch_results):
                serp_item = top_items[idx]
                domain = serp_item.get("domain", "")
                text_match_level = pre_title_levels[idx] if idx < len(pre_title_levels) else "NONE"

                cls = classify_page_with_niche(
                    page=fr,
                    keyword=keyword,
                    domain=domain,
                    text_match_level=text_match_level,
                    niche=niche,
                )
                page_analyses[idx] = PageAnalysisDetail(
                    fetch_ok=fr.fetch_ok,
                    final_url=fr.final_url,
                    page_type_html=cls.page_type_html,
                    competitor_level=cls.competitor_level,
                    intent_coverage=cls.intent_coverage,
                    h1=fr.h1,
                    meta_description=fr.meta_description,
                    cta_signals=fr.cta_signals,
                    has_upload_form=fr.has_upload_form,
                    has_pricing=fr.has_pricing,
                    text_length=fr.text_length,
                    explanation=cls.explanation,
                    niche=niche,
                    page_type_domain=cls.page_type_domain,
                    domain_rule_applied=cls.domain_rule_applied,
                    html_status=cls.html_status,
                    final_page_type=cls.final_page_type,
                    final_competitor_level=cls.final_competitor_level,
                    final_intent_coverage=cls.final_intent_coverage,
                    classification_source=cls.classification_source,
                    classification_comment=cls.classification_comment,
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("[deep_analysis] fetch_pages failed for '%s': %s", keyword, exc)

    for idx, item in enumerate(organic_items):
        title = item.get("title", "")
        desc = item.get("description", "")
        domain = item.get("domain", "")
        url = item.get("url", "")

        title_lemmas = lemmatize_tokens(title)
        desc_lemmas = lemmatize_tokens(desc)

        title_cov = coverage(key_lemmas, title_lemmas)
        desc_cov = coverage(key_lemmas, desc_lemmas)
        title_level = level_by_coverage(title_cov)
        desc_level = level_by_coverage(desc_cov)

        # Layer 2 — intent / competitive type (по сниппету)
        intent_type, is_direct, comp_weight, intent_explanation = classify_intent(title, desc, domain)

        # Layer 2b — углублённый анализ страницы (если есть)
        page_detail = page_analyses.get(idx)
        if page_detail and page_detail.fetch_ok:
            adjusted_weight, adjust_note = adjust_weight_for_page_analysis(
                comp_weight, page_detail.competitor_level, page_detail.intent_coverage,
            )
            if adjust_note:
                intent_explanation += f" · {adjust_note}"
            comp_weight = adjusted_weight
            # Если ранее не считался прямым, но deep-анализ говорит DIRECT — корректируем.
            if page_detail.competitor_level == "DIRECT":
                is_direct = True

        # Layer 3 — geo relevance
        geo_rel, geo_mult, geo_explanation = check_geo_relevance(
            title, desc, domain, location_name, region
        )

        # Combined weight
        final_weight = round(comp_weight * geo_mult, 3)

        # Three-layer score
        item_seo = organic_item_score(title_level, desc_level, comp_weight, geo_mult)
        seo_score += item_seo

        # Update counters
        if title_level == "STRONG":
            counters.organic_strong += 1
        elif title_level == "NEAR":
            counters.organic_near += 1
        elif title_level == "PARTIAL":
            counters.organic_partial += 1

        if is_direct:
            counters.organic_commercial += 1

        # Weighted competition pressure
        counters.weighted_competition += final_weight * TEXT_PRESSURE.get(title_level, 0.0)

        organic_matches.append(OrganicMatchDetail(
            position=idx + 1,
            title=title,
            description=desc,
            url=url,
            title_coverage=round(title_cov, 3),
            title_level=title_level,
            desc_coverage=round(desc_cov, 3),
            desc_level=desc_level,
            intent_type=intent_type,
            is_direct_competitor=is_direct,
            competitive_weight=comp_weight,
            intent_explanation=intent_explanation,
            geo_relevance=geo_rel,
            geo_multiplier=geo_mult,
            geo_explanation=geo_explanation,
            final_weight=final_weight,
            seo_contribution=item_seo,
            page_analysis=page_detail,
        ))

    ads_density_bonus = 0.0
    for idx, ad in enumerate(serp_data.get("ads", [])):
        counters.ads_count += 1
        title = ad.get("title", "")
        desc = ad.get("description", "")
        domain = ad.get("domain", "")
        url = ad.get("url", "")

        title_lemmas = lemmatize_tokens(title)
        desc_lemmas = lemmatize_tokens(desc)

        title_cov = coverage(key_lemmas, title_lemmas)
        desc_cov = coverage(key_lemmas, desc_lemmas)
        title_level = level_by_coverage(title_cov)
        desc_level = level_by_coverage(desc_cov)

        intent_type, is_direct, comp_weight, intent_explanation = classify_intent(title, desc, domain)
        geo_rel, geo_mult, geo_explanation = check_geo_relevance(
            title, desc, domain, location_name, region
        )
        final_weight = round(comp_weight * geo_mult, 3)

        item_ads = ads_item_score(title_level, desc_level, comp_weight, geo_mult)
        ads_score += item_ads

        if title_level == "STRONG":
            counters.ads_strong += 1
        elif title_level == "NEAR":
            counters.ads_near += 1

        ads_matches.append(AdsMatchDetail(
            position=idx + 1,
            title=title,
            description=desc,
            url=url,
            title_coverage=round(title_cov, 3),
            title_level=title_level,
            desc_coverage=round(desc_cov, 3),
            desc_level=desc_level,
            intent_type=intent_type,
            is_direct_competitor=is_direct,
            competitive_weight=comp_weight,
            intent_explanation=intent_explanation,
            geo_relevance=geo_rel,
            geo_multiplier=geo_mult,
            geo_explanation=geo_explanation,
            final_weight=final_weight,
            ads_contribution=item_ads,
        ))

    ads_density_bonus = round(counters.ads_count * 0.5, 2)
    ads_score += ads_density_bonus
    weighted_competition = round(counters.weighted_competition, 2)

    # SERP mix — однородность типов страниц по органике
    serp_mix_label, serp_mix_breakdown, serp_mix_explanation = compute_serp_mix(
        [m.intent_type for m in organic_matches]
    )
    serp_mix_info = SerpMixInfo(
        label=serp_mix_label,
        breakdown=serp_mix_breakdown,
        explanation=serp_mix_explanation,
    )

    # ── Deep stats (aggregate from page_analysis, using final_competitor_level) ─
    _TOOL_LIKE = {"TOOL_SERVICE", "CONVERTER", "SAAS", "LANDING"}
    _ARTICLE_LIKE = {"ARTICLE", "REVIEW_LIST", "DOCS", "FORUM"}
    ds = DeepStats(total_results=total_organic)
    for m in organic_matches:
        pa = m.page_analysis
        if pa is None:
            continue
        if pa.fetch_ok:
            ds.html_loaded += 1
            pt = pa.page_type_html
            if pt in _TOOL_LIKE:
                ds.tool_like_count += 1
            elif pt in _ARTICLE_LIKE:
                ds.article_like_count += 1
        elif pa.domain_rule_applied:
            ds.domain_classified_count += 1
        else:
            ds.unloaded_count += 1

        # Use final_competitor_level (HTML + domain fallback) for counts
        fcl = pa.final_competitor_level
        fic = pa.final_intent_coverage
        if fcl == "DIRECT":
            ds.direct_count += 1
        elif fcl == "CLOSE":
            ds.close_count += 1
        elif fcl == "INDIRECT":
            ds.indirect_count += 1
        elif fcl == "NOT_COMPETITOR":
            ds.not_competitor_count += 1
        else:
            ds.unknown_count += 1

        if fic == "STRONG":
            ds.strong_intent_count += 1
        elif fic == "PARTIAL":
            ds.partial_intent_count += 1

    # ── Base class + guardrails ───────────────────────────────────────────────
    label = competition_class(weighted_competition)
    guardrail_reason = ""
    if deep_analysis and ds.html_loaded > 0:
        label, guardrail_reason = apply_deep_guardrails(
            current_class=label,
            direct_count=ds.direct_count,
            strong_intent_count=ds.strong_intent_count,
            tool_like_count=ds.tool_like_count,
            serp_mix_label=serp_mix_label,
            total_results=total_organic,
        )

    # ── Score alignment ───────────────────────────────────────────────────────
    total = total_score(seo_score, ads_score)
    floor = CLASS_SCORE_FLOOR.get(label, 0.0)
    if total < floor:
        total = round(floor, 2)

    # ── Recommendation ────────────────────────────────────────────────────────
    rec = recommendation(
        label,
        counters.organic_commercial,
        total_organic,
        serp_mix_label,
        direct_count=ds.direct_count,
        strong_intent_count=ds.strong_intent_count,
    )

    # ── analysis_status ───────────────────────────────────────────────────────
    if is_fallback:
        analysis_status = "mock_used"
    elif fetch_failed or total_organic == 0:
        analysis_status = "serp_error"
    elif ds.unloaded_count > 0 and ds.html_loaded == 0 and ds.domain_classified_count == 0:
        analysis_status = "partial_success"
    elif ds.unloaded_count > 0 or ds.domain_classified_count > 0:
        analysis_status = "success_with_html_errors"
    else:
        analysis_status = "success"

    logger.info(
        "[%s] ключ='%s' lemmas=%s commercial=%s/%s weighted_comp=%.2f class=%s "
        "seo=%.2f ads=%.2f total=%.2f mix=%s deep=%s direct=%d close=%d unknown=%d "
        "domain_cls=%d guardrail='%s' niche=%s status=%s",
        "MOCK" if is_fallback else "REAL",
        keyword,
        key_lemmas,
        counters.organic_commercial,
        total_organic,
        weighted_competition,
        label,
        seo_score,
        ads_score,
        total,
        serp_mix_label,
        deep_analysis,
        ds.direct_count,
        ds.close_count,
        ds.unknown_count,
        ds.domain_classified_count,
        guardrail_reason,
        niche,
        analysis_status,
    )

    fetch_status = FetchStatusInfo(
        source=source,
        success=fetch_debug.get("success", not fetch_failed),
        captcha=fetch_debug.get("captcha", False),
        blocked=fetch_debug.get("blocked", False),
        error=serp_data.get("fetch_error", ""),
        url_fetched=fetch_debug.get("url_fetched", ""),
        html_length=fetch_debug.get("html_length", 0),
        organic_found=fetch_debug.get("organic_found", len(organic_items)),
        ads_found=fetch_debug.get("ads_found", len(serp_data.get("ads", []))),
        attempts=fetch_debug.get("attempts", 0),
        proxy_used=fetch_debug.get("proxy_used", False),
        parse_strategy=fetch_debug.get("parse_strategy", ""),
    )

    return AnalyzeResultItem(
        ключ=keyword,
        ниша=niche,
        analysis_status=analysis_status,
        локация=LocationOut(страна=country, регион=region, город=city, режим=geo_mode),
        органика=OrganicOut(
            strong=counters.organic_strong,
            near=counters.organic_near,
            partial=counters.organic_partial,
            commercial=counters.organic_commercial,
        ),
        реклама=AdsOut(
            количество=counters.ads_count,
            strong=counters.ads_strong,
            near=counters.ads_near,
        ),
        оценка=ScoreOut(seo=round(seo_score, 2), ads=round(ads_score, 2), итог=total),
        класс=label,
        рекомендация=rec,
        отладка=DebugInfo(
            key_lemmas=key_lemmas,
            using_fallback=is_fallback,
            fetch_status=fetch_status,
            organic_matches=organic_matches,
            ads_matches=ads_matches,
            seo_score_raw=round(seo_score, 2),
            ads_score_raw=round(ads_score, 2),
            ads_density_bonus=ads_density_bonus,
            weighted_competition=weighted_competition,
            serp_mix=serp_mix_info,
            deep_analysis_used=deep_analysis,
            deep_stats=ds,
            classification_adjustments=guardrail_reason,
        ),
    )
