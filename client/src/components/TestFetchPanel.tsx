import { useState } from 'react'

interface DebugResult {
  keyword: string
  source: string
  error?: string
  fetch: {
    success: boolean
    captcha: boolean
    blocked: boolean
    html_length: number
    proxy_used: boolean
    parse_strategy: string
  }
  organic: Array<{ position: number; title: string; url: string }>
  ads: Array<{ position: number; title: string; url: string }>
}

export function TestFetchPanel() {
  const [open, setOpen] = useState(false)
  const [keyword, setKeyword] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<DebugResult | null>(null)
  const [error, setError] = useState('')

  const run = async () => {
    if (!keyword.trim()) return
    setLoading(true)
    setError('')
    setResult(null)
    try {
      const resp = await fetch('/api/parse-debug', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ keyword: keyword.trim(), location_name: 'Москва', depth: 5 }),
      })
      const data = await resp.json()
      if (!resp.ok) throw new Error(data.detail || 'Ошибка запроса')
      setResult(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <div
        style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8, userSelect: 'none' }}
        onClick={() => setOpen(!open)}
      >
        <span>🔍</span>
        <span style={{ fontWeight: 600 }}>Проверить Search API (один ключ)</span>
        <span style={{ marginLeft: 'auto', color: '#9ca3af', fontSize: 12 }}>{open ? '▲' : '▼'}</span>
      </div>

      {open && (
        <div style={{ marginTop: 12 }}>
          <div style={{ display: 'flex', gap: 8 }}>
            <input
              type="text"
              placeholder="Введите ключевое слово..."
              value={keyword}
              onChange={e => setKeyword(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && run()}
              style={{ flex: 1, padding: '8px 12px', border: '1px solid #d1d5db', borderRadius: 8, fontSize: 14 }}
            />
            <button onClick={run} disabled={loading || !keyword.trim()} style={{ padding: '8px 16px', fontSize: 14 }}>
              {loading ? '...' : 'Проверить'}
            </button>
          </div>

          {error && (
            <div style={{ marginTop: 10, padding: '8px 12px', background: '#fef2f2', borderRadius: 6, color: '#b91c1c', fontSize: 13 }}>
              {error}
            </div>
          )}

          {result && (
            <div style={{ marginTop: 12, fontSize: 13 }}>
              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 8 }}>
                <span style={{
                  padding: '2px 8px', borderRadius: 6, fontSize: 12, fontWeight: 700,
                  background: result.fetch.success ? '#f0fdf4' : '#fef2f2',
                  color: result.fetch.success ? '#15803d' : '#dc2626',
                }}>
                  {result.fetch.success ? '✓ Успех' : '✗ Ошибка'}
                </span>
                <span style={{ color: '#6b7280' }}>источник: {result.source}</span>
                {result.error && <span style={{ color: '#dc2626' }}>{result.error}</span>}
                <span style={{ color: '#6b7280' }}>HTML: {result.fetch.html_length} байт</span>
                <span style={{ color: '#6b7280' }}>стратегия: {result.fetch.parse_strategy}</span>
              </div>

              {result.organic.length > 0 && (
                <div>
                  <div style={{ fontWeight: 600, marginBottom: 4 }}>Органика ({result.organic.length}):</div>
                  {result.organic.slice(0, 5).map(r => (
                    <div key={r.position} style={{ padding: '4px 0', borderBottom: '1px solid #f3f4f6' }}>
                      <span style={{ color: '#9ca3af', marginRight: 6 }}>{r.position}.</span>
                      <a href={r.url} target="_blank" rel="noreferrer" style={{ color: '#1d4ed8' }}>{r.title || r.url}</a>
                    </div>
                  ))}
                </div>
              )}

              {result.organic.length === 0 && result.fetch.success && (
                <div style={{ color: '#92400e' }}>Search API вернул ответ, но органика не распознана.</div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
