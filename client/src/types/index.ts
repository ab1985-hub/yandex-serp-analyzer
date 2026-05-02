export type GeoMode = 'strict' | 'region_only'
export type AppMode = 'search' | 'wordstat' | 'combined'

export interface KeywordItem {
  keyword: string
  frequency: number | null
}

export interface RegionNode {
  id: number
  name: string
  parentId?: number
  children?: RegionNode[]
}

export interface PageAnalysisDetail {
  fetch_ok: boolean
  final_url: string
  page_type_html: string
  competitor_level: string
  intent_coverage: string
  h1: string
  meta_description: string
  cta_signals: string[]
  has_upload_form: boolean
  has_pricing: boolean
  text_length: number
  explanation: string
  // Niche-aware extended fields
  niche?: string
  page_type_domain?: string | null
  domain_rule_applied?: boolean
  html_status?: string
  final_page_type?: string
  final_competitor_level?: string
  final_intent_coverage?: string
  classification_source?: string
  classification_comment?: string
}

export interface SerpMixInfo {
  label: string
  breakdown: Record<string, number>
  explanation: string
}

export interface OrganicMatchDetail {
  position: number
  title: string
  description: string
  url: string
  title_coverage: number
  title_level: string
  desc_coverage: number
  desc_level: string
  intent_type: string
  is_direct_competitor: boolean
  competitive_weight: number
  intent_explanation: string
  geo_relevance: string
  geo_multiplier: number
  geo_explanation: string
  final_weight: number
  seo_contribution: number
  page_analysis?: PageAnalysisDetail | null
}

export interface AdsMatchDetail {
  position: number
  title: string
  description: string
  url: string
  title_coverage: number
  title_level: string
  desc_coverage: number
  desc_level: string
  intent_type: string
  is_direct_competitor: boolean
  competitive_weight: number
  intent_explanation: string
  geo_relevance: string
  geo_multiplier: number
  geo_explanation: string
  final_weight: number
  ads_contribution: number
}

export interface FetchStatusInfo {
  source: string
  success: boolean
  captcha: boolean
  blocked: boolean
  error: string
  url_fetched: string
  html_length: number
  organic_found: number
  ads_found: number
  attempts: number
  proxy_used: boolean
  parse_strategy: string
}

export interface DeepStats {
  total_results: number
  html_loaded: number
  direct_count: number
  close_count: number
  indirect_count: number
  not_competitor_count: number
  unknown_count: number
  strong_intent_count: number
  partial_intent_count: number
  tool_like_count: number
  article_like_count: number
  unloaded_count: number
  domain_classified_count: number
}

export interface DebugInfo {
  key_lemmas: string[]
  using_fallback: boolean
  fetch_status: FetchStatusInfo
  organic_matches: OrganicMatchDetail[]
  ads_matches: AdsMatchDetail[]
  seo_score_raw: number
  ads_score_raw: number
  ads_density_bonus: number
  weighted_competition: number
  serp_mix?: SerpMixInfo | null
  deep_analysis_used?: boolean
  deep_stats?: DeepStats | null
  classification_adjustments?: string
}

export interface AnalyzeResult {
  ключ: string
  частотность?: number | null
  ниша?: string
  analysis_status?: string
  локация: {
    страна: string
    регион: string
    город: string
    режим: string
  }
  органика: {
    strong: number
    near: number
    partial: number
    commercial: number
  }
  реклама: {
    количество: number
    strong: number
    near: number
  }
  оценка: {
    seo: number
    ads: number
    итог: number
  }
  класс: 'A' | 'B' | 'C' | 'D'
  рекомендация: string
  отладка: DebugInfo
}

export interface AnalyzeResponse {
  результаты: AnalyzeResult[]
}

export interface WordstatKeyword {
  keyword: string
  frequency: number
}
