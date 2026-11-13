import { useState } from 'react'
import { Link } from 'react-router-dom'
import { EmptyState } from '../../components/EmptyState'
import { ErrorState } from '../../components/ErrorState'
import { FitBar } from '../../components/FitBar'
import { Loading } from '../../components/Loading'
import { RiskBadge } from '../../components/RiskBadge'
import { jobsApi, type InboxItem } from '../../lib/api/endpoints'
import { useAsync } from '../../lib/api/hooks'
import { label, money } from '../../lib/format'

export function Inbox() {
  const [showSkipped, setShowSkipped] = useState(false)
  const [status, setStatus] = useState('')
  const [action, setAction] = useState('')
  const [text, setText] = useState('')
  const [notice, setNotice] = useState('')
  const [problem, setProblem] = useState('')
  const jobs = useAsync(() => jobsApi.list(showSkipped), [showSkipped], 20_000)

  async function scoutNow() {
    setProblem('')
    try {
      await jobsApi.scout()
      setNotice('Scouting started. New jobs will appear here shortly.')
      window.setTimeout(jobs.reload, 4000)
    } catch (err) {
      setProblem(err instanceof Error ? err.message : 'Could not start scouting.')
    }
  }

  async function skip(job: InboxItem) {
    setProblem('')
    try {
      await jobsApi.skip(job.job_id)
      setNotice(`Skipped "${job.title}".`)
      jobs.reload()
    } catch (err) {
      setProblem(err instanceof Error ? err.message : 'Could not skip this job.')
    }
  }

  const all = jobs.data ?? []
  const statuses = [...new Set(all.map((job) => job.status))]
  const query = text.trim().toLowerCase()
  const visible = all.filter(
    (job) =>
      (!status || job.status === status) &&
      (!action || job.action === action) &&
      (!query || `${job.title} ${(job.skills ?? []).join(' ')}`.toLowerCase().includes(query)),
  )

  return (
    <div className="page">
      <div className="page-head">
        <h1>Job inbox</h1>
        <button type="button" className="primary" onClick={() => void scoutNow()}>
          Scout now
        </button>
      </div>
      <div role="status">{notice && <p className="ok-text">{notice}</p>}</div>
      <div role="alert">{problem && <p className="error-text">{problem}</p>}</div>

      <form className="filters" role="search" aria-label="Filter jobs" onSubmit={(e) => e.preventDefault()}>
        <div>
          <label htmlFor="filter-text">Search</label>
          <input id="filter-text" value={text} onChange={(e) => setText(e.target.value)} placeholder="Title or skill" />
        </div>
        <div>
          <label htmlFor="filter-status">Status</label>
          <select id="filter-status" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">All</option>
            {statuses.map((s) => (
              <option key={s} value={s}>
                {label(s)}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="filter-action">Recommended action</label>
          <select id="filter-action" value={action} onChange={(e) => setAction(e.target.value)}>
            <option value="">All</option>
            <option value="bid">Bid</option>
            <option value="watch">Watch</option>
            <option value="skip">Skip</option>
          </select>
        </div>
        <label className="inline-check">
          <input type="checkbox" checked={showSkipped} onChange={(e) => setShowSkipped(e.target.checked)} />
          Show skipped jobs
        </label>
      </form>

      {jobs.loading && !jobs.data && <Loading label="Loading jobs" />}
      {jobs.error && !jobs.data && <ErrorState error={jobs.error} onRetry={jobs.reload} />}
      {jobs.data && all.length === 0 && (
        <EmptyState title="No jobs yet">Press "Scout now" and GigBid will look for jobs that fit you.</EmptyState>
      )}
      {jobs.data && all.length > 0 && visible.length === 0 && <EmptyState title="No jobs match these filters" />}

      <ul className="job-list">
        {visible.map((job) => (
          <li key={job.job_id} className="card job-row">
            <div className="job-main">
              <h2>
                <Link to={`/jobs/${encodeURIComponent(job.job_id)}`}>{job.title}</Link>
              </h2>
              <div className="meta">
                <span className={`badge action-${job.action ?? 'none'}`}>{job.action ? `Recommended: ${job.action}` : 'Not analysed'}</span>
                <span className="badge">{label(job.status)}</span>
                <RiskBadge score={job.risk} flags={job.risk_flags} />
              </div>
              {job.status_reason && <p className="muted small">{job.status_reason}</p>}
            </div>
            <div className="job-side">
              <FitBar score={job.fit} />
              <div className="small">
                {job.price != null ? <>Suggested price {money(job.price, job.payment_type)}</> : <>Budget {money(job.budget_min)} to {money(job.budget_max)}</>}
                {job.connects_cost != null && <> | {job.connects_cost} Connects</>}
              </div>
              <div className="button-row">
                <Link className="button" to={`/jobs/${encodeURIComponent(job.job_id)}`}>
                  Open<span className="sr-only"> {job.title}</span>
                </Link>
                {job.status !== 'skipped' && (
                  <button type="button" onClick={() => void skip(job)}>
                    Skip<span className="sr-only"> {job.title}</span>
                  </button>
                )}
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}
