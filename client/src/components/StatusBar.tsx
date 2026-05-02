import { useEffect, useState } from 'react'
import { getStatus } from '../services/api'
import type { SerpStatus } from '../services/api'

export function StatusBar() {
  const [status, setStatus] = useState<SerpStatus | null>(null)

  useEffect(() => {
    getStatus()
      .then(setStatus)
      .catch(() => setStatus(null))
  }, [])

  if (!status) return null

  const ok = status.api_configured === true

  return (
    <div style={{
      padding: '10px 16px',
      borderRadius: 10,
      background: ok ? '#f0fdf4' : '#fef2f2',
      border: `1px solid ${ok ? '#bbf7d0' : '#fecaca'}`,
      fontSize: 13,
      marginBottom: 16,
      display: 'flex',
      alignItems: 'center',
      gap: 10,
      flexWrap: 'wrap',
    }}>
      <span style={{
        display: 'inline-block',
        width: 10, height: 10,
        borderRadius: '50%',
        background: ok ? '#16a34a' : '#dc2626',
        flexShrink: 0,
      }} />
      <span style={{ fontWeight: 700, color: ok ? '#15803d' : '#b91c1c' }}>
        {ok ? '✓ Yandex Search API + Wordstat API' : '⚠ API не настроен'}
      </span>
      <span style={{ color: '#6b7280', flex: 1 }}>{status.message}</span>
    </div>
  )
}
