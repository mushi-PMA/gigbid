import { Link } from 'react-router-dom'
import { EmptyState } from '../../components/EmptyState'
import { ErrorState } from '../../components/ErrorState'
import { Loading } from '../../components/Loading'
import { approvalsApi } from '../../lib/api/endpoints'
import { useAsync } from '../../lib/api/hooks'
import { formatTime, studioPath } from '../../lib/format'

export function Approvals() {
  const { data, error, loading, reload } = useAsync(() => approvalsApi.list(), [], 20_000)
  return (
    <div className="page">
      <h1>Waiting for your approval</h1>
      {loading && !data && <Loading />}
      {error && !data && <ErrorState error={error} onRetry={reload} />}
      {data && data.length === 0 && <EmptyState title="Nothing is waiting">When GigBid drafts a proposal or a reply, it shows up here.</EmptyState>}
      <ul className="job-list">
        {data?.map((item) => (
          <li key={item.thread_id} className="card job-row">
            <div className="job-main">
              <h2>{item.title}</h2>
              <div className="meta">
                <span className="badge">{item.kind === 'proposal' ? 'Proposal' : 'Message reply'}</span>
                {item.created_at && <span className="muted small">{formatTime(item.created_at)}</span>}
              </div>
            </div>
            <Link
              className="button primary"
              to={item.kind === 'proposal' ? studioPath(item.thread_id) : `/messages/${encodeURIComponent(item.request.kind === 'message' ? item.request.thread_id : item.thread_id)}`}
            >
              Review<span className="sr-only"> {item.title}</span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  )
}
