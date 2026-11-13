import type { Evidence } from './types'

export const percent = (value: number | null | undefined) =>
  value == null ? 'n/a' : `${Math.round(value * 100)}%`

export const money = (value: number | null | undefined, type?: string | null) =>
  value == null ? 'n/a' : `$${Math.round(value).toLocaleString()}${type === 'hourly' ? '/hr' : ''}`

export const seconds = (value: number | null | undefined) => (value == null ? 'n/a' : `${value.toFixed(1)} s`)

export const usd = (value: number | null | undefined) => (value == null ? 'n/a' : `$${value.toFixed(4)}`)

export const label = (text: string) => text.replace(/_/g, ' ')

export function formatTime(iso: string | null | undefined): string {
  if (!iso) return ''
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleString()
}

/** Thread ids contain colons, so links always encode them. */
export const studioPath = (threadId: string) => `/studio/${encodeURIComponent(threadId)}`
export const runPath = (threadId: string) => `/runs/${encodeURIComponent(threadId)}`

/** Finds evidence for a citation such as [persona:cs:cs-aiml-03] (exact id first, then the last part of the id). */
export function findEvidence(citation: string, pool: Map<string, Evidence>): Evidence | undefined {
  const exact = pool.get(citation)
  if (exact) return exact
  const last = citation.split(':').pop() ?? citation
  for (const [id, item] of pool) if (id === last || id.endsWith(`:${last}`)) return item
  return undefined
}
