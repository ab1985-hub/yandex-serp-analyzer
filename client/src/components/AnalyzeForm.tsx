import { useRef, useState } from 'react'
import { uploadKeywordsFile } from '../services/api'
import { RegionSelector } from './RegionSelector'

interface Props {
  loading: boolean
  regionId: number
  regionName: string
  onRegionChange: (id: number, name: string) => void
  onSubmit: (keywords: string[], minusPhrases: string[]) => void
}

export function SearchForm({ loading, regionId, regionName, onRegionChange, onSubmit }: Props) {
  const [keywordsInput, setKeywordsInput] = useState('')
  const [minusInput, setMinusInput] = useState('')
  const [fileInfo, setFileInfo] = useState('')
  const [uploading, setUploading] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  const parseKeywords = (text: string) =>
    text.split(/\r?\n|,|;/).map(s => s.trim()).filter(Boolean)

  const handleFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    try {
      const kws = await uploadKeywordsFile(file)
      setKeywordsInput(kws.join('\n'))
      setFileInfo(`Загружено ${kws.length} ключей из ${file.name}`)
    } catch (err) {
      setFileInfo(`Ошибка: ${err instanceof Error ? err.message : err}`)
    } finally {
      setUploading(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  const submit = () => {
    onSubmit(
      parseKeywords(keywordsInput),
      parseKeywords(minusInput),
    )
  }

  return (
    <section className="card">
      <h2>Параметры анализа</h2>

      <label>Список ключевых слов</label>
      <textarea
        rows={6}
        placeholder="Введите ключевые слова: по одному на строку или через запятую"
        value={keywordsInput}
        onChange={e => setKeywordsInput(e.target.value)}
      />

      <label>Загрузка файла (.txt, .csv, .xlsx)</label>
      <input ref={fileRef} type="file" accept=".txt,.csv,.xlsx" onChange={handleFile} />
      {uploading && <div style={{ fontSize: 13, color: '#6b7280' }}>Загрузка файла...</div>}
      {fileInfo && <div style={{ fontSize: 13, color: '#374151' }}>{fileInfo}</div>}
      {keywordsInput && (
        <div style={{ fontSize: 12, color: '#6b7280', marginTop: 4 }}>
          Ключей: {parseKeywords(keywordsInput).length}
        </div>
      )}

      <label style={{ marginTop: 12 }}>Минус-фразы (по одной на строку)</label>
      <textarea
        rows={3}
        placeholder="бесплатно&#10;фото&#10;видео"
        value={minusInput}
        onChange={e => setMinusInput(e.target.value)}
      />

      <label style={{ marginTop: 12 }}>Регион поиска</label>
      <RegionSelector
        regionId={regionId}
        regionName={regionName}
        onChange={onRegionChange}
      />

      <button style={{ marginTop: 16 }} onClick={submit} disabled={loading || uploading}>
        {loading ? 'Выполняется анализ...' : 'Запустить анализ'}
      </button>
    </section>
  )
}
