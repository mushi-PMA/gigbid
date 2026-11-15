import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { EmptyState } from '../../../components/EmptyState'
import { ErrorState } from '../../../components/ErrorState'
import { RunTimeline, runPhase } from '../../../components/RunTimeline'
import { runsApi } from '../../../lib/api/endpoints'
import { useAsync } from '../../../lib/api/hooks'
import { formatTime, label, studioPath } from '../../../lib/format'
import type { RunEvent } from '../../../lib/types'

const EVENT_NAMES: RunEvent['type'][] = ['run_started', 'node', 'awaiting_approval', 'run_finished', 'ping']
const API_BASE = import.meta.env.VITE_API_URL ?? ''

/** Adds events to the list, skipping any that we already have (the stream replays history on connect). */
function mergeEvents(current: RunEvent[], incoming: RunEvent[]): RunEvent[] {
  const seen = new Set(current.map((event) => JSON.stringify(event)))
  const fresh = incoming.filter((event) => event.type !== 'ping' && !seen.has(JSON.stringify(event)))
  return fresh.length ? [...current, ...fresh] : current
}

/** Where the user decides, depending on the kind of thread. */
function approvalLink(threadId: string): string {
  return threadId.startsWith('conv:')
    ? `/messages/${encodeURIComponent(threadId.split(':').slice(2).join(':'))}`
    : studioPath(threadId)
}

export function RunViewer() {
  const { threadId = '' } = useParams()
  const info = useAsync(() => runsApi.get(threadId), [threadId])
  const [events, setEvents] = useState<RunEvent[]>([])
  const [lastEventAt, setLastEventAt] = useState<number | null>(null)
  const [connection, setConnection] = useState<'connecting' | 'live' | 'reconnecting'>('connecting')
  const [notice, setNotice] = useState('')
  const [problem, setProblem] = useState('')
  const { reload } = info

  useEffect(() => {
    setEvents([])
    const source = new EventSource(`${API_BASE}/api/runs/${encodeURIComponent(threadId)}/stream`, { withCredentials: true })
    const onEvent = (message: MessageEvent<string>) => {
      let event: RunEvent
      try {
        event = JSON.parse(message.data) as RunEvent
      } catch {
        return
      }
      setConnection('live')
      if (event.type === 'ping') return
      setLastEventAt(Date.now())
      setEvents((current) => mergeEvents(current, [event]))
      if (event.type === 'run_finished' || event.type === 'awaiting_approval') reload()
    }
    EVENT_NAMES.forEach((name) => source.addEventListener(name, onEvent as EventListener))
    source.onopen = () => setConnection('live')
    source.onerror = () => setConnection('reconnecting')
    return () => source.close()
  }, [threadId, reload])

  // Events already stored on the server show up even if the live stream is slow to connect.
  useEffect(() => {
    const stored = (info.data?.events ?? []) as unknown as RunEvent[]
    if (stored.length) setEvents((current) => mergeEvents(stored, current))
  }, [info.data])

  const replay = useCallback(
    async (checkpointId: string) => {
      setProblem('')
      try {
        await runsApi.replay(threadId, checkpointId)
        setNotice('Replay started. New steps will appear in the timeline.')
        setEvents([])
        reload()
      } catch (err) {
        setProblem(err instanceof Error ? err.message : 'Could not replay from this step.')
      }
    },
    [threadId, reload],
  )

  const phase = runPhase(events)
  const phaseText = {
    idle: 'Waiting for the first update. Nothing is wrong, the run may not have started yet.',
    running: 'The agents are working.',
    waiting: 'The agents finished their draft and are waiting for you.',
    finished: 'The run is finished.',
  }[phase]

  return (
    <div className="page">
      <div className="page-head">
        <h1>Agent run</h1>
        <div className="button-row">
          {(phase === 'waiting' || info.data?.history?.[0]?.status === 'awaiting_approval') && (
            <Link className="button primary" to={approvalLink(threadId)}>
              Review and decide
            </Link>
          )}
          {info.data?.trace_url && (
            <a className="button" href={info.data.trace_url} target="_blank" rel="noreferrer">
              Open full trace
            </a>
          )}
        </div>
      </div>
      <p className="muted small">Thread {threadId}</p>
      <p role="status">
        {phaseText} <span className="badge">{connection === 'live' ? 'Live' : connection === 'connecting' ? 'Connecting' : 'Reconnecting'}</span>
      </p>
      <div role="status">{notice && <p className="ok-text">{notice}</p>}</div>
      <div role="alert">{problem && <p className="error-text">{problem}</p>}</div>

      <section className="card" aria-labelledby="timeline-heading">
        <h2 id="timeline-heading">Progress</h2>
        {events.length === 0 && phase === 'idle' && (
          <p className="muted">No steps yet. This page updates by itself as soon as the first step finishes.</p>
        )}
        <RunTimeline events={events} lastEventAt={lastEventAt} />
      </section>

      <section className="card" aria-labelledby="history-heading">
        <h2 id="history-heading">History</h2>
        {info.error && !info.data && <ErrorState error={info.error} onRetry={info.reload} />}
        {info.data && (info.data.history ?? []).length === 0 && <EmptyState title="No checkpoints yet" />}
        {info.data && (info.data.history ?? []).length > 0 && (
          <div className="table-wrap">
            <table>
              <caption className="sr-only">Checkpoints</caption>
              <thead>
                <tr>
                  <th scope="col">Step</th>
                  <th scope="col">Next</th>
                  <th scope="col">Status</th>
                  <th scope="col">When</th>
                  <th scope="col">Replay</th>
                </tr>
              </thead>
              <tbody>
                {info.data.history?.map((step) => (
                  <tr key={step.checkpoint_id}>
                    <td>{step.step ?? ''}</td>
                    <td>{step.next.map(label).join(', ') || 'end'}</td>
                    <td>{step.status ? label(step.status) : ''}</td>
                    <td>{formatTime(step.created_at)}</td>
                    <td>
                      <button type="button" onClick={() => void replay(step.checkpoint_id)}>
                        Replay<span className="sr-only"> from step {step.step}</span>
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}
