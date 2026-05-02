import React, { useMemo, useState } from 'react'
import type { AnalyzeResult, OrganicMatchDetail, AdsMatchDetail, SerpMixInfo, WordstatKeyword, AppMode } from '../types'
import { FetchStatusBadge } from './FetchStatusBadge'
import { exportXlsx, exportRichJson, exportChatGPTZip } from '../utils/exportHelpers'

interface Props {
  rows: AnalyzeResult[]
  mode?: AppMode
  wordstatRows?: WordstatKeyword[]
  regionName?: string
}

type SortField = 'ключ' | 'итог' | 'класс' | 'seo' | 'ads'

// ─────────────────────────────────────────────────────────────
// Russian label & colour maps
// ─────────────────────────────────────────────────────────────

const LEVEL_LABEL_RU: Record<string, string> = {
  STRONG: 'Полное совпадение',
  NEAR: 'Близкое совпадение',
  PARTIAL: 'Частичное совпадение',
  NONE: 'Нет совпадения',
}

const LEVEL_COLOR: Record<string, string> = {
  STRONG: '#16a34a',
  NEAR: '#ca8a04',
  PARTIAL: '#ea580c',
  NONE: '#94a3b8',
}

const INTENT_LABEL_RU: Record<string, string> = {
  AGGREGATOR: 'Агрегатор / каталог',
  DEVELOPER_CARD: 'Карточка объекта / застройщик',
  COMMERCIAL: 'Коммерческая страница',
  COMMERCIAL_INFO: 'Коммерческо-информационный',
  INFORMATIONAL: 'Информационная статья',
  GOVERNMENT: 'Государственный / справочный',
  IRRELEVANT: 'Нерелевантный результат',
}

const INTENT_COLOR: Record<string, string> = {
  AGGREGATOR: '#0369a1',
  DEVELOPER_CARD: '#16a34a',
  COMMERCIAL: '#15803d',
  COMMERCIAL_INFO: '#b45309',
  INFORMATIONAL: '#6366f1',
  GOVERNMENT: '#94a3b8',
  IRRELEVANT: '#cbd5e1',
}

const GEO_LABEL_RU: Record<string, string> = {
  RELEVANT: 'Гео-релевантен',
  NEUTRAL: 'Гео-нейтрален',
  IRRELEVANT: 'Гео-нерелевантен',
}

const GEO_COLOR: Record<string, string> = {
  RELEVANT: '#16a34a',
  NEUTRAL: '#ca8a04',
  IRRELEVANT: '#dc2626',
}

// Deep page analysis (HTML) labels
const PAGE_TYPE_LABEL_RU: Record<string, string> = {
  TOOL_SERVICE: 'Онлайн-инструмент',
  SAAS: 'SaaS-сервис',
  CONVERTER: 'Конвертер',
  LANDING: 'Лендинг',
  ARTICLE: 'Статья',
  REVIEW_LIST: 'Подборка / обзор',
  DOCS: 'Документация',
  MARKETPLACE: 'Маркетплейс',
  FORUM: 'Форум',
  UNKNOWN: 'Не определён',
}

const PAGE_TYPE_COLOR: Record<string, string> = {
  TOOL_SERVICE: '#15803d',
  SAAS: '#15803d',
  CONVERTER: '#15803d',
  LANDING: '#0369a1',
  ARTICLE: '#6366f1',
  REVIEW_LIST: '#7c3aed',
  DOCS: '#94a3b8',
  MARKETPLACE: '#0369a1',
  FORUM: '#94a3b8',
  UNKNOWN: '#cbd5e1',
}

const COMPETITOR_LABEL_RU: Record<string, string> = {
  DIRECT: 'Прямой',
  CLOSE: 'Близкий',
  INDIRECT: 'Непрямой',
  NOT_COMPETITOR: 'Не конкурент',
  NONE: 'Не конкурент',
  UNKNOWN: 'Не определено',
}

const COMPETITOR_COLOR: Record<string, string> = {
  DIRECT: '#dc2626',
  CLOSE: '#b45309',
  INDIRECT: '#ca8a04',
  NOT_COMPETITOR: '#94a3b8',
  NONE: '#94a3b8',
  UNKNOWN: '#cbd5e1',
}

const INTENT_COVERAGE_LABEL_RU: Record<string, string> = {
  STRONG: 'Сильно закрывает',
  PARTIAL: 'Частично закрывает',
  WEAK: 'Слабо закрывает',
  NONE: 'Не закрывает',
}

const INTENT_COVERAGE_COLOR: Record<string, string> = {
  STRONG: '#16a34a',
  PARTIAL: '#ca8a04',
  WEAK: '#ea580c',
  NONE: '#94a3b8',
}

const SERP_MIX_LABEL_RU: Record<string, string> = {
  HOMOGENEOUS: 'Однородная выдача',
  MIXED: 'Смешанная выдача',
  STRONGLY_MIXED: 'Сильно смешанная',
}

// Per UI spec: HOMOGENEOUS — green, MIXED — yellow, STRONGLY_MIXED — blue
const SERP_MIX_COLOR: Record<string, string> = {
  HOMOGENEOUS: '#16a34a',
  MIXED: '#ca8a04',
  STRONGLY_MIXED: '#0369a1',
}

const SERP_MIX_HINT_RU: Record<string, string> = {
  HOMOGENEOUS: 'Яндекс уже выбрал тип страниц для этого запроса — выдача однородная, конкуренция сфокусирована.',
  MIXED: 'В выдаче несколько типов страниц — стандартная конкурентная ситуация.',
  STRONGLY_MIXED: 'Яндекс ещё не определился с интентом — есть шанс занять нишу.',
}

// ─────────────────────────────────────────────────────────────
// Shared cell styles
// ─────────────────────────────────────────────────────────────

const thS: React.CSSProperties = {
  border: '1px solid #e2e8f0',
  padding: '5px 8px',
  textAlign: 'left',
  fontWeight: 600,
  whiteSpace: 'nowrap',
  background: '#f1f5f9',
  fontSize: 12,
}

const tdS: React.CSSProperties = {
  border: '1px solid #e2e8f0',
  padding: '5px 8px',
  verticalAlign: 'top',
  fontSize: 12,
}

// ─────────────────────────────────────────────────────────────
// Badge atoms
// ─────────────────────────────────────────────────────────────

function Badge({ text, bg, color = '#fff' }: { text: string; bg: string; color?: string }) {
  return (
    <span style={{
      display: 'inline-block',
      padding: '2px 8px',
      borderRadius: 10,
      fontSize: 11,
      fontWeight: 600,
      color,
      background: bg,
      whiteSpace: 'nowrap',
    }}>
      {text}
    </span>
  )
}

function LevelBadge({ level }: { level: string }) {
  return <Badge text={LEVEL_LABEL_RU[level] ?? level} bg={LEVEL_COLOR[level] ?? '#94a3b8'} />
}

function IntentBadge({ intent }: { intent: string }) {
  return <Badge text={INTENT_LABEL_RU[intent] ?? intent} bg={INTENT_COLOR[intent] ?? '#94a3b8'} />
}

function GeoBadge({ geo }: { geo: string }) {
  return <Badge text={GEO_LABEL_RU[geo] ?? geo} bg={GEO_COLOR[geo] ?? '#94a3b8'} />
}

const NICHE_PAGE_TYPE_LABEL: Record<string, string> = {
  REAL_ESTATE_AGGREGATOR: 'Агрегатор недвижимости',
  DEVELOPER_SITE: 'Сайт застройщика',
  RESIDENTIAL_COMPLEX_PAGE: 'Страница ЖК',
  AGENCY_SITE: 'Агентство',
  BANK_MORTGAGE_PAGE: 'Банк/ипотека',
  CLASSIFIEDS: 'Объявления',
  MAP_SERVICE: 'Карты/гео',
  ARTICLE: 'Статья',
  NEWS: 'Новости',
  IRRELEVANT: 'Нерелевантно',
  UNKNOWN: 'Не определён',
}

const SOURCE_LABEL: Record<string, string> = {
  'html': 'HTML',
  'html+domain': 'HTML+домен',
  'domain+serp': 'Домен+SERP',
  'serp': 'SERP',
  'none': 'Нет данных',
}

function CompetitorCell({ m }: { m: OrganicMatchDetail }) {
  if (m.page_analysis) {
    const pa = m.page_analysis
    // Use final_competitor_level (niche-aware) if available
    const finalLv = pa.final_competitor_level && pa.final_competitor_level !== 'UNKNOWN'
      ? pa.final_competitor_level
      : (pa.fetch_ok ? pa.competitor_level : null)

    if (finalLv && finalLv !== 'UNKNOWN') {
      const domainNote = pa.domain_rule_applied
        ? ` (${SOURCE_LABEL[pa.classification_source ?? ''] ?? pa.classification_source})`
        : ''
      const title = pa.classification_comment || pa.explanation
      return (
        <span title={title}>
          <Badge
            text={(COMPETITOR_LABEL_RU[finalLv] ?? finalLv) + domainNote}
            bg={COMPETITOR_COLOR[finalLv] ?? '#94a3b8'}
          />
        </span>
      )
    }

    if (pa.domain_rule_applied) {
      const lv = pa.final_competitor_level || 'UNKNOWN'
      return (
        <span title={pa.classification_comment || ''}>
          <Badge
            text={(COMPETITOR_LABEL_RU[lv] ?? lv) + ' (домен)'}
            bg={COMPETITOR_COLOR[lv] ?? '#94a3b8'}
          />
        </span>
      )
    }

    if (!pa.fetch_ok) {
      return (
        <span style={{ fontSize: 11, color: '#94a3b8' }} title={pa.classification_comment || pa.explanation}>
          Не загружено
        </span>
      )
    }

    const lv = pa.competitor_level
    return (
      <Badge
        text={COMPETITOR_LABEL_RU[lv] ?? lv}
        bg={COMPETITOR_COLOR[lv] ?? '#94a3b8'}
      />
    )
  }
  if (m.is_direct_competitor) {
    return <Badge text="Прямой" bg="#dc2626" />
  }
  return <span style={{ fontSize: 11, color: '#cbd5e1' }}>—</span>
}

function WeightBar({ weight }: { weight: number }) {
  const pct = Math.round(Math.min(weight, 1) * 100)
  const color = weight >= 0.85 ? '#16a34a' : weight >= 0.4 ? '#ca8a04' : weight >= 0.15 ? '#6366f1' : '#94a3b8'
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 5, minWidth: 80 }}>
      <div style={{ flex: 1, height: 6, background: '#e2e8f0', borderRadius: 3, overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: 3 }} />
      </div>
      <span style={{ fontSize: 11, color: '#475569', whiteSpace: 'nowrap' }}>{pct}%</span>
    </div>
  )
}

function UrlLink({ url }: { url: string }) {
  if (!url) return <span style={{ color: '#94a3b8', fontSize: 11 }}>—</span>
  let display = url
  try {
    const u = new URL(url)
    display = u.hostname + (u.pathname !== '/' ? u.pathname : '')
    if (display.length > 45) display = display.slice(0, 44) + '…'
  } catch {
    if (display.length > 45) display = display.slice(0, 44) + '…'
  }
  return (
    <a href={url} target="_blank" rel="noopener noreferrer" title={url} style={{
      color: '#0369a1',
      textDecoration: 'underline',
      fontSize: 11,
      wordBreak: 'break-all',
    }}>
      {display}
    </a>
  )
}

// ─────────────────────────────────────────────────────────────
// Debug tables
// ─────────────────────────────────────────────────────────────

function OrganicDebugTable({ matches, deepAnalysisUsed }: { matches: OrganicMatchDetail[]; deepAnalysisUsed: boolean }) {
  // Extra Тип HTML + Интент columns shown only when deep analysis was used and data is present
  const showDeepCols = deepAnalysisUsed && matches.some(m => m.page_analysis)
  // Without deep: 9 cols. With deep: 11 cols.
  const minW = showDeepCols ? 1000 : 760
  return (
    <div style={{ marginBottom: 20 }}>
      <div style={{ fontWeight: 700, marginBottom: 8, fontSize: 13, color: '#0f172a' }}>
        Органическая выдача — три слоя анализа{showDeepCols ? ' + углублённый анализ страниц (top-10)' : ''}
      </div>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', tableLayout: 'fixed', minWidth: minW }}>
          <colgroup>
            <col style={{ width: 28 }} />
            <col style={{ width: showDeepCols ? '18%' : '23%' }} />
            <col style={{ width: showDeepCols ? '11%' : '14%' }} />
            <col style={{ width: showDeepCols ? '12%' : '16%' }} />
            <col style={{ width: showDeepCols ? '12%' : '15%' }} />
            {showDeepCols && <col style={{ width: '10%' }} />}
            {showDeepCols && <col style={{ width: '10%' }} />}
            <col style={{ width: showDeepCols ? '9%' : '11%' }} />
            <col style={{ width: showDeepCols ? '9%' : '12%' }} />
            <col style={{ width: 80 }} />
            <col style={{ width: 44 }} />
          </colgroup>
          <thead>
            <tr>
              <th style={thS}>#</th>
              <th style={thS}>Заголовок и описание</th>
              <th style={thS}>Страница</th>
              <th style={thS}>Слой 1: текст</th>
              <th style={thS}>Слой 2: тип</th>
              {showDeepCols && <th style={thS} title="Тип страницы по реальному HTML">Тип (HTML)</th>}
              {showDeepCols && <th style={thS} title="Насколько страница закрывает интент пользователя">Интент</th>}
              <th style={thS} title="Уровень конкурента (HTML-анализ если доступен, иначе по сниппету)">Конкурент</th>
              <th style={thS}>Слой 3: гео</th>
              <th style={thS}>Итог. вес</th>
              <th style={{ ...thS, textAlign: 'center' }}>Вклад</th>
            </tr>
          </thead>
          <tbody>
            {matches.map((m) => (
              <tr key={m.position} style={{ borderBottom: '1px solid #e2e8f0' }}>
                <td style={tdS}>{m.position}</td>
                <td style={{ ...tdS, overflow: 'hidden' }}>
                  <div style={{ fontWeight: 500, lineHeight: 1.3, marginBottom: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={m.title}>
                    {m.title}
                  </div>
                  {m.description && (
                    <div style={{ color: '#64748b', fontSize: 10, lineHeight: 1.3, overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' }}>
                      {m.description}
                    </div>
                  )}
                </td>
                <td style={{ ...tdS, overflow: 'hidden' }}>
                  <UrlLink url={m.url} />
                </td>
                <td style={tdS}>
                  <div style={{ marginBottom: 2 }}>
                    <span style={{ color: '#64748b', fontSize: 10 }}>Загол.: </span>
                    <LevelBadge level={m.title_level} />
                  </div>
                  <div>
                    <span style={{ color: '#64748b', fontSize: 10 }}>Описание: </span>
                    <LevelBadge level={m.desc_level} />
                  </div>
                </td>
                <td style={tdS}>
                  <IntentBadge intent={m.intent_type} />
                  <div style={{ fontSize: 10, color: '#64748b', marginTop: 2, lineHeight: 1.3 }}>
                    {m.intent_explanation}
                  </div>
                </td>
                {showDeepCols && (
                  <td style={tdS}>
                    {m.page_analysis ? (() => {
                      const pa = m.page_analysis
                      // Show final_page_type (could be HTML or domain-classified)
                      const fp = pa.final_page_type || (pa.fetch_ok ? pa.page_type_html : null)
                      const isNicheType = fp && NICHE_PAGE_TYPE_LABEL[fp]
                      const label = isNicheType
                        ? NICHE_PAGE_TYPE_LABEL[fp!]
                        : (fp ? (PAGE_TYPE_LABEL_RU[fp] ?? fp) : null)
                      const bg = pa.fetch_ok
                        ? (PAGE_TYPE_COLOR[pa.page_type_html] ?? '#94a3b8')
                        : (pa.domain_rule_applied ? '#7c3aed' : '#94a3b8')
                      return label ? (
                        <>
                          <Badge text={label} bg={bg} />
                          {pa.domain_rule_applied && (
                            <div style={{ fontSize: 9, color: '#7c3aed', marginTop: 2 }}>
                              домен
                            </div>
                          )}
                          {pa.fetch_ok && pa.h1 && (
                            <div style={{ fontSize: 10, color: '#64748b', marginTop: 2, lineHeight: 1.3, overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' }} title={pa.h1}>
                              H1: {pa.h1}
                            </div>
                          )}
                        </>
                      ) : (
                        <span style={{ fontSize: 11, color: '#94a3b8' }} title={pa.classification_comment || pa.explanation}>
                          {pa.domain_rule_applied ? 'домен' : 'Не загружено'}
                        </span>
                      )
                    })() : (
                      <span style={{ fontSize: 11, color: '#cbd5e1' }}>—</span>
                    )}
                  </td>
                )}
                {showDeepCols && (
                  <td style={tdS}>
                    {m.page_analysis ? (() => {
                      const pa = m.page_analysis
                      const fi = pa.final_intent_coverage || (pa.fetch_ok ? pa.intent_coverage : null)
                      return fi && fi !== 'NONE' ? (
                        <Badge
                          text={INTENT_COVERAGE_LABEL_RU[fi] ?? fi}
                          bg={INTENT_COVERAGE_COLOR[fi] ?? '#94a3b8'}
                        />
                      ) : (
                        <span style={{ fontSize: 11, color: '#94a3b8' }}>
                          {pa.fetch_ok || pa.domain_rule_applied ? '—' : 'Не загружено'}
                        </span>
                      )
                    })() : (
                      <span style={{ fontSize: 11, color: '#cbd5e1' }}>—</span>
                    )}
                  </td>
                )}
                <td style={tdS}>
                  <CompetitorCell m={m} />
                </td>
                <td style={tdS}>
                  <GeoBadge geo={m.geo_relevance} />
                  <div style={{ fontSize: 10, color: '#64748b', marginTop: 2, lineHeight: 1.3 }}>
                    {m.geo_explanation}
                  </div>
                </td>
                <td style={tdS}>
                  <WeightBar weight={m.final_weight} />
                  <div style={{ fontSize: 10, color: '#64748b', marginTop: 2 }}>
                    {m.competitive_weight} × {m.geo_multiplier}
                  </div>
                </td>
                <td style={{ ...tdS, fontWeight: 700, textAlign: 'center', color: m.seo_contribution > 0 ? '#0f172a' : '#94a3b8' }}>
                  {m.seo_contribution > 0 ? `+${m.seo_contribution}` : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function AdsDebugTable({ matches }: { matches: AdsMatchDetail[] }) {
  if (!matches.length) {
    return <div style={{ marginBottom: 16, color: '#94a3b8', fontSize: 13 }}>Рекламные объявления не обнаружены</div>
  }
  return (
    <div style={{ marginBottom: 20 }}>
      <div style={{ fontWeight: 700, marginBottom: 8, fontSize: 13, color: '#0f172a' }}>
        Рекламная выдача
      </div>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', tableLayout: 'fixed', minWidth: 720 }}>
          <colgroup>
            <col style={{ width: 28 }} />
            <col style={{ width: '22%' }} />
            <col style={{ width: '14%' }} />
            <col style={{ width: '16%' }} />
            <col style={{ width: '17%' }} />
            <col style={{ width: 72 }} />
            <col style={{ width: '13%' }} />
            <col style={{ width: 90 }} />
            <col style={{ width: 44 }} />
          </colgroup>
          <thead>
            <tr>
              <th style={thS}>#</th>
              <th style={thS}>Заголовок и описание</th>
              <th style={thS}>Страница</th>
              <th style={thS}>Слой 1: текст</th>
              <th style={thS}>Тип страницы</th>
              <th style={thS} title="Оценка конкурентности по сниппету объявления">Конкурент</th>
              <th style={thS}>Гео</th>
              <th style={thS}>Итог. вес</th>
              <th style={{ ...thS, textAlign: 'center' }}>Вклад</th>
            </tr>
          </thead>
          <tbody>
            {matches.map((m) => (
              <tr key={m.position} style={{ borderBottom: '1px solid #e2e8f0' }}>
                <td style={tdS}>{m.position}</td>
                <td style={{ ...tdS, overflow: 'hidden' }}>
                  <div style={{ fontWeight: 500, lineHeight: 1.3, marginBottom: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={m.title}>
                    {m.title}
                  </div>
                  {m.description && (
                    <div style={{ color: '#64748b', fontSize: 10, lineHeight: 1.3, overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' }}>
                      {m.description}
                    </div>
                  )}
                </td>
                <td style={{ ...tdS, overflow: 'hidden' }}>
                  <UrlLink url={m.url} />
                </td>
                <td style={tdS}>
                  <div style={{ marginBottom: 2 }}>
                    <span style={{ color: '#64748b', fontSize: 10 }}>Загол.: </span>
                    <LevelBadge level={m.title_level} />
                  </div>
                  <div>
                    <span style={{ color: '#64748b', fontSize: 10 }}>Описание: </span>
                    <LevelBadge level={m.desc_level} />
                  </div>
                </td>
                <td style={tdS}>
                  <IntentBadge intent={m.intent_type} />
                  <div style={{ fontSize: 10, color: '#64748b', marginTop: 2, lineHeight: 1.3 }}>
                    {m.intent_explanation}
                  </div>
                </td>
                <td style={tdS}>
                  {m.is_direct_competitor
                    ? <Badge text="Прямой" bg="#dc2626" />
                    : <span style={{ fontSize: 11, color: '#cbd5e1' }}>—</span>}
                </td>
                <td style={tdS}>
                  <GeoBadge geo={m.geo_relevance} />
                </td>
                <td style={tdS}>
                  <WeightBar weight={m.final_weight} />
                  <div style={{ fontSize: 10, color: '#64748b', marginTop: 2 }}>
                    {m.competitive_weight} × {m.geo_multiplier}
                  </div>
                </td>
                <td style={{ ...tdS, fontWeight: 700, textAlign: 'center', color: m.ads_contribution > 0 ? '#0f172a' : '#94a3b8' }}>
                  {m.ads_contribution > 0 ? `+${m.ads_contribution}` : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────
// Score breakdown + legend
// ─────────────────────────────────────────────────────────────

function ScoreBreakdown({ row }: { row: AnalyzeResult }) {
  const d = row.отладка
  return (
    <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
      <div style={{
        flex: '1 1 360px',
        background: '#fff',
        border: '1px solid #e2e8f0',
        borderRadius: 8,
        padding: '12px 16px',
        fontSize: 13,
      }}>
        <div style={{ fontWeight: 700, marginBottom: 10 }}>Разбивка оценок</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '5px 16px' }}>
          <span style={{ color: '#64748b' }}>SEO score (органика):</span>
          <span><strong>{d.seo_score_raw}</strong> = Σ (текст × тип × гео) по каждому результату</span>

          <span style={{ color: '#64748b' }}>Ads score (реклама):</span>
          <span>
            <strong>{(d.ads_score_raw - d.ads_density_bonus).toFixed(2)}</strong> (совп.) +{' '}
            <strong>{d.ads_density_bonus}</strong> (плотность × {row.реклама.количество} объявл.) ={' '}
            <strong>{d.ads_score_raw}</strong>
          </span>

          <span style={{ color: '#64748b' }}>Итоговый score:</span>
          <span>
            {d.seo_score_raw} × 0.8 + {d.ads_score_raw} × 0.2 = <strong>{row.оценка.итог}</strong>
          </span>

          <span style={{ color: '#64748b' }}>Давление конкуренции:</span>
          <span>
            <strong>{d.weighted_competition}</strong> (взвешенный) → класс <strong>{row.класс}</strong>
          </span>

          <span style={{ color: '#64748b' }}>Прямых конкурентов:</span>
          <span>
            <strong>{row.органика.commercial}</strong> из {d.organic_matches.length} органических
          </span>
        </div>
      </div>

      <div style={{
        flex: '1 1 300px',
        background: '#fff',
        border: '1px solid #e2e8f0',
        borderRadius: 8,
        padding: '12px 16px',
        fontSize: 12,
      }}>
        <div style={{ fontWeight: 700, marginBottom: 8, fontSize: 13 }}>Вес по типу страницы</div>
        {[
          ['AGGREGATOR', 'Прямой — 100%'],
          ['DEVELOPER_CARD', 'Прямой — 100%'],
          ['COMMERCIAL', 'Прямой — 90%'],
          ['COMMERCIAL_INFO', 'Не прямой — 35%'],
          ['INFORMATIONAL', 'Не прямой — 20%'],
          ['GOVERNMENT', 'Не прямой — 5%'],
          ['IRRELEVANT', 'Не прямой — 5%'],
        ].map(([k, desc]) => (
          <div key={k} style={{ display: 'flex', gap: 6, alignItems: 'flex-start', marginBottom: 4 }}>
            <IntentBadge intent={k} />
            <span style={{ color: '#475569', lineHeight: 1.4 }}>{desc}</span>
          </div>
        ))}
        <div style={{ marginTop: 10, borderTop: '1px solid #e2e8f0', paddingTop: 8, fontWeight: 700, marginBottom: 4, fontSize: 13 }}>
          Гео-множитель
        </div>
        {[
          ['RELEVANT', '× 1.0 — целевой регион'],
          ['NEUTRAL', '× 0.7 — федеральный охват'],
          ['IRRELEVANT', '× 0.3 — другой регион'],
        ].map(([k, desc]) => (
          <div key={k} style={{ display: 'flex', gap: 6, alignItems: 'center', marginBottom: 3 }}>
            <GeoBadge geo={k} />
            <span style={{ color: '#475569' }}>{desc}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────
// Per-row expandable debug panel
// ─────────────────────────────────────────────────────────────

function SerpMixBadge({ mix }: { mix: SerpMixInfo }) {
  const label = SERP_MIX_LABEL_RU[mix.label] ?? mix.label
  const color = SERP_MIX_COLOR[mix.label] ?? '#94a3b8'
  const hint = SERP_MIX_HINT_RU[mix.label] ?? mix.explanation
  return (
    <span
      title={`${mix.explanation}\n\n${hint}`}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        padding: '3px 10px',
        borderRadius: 10,
        fontSize: 12,
        fontWeight: 600,
        color: '#fff',
        background: color,
        cursor: 'help',
      }}
    >
      SERP: {label}
    </span>
  )
}

function DebugPanel({ row }: { row: AnalyzeResult }) {
  const d = row.отладка
  return (
    <td colSpan={17} style={{ padding: '16px 20px', background: '#f8fafc', borderTop: '2px solid #cbd5e1' }}>
      <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 14, flexWrap: 'wrap' }}>
        <div style={{ fontWeight: 700, fontSize: 15 }}>Детали анализа: «{row.ключ}»</div>
        {d.serp_mix && <SerpMixBadge mix={d.serp_mix} />}
        {d.deep_analysis_used && (
          <span style={{
            display: 'inline-block',
            padding: '2px 10px',
            borderRadius: 10,
            fontSize: 11,
            fontWeight: 600,
            background: '#dbeafe',
            color: '#1e40af',
            border: '1px solid #93c5fd',
          }} title="Топ-10 страниц проанализированы по реальному HTML">
            🔍 Углублённый анализ (top-10)
          </span>
        )}
        {d.using_fallback && (
          <span style={{
            display: 'inline-block',
            padding: '2px 10px',
            borderRadius: 10,
            fontSize: 11,
            fontWeight: 700,
            background: '#fef3c7',
            color: '#92400e',
            border: '1px solid #fbbf24',
          }}>
            ⚠ Мок-данные (прямой съём не удался)
          </span>
        )}
        {row.ниша && (
          <span style={{
            display: 'inline-block',
            padding: '2px 10px',
            borderRadius: 10,
            fontSize: 11,
            fontWeight: 600,
            background: '#f0f9ff',
            color: '#0369a1',
            border: '1px solid #bae6fd',
          }}>
            {row.ниша === 'real_estate' ? '🏠 Недвижимость' : '🌐 Универсальная'}
          </span>
        )}
        {row.analysis_status && row.analysis_status !== 'success' && (
          <span style={{
            display: 'inline-block',
            padding: '2px 10px',
            borderRadius: 10,
            fontSize: 11,
            fontWeight: 600,
            background: row.analysis_status === 'mock_used' ? '#fef3c7'
              : row.analysis_status === 'serp_error' ? '#fee2e2'
              : '#f0fdf4',
            color: row.analysis_status === 'mock_used' ? '#92400e'
              : row.analysis_status === 'serp_error' ? '#991b1b'
              : '#15803d',
            border: `1px solid ${row.analysis_status === 'serp_error' ? '#fca5a5' : '#86efac'}`,
          }}>
            {row.analysis_status === 'mock_used' ? '⚠ Тестовые данные'
              : row.analysis_status === 'serp_error' ? '✗ SERP не получен'
              : row.analysis_status === 'partial_success' ? 'Частичный анализ'
              : row.analysis_status === 'success_with_html_errors' ? '⚡ HTML частично (домен)'
              : row.analysis_status}
          </span>
        )}
      </div>
      {d.serp_mix && (
        <div style={{ fontSize: 12, color: '#475569', marginBottom: 12, lineHeight: 1.4 }}>
          {d.serp_mix.explanation}
        </div>
      )}

      {/* ── Deep stats + guardrail ─────────────────────────────────── */}
      {d.deep_stats && d.deep_stats.total_results > 0 && (
        <div style={{
          marginBottom: 12,
          padding: '10px 14px',
          background: '#f1f5f9',
          border: '1px solid #cbd5e1',
          borderRadius: 8,
          fontSize: 12,
        }}>
          <div style={{ fontWeight: 700, marginBottom: 6, fontSize: 13 }}>Deep-анализ (top-{d.deep_stats.total_results})</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px 18px' }}>
            <span>
              HTML: <strong>{d.deep_stats.html_loaded}</strong>/{d.deep_stats.total_results}
              {(d.deep_stats.domain_classified_count ?? 0) > 0 && (
                <span style={{ color: '#7c3aed' }}> · домен: {d.deep_stats.domain_classified_count}</span>
              )}
              {d.deep_stats.unloaded_count > 0 && <span style={{ color: '#94a3b8' }}> · не загружено: {d.deep_stats.unloaded_count}</span>}
            </span>
            <span>Прямой: <strong style={{ color: '#dc2626' }}>{d.deep_stats.direct_count}</strong></span>
            <span>Близкий: <strong style={{ color: '#ea580c' }}>{d.deep_stats.close_count}</strong></span>
            <span>Непрямой: <strong>{d.deep_stats.indirect_count}</strong></span>
            <span>Не конкурент: <strong style={{ color: '#16a34a' }}>{d.deep_stats.not_competitor_count}</strong></span>
            {(d.deep_stats.unknown_count ?? 0) > 0 && (
              <span>Неизвестно: <strong style={{ color: '#94a3b8' }}>{d.deep_stats.unknown_count}</strong></span>
            )}
            <span>Сильный интент: <strong style={{ color: '#7c3aed' }}>{d.deep_stats.strong_intent_count}</strong></span>
            <span>Tool-like: <strong>{d.deep_stats.tool_like_count}</strong></span>
            <span>Article-like: <strong>{d.deep_stats.article_like_count}</strong></span>
          </div>
          {d.classification_adjustments && (
            <div style={{
              marginTop: 8,
              padding: '6px 10px',
              background: '#fef3c7',
              border: '1px solid #fbbf24',
              borderRadius: 6,
              color: '#92400e',
              fontWeight: 600,
              fontSize: 12,
            }}>
              ⚠ {d.classification_adjustments}
            </div>
          )}
        </div>
      )}

      <div style={{ marginBottom: 14 }}>
        <span style={{ fontWeight: 600, fontSize: 13 }}>Леммы ключа: </span>
        {d.key_lemmas.map((l) => (
          <span key={l} style={{
            display: 'inline-block',
            marginRight: 6,
            padding: '2px 8px',
            background: '#dbeafe',
            color: '#1e40af',
            borderRadius: 8,
            fontSize: 12,
            fontWeight: 500,
          }}>{l}</span>
        ))}
      </div>

      <OrganicDebugTable matches={d.organic_matches} deepAnalysisUsed={!!d.deep_analysis_used} />
      <AdsDebugTable matches={d.ads_matches} />
      <ScoreBreakdown row={row} />
    </td>
  )
}

// ─────────────────────────────────────────────────────────────
// Main results table
// ─────────────────────────────────────────────────────────────

export function ResultsTable({ rows, mode = 'search', wordstatRows = [], regionName = '' }: Props) {
  const [query, setQuery] = useState('')
  const [classFilter, setClassFilter] = useState<'ALL' | 'A' | 'B' | 'C' | 'D'>('ALL')
  const [minScore, setMinScore] = useState('')
  const [maxScore, setMaxScore] = useState('')
  const [sortField, setSortField] = useState<SortField>('итог')
  const [sortAsc, setSortAsc] = useState(false)
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null)

  const filtered = useMemo(() => {
    const min = minScore ? Number(minScore) : -Infinity
    const max = maxScore ? Number(maxScore) : Infinity

    const result = rows.filter((row) => {
      const matchesQuery = row.ключ.toLowerCase().includes(query.toLowerCase())
      const matchesClass = classFilter === 'ALL' || row.класс === classFilter
      const score = row.оценка.итог
      return matchesQuery && matchesClass && score >= min && score <= max
    })

    result.sort((a, b) => {
      if (sortField === 'ключ') {
        return sortAsc ? a.ключ.localeCompare(b.ключ) : b.ключ.localeCompare(a.ключ)
      }
      if (sortField === 'класс') {
        return sortAsc ? a.класс.localeCompare(b.класс) : b.класс.localeCompare(a.класс)
      }
      let av = 0; let bv = 0
      if (sortField === 'seo') { av = a.оценка.seo; bv = b.оценка.seo }
      else if (sortField === 'ads') { av = a.оценка.ads; bv = b.оценка.ads }
      else { av = a.оценка.итог; bv = b.оценка.итог }
      return sortAsc ? av - bv : bv - av
    })

    return result
  }, [rows, query, classFilter, minScore, maxScore, sortField, sortAsc])

  const [exporting, setExporting] = useState<string | null>(null)

  const handleExportXlsx = () => {
    exportXlsx(filtered, mode, wordstatRows, regionName)
  }

  const handleExportJson = () => {
    exportRichJson(filtered, mode, wordstatRows, regionName)
  }

  const handleExportChatGPT = async () => {
    setExporting('chatgpt')
    try {
      await exportChatGPTZip(filtered, mode, wordstatRows, regionName)
    } finally {
      setExporting(null)
    }
  }

  if (!rows.length) {
    return <section className="card"><p>Пока нет результатов. Запустите анализ, чтобы увидеть таблицу.</p></section>
  }

  return (
    <section className="card">
      <h2>Результаты анализа</h2>

      <div className="filters">
        <input placeholder="Поиск по ключу" value={query} onChange={(e) => setQuery(e.target.value)} />
        <select value={classFilter} onChange={(e) => setClassFilter(e.target.value as typeof classFilter)}>
          <option value="ALL">Все классы</option>
          <option value="A">Класс A — очень низкая конкуренция</option>
          <option value="B">Класс B — умеренная конкуренция</option>
          <option value="C">Класс C — заметная конкуренция</option>
          <option value="D">Класс D — высокая конкуренция</option>
        </select>
        <input placeholder="Мин. score" value={minScore} onChange={(e) => setMinScore(e.target.value)} />
        <input placeholder="Макс. score" value={maxScore} onChange={(e) => setMaxScore(e.target.value)} />
        <select value={sortField} onChange={(e) => setSortField(e.target.value as SortField)}>
          <option value="итог">Сортировка: итоговый score</option>
          <option value="ключ">Сортировка: ключевое слово</option>
          <option value="класс">Сортировка: класс конкуренции</option>
          <option value="seo">Сортировка: SEO score</option>
          <option value="ads">Сортировка: Ads score</option>
        </select>
        <button onClick={() => setSortAsc((p) => !p)}>{sortAsc ? '↑ По возрастанию' : '↓ По убыванию'}</button>
        <button onClick={handleExportXlsx} disabled={!filtered.length} title="Скачать XLSX с 5 листами: Сводка, Ключи, SERP детали, Wordstat, Справочник">
          Экспорт XLSX
        </button>
        <button onClick={handleExportJson} disabled={!filtered.length} title="Скачать полный JSON с метаданными, legend и SERP деталями">
          Экспорт JSON
        </button>
        <button
          onClick={handleExportChatGPT}
          disabled={!filtered.length || exporting === 'chatgpt'}
          title="Скачать ZIP для ChatGPT: summary.md + data.json + schema.md"
          style={{ background: exporting === 'chatgpt' ? '#475569' : undefined }}
        >
          {exporting === 'chatgpt' ? 'Упаковка...' : 'Экспорт для ChatGPT'}
        </button>
      </div>

      <div className="tableWrap">
        <table>
          <thead>
            <tr>
              <th></th>
              <th>Ключевое слово</th>
              <th title="Частотность из Wordstat (показов/мес.)">Частотность</th>
              <th title="Статус получения данных Яндекс SERP">Данные</th>
              <th>Страна</th><th>Регион</th>
              <th title="Полные совпадения заголовков в органике">Полных совп.</th>
              <th title="Близкие совпадения в органике">Близких совп.</th>
              <th title="Частичные совпадения в органике">Частичных совп.</th>
              <th title="Страницы, классифицированные как прямые конкуренты">Прямых конкурентов</th>
              <th>Объявлений</th>
              <th>Полных совп. (рекл.)</th>
              <th>Близких совп. (рекл.)</th>
              <th>SEO score</th>
              <th>Ads score</th>
              <th>Итоговый score</th>
              <th>Класс</th>
              <th>Рекомендация</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((row, idx) => (
              <React.Fragment key={`${row.ключ}-${idx}`}>
                <tr>
                  <td style={{ textAlign: 'center' }}>
                    <button
                      onClick={() => setExpandedIdx(expandedIdx === idx ? null : idx)}
                      style={{
                        width: 'auto',
                        padding: '3px 10px',
                        fontSize: 12,
                        marginTop: 0,
                        background: expandedIdx === idx ? '#475569' : '#0f172a',
                        borderRadius: 6,
                      }}
                    >
                      {expandedIdx === idx ? '▲ Скрыть' : '▼ Детали'}
                    </button>
                  </td>
                  <td>{row.ключ}</td>
                  <td style={{ textAlign: 'right', color: row.частотность != null ? undefined : '#94a3b8' }}>
                    {row.частотность != null ? row.частотность.toLocaleString('ru-RU') : '—'}
                  </td>
                  <td style={{ textAlign: 'center', whiteSpace: 'nowrap' }}>
                    <FetchStatusBadge status={row.отладка.fetch_status} compact />
                  </td>
                  <td>{row.локация.страна}</td>
                  <td>{row.локация.регион}</td>
                  <td style={{ color: row.органика.strong > 0 ? '#16a34a' : undefined, fontWeight: row.органика.strong > 0 ? 700 : undefined }}>
                    {row.органика.strong}
                  </td>
                  <td style={{ color: row.органика.near > 0 ? '#ca8a04' : undefined }}>
                    {row.органика.near}
                  </td>
                  <td>{row.органика.partial}</td>
                  <td style={{ fontWeight: 700, color: row.органика.commercial > 0 ? '#dc2626' : '#94a3b8' }}>
                    {row.органика.commercial}
                  </td>
                  <td>{row.реклама.количество}</td>
                  <td>{row.реклама.strong}</td>
                  <td>{row.реклама.near}</td>
                  <td>{row.оценка.seo}</td>
                  <td>{row.оценка.ads}</td>
                  <td style={{ fontWeight: 700 }}>{row.оценка.итог}</td>
                  <td style={{
                    fontWeight: 700,
                    color: row.класс === 'A' ? '#16a34a' : row.класс === 'B' ? '#ca8a04' : row.класс === 'C' ? '#ea580c' : '#dc2626',
                  }}>
                    {row.класс}
                  </td>
                  <td>{row.рекомендация}</td>
                </tr>
                {expandedIdx === idx && (
                  <tr>
                    <DebugPanel row={row} />
                  </tr>
                )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
