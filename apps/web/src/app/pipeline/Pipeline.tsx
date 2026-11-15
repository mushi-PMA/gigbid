import type { CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import { EmptyState } from '../../components/EmptyState'
import { ErrorState } from '../../components/ErrorState'
import { Loading } from '../../components/Loading'
import { pipelineApi, type PipelineCard } from '../../lib/api/endpoints'
import { useAsync } from '../../lib/api/hooks'
import { formatTime, studioPath } from '../../lib/format'

const STAGES: PipelineCard['stage'][] = ['drafted', 'submitted', 'viewed', 'replied', 'interview', 'hired', 'lost']

function cardLink(card: PipelineCard): string {
  const graphThread = card.data?.graph_thread_id
  if (card.stage === 'drafted' && typeof graphThread === 'string') return studioPath(graphThread)
  return `/jobs/${encodeURIComponent(card.job_id)}`
}

export function Pipeline() {
  const { data, error, loading, reload } = useAsync(() => pipelineApi.list(), [], 20_000)
  return (
    <div className="page wide">
      <h1>Pipeline</h1>
      {loading && !data && <Loading />}
      {error && !data && <ErrorState error={error} onRetry={reload} />}
      {data && data.length === 0 && <EmptyState title="No proposals yet">Approved proposals show up here.</EmptyState>}
      {data && data.length > 0 && (
        <div className="board">
          {STAGES.map((stage) => {
            const cards = data.filter((card) => card.stage === stage)
            return (
              <section key={stage} className={`column stage-${stage}`} aria-labelledby={`col-${stage}`}>
                <h2 id={`col-${stage}`}>
                  {stage} <span className="count">{cards.length}</span>
                </h2>
                {cards.length === 0 && <div className="column-empty">No jobs</div>}
                {cards.map((card, index) => (
                  <article key={card.proposal_id} className="card pipeline-card" style={{ '--i': index } as CSSProperties}>
                    <Link to={cardLink(card)}>{card.title || card.job_id}</Link>
                    <div className="muted small">{formatTime(card.updated_at)}</div>
                  </article>
                ))}
              </section>
            )
          })}
        </div>
      )}
    </div>
  )
}
