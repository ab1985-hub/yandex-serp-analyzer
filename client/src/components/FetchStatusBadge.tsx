import type { FetchStatusInfo } from '../types'

interface Props {
  status: FetchStatusInfo
  compact?: boolean
}

export function FetchStatusBadge({ status, compact = false }: Props) {
  let label: string
  let bg: string
  let color: string
  let title: string

  if (status.source === 'mock') {
    label = 'MOCK'
    bg = '#fef2f2'
    color = '#dc2626'
    title = 'Мок-данные (прямой съём не удался)'
  } else if (status.captcha) {
    label = 'CAPTCHA'
    bg = '#fef3c7'
    color = '#92400e'
    title = 'Яндекс вернул CAPTCHA: ' + status.error
  } else if (status.blocked) {
    label = 'BLOCKED'
    bg = '#fef2f2'
    color = '#dc2626'
    title = 'Запрос заблокирован: ' + status.error
  } else if (!status.success) {
    label = 'ОШИБКА'
    bg = '#fef2f2'
    color = '#dc2626'
    title = status.error || 'Съём не удался'
  } else {
    label = 'Яндекс'
    bg = '#f0fdf4'
    color = '#15803d'
    title = `Реальные данные · ${status.organic_found} орг. · ${status.ads_found} рекл. · стратегия: ${status.parse_strategy}`
  }

  return (
    <span
      title={title}
      style={{
        display: 'inline-block',
        padding: compact ? '1px 5px' : '2px 7px',
        borderRadius: 6,
        background: bg,
        color,
        fontSize: compact ? 10 : 11,
        fontWeight: 700,
        letterSpacing: '0.02em',
        border: `1px solid ${color}30`,
        cursor: 'help',
        userSelect: 'none',
      }}
    >
      {label}
    </span>
  )
}
