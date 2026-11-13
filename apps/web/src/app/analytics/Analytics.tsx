import { EmptyState } from '../../components/EmptyState'
import { ErrorState } from '../../components/ErrorState'
import { Loading } from '../../components/Loading'
import { analyticsApi } from '../../lib/api/endpoints'
import { useAsync } from '../../lib/api/hooks'
import { label, percent, seconds, usd } from '../../lib/format'
import type { CostStats } from '../../lib/types'

/** One CSS bar. `value` and `max` are numbers; the visible text always carries the real value. */
function Bar({ name, value, max, text }: { name: string; value: number; max: number; text: string }) {
  const width = max > 0 ? Math.min(100, (value / max) * 100) : 0
  return (
    <div className="bar-row">
      <span className="bar-label">{name}</span>
      <span className="bar-track" aria-hidden="true">
        <span className="bar-fill" style={{ width: `${width}%` }} />
      </span>
      <span className="bar-value">{text}</span>
    </div>
  )
}

function Budget({ name, stats, p95Budget, usdBudget }: { name: string; stats: CostStats; p95Budget?: number; usdBudget?: number }) {
  const overLatency = p95Budget != null && stats.p95_s != null && stats.p95_s > p95Budget
  const overCost = usdBudget != null && stats.mean_usd != null && stats.mean_usd > usdBudget
  return (
    <tr>
      <th scope="row">{name}</th>
      <td>{seconds(stats.p50_s)}</td>
      <td className={overLatency ? 'over' : ''}>
        {seconds(stats.p95_s)} <span className="muted small">(budget {p95Budget != null ? `${p95Budget} s` : 'n/a'})</span>
        {overLatency && <span className="sr-only"> over budget</span>}
      </td>
      <td className={overCost ? 'over' : ''}>
        {usd(stats.mean_usd)} <span className="muted small">(budget {usd(usdBudget)})</span>
        {overCost && <span className="sr-only"> over budget</span>}
      </td>
    </tr>
  )
}

export function Analytics() {
  const { data, error, loading, reload } = useAsync(() => analyticsApi.get(), [])
  if (loading && !data) return <Loading label="Loading analytics" />
  if (error && !data) return <ErrorState error={error} onRetry={reload} />
  if (!data) return null

  const categories = data.reply_and_hire_by_category
  const connects = Object.entries(data.connects_by_outcome)
  const maxConnects = Math.max(0, ...connects.map(([, n]) => n))
  const reasons = data.top_rejection_reasons
  const maxReason = Math.max(0, ...reasons.map(([, n]) => n))
  const declared = data.cost_latency.declared

  return (
    <div className="page">
      <h1>Analytics</h1>
      <p className="muted">{data.jobs_analysed} jobs analysed so far.</p>

      <section className="card" aria-labelledby="rates-heading">
        <h2 id="rates-heading">Reply and hire rate by category</h2>
        {categories.length === 0 && <EmptyState title="No sent proposals yet">Rates appear after your first proposals go out.</EmptyState>}
        {categories.map((row) => (
          <div key={row.category} className="rate-group">
            <strong>{label(row.category)}</strong> <span className="muted small">({row.sent} sent)</span>
            <Bar name="Replied" value={row.reply_rate} max={1} text={percent(row.reply_rate)} />
            <Bar name="Hired" value={row.hire_rate} max={1} text={percent(row.hire_rate)} />
          </div>
        ))}
      </section>

      <section className="card" aria-labelledby="connects-heading">
        <h2 id="connects-heading">Connects spent by outcome</h2>
        {connects.length === 0 && <p className="muted">No Connects spent yet.</p>}
        {connects.map(([stage, count]) => (
          <Bar key={stage} name={label(stage)} value={count} max={maxConnects} text={`${count} Connects`} />
        ))}
      </section>

      <section className="card" aria-labelledby="cost-heading">
        <h2 id="cost-heading">Speed and cost against the declared budgets</h2>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th scope="col">Work</th>
                <th scope="col">Typical time (p50)</th>
                <th scope="col">Slowest 5% (p95)</th>
                <th scope="col">Average cost</th>
              </tr>
            </thead>
            <tbody>
              <Budget name="Per job analysed" stats={data.cost_latency.per_job_analysed}
                p95Budget={declared.p95_latency_seconds_per_job_analysed} usdBudget={declared.usd_per_job_analysed} />
              <Budget name="Per proposal" stats={data.cost_latency.per_proposal}
                p95Budget={declared.p95_latency_seconds_per_proposal} usdBudget={declared.usd_per_proposal} />
            </tbody>
          </table>
        </div>
      </section>

      <section className="card" aria-labelledby="reasons-heading">
        <h2 id="reasons-heading">Top rejection reasons</h2>
        {reasons.length === 0 && <p className="muted">You have not rejected a draft yet.</p>}
        {reasons.map(([reason, count]) => (
          <Bar key={reason} name={reason} value={count} max={maxReason} text={String(count)} />
        ))}
      </section>
    </div>
  )
}
