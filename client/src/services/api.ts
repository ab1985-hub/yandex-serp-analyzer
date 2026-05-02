import type { AnalyzeResult, WordstatKeyword, RegionNode, KeywordItem } from '../types'

export interface SerpStatus {
  mode: 'api' | 'unconfigured'
  source?: string
  api_configured?: boolean
  message: string
}

export async function getStatus(): Promise<SerpStatus> {
  const response = await fetch('/api/status')
  if (!response.ok) throw new Error('Не удалось получить статус сервиса')
  return response.json()
}

export async function getRegions(): Promise<RegionNode[]> {
  const response = await fetch('/api/regions')
  if (!response.ok) throw new Error('Не удалось загрузить регионы')
  const data = await response.json()
  return data.regions ?? []
}

export interface SearchAnalyzeOptions {
  keywords: (string | KeywordItem)[]
  region_id: number
  region_name: string
  country: string
  minus_phrases: string[]
  depth: number
  preset: string
  deep_analysis?: boolean
  niche?: string
}

export async function runSearchAnalyze(opts: SearchAnalyzeOptions): Promise<AnalyzeResult[]> {
  const response = await fetch('/api/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(opts),
  })
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(err.detail ?? 'Ошибка анализа')
  }
  const data = await response.json()
  return data.результаты ?? []
}

export interface WordstatOptions {
  seed_keyword: string
  region_id: number
  limit: number
  minus_phrases: string[]
  min_frequency: number
}

export async function runWordstat(opts: WordstatOptions): Promise<WordstatKeyword[]> {
  const response = await fetch('/api/wordstat/top', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(opts),
  })
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(err.detail ?? 'Ошибка Wordstat')
  }
  const data = await response.json()
  return data.keywords ?? []
}

export async function uploadKeywordsFile(file: File): Promise<string[]> {
  const form = new FormData()
  form.append('file', file)
  const response = await fetch('/api/keywords/upload', {
    method: 'POST',
    body: form,
  })
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(err.detail ?? 'Ошибка загрузки файла')
  }
  const data = await response.json()
  return data.keywords ?? []
}
