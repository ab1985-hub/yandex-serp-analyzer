import { useMemo, useState } from 'react'
import { SearchForm } from '../components/AnalyzeForm'
import { ResultsTable } from '../components/ResultsTable'
import { StatusBar } from '../components/StatusBar'
import { WordstatForm } from '../components/WordstatForm'
import { WordstatTable } from '../components/WordstatTable'
import { runSearchAnalyze, runWordstat } from '../services/api'
import type { AnalyzeResult, AppMode, WordstatKeyword, KeywordItem } from '../types'

const DEFAULT_REGION_ID = 213
const DEFAULT_REGION_NAME = 'Москва'

export function HomePage() {
  const [mode, setMode] = useState<AppMode>('search')
  const [niche, setNiche] = useState<string>('real_estate')

  const [regionId, setRegionId] = useState(DEFAULT_REGION_ID)
  const [regionName, setRegionName] = useState(DEFAULT_REGION_NAME)

  const [rows, setRows] = useState<AnalyzeResult[]>([])
  const [wordstatRows, setWordstatRows] = useState<WordstatKeyword[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  // Minus-phrases state lifted here so WordstatTable can append words to it
  const [wordstatMinus, setWordstatMinus] = useState('')
  const [wordstatMinFreq, setWordstatMinFreq] = useState(0)
  const [wordstatSeed, setWordstatSeed] = useState('')

  const handleRegionChange = (id: number, name: string) => {
    setRegionId(id)
    setRegionName(name)
  }

  const parseLines = (text: string) =>
    text.split(/\r?\n/).map(s => s.trim()).filter(Boolean)

  // Canonical filtered list — single source of truth for WordstatTable, checkboxes, export, analysis
  const filteredWordstatRows = useMemo(() => {
    const minusList = parseLines(wordstatMinus).map(s => s.toLowerCase())
    if (!minusList.length) return wordstatRows
    return wordstatRows.filter(kw => {
      const kwLower = kw.keyword.toLowerCase()
      return !minusList.some(m => kwLower.includes(m))
    })
  }, [wordstatRows, wordstatMinus])

  // Called from WordstatTable when user clicks "Исключить минус-слова"
  const handleAddMinusWords = (words: string[]) => {
    setWordstatMinus(prev => {
      const existing = new Set(
        prev.split(/\r?\n/).map(s => s.trim().toLowerCase()).filter(Boolean)
      )
      const toAdd = words.filter(w => !existing.has(w.toLowerCase()))
      if (!toAdd.length) return prev
      return (prev.trim() ? prev.trim() + '\n' : '') + toAdd.join('\n')
    })
  }

  const runAnalysis = async (keywords: string[], minusPhrases: string[]) => {
    if (!keywords.length) { setError('Добавьте хотя бы один ключ'); return }
    setLoading(true)
    setError('')
    try {
      const results = await runSearchAnalyze({
        keywords,
        region_id: regionId,
        region_name: regionName,
        country: 'Россия',
        minus_phrases: minusPhrases,
        depth: 10,
        preset: 'bulk-analysis',
        deep_analysis: true,
        niche,
      })
      setRows(results)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Неизвестная ошибка')
    } finally {
      setLoading(false)
    }
  }

  const runWordstatCollect = async (seed: string, minus: string[], limit: number, minFreq: number) => {
    setLoading(true)
    setError('')
    setWordstatSeed(seed)
    try {
      const kws = await runWordstat({
        seed_keyword: seed,
        region_id: regionId,
        limit,
        minus_phrases: minus,
        min_frequency: minFreq,
      })
      setWordstatRows(kws)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Ошибка Wordstat')
    } finally {
      setLoading(false)
    }
  }

  const handleCombined = async (seed: string, minus: string[], limit: number, minFreq: number) => {
    setLoading(true)
    setError('')
    setWordstatRows([])
    setRows([])
    setWordstatSeed(seed)
    try {
      const kws = await runWordstat({
        seed_keyword: seed,
        region_id: regionId,
        limit,
        minus_phrases: minus,
        min_frequency: minFreq,
      })
      setWordstatRows(kws)
      if (!kws.length) { setError('Wordstat не вернул ключей после применения фильтров'); return }
      const results = await runSearchAnalyze({
        keywords: kws.map(k => ({ keyword: k.keyword, frequency: k.frequency })),
        region_id: regionId,
        region_name: regionName,
        country: 'Россия',
        minus_phrases: minus,
        depth: 10,
        preset: 'bulk-analysis',
        deep_analysis: true,
        niche,
      })
      setRows(results)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Ошибка')
    } finally {
      setLoading(false)
    }
  }

  const sendToAnalysis = async (keywords: KeywordItem[]) => {
    setLoading(true)
    setError('')
    setRows([])
    try {
      const currentMinus = parseLines(wordstatMinus)
      const results = await runSearchAnalyze({
        keywords,
        region_id: regionId,
        region_name: regionName,
        country: 'Россия',
        minus_phrases: currentMinus,
        depth: 10,
        preset: 'bulk-analysis',
        deep_analysis: true,
        niche,
      })
      setRows(results)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Ошибка анализа')
    } finally {
      setLoading(false)
    }
  }

  const tabStyle = (m: AppMode): React.CSSProperties => ({
    padding: '10px 20px',
    borderRadius: '8px 8px 0 0',
    border: 'none',
    cursor: 'pointer',
    fontSize: 14,
    fontWeight: mode === m ? 700 : 400,
    background: mode === m ? '#fff' : '#f3f4f6',
    color: mode === m ? '#1d4ed8' : '#6b7280',
    borderBottom: mode === m ? '2px solid #1d4ed8' : '2px solid transparent',
    transition: 'all 0.15s',
    marginTop: 0,
    width: 'auto',
  })

  return (
    <main className="container">
      <h1>Анализ конкурентности ключевых слов (Яндекс SERP)</h1>
      <p className="subtitle">Yandex Search API · Wordstat API — официальные источники данных</p>

      <StatusBar />

      {/* Mode switcher + niche selector */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8, borderBottom: '2px solid #e5e7eb', marginBottom: 20 }}>
        <div style={{ display: 'flex', gap: 4 }}>
          <button style={tabStyle('search')} onClick={() => { setMode('search'); setError('') }}>
            Search API
          </button>
          <button style={tabStyle('wordstat')} onClick={() => { setMode('wordstat'); setError('') }}>
            Wordstat API
          </button>
          <button style={tabStyle('combined')} onClick={() => { setMode('combined'); setError('') }}>
            Комбинированный
          </button>
        </div>

        {/* Niche selector */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, paddingBottom: 4 }}>
          <label htmlFor="niche-select" style={{ fontSize: 13, color: '#374151', fontWeight: 500, whiteSpace: 'nowrap' }}>
            Ниша анализа:
          </label>
          <select
            id="niche-select"
            value={niche}
            onChange={e => setNiche(e.target.value)}
            style={{
              fontSize: 13,
              padding: '4px 8px',
              borderRadius: 6,
              border: '1px solid #d1d5db',
              background: '#f9fafb',
              color: '#374151',
              cursor: 'pointer',
            }}
          >
            <option value="real_estate">🏠 Недвижимость</option>
            <option value="universal">🌐 Универсальная</option>
          </select>
        </div>
      </div>

      {/* Mode: Search API */}
      {mode === 'search' && (
        <SearchForm
          loading={loading}
          regionId={regionId}
          regionName={regionName}
          onRegionChange={handleRegionChange}
          onSubmit={runAnalysis}
        />
      )}

      {/* Mode: Wordstat */}
      {mode === 'wordstat' && (
        <WordstatForm
          loading={loading}
          regionId={regionId}
          regionName={regionName}
          onRegionChange={handleRegionChange}
          onSubmit={runWordstatCollect}
          submitLabel="Собрать ключи"
          minus={wordstatMinus}
          onMinusChange={setWordstatMinus}
          minFrequency={wordstatMinFreq}
          onMinFrequencyChange={setWordstatMinFreq}
        />
      )}

      {/* Mode: Combined */}
      {mode === 'combined' && (
        <WordstatForm
          loading={loading}
          regionId={regionId}
          regionName={regionName}
          onRegionChange={handleRegionChange}
          onSubmit={handleCombined}
          submitLabel="Собрать и проанализировать"
          minus={wordstatMinus}
          onMinusChange={setWordstatMinus}
          minFrequency={wordstatMinFreq}
          onMinFrequencyChange={setWordstatMinFreq}
        />
      )}

      {loading && (
        <div className="card" style={{ textAlign: 'center', color: '#6b7280' }}>
          {mode === 'combined' ? 'Сбор ключей через Wordstat + анализ через Search API...' :
           mode === 'wordstat' ? 'Загрузка ключей из Wordstat...' :
           'Анализ ключевых слов через Yandex Search API...'}
        </div>
      )}
      {error && <div className="card error">Ошибка: {error}</div>}

      {/* Wordstat result table (wordstat + combined modes) */}
      {filteredWordstatRows.length > 0 && (mode === 'wordstat' || mode === 'combined') && (
        <WordstatTable
          keywords={filteredWordstatRows}
          onSendToAnalysis={sendToAnalysis}
          onAddMinusWords={handleAddMinusWords}
          seedKeyword={wordstatSeed}
          regionName={regionName}
          loading={loading}
        />
      )}
      {wordstatRows.length > 0 && filteredWordstatRows.length === 0 && (mode === 'wordstat' || mode === 'combined') && (
        <div className="card" style={{ color: '#6b7280', textAlign: 'center' }}>
          Все ключи исключены минус-фразами. Измените минус-фразы или соберите ключи заново.
        </div>
      )}

      {/* Competition analysis results table */}
      {rows.length > 0 && (
        <ResultsTable
          rows={rows}
          mode={mode}
          wordstatRows={wordstatRows}
          regionName={regionName}
        />
      )}
    </main>
  )
}
