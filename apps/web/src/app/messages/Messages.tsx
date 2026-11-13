import { Link } from 'react-router-dom'
import { EmptyState } from '../../components/EmptyState'
import { ErrorState } from '../../components/ErrorState'
import { Loading } from '../../components/Loading'
import { messagesApi } from '../../lib/api/endpoints'
import { useAsync } from '../../lib/api/hooks'
import { formatTime, label } from '../../lib/format'

export function Messages() {
  const { data, error, loading, reload } = useAsync(() => messagesApi.threads(), [], 30_000)
  return (
    <div className="page">
      <h1>Client messages</h1>
      {loading && !data && <Loading />}
      {error && !data && <ErrorState error={error} onRetry={reload} />}
      {data && data.length === 0 && <EmptyState title="No client messages yet">When a client writes back, the thread shows up here.</EmptyState>}
      <ul className="job-list">
        {data?.map((thread) => (
          <li key={thread.thread_id} className="card job-row">
            <div className="job-main">
              <h2>
                <Link to={`/messages/${encodeURIComponent(thread.thread_id)}`}>Client {thread.client_id || thread.thread_id}</Link>
              </h2>
              <div className="meta">
                {thread.job_id && <span className="muted small">Job {thread.job_id}</span>}
                {thread.status && <span className="badge">{label(thread.status)}</span>}
                {(thread.unread ?? 0) > 0 && <span className="badge risk-medium">{thread.unread} unread</span>}
                <span className="muted small">{formatTime(thread.last_message_at)}</span>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}
