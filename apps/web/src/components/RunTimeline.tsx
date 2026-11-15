import { useEffect, useState } from 'react'
import { label, seconds } from '../lib/format'
import type { RunEvent } from '../lib/types'

export type RunPhase = 'idle' | 'running' | 'waiting' | 'finished'

export function runPhase(events: RunEvent[]): RunPhase {
  const last = [...events].reverse().find((event) => event.type !== 'ping')
  if (!last) return 'idle'
  if (last.type === 'run_finished') return 'finished'
  if (last.type === 'awaiting_approval') return 'waiting'
  return 'running'
}

function describe(event: RunEvent): string {
  switch (event.type) {
    case 'run_started':
      return 'Run started'
    case 'awaiting_approval':
      return 'Waiting for your approval'
    case 'run_finished':
      return `Run finished${event.status ? ` (${label(event.status)})` : ''}`
    default:
      return label(event.node ?? 'step')
  }
}

/** Node-by-node progress. While a run is active it also shows what is happening and how long since the last step. */
export function RunTimeline({ events, lastEventAt }: { events: RunEvent[]; lastEventAt: number | null }) {
  const steps = events.filter((event) => event.type !== 'ping')
  const phase = runPhase(events)
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    if (phase !== 'running') return
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [phase])

  // one group per run of the thread: the latest stays open, earlier attempts fold away
  const runs: RunEvent[][] = []
  for (const event of steps) {
    if (event.type === 'run_started' || runs.length === 0) runs.push([])
    runs[runs.length - 1].push(event)
  }
  const latest = runs[runs.length - 1] ?? []
  const earlier = runs.slice(0, -1)

  return (
    <>
      {earlier.length > 0 && (
        <details className="disclosure earlier-runs">
          <summary>Earlier runs ({earlier.length})</summary>
          {earlier.map((run, index) => (
            <Steps key={index} events={run} />
          ))}
        </details>
      )}
      <Steps events={latest} live={phase === 'running' ? (lastEventAt ? Math.max(0, Math.round((now - lastEventAt) / 1000)) : -1) : null} />
    </>
  )
}

const QUIET = new Set(['running', 'ok', 'done', ''])

function Steps({ events, live = null }: { events: RunEvent[]; live?: number | null }) {
  return (
    <ol className="timeline" aria-label="Run progress" aria-live="polite">
      {events.map((event, index) => (
        <li key={index} className={`timeline-step step-${event.type}`}>
          <span className="timeline-dot" aria-hidden="true" />
          <span className="timeline-body">
            <strong>{describe(event)}</strong>
            {event.type === 'node' && event.status && !QUIET.has(event.status) && (
              <span className={`badge ${event.status === 'dead_letter' ? 'risk-high' : ''}`}>{label(event.status)}</span>
            )}
          </span>
          {event.type === 'node' && (
            <span className="timeline-meta">
              {seconds(event.seconds)}
              {event.tokens ? ` · ${event.tokens.toLocaleString()} tokens` : ''}
            </span>
          )}
        </li>
      ))}
      {live !== null && (
        <li className="timeline-step step-live">
          <span className="timeline-dot pulse" aria-hidden="true" />
          <span className="timeline-body muted">
            Working on the next step{live >= 0 ? ` (last update ${live} s ago)` : ''}
          </span>
        </li>
      )}
    </ol>
  )
}
