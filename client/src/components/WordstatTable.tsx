import { useEffect, useState } from 'react'
import * as XLSX from 'xlsx'
import type { WordstatKeyword, KeywordItem } from '../types'

const PAGE_SIZE_OPTIONS = [25, 50, 100]

interface Props {
  keywords: WordstatKeyword[]
  onSendToAnalysis: (keywords: KeywordItem[]) => void
  onAddMinusWords: (words: string[]) => void
  seedKeyword?: string
  regionName?: string
  loading?: boolean
}

function tokenize(phrase: string): string[] {
  return phrase
    .split(/\s+/)
    .map(w => w.replace(/^[^a-zA-Zа-яёА-ЯЁ0-9]+|[^a-zA-Zа-яёА-ЯЁ0-9]+$/g, ''))
    .filter(Boolean)
}

function slugify(s: string): string {
  return s.trim().toLowerCase().replace(/\s+/g, '-').replace(/[^\wа-яёА-ЯЁ-]/g, '').slice(0, 40)
}

export function WordstatTable({
  keywords,
  onSendToAnalysis,
  onAddMinusWords,
  seedKeyword = '',
  regionName = '',
  loading = false,
}: Props) {
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [selectedWords, setSelectedWords] = useState<Set<string>>(new Set())
  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useState(50)
  const [activeBtn, setActiveBtn] = useState<'all' | 'selected' | null>(null)
  const [sentMsg, setSentMsg] = useState<string | null>(null)

  // Reset to first page when keyword list changes
  useEffect(() => { setPage(0) }, [keywords])

  // Clear the "sent" banner once loading finishes
  useEffect(() => { if (!loading) setSentMsg(null) }, [loading])

  if (!keywords.length) return null

  const totalPages = Math.max(1, Math.ceil(keywords.length / pageSize))
  const safePage = Math.min(page, totalPages - 1)
  const pageStart = safePage * pageSize
  const pageEnd = Math.min(pageStart + pageSize, keywords.length)
  const pageRows = keywords.slice(pageStart, pageEnd)

  // Selection helpers
  const allPageSelected = pageRows.length > 0 && pageRows.every(k => selected.has(k.keyword))
  const somePageSelected = pageRows.some(k => selected.has(k.keyword))
  const someSelected = selected.size > 0
  const allSelected = selected.size === keywords.length
  const someWords = selectedWords.size > 0

  const toggleRow = (kw: string) => {
    const next = new Set(selected)
    if (next.has(kw)) next.delete(kw)
    else next.add(kw)
    setSelected(next)
  }

  const togglePageAll = () => {
    const next = new Set(selected)
    if (allPageSelected) {
      pageRows.forEach(k => next.delete(k.keyword))
    } else {
      pageRows.forEach(k => next.add(k.keyword))
    }
    setSelected(next)
  }

  const selectAllFiltered = () => setSelected(new Set(keywords.map(k => k.keyword)))
  const clearSelection = () => setSelected(new Set())

  const toggleWord = (word: string) => {
    const key = word.toLowerCase()
    const next = new Set(selectedWords)
    if (next.has(key)) next.delete(key)
    else next.add(key)
    setSelectedWords(next)
  }

  const handleAddMinus = () => {
    onAddMinusWords(Array.from(selectedWords))
    setSelectedWords(new Set())
  }

  const handlePageSize = (n: number) => {
    setPageSize(n)
    setPage(0)
  }

  // --- Exports ---
  const exportCsv = () => {
    const rows = [['Ключ', 'Частотность'], ...keywords.map(k => [k.keyword, k.frequency])]
    const csv = rows.map(r => r.join(',')).join('\n')
    const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = 'wordstat.csv'; a.click()
    URL.revokeObjectURL(url)
  }

  const exportXlsx = () => {
    const ws = XLSX.utils.aoa_to_sheet([
      ['Ключ', 'Частотность'],
      ...keywords.map(k => [k.keyword, k.frequency]),
    ])
    ws['!cols'] = [{ wch: 50 }, { wch: 16 }]
    const wb = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(wb, ws, 'Wordstat')
    const dateStr = new Date().toISOString().slice(0, 10)
    const seed = slugify(seedKeyword) || 'export'
    const region = slugify(regionName)
    const filename = region ? `wordstat_${seed}_${region}_${dateStr}.xlsx` : `wordstat_${seed}_${dateStr}.xlsx`
    XLSX.writeFile(wb, filename)
  }

  const handleSendAll = () => {
    setActiveBtn('all')
    setSentMsg(`✓ Отправлено ${keywords.length} ключей на анализ — результаты появятся ниже`)
    setTimeout(() => setActiveBtn(null), 250)
    onSendToAnalysis(keywords.map(k => ({ keyword: k.keyword, frequency: k.frequency })))
  }

  const handleSendSelected = () => {
    setActiveBtn('selected')
    setSentMsg(`✓ Отправлено ${selected.size} выбранных ключей на анализ — результаты появятся ниже`)
    setTimeout(() => setActiveBtn(null), 250)
    onSendToAnalysis(keywords.filter(k => selected.has(k.keyword)).map(k => ({ keyword: k.keyword, frequency: k.frequency })))
  }

  const btnBase: React.CSSProperties = {
    padding: '6px 12px',
    fontSize: 13,
    borderRadius: 6,
    cursor: 'pointer',
    border: '1px solid #d1d5db',
    background: '#f9fafb',
    color: '#374151',
    marginTop: 0,
    width: 'auto',
    transition: 'all 0.15s',
  }

  return (
    <section className="card">
      {/* Header row */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 10, flexWrap: 'wrap', gap: 8 }}>
        <div>
          <h2 style={{ margin: '0 0 4px' }}>
            Ключи Wordstat&nbsp;
            <span style={{ color: '#6b7280', fontWeight: 400 }}>({keywords.length})</span>
          </h2>
          <p style={{ margin: 0, fontSize: 12, color: '#6b7280' }}>
            Кликайте по словам внутри фраз, чтобы добавить их в минус-слова
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <button onClick={exportCsv} style={btnBase}>Экспорт CSV</button>
          <button onClick={exportXlsx} style={{ ...btnBase, color: '#15803d', borderColor: '#86efac' }}>
            Экспорт XLSX
          </button>
          <button
            onClick={handleSendAll}
            style={{
              ...btnBase,
              background: activeBtn === 'all' ? '#1e40af' : '#1d4ed8',
              color: '#fff',
              border: 'none',
              transform: activeBtn === 'all' ? 'scale(0.96)' : 'scale(1)',
              boxShadow: activeBtn === 'all' ? 'inset 0 2px 4px rgba(0,0,0,0.2)' : '0 1px 3px rgba(0,0,0,0.15)',
            }}
          >
            Отправить все ({keywords.length}) в анализ
          </button>
          {someSelected && (
            <button
              onClick={handleSendSelected}
              style={{
                ...btnBase,
                background: activeBtn === 'selected' ? '#15803d' : '#16a34a',
                color: '#fff',
                border: 'none',
                transform: activeBtn === 'selected' ? 'scale(0.96)' : 'scale(1)',
                boxShadow: activeBtn === 'selected' ? 'inset 0 2px 4px rgba(0,0,0,0.2)' : '0 1px 3px rgba(0,0,0,0.15)',
              }}
            >
              Отправить выбранные ({selected.size}) в анализ
            </button>
          )}
          {someWords && (
            <button
              onClick={handleAddMinus}
              style={{ ...btnBase, background: '#dc2626', color: '#fff', border: 'none' }}
            >
              Исключить минус-слова ({selectedWords.size})
            </button>
          )}
        </div>
      </div>

      {/* "Sent to analysis" notification banner */}
      {sentMsg && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          marginBottom: 10,
          padding: '10px 14px',
          background: '#f0fdf4',
          border: '1px solid #86efac',
          borderRadius: 8,
          fontSize: 13,
          color: '#15803d',
          fontWeight: 500,
          animation: 'fadeIn 0.2s ease',
        }}>
          <span style={{ fontSize: 16 }}>✓</span>
          <span>{sentMsg.replace('✓ ', '')}</span>
          {loading && (
            <span style={{ marginLeft: 4, color: '#6b7280', fontWeight: 400 }}>
              — анализ выполняется...
            </span>
          )}
        </div>
      )}

      {/* Selected minus-words badge strip */}
      {someWords && (
        <div style={{ marginBottom: 10, padding: '8px 12px', background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 8, fontSize: 12 }}>
          <span style={{ color: '#991b1b', fontWeight: 600 }}>Выбранные слова: </span>
          {Array.from(selectedWords).map(w => (
            <span
              key={w}
              onClick={() => toggleWord(w)}
              style={{
                display: 'inline-block',
                margin: '0 4px 2px 0',
                padding: '2px 8px',
                background: '#fee2e2',
                border: '1px solid #fca5a5',
                borderRadius: 4,
                color: '#991b1b',
                cursor: 'pointer',
                fontWeight: 500,
              }}
            >
              {w} ×
            </span>
          ))}
        </div>
      )}

      {/* Pagination top bar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8, flexWrap: 'wrap', gap: 6 }}>
        {/* Left: selection actions + page size */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 12, color: '#6b7280' }}>Показывать:</span>
          {PAGE_SIZE_OPTIONS.map(n => (
            <button
              key={n}
              onClick={() => handlePageSize(n)}
              style={{
                ...btnBase,
                padding: '3px 10px',
                fontSize: 12,
                background: pageSize === n ? '#1d4ed8' : '#f9fafb',
                color: pageSize === n ? '#fff' : '#374151',
                border: pageSize === n ? 'none' : '1px solid #d1d5db',
                fontWeight: pageSize === n ? 700 : 400,
              }}
            >
              {n}
            </button>
          ))}
          {someSelected ? (
            <span style={{ fontSize: 12, color: '#374151', marginLeft: 4 }}>
              Выбрано: <b>{selected.size}</b>
              {!allSelected && (
                <button
                  onClick={selectAllFiltered}
                  style={{ marginLeft: 8, fontSize: 11, color: '#1d4ed8', background: 'none', border: 'none', cursor: 'pointer', padding: 0, textDecoration: 'underline' }}
                >
                  Выбрать все {keywords.length}
                </button>
              )}
              <button
                onClick={clearSelection}
                style={{ marginLeft: 8, fontSize: 11, color: '#dc2626', background: 'none', border: 'none', cursor: 'pointer', padding: 0, textDecoration: 'underline' }}
              >
                Снять выбор
              </button>
            </span>
          ) : (
            <button
              onClick={selectAllFiltered}
              style={{ fontSize: 11, color: '#6b7280', background: 'none', border: 'none', cursor: 'pointer', padding: 0, textDecoration: 'underline', marginLeft: 4 }}
            >
              Выбрать все {keywords.length}
            </button>
          )}
        </div>

        {/* Right: pagination info + nav */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
          <span style={{ color: '#6b7280' }}>
            {pageStart + 1}–{pageEnd} из {keywords.length} · Стр. {safePage + 1} / {totalPages}
          </span>
          <button
            onClick={() => setPage(p => Math.max(0, p - 1))}
            disabled={safePage === 0}
            style={{ ...btnBase, padding: '4px 10px', fontSize: 13, opacity: safePage === 0 ? 0.4 : 1 }}
          >
            ← Назад
          </button>
          <button
            onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
            disabled={safePage >= totalPages - 1}
            style={{ ...btnBase, padding: '4px 10px', fontSize: 13, opacity: safePage >= totalPages - 1 ? 0.4 : 1 }}
          >
            Вперёд →
          </button>
        </div>
      </div>

      {/* Table */}
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead>
            <tr style={{ background: '#f9fafb', borderBottom: '2px solid #e5e7eb' }}>
              <th style={{ width: 40, padding: '8px 10px', textAlign: 'center' }}>
                <input
                  type="checkbox"
                  checked={allPageSelected}
                  ref={el => { if (el) el.indeterminate = somePageSelected && !allPageSelected }}
                  onChange={togglePageAll}
                  style={{ cursor: 'pointer' }}
                  title="Выбрать/снять всё на текущей странице"
                />
              </th>
              <th style={{ padding: '8px 10px', textAlign: 'left', fontWeight: 600, color: '#374151' }}>
                Ключ
                <span style={{ marginLeft: 6, fontWeight: 400, fontSize: 11, color: '#9ca3af' }}>
                  (кликайте по словам)
                </span>
              </th>
              <th style={{ padding: '8px 10px', textAlign: 'right', fontWeight: 600, color: '#374151', width: 120 }}>
                Частотность
              </th>
            </tr>
          </thead>
          <tbody>
            {pageRows.map((k, i) => {
              const rowChecked = selected.has(k.keyword)
              const words = tokenize(k.keyword)
              return (
                <tr
                  key={k.keyword}
                  style={{
                    borderBottom: '1px solid #f3f4f6',
                    background: rowChecked ? '#eff6ff' : i % 2 === 0 ? '#fff' : '#fafafa',
                  }}
                >
                  <td
                    style={{ padding: '7px 10px', textAlign: 'center' }}
                    onClick={() => toggleRow(k.keyword)}
                  >
                    <input
                      type="checkbox"
                      checked={rowChecked}
                      onChange={() => toggleRow(k.keyword)}
                      onClick={e => e.stopPropagation()}
                      style={{ cursor: 'pointer' }}
                    />
                  </td>
                  <td style={{ padding: '7px 10px', color: '#1f2937' }}>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '3px 2px', alignItems: 'center' }}>
                      {words.map((word, wi) => {
                        const wKey = word.toLowerCase()
                        const wSel = selectedWords.has(wKey)
                        return (
                          <span
                            key={wi}
                            onClick={e => { e.stopPropagation(); toggleWord(wKey) }}
                            title={wSel ? 'Снять выделение' : 'Добавить в минус-слова'}
                            style={{
                              cursor: 'pointer',
                              padding: '1px 5px',
                              borderRadius: 4,
                              fontSize: 12,
                              userSelect: 'none',
                              background: wSel ? '#fee2e2' : 'transparent',
                              color: wSel ? '#b91c1c' : '#1f2937',
                              border: wSel ? '1px solid #fca5a5' : '1px solid transparent',
                              fontWeight: wSel ? 600 : 400,
                              transition: 'all 0.1s',
                            }}
                            onMouseEnter={e => {
                              if (!wSel) {
                                (e.currentTarget as HTMLSpanElement).style.background = '#f3f4f6'
                                ;(e.currentTarget as HTMLSpanElement).style.borderColor = '#d1d5db'
                              }
                            }}
                            onMouseLeave={e => {
                              if (!wSel) {
                                (e.currentTarget as HTMLSpanElement).style.background = 'transparent'
                                ;(e.currentTarget as HTMLSpanElement).style.borderColor = 'transparent'
                              }
                            }}
                          >
                            {word}
                          </span>
                        )
                      })}
                    </div>
                  </td>
                  <td style={{ padding: '7px 10px', textAlign: 'right', color: '#6b7280', fontVariantNumeric: 'tabular-nums' }}>
                    {k.frequency.toLocaleString('ru-RU')}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Pagination bottom bar */}
      {totalPages > 1 && (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 8, marginTop: 10, fontSize: 13 }}>
          <span style={{ color: '#6b7280' }}>
            {pageStart + 1}–{pageEnd} из {keywords.length} · Стр. {safePage + 1} / {totalPages}
          </span>
          <button
            onClick={() => setPage(p => Math.max(0, p - 1))}
            disabled={safePage === 0}
            style={{ ...btnBase, padding: '4px 10px', fontSize: 13, opacity: safePage === 0 ? 0.4 : 1 }}
          >
            ← Назад
          </button>
          <button
            onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
            disabled={safePage >= totalPages - 1}
            style={{ ...btnBase, padding: '4px 10px', fontSize: 13, opacity: safePage >= totalPages - 1 ? 0.4 : 1 }}
          >
            Вперёд →
          </button>
        </div>
      )}
    </section>
  )
}
