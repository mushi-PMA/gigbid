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

  return (
    <ol className="timeline" aria-label="Run progress" aria-live="polite">
      {steps.map((event, index) => (
        <li key={index} className={`timeline-step step-${event.type}`}>
          <span className="timeline-dot" aria-hidden="true" />
          <span className="timeline-body">
            <strong>{describe(event)}</strong>
            {event.type === 'node' && (
              <span className="muted">
                {' '}
                {event.status ? `${label(event.status)}, ` : ''}
                {seconds(event.seconds)}
                {event.tokens != null ? `, ${event.tokens} tokens` : ''}
              </span>
            )}
          </span>
        </li>
      ))}
      {phase === 'running' && (
        <li className="timeline-step step-live">
          <span className="timeline-dot pulse" aria-hidden="true" />
          <span className="timeline-body muted">
            Working on the next step
            {lastEventAt ? ` (last update ${Math.max(0, Math.round((now - lastEventAt) / 1000))} s ago)` : ''}
          </span>
        </li>
      )}
    </ol>
  )
}
