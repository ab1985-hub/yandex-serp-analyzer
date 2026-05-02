import { useState } from 'react'
import { RegionSelector } from './RegionSelector'

interface Props {
  loading: boolean
  regionId: number
  regionName: string
  onRegionChange: (id: number, name: string) => void
  onSubmit: (seedKeyword: string, minusPhrases: string[], limit: number, minFrequency: number) => void
  submitLabel?: string
  minus: string
  onMinusChange: (v: string) => void
  minFrequency: number
  onMinFrequencyChange: (v: number) => void
}

export function WordstatForm({
  loading, regionId, regionName, onRegionChange, onSubmit,
  submitLabel = 'Собрать ключи', minus, onMinusChange,
  minFrequency, onMinFrequencyChange,
}: Props) {
  const [seed, setSeed] = useState('')
  const [limit, setLimit] = useState(100)

  const parseLines = (text: string) =>
    text.split(/\r?\n/).map(s => s.trim()).filter(Boolean)

  const submit = () => {
    if (!seed.trim()) return
    onSubmit(seed.trim(), parseLines(minus), limit, minFrequency)
  }

  return (
    <section className="card">
      <h2>Параметры Wordstat</h2>

      <label>Тема / стартовый ключ</label>
      <input
        type="text"
        placeholder="Например: купить квартиру Москва"
        value={seed}
        onChange={e => setSeed(e.target.value)}
        onKeyDown={e => e.key === 'Enter' && submit()}
        style={{ width: '100%', padding: '10px 12px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: 14, boxSizing: 'border-box' }}
      />

      <label style={{ marginTop: 12 }}>Регион поиска</label>
      <RegionSelector
        regionId={regionId}
        regionName={regionName}
        onChange={onRegionChange}
      />

      <label style={{ marginTop: 12 }}>Минус-фразы (по одной на строку)</label>
      <textarea
        rows={3}
        placeholder="бесплатно&#10;фото&#10;видео"
        value={minus}
        onChange={e => onMinusChange(e.target.value)}
      />

      <div style={{ display: 'flex', gap: 24, alignItems: 'flex-end', flexWrap: 'wrap', marginTop: 12 }}>
        <div>
          <label style={{ display: 'block', marginBottom: 4 }}>Лимит ключей</label>
          <input
            type="number"
            min={1}
            max={1000}
            value={limit}
            onChange={e => setLimit(Math.max(1, Math.min(1000, Number(e.target.value))))}
            style={{ width: 120, padding: '8px 12px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: 14 }}
          />
        </div>
        <div>
          <label style={{ display: 'block', marginBottom: 4 }}>
            Мин. частотность
            <span style={{ marginLeft: 6, fontSize: 11, color: '#9ca3af', fontWeight: 400 }}>
              (0 = без фильтра)
            </span>
          </label>
          <input
            type="number"
            min={0}
            value={minFrequency}
            onChange={e => onMinFrequencyChange(Math.max(0, Number(e.target.value)))}
            style={{ width: 130, padding: '8px 12px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: 14 }}
          />
        </div>
      </div>

      <button style={{ marginTop: 16 }} onClick={submit} disabled={loading || !seed.trim()}>
        {loading ? 'Загрузка...' : submitLabel}
      </button>
    </section>
  )
}
