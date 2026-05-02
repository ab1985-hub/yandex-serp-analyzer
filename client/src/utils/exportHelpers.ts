import * as XLSX from 'xlsx'
import JSZip from 'jszip'
import type { AnalyzeResult, WordstatKeyword, AppMode } from '../types'

// ─── helpers ────────────────────────────────────────────────────────────────

function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

function isoDate() {
  return new Date().toLocaleString('ru-RU', { timeZone: 'Europe/Moscow' })
}

function isoDateFile() {
  return new Date().toISOString().slice(0, 10)
}

function modeName(mode: AppMode) {
  if (mode === 'search') return 'Search API'
  if (mode === 'wordstat') return 'Wordstat API'
  return 'Combined (Wordstat + Search API)'
}

function classLabel(c: string) {
  return { A: 'Низкая', B: 'Умеренная', C: 'Высокая', D: 'Очень высокая' }[c] ?? c
}

function serpMixRu(label: string) {
  return (
    { HOMOGENEOUS: 'Однородная', MIXED: 'Смешанная', STRONGLY_MIXED: 'Сильно смешанная' }[label] ??
    label
  )
}

function competitorRu(level: string) {
  return (
    {
      DIRECT: 'Прямой',
      CLOSE: 'Близкий',
      INDIRECT: 'Непрямой',
      NOT_COMPETITOR: 'Не конкурент',
      UNKNOWN: 'Не загружено',
    }[level] ?? level
  )
}

function intentCovRu(ic: string) {
  return (
    { STRONG: 'Сильно', PARTIAL: 'Частично', WEAK: 'Слабо', NONE: 'Нет' }[ic] ?? ic
  )
}

function colWidths(cols: number[]) {
  return cols.map((w) => ({ wch: w }))
}

// ─── legend used in JSON + ChatGPT exports ──────────────────────────────────

const LEGEND = {
  competition_classes: {
    A: 'Низкая конкуренция — хороший кандидат для SEO',
    B: 'Умеренная конкуренция — можно брать в работу',
    C: 'Высокая конкуренция — заходить осторожно',
    D: 'Очень высокая конкуренция — выдача плотно занята прямыми конкурентами',
  },
  score: {
    description: 'Числовая оценка конкурентности (seo_score×0.8 + ads_score×0.2)',
    thresholds: { A: '0–9.99', B: '10–19.99', C: '20–29.99', D: '30+' },
    note: 'Чем выше score, тем сложнее запрос. При срабатывании guardrail score поднимается до нижней границы класса.',
  },
  serp_mix: {
    HOMOGENEOUS: 'В топе ≥60% одного типа страниц — выдача однородная, заходить сложнее',
    MIXED: 'В топе несколько типов страниц — стандартная ситуация',
    STRONGLY_MIXED: 'В топе ≥3 разных типов — Яндекс не определился с интентом, есть SEO-шанс',
  },
  competitor_levels: {
    DIRECT: 'Прямой конкурент — страница решает ту же задачу',
    CLOSE: 'Близкий конкурент — смежная задача или частичное решение',
    INDIRECT: 'Непрямой конкурент — тема похожа, но нет продуктового решения',
    NOT_COMPETITOR: 'Не конкурент',
    UNKNOWN: 'HTML страницы не загружен, использован только SERP-layer',
  },
  page_types: {
    TOOL_SERVICE: 'Онлайн-инструмент / сервис',
    CONVERTER: 'Конвертер / транскрибатор',
    SAAS: 'SaaS / web-app',
    LANDING: 'Продуктовый лендинг',
    ARTICLE: 'Информационная статья',
    REVIEW_LIST: 'Обзор / подборка / список сервисов',
    DOCS: 'Документация / help / support',
    MARKETPLACE: 'Маркетплейс / каталог',
    FORUM: 'Форум / UGC',
    IRRELEVANT: 'Нерелевантный результат',
    UNKNOWN: 'HTML не загружен',
  },
  intent_coverage: {
    STRONG: 'Сильно закрывает интент пользователя',
    PARTIAL: 'Частично закрывает интент',
    WEAK: 'Слабо закрывает интент',
    NONE: 'Не закрывает интент',
  },
  fetch_status: {
    true: 'HTML страницы успешно загружен и проанализирован',
    false: 'HTML страницы не загружен — анализ по SERP-данным',
  },
  guardrails: {
    description:
      'Guardrail — правило, которое повышает класс конкуренции, если deep-analysis показывает плотную выдачу. ' +
      'Guardrail никогда не понижает класс. Если поле пустое — корректировки не было.',
    examples: [
      'Класс повышен A→C: direct=6≥5, strong_intent=5≥5',
      'Класс повышен B→D: direct=7, strong_intent=7, mix=HOMOGENEOUS',
    ],
  },
}

// ─── 1. Rich JSON ────────────────────────────────────────────────────────────

export function buildRichJson(
  rows: AnalyzeResult[],
  mode: AppMode,
  wordstatRows: WordstatKeyword[],
  regionName: string,
) {
  const region = rows[0]?.локация?.регион ?? regionName

  const summary = (() => {
    const dist: Record<string, number> = {}
    const mixDist: Record<string, number> = {}
    let totalScore = 0
    let totalDirect = 0
    let totalClose = 0

    rows.forEach((r) => {
      dist[r.класс] = (dist[r.класс] ?? 0) + 1
      totalScore += r.оценка.итог
      totalDirect += r.отладка.deep_stats?.direct_count ?? 0
      totalClose += r.отладка.deep_stats?.close_count ?? 0
      const mix = r.отладка.serp_mix?.label ?? 'UNKNOWN'
      mixDist[mix] = (mixDist[mix] ?? 0) + 1
    })

    const sorted = [...rows].sort((a, b) => a.оценка.итог - b.оценка.итог)
    return {
      average_score: rows.length ? Math.round((totalScore / rows.length) * 100) / 100 : 0,
      class_distribution: dist,
      serp_mix_distribution: mixDist,
      total_direct_competitors: totalDirect,
      total_close_competitors: totalClose,
      best_opportunities: sorted.slice(0, 5).map((r) => ({ keyword: r.ключ, class: r.класс, score: r.оценка.итог })),
      hardest_keywords: sorted.slice(-5).reverse().map((r) => ({ keyword: r.ключ, class: r.класс, score: r.оценка.итог })),
    }
  })()

  const keywords = rows.map((r) => {
    const ds = r.отладка.deep_stats
    return {
      keyword: r.ключ,
      frequency: r.частотность ?? null,
      region,
      class: r.класс,
      competition_level: classLabel(r.класс),
      score: r.оценка.итог,
      serp_mix: r.отладка.serp_mix?.label ?? null,
      direct_count: ds?.direct_count ?? null,
      close_count: ds?.close_count ?? null,
      indirect_count: ds?.indirect_count ?? null,
      not_competitor_count: ds?.not_competitor_count ?? null,
      html_loaded_count: ds?.html_loaded ?? null,
      html_failed_count: ds?.unloaded_count ?? null,
      strong_intent_count: ds?.strong_intent_count ?? null,
      partial_intent_count: ds?.partial_intent_count ?? null,
      tool_like_count: ds?.tool_like_count ?? null,
      class_guardrail_reason: r.отладка.classification_adjustments || null,
      recommendation: r.рекомендация,
    }
  })

  const serp_details = rows.flatMap((r) =>
    r.отладка.organic_matches.map((m) => {
      const pa = m.page_analysis
      return {
        keyword: r.ключ,
        position: m.position,
        domain: (() => { try { return new URL(m.url).hostname } catch { return m.url } })(),
        url: m.url,
        title: m.title,
        description: m.description,
        page_type_serp: m.intent_type,
        page_type_html: pa?.page_type_html ?? null,
        competitor_level: pa?.competitor_level ?? m.intent_type,
        intent_coverage: pa?.intent_coverage ?? null,
        fetch_ok: pa?.fetch_ok ?? null,
        score_contribution: m.seo_contribution,
        text_match_level: m.title_level,
        geo_type: m.geo_relevance,
        classification_comment: pa?.explanation ?? null,
      }
    }),
  )

  const wordstat = wordstatRows.map((w) => ({
    phrase: w.keyword,
    count: w.frequency,
    selected: true,
    excluded_by_minus: false,
    source: 'wordstat_api',
  }))

  return {
    metadata: {
      exported_at: isoDate(),
      analysis_mode: modeName(mode),
      region,
      keywords_count: rows.length,
      source: 'seo-machine-yandex-search-api-wordstat-api',
      schema_version: '1.0',
    },
    legend: LEGEND,
    keywords,
    serp_details,
    wordstat: wordstat.length ? wordstat : [],
    summary,
  }
}

// ─── 2. XLSX ─────────────────────────────────────────────────────────────────

export function exportXlsx(
  rows: AnalyzeResult[],
  mode: AppMode,
  wordstatRows: WordstatKeyword[],
  regionName: string,
) {
  const wb = XLSX.utils.book_new()
  const region = rows[0]?.локация?.регион ?? regionName
  const dateStr = isoDate()
  const json = buildRichJson(rows, mode, wordstatRows, regionName)

  // ── Sheet 1: Сводка ────────────────────────────────────────────────────────
  const dist = json.summary.class_distribution
  const mixDist = json.summary.serp_mix_distribution
  const sheetSummary = XLSX.utils.aoa_to_sheet([
    ['Сводка результатов анализа'],
    [],
    ['Дата анализа', dateStr],
    ['Режим анализа', modeName(mode)],
    ['Регион', region],
    ['Количество ключей', rows.length],
    ['Средний score', json.summary.average_score],
    [],
    ['Распределение по классам'],
    ['Класс A — Низкая конкуренция', dist['A'] ?? 0],
    ['Класс B — Умеренная конкуренция', dist['B'] ?? 0],
    ['Класс C — Высокая конкуренция', dist['C'] ?? 0],
    ['Класс D — Очень высокая конкуренция', dist['D'] ?? 0],
    [],
    ['Тип выдачи (SERP mix)'],
    ['Однородная (HOMOGENEOUS)', mixDist['HOMOGENEOUS'] ?? 0],
    ['Смешанная (MIXED)', mixDist['MIXED'] ?? 0],
    ['Сильно смешанная (STRONGLY_MIXED)', mixDist['STRONGLY_MIXED'] ?? 0],
    [],
    ['Deep-анализ (суммарно)'],
    ['Всего прямых конкурентов (direct)', json.summary.total_direct_competitors],
    ['Всего близких конкурентов (close)', json.summary.total_close_competitors],
    [
      'Среднее direct на ключ',
      rows.length ? Math.round((json.summary.total_direct_competitors / rows.length) * 10) / 10 : 0,
    ],
    [],
    ['Пояснение шкалы score'],
    ['A: score 0–9.99 — низкая конкуренция'],
    ['B: score 10–19.99 — умеренная конкуренция'],
    ['C: score 20–29.99 — высокая конкуренция'],
    ['D: score 30+ — очень высокая конкуренция'],
  ])
  sheetSummary['!cols'] = colWidths([40, 30])
  XLSX.utils.book_append_sheet(wb, sheetSummary, 'Сводка')

  // ── Sheet 2: Ключи ─────────────────────────────────────────────────────────
  const keyHeaders = [
    'Ключ', 'Частотность', 'Регион', 'Класс', 'Уровень конкуренции', 'Score',
    'SERP mix', 'Прямых', 'Близких', 'Непрямых', 'Не конкурентов',
    'HTML загружено', 'HTML не загружено',
    'Сильный интент', 'Частичный интент', 'Tool-like страниц',
    'Причина корректировки класса', 'Рекомендация',
  ]
  const keyRows = rows.map((r) => {
    const ds = r.отладка.deep_stats
    return [
      r.ключ,
      r.частотность ?? '',
      r.локация.регион,
      r.класс,
      classLabel(r.класс),
      r.оценка.итог,
      serpMixRu(r.отладка.serp_mix?.label ?? ''),
      ds?.direct_count ?? '',
      ds?.close_count ?? '',
      ds?.indirect_count ?? '',
      ds?.not_competitor_count ?? '',
      ds?.html_loaded ?? '',
      ds?.unloaded_count ?? '',
      ds?.strong_intent_count ?? '',
      ds?.partial_intent_count ?? '',
      ds?.tool_like_count ?? '',
      r.отладка.classification_adjustments || '',
      r.рекомендация,
    ]
  })
  const sheetKeys = XLSX.utils.aoa_to_sheet([keyHeaders, ...keyRows])
  sheetKeys['!cols'] = colWidths([30, 14, 20, 8, 22, 8, 20, 8, 8, 10, 14, 14, 16, 14, 15, 15, 40, 60])
  XLSX.utils.book_append_sheet(wb, sheetKeys, 'Ключи')

  // ── Sheet 3: SERP детали ───────────────────────────────────────────────────
  const serpHeaders = [
    'Ключ', 'Позиция', 'Домен', 'URL', 'Title', 'Description/Snippet',
    'Тип (SERP)', 'Тип (HTML)', 'Конкурент', 'Закрытие интента',
    'HTML загружен', 'Вклад в score', 'Текстовое совпадение',
    'Гео-тип', 'Комментарий классификации',
  ]
  const serpRows = rows.flatMap((r) =>
    r.отладка.organic_matches.map((m) => {
      const pa = m.page_analysis
      let domain = m.url
      try { domain = new URL(m.url).hostname } catch {}
      return [
        r.ключ,
        m.position,
        domain,
        m.url,
        m.title,
        m.description,
        m.intent_type,
        pa?.page_type_html ?? '',
        pa ? competitorRu(pa.competitor_level) : competitorRu(m.intent_type),
        pa ? intentCovRu(pa.intent_coverage) : '',
        pa ? (pa.fetch_ok ? 'Да' : 'Нет') : '',
        m.seo_contribution,
        m.title_level,
        m.geo_relevance,
        pa?.explanation ?? '',
      ]
    }),
  )
  const sheetSerp = XLSX.utils.aoa_to_sheet([serpHeaders, ...serpRows])
  sheetSerp['!cols'] = colWidths([28, 8, 28, 55, 55, 60, 20, 16, 16, 18, 12, 12, 18, 12, 55])
  XLSX.utils.book_append_sheet(wb, sheetSerp, 'SERP детали')

  // ── Sheet 4: Wordstat (if present) ─────────────────────────────────────────
  if (wordstatRows.length > 0) {
    const wsHeaders = ['Ключ', 'Частотность', 'Выбран']
    const wsData = wordstatRows.map((w) => [w.keyword, w.frequency, 'Да'])
    const sheetWs = XLSX.utils.aoa_to_sheet([wsHeaders, ...wsData])
    sheetWs['!cols'] = colWidths([35, 14, 10])
    XLSX.utils.book_append_sheet(wb, sheetWs, 'Wordstat')
  }

  // ── Sheet 5: Справочник ────────────────────────────────────────────────────
  const glossaryRows: unknown[][] = [
    ['Справочник: значения полей и классификаций'],
    [],
    ['── Классы конкуренции ──'],
    ['A', 'Низкая конкуренция', 'Хороший кандидат для SEO-продвижения (score 0–9.99)'],
    ['B', 'Умеренная конкуренция', 'Можно брать в работу (score 10–19.99)'],
    ['C', 'Высокая конкуренция', 'Заходить осторожно (score 20–29.99)'],
    ['D', 'Очень высокая конкуренция', 'Плотная выдача, продвижение будет сложным (score 30+)'],
    [],
    ['── Score ──'],
    ['Описание', 'Числовая оценка конкурентности: seo_score × 0.8 + ads_score × 0.2'],
    ['Чем выше score', 'тем сложнее запрос'],
    ['Guardrail', 'При повышении класса score поднимается до нижней границы класса'],
    [],
    ['── SERP mix ──'],
    ['HOMOGENEOUS', 'Однородная', '≥60% одного типа страниц — заходить сложнее'],
    ['MIXED', 'Смешанная', 'Несколько типов страниц — стандартная ситуация'],
    ['STRONGLY_MIXED', 'Сильно смешанная', '≥3 типов — Яндекс не определился с интентом, есть SEO-шанс'],
    [],
    ['── Конкурентный статус (competitor_level) ──'],
    ['DIRECT', 'Прямой', 'Страница решает ту же задачу — прямой конкурент'],
    ['CLOSE', 'Близкий', 'Смежная задача или частичное решение'],
    ['INDIRECT', 'Непрямой', 'Тема похожа, но нет продуктового решения'],
    ['NOT_COMPETITOR', 'Не конкурент', 'Результат не является конкурентом'],
    ['(нет данных)', 'HTML не загружен', 'Используется только SERP-layer'],
    [],
    ['── Типы страниц (page_type_html) ──'],
    ['TOOL_SERVICE', 'Онлайн-инструмент / сервис'],
    ['CONVERTER', 'Конвертер / транскрибатор'],
    ['SAAS', 'SaaS / web-app'],
    ['LANDING', 'Продуктовый лендинг'],
    ['ARTICLE', 'Информационная статья'],
    ['REVIEW_LIST', 'Обзор / подборка / список сервисов'],
    ['DOCS', 'Документация / help / support'],
    ['MARKETPLACE', 'Маркетплейс / каталог'],
    ['FORUM', 'Форум / UGC'],
    ['IRRELEVANT', 'Нерелевантный результат'],
    [],
    ['── Закрытие интента (intent_coverage) ──'],
    ['STRONG', 'Сильно', 'Страница хорошо решает задачу пользователя'],
    ['PARTIAL', 'Частично', 'Страница решает задачу частично'],
    ['WEAK', 'Слабо', 'Страница слабо соответствует интенту'],
    ['NONE', 'Нет', 'Страница не закрывает интент'],
    [],
    ['── Fetch status ──'],
    ['fetch_ok = true / Да', 'HTML страницы успешно загружен и проанализирован'],
    ['fetch_ok = false / Нет', 'HTML страницы не загружен, анализ основан только на SERP-данных'],
    [],
    ['── Guardrails ──'],
    ['Что это', 'Правило, которое повышает итоговый класс, если deep-analysis выявляет плотную выдачу'],
    ['Пример', 'Класс повышен A→C: direct=6≥5, strong_intent=5≥5'],
    ['Важно', 'Guardrail никогда не понижает класс — только повышает. Пустое поле = корректировок не было.'],
  ]
  const sheetGlossary = XLSX.utils.aoa_to_sheet(glossaryRows)
  sheetGlossary['!cols'] = colWidths([22, 24, 70])
  XLSX.utils.book_append_sheet(wb, sheetGlossary, 'Справочник')

  XLSX.writeFile(wb, `результаты-анализа-${isoDateFile()}.xlsx`)
}

// ─── 3. Rich JSON export ─────────────────────────────────────────────────────

export function exportRichJson(
  rows: AnalyzeResult[],
  mode: AppMode,
  wordstatRows: WordstatKeyword[],
  regionName: string,
) {
  const data = buildRichJson(rows, mode, wordstatRows, regionName)
  triggerDownload(
    new Blob([JSON.stringify(data, null, 2)], { type: 'application/json;charset=utf-8' }),
    `результаты-анализа-${isoDateFile()}.json`,
  )
}

// ─── 4. ChatGPT ZIP ─────────────────────────────────────────────────────────

export async function exportChatGPTZip(
  rows: AnalyzeResult[],
  mode: AppMode,
  wordstatRows: WordstatKeyword[],
  regionName: string,
) {
  const region = rows[0]?.локация?.регион ?? regionName
  const json = buildRichJson(rows, mode, wordstatRows, regionName)

  // ── analysis_summary.md ─────────────────────────────────────────────────
  const sorted = [...rows].sort((a, b) => a.оценка.итог - b.оценка.итог)
  const top5 = sorted.slice(0, 5)
  const hard5 = sorted.slice(-5).reverse()

  const classCounts = json.summary.class_distribution
  const tableHeader = '| Ключ | Частотность | Класс | Score | SERP mix | Прямых | Близких | Рекомендация |\n|---|---|---|---|---|---|---|---|'
  const tableRows = rows
    .map((r) => {
      const ds = r.отладка.deep_stats
      const freq = r.частотность != null ? r.частотность.toLocaleString('ru-RU') : '—'
      return `| ${r.ключ} | ${freq} | ${r.класс} | ${r.оценка.итог} | ${serpMixRu(r.отладка.serp_mix?.label ?? '')} | ${ds?.direct_count ?? '—'} | ${ds?.close_count ?? '—'} | ${r.рекомендация.slice(0, 60)}... |`
    })
    .join('\n')

  const summaryMd = `# Результаты SEO-анализа конкурентности ключевых слов

## Метаданные
- **Дата анализа:** ${isoDate()}
- **Режим:** ${modeName(mode)}
- **Регион:** ${region}
- **Количество ключей:** ${rows.length}

## Распределение по классам
- A (Низкая конкуренция): **${classCounts['A'] ?? 0}** ключей
- B (Умеренная): **${classCounts['B'] ?? 0}** ключей
- C (Высокая): **${classCounts['C'] ?? 0}** ключей
- D (Очень высокая): **${classCounts['D'] ?? 0}** ключей
- **Средний score:** ${json.summary.average_score}

## Таблица ключей
${tableHeader}
${tableRows}

## Топ перспективных ключей (низкий score)
${top5.map((r) => `- **${r.ключ}** — класс ${r.класс}, score ${r.оценка.итог}`).join('\n')}

## Самые конкурентные ключи (высокий score)
${hard5.map((r) => `- **${r.ключ}** — класс ${r.класс}, score ${r.оценка.итог}`).join('\n')}

## Как читать результаты

- **Класс A**: низкая конкуренция, хороший кандидат для продвижения (score < 10)
- **Класс B**: умеренная конкуренция, можно брать в работу (score 10–20)
- **Класс C**: высокая конкуренция, заходить осторожно (score 20–30)
- **Класс D**: очень высокая конкуренция, плотная выдача (score ≥ 30)
- **SERP mix HOMOGENEOUS**: в топ-10 преобладает один тип страниц — сложнее найти нишу
- **Прямой конкурент (DIRECT)**: страница решает ту же задачу, что и целевой продукт
- **score**: числовая оценка, чем выше — тем сложнее запрос
- **Guardrail**: автоматическая корректировка класса на основе глубокого анализа (повышает, никогда не понижает)

> Полные данные с SERP-деталями и guardrail-пояснениями — в файле \`analysis_data.json\`.
> Описание всех полей — в файле \`schema_explanation.md\`.
`

  // ── analysis_data.json ──────────────────────────────────────────────────
  const dataJson = JSON.stringify(json, null, 2)

  // ── schema_explanation.md ───────────────────────────────────────────────
  const schemaMd = `# Описание схемы данных: analysis_data.json

## Что это
Экспорт результатов SEO-анализа конкурентности ключевых слов.
Анализ выполнен с помощью Yandex Search API и deep-analysis (реальный HTML top-10 страниц).

## Как был собран анализ
1. **Yandex Search API** — получение органической выдачи и рекламы по каждому ключу
2. **Deep-analysis (top-10)** — загрузка и анализ реального HTML каждой страницы в топ-10
3. **Scoring** — формула: seo_score × 0.8 + ads_score × 0.2
4. **Guardrails** — правила корректировки класса на основе deep-analysis статистики

## Разделы JSON

### \`metadata\`
Информация об экспорте: дата, режим анализа, регион, количество ключей.

### \`legend\`
Полный справочник всех используемых enum-значений. Используйте этот раздел для интерпретации
полей \`class\`, \`serp_mix\`, \`competitor_level\`, \`page_type_html\`, \`intent_coverage\`.

### \`keywords\`
Сводная строка по каждому ключу. Поля:
| Поле | Описание |
|---|---|
| keyword | Ключевое слово |
| frequency | Частотность из Wordstat (показов/мес.), null если анализ запускался без Wordstat |
| class | Класс A/B/C/D |
| score | Итоговый score |
| serp_mix | Тип выдачи (HOMOGENEOUS/MIXED/STRONGLY_MIXED) |
| direct_count | Количество прямых конкурентов в top-10 |
| close_count | Количество близких конкурентов |
| strong_intent_count | Страниц с сильным закрытием интента |
| tool_like_count | Страниц типа TOOL/CONVERTER/SAAS/LANDING |
| html_loaded_count | Успешно загруженных HTML страниц |
| class_guardrail_reason | Причина корректировки класса (пустое = не корректировался) |
| recommendation | Текстовая рекомендация |

### \`serp_details\`
Каждая строка органической выдачи для каждого ключа. Поля:
| Поле | Описание |
|---|---|
| keyword | Ключевое слово |
| position | Позиция в выдаче (1–10) |
| domain | Домен |
| url | Полный URL |
| page_type_serp | Тип страницы по SERP-сигналам |
| page_type_html | Тип страницы по HTML-анализу (если загружен) |
| competitor_level | Конкурентный статус (DIRECT/CLOSE/INDIRECT/NOT_COMPETITOR) |
| intent_coverage | Закрытие интента (STRONG/PARTIAL/WEAK/NONE) |
| fetch_ok | true = HTML загружен и проанализирован |
| score_contribution | Вклад этой страницы в итоговый score |

### \`wordstat\`
Ключевые слова из Wordstat API (если анализ запускался в режиме Wordstat или Combined).

### \`summary\`
Агрегированная статистика: распределение классов, топ перспективных и конкурентных ключей.

## Как читать классы A/B/C/D
- **A** (score 0–9.99): прямых конкурентов мало, хороший кандидат для SEO
- **B** (score 10–19.99): умеренная конкуренция, выдача не полностью занята
- **C** (score 20–29.99): заметная конкуренция, заходить осторожно
- **D** (score ≥ 30): очень высокая конкуренция, плотная выдача

## Как читать SERP mix
- **HOMOGENEOUS**: в топ-10 ≥60% одного типа страниц — выдача однородная
- **MIXED**: несколько типов страниц — стандартная ситуация
- **STRONGLY_MIXED**: ≥3 типов — Яндекс не определился с интентом, есть SEO-возможность

## Как читать competitor_level
- **DIRECT**: страница решает ту же задачу — прямой конкурент
- **CLOSE**: смежная задача или частичное решение
- **INDIRECT**: похожая тема, но нет продуктового ответа
- **NOT_COMPETITOR**: не конкурент
- **UNKNOWN / null**: HTML не был загружен

## Как читать intent_coverage
- **STRONG**: страница хорошо закрывает интент пользователя
- **PARTIAL**: частично закрывает
- **WEAK**: слабо соответствует
- **NONE**: не закрывает

## Что означает fetch_ok
- \`true\`: HTML страницы успешно загружен — анализ по реальному содержимому
- \`false\`: HTML не получен — анализ только по заголовку и сниппету из SERP

## Что такое class_guardrail_reason
Guardrail — правило, которое повышает итоговый класс при обнаружении плотной конкурентной выдачи.
Например: \`Класс повышен A→C: direct=6≥5, strong_intent=5≥5\`
Если поле пустое или null — класс не корректировался.

## Ограничения анализа
1. Часть HTML-страниц может не загрузиться (503, CAPTCHA, JS-рендеринг) — для них используется только SERP-layer
2. JS-only страницы без серверного рендеринга могут анализироваться неполно
3. Классификация rule-based, не является абсолютной истиной — нужна ручная проверка граничных случаев
4. Wordstat-частотность зависит от API Яндекса и выбранного региона
5. Выдача Яндекса персонализирована и меняется со временем — данные актуальны на момент сбора
`

  // ── pack into ZIP ─────────────────────────────────────────────────────────
  const zip = new JSZip()
  zip.file('analysis_summary.md', summaryMd)
  zip.file('analysis_data.json', dataJson)
  zip.file('schema_explanation.md', schemaMd)

  const blob = await zip.generateAsync({ type: 'blob' })
  triggerDownload(blob, `chatgpt-export-${isoDateFile()}.zip`)
}
