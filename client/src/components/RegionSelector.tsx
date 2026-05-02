import { useEffect, useRef, useState } from 'react'
import { getRegions } from '../services/api'
import type { RegionNode } from '../types'

interface Props {
  regionId: number
  regionName: string
  onChange: (id: number, name: string) => void
}

function flattenTree(nodes: RegionNode[], depth = 0): Array<{ id: number; name: string; depth: number }> {
  const result: Array<{ id: number; name: string; depth: number }> = []
  for (const n of nodes) {
    result.push({ id: n.id, name: n.name, depth })
    if (n.children?.length) {
      result.push(...flattenTree(n.children, depth + 1))
    }
  }
  return result
}

const FALLBACK_REGIONS: Array<{ id: number; name: string; depth: number }> = [
  { id: 225, name: 'Россия', depth: 0 },
  { id: 1, name: 'Москва и Московская область', depth: 1 },
  { id: 213, name: 'Москва', depth: 2 },
  { id: 2, name: 'Санкт-Петербург', depth: 1 },
  { id: 65, name: 'Новосибирск', depth: 1 },
  { id: 54, name: 'Екатеринбург', depth: 1 },
  { id: 43, name: 'Казань', depth: 1 },
  { id: 47, name: 'Нижний Новгород', depth: 1 },
  { id: 56, name: 'Челябинск', depth: 1 },
  { id: 51, name: 'Самара', depth: 1 },
  { id: 172, name: 'Уфа', depth: 1 },
  { id: 39, name: 'Ростов-на-Дону', depth: 1 },
  { id: 62, name: 'Красноярск', depth: 1 },
  { id: 50, name: 'Пермь', depth: 1 },
  { id: 35, name: 'Краснодар', depth: 1 },
  { id: 194, name: 'Саратов', depth: 1 },
  { id: 55, name: 'Тюмень', depth: 1 },
  { id: 66, name: 'Омск', depth: 1 },
]

export function RegionSelector({ regionId, regionName, onChange }: Props) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const [flat, setFlat] = useState(FALLBACK_REGIONS)
  const [loading, setLoading] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    setLoading(true)
    getRegions()
      .then(tree => {
        if (tree?.length) setFlat(flattenTree(tree))
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const filtered = flat.filter(r =>
    r.name.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        style={{
          width: '100%',
          padding: '10px 14px',
          border: '1px solid #d1d5db',
          borderRadius: 8,
          background: '#fff',
          color: '#1f2937',
          textAlign: 'left',
          cursor: 'pointer',
          fontSize: 14,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginTop: 0,
        }}
      >
        <span>{regionName || 'Выберите регион'}</span>
        <span style={{ color: '#9ca3af', fontSize: 12 }}>{open ? '▲' : '▼'}</span>
      </button>

      {open && (
        <div style={{
          position: 'absolute',
          top: '100%',
          left: 0,
          right: 0,
          zIndex: 200,
          background: '#fff',
          border: '1px solid #d1d5db',
          borderRadius: 8,
          boxShadow: '0 4px 20px rgba(0,0,0,0.12)',
          maxHeight: 320,
          display: 'flex',
          flexDirection: 'column',
        }}>
          <div style={{ padding: '8px 10px', borderBottom: '1px solid #f0f0f0' }}>
            <input
              autoFocus
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Поиск региона..."
              style={{
                width: '100%',
                padding: '6px 10px',
                border: '1px solid #e5e7eb',
                borderRadius: 6,
                fontSize: 13,
                outline: 'none',
                boxSizing: 'border-box',
              }}
            />
          </div>
          <div style={{ overflowY: 'auto', flex: 1 }}>
            {loading && (
              <div style={{ padding: 12, color: '#9ca3af', fontSize: 13 }}>Загрузка регионов...</div>
            )}
            {filtered.map((r, i) => (
              <div
                key={`${r.id}-${i}`}
                onClick={() => { onChange(r.id, r.name); setOpen(false); setSearch('') }}
                style={{
                  padding: `8px 14px 8px ${14 + r.depth * 14}px`,
                  cursor: 'pointer',
                  fontSize: 13,
                  background: r.id === regionId ? '#eff6ff' : 'transparent',
                  color: r.id === regionId ? '#1d4ed8' : '#1f2937',
                  fontWeight: r.id === regionId ? 600 : 400,
                  borderLeft: r.id === regionId ? '3px solid #3b82f6' : '3px solid transparent',
                }}
                onMouseEnter={e => {
                  if (r.id !== regionId) (e.currentTarget as HTMLDivElement).style.background = '#f9fafb'
                }}
                onMouseLeave={e => {
                  if (r.id !== regionId) (e.currentTarget as HTMLDivElement).style.background = 'transparent'
                }}
              >
                {r.name}
              </div>
            ))}
            {!loading && !filtered.length && (
              <div style={{ padding: 12, color: '#9ca3af', fontSize: 13 }}>Ничего не найдено</div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
