import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { EmptyState } from '../../../components/EmptyState'
import { ErrorState } from '../../../components/ErrorState'
import { FitBar } from '../../../components/FitBar'
import { Loading } from '../../../components/Loading'
import { RequirementMatrix } from '../../../components/RequirementMatrix'
import { RiskBadge } from '../../../components/RiskBadge'
import { jobsApi } from '../../../lib/api/endpoints'
import { useAsync } from '../../../lib/api/hooks'
import { label, money, runPath, studioPath, usd } from '../../../lib/format'

export function JobDetail() {
  const { jobId = '' } = useParams()
  const { data, error, loading, reload } = useAsync(() => jobsApi.get(jobId), [jobId])
  const [notice, setNotice] = useState('')
  const [problem, setProblem] = useState('')

  async function analyze() {
    setProblem('')
    try {
      await jobsApi.analyze(jobId)
      setNotice('Analysis started. Follow the progress in the run viewer.')
      window.setTimeout(reload, 4000)
    } catch (err) {
      setProblem(err instanceof Error ? err.message : 'Could not start the analysis.')
    }
  }

  if (loading && !data) return <Loading label="Loading job" />
  if (error && !data) return <ErrorState error={error} onRetry={reload} />
  if (!data) return null

  const { job, job_spec: spec, risk, fit, decision, price } = data
  const title = spec?.title ?? job.title ?? jobId
  const waitingForApproval = data.pending_approval?.kind === 'proposal' || data.status === 'awaiting_approval'

  return (
    <div className="page">
      <p>
        <Link to="/">Back to inbox</Link>
      </p>
      <div className="page-head">
        <h1>{title}</h1>
        <div className="button-row">
          <button type="button" onClick={() => void analyze()}>
            Analyze
          </button>
          {data.thread_id && <Link className="button" to={runPath(data.thread_id)}>Open run viewer</Link>}
          {waitingForApproval && data.thread_id && (
            <Link className="button primary" to={studioPath(data.thread_id)}>
              Review the proposal
            </Link>
          )}
        </div>
      </div>
      <div role="status">{notice && <p className="ok-text">{notice}</p>}</div>
      <div role="alert">{problem && <p className="error-text">{problem}</p>}</div>
      <p className="meta">
        <span className="badge">{label(data.status ?? 'new')}</span>
        {data.status_reason && <span className="muted">{data.status_reason}</span>}
      </p>

      {!spec && !fit && (
        <EmptyState title="This job has not been analysed yet">Press "Analyze" and the agents will read it, check the risks and score the fit.</EmptyState>
      )}

      {spec && (
        <section className="card" aria-labelledby="spec-heading">
          <h2 id="spec-heading">What the client wants</h2>
          <p>{spec.summary}</p>
          {spec.deliverables.length > 0 && (
            <>
              <h3>Deliverables</h3>
              <ul>{spec.deliverables.map((item) => <li key={item}>{item}</li>)}</ul>
            </>
          )}
          <p className="small">
            Payment: {label(spec.payment_type)}, {money(spec.budget_min)} to {money(spec.budget_max)}
            {spec.timeline && <> | Timeline: {spec.timeline}</>}
          </p>
          <p className="small">
            Skills: {[...spec.required_skills, ...spec.nice_to_have_skills].join(', ') || 'none listed'}
          </p>
          {spec.hidden_needs.length > 0 && (
            <>
              <h3>Needs between the lines</h3>
              <ul>{spec.hidden_needs.map((item) => <li key={item}>{item}</li>)}</ul>
            </>
          )}
        </section>
      )}

      {decision && (
        <section className="card" aria-labelledby="decision-heading">
          <h2 id="decision-heading">Bid or skip</h2>
          <p>
            Recommendation: <span className={`badge action-${decision.action}`}>{decision.action}</span>
          </p>
          <ul>{decision.reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul>
        </section>
      )}

      {fit && (
        <section className="card" aria-labelledby="fit-heading">
          <h2 id="fit-heading">How well you fit</h2>
          <FitBar score={fit.score} />
          <RequirementMatrix matches={fit.matches} evidence={data.evidence} />
          {fit.missing_skills.length > 0 && <p className="small">Skills you do not show yet: {fit.missing_skills.join(', ')}</p>}
        </section>
      )}

      {risk && (
        <section className="card" aria-labelledby="risk-heading">
          <h2 id="risk-heading">Risk report</h2>
          <RiskBadge score={risk.score} />
          {risk.injection_detected && <p className="error-text">The job text tried to give instructions to the agents. It was ignored.</p>}
          {risk.explanation && <p>{risk.explanation}</p>}
          {risk.flags.length === 0 && <p className="muted">No risk flags were raised.</p>}
          <ul className="plain-list">
            {risk.flags.map((flag, index) => (
              <li key={index}>
                <strong>{label(flag.kind)}</strong>
                <blockquote>{flag.evidence}</blockquote>
              </li>
            ))}
          </ul>
        </section>
      )}

      {price && (
        <section className="card" aria-labelledby="price-heading">
          <h2 id="price-heading">Price</h2>
          <p>
            Suggested: <strong>{money(price.amount, price.payment_type)}</strong> | Your floor {money(price.floor, price.payment_type)} | {price.connects_cost} Connects
            {!price.connects_worth_it && <span className="badge risk-medium">Connects may not be worth it</span>}
          </p>
          <p className="small muted">
            Market: {money(price.market_p25)} (low), {money(price.market_p50)} (middle), {money(price.market_p75)} (high)
          </p>
          <p>{price.rationale}</p>
        </section>
      )}

      {job.description && (
        <details className="card">
          <summary>Original job post</summary>
          <p className="preview">{job.description}</p>
        </details>
      )}
      <p className="muted small">
        Analysis cost so far: {data.tokens} tokens, {usd(data.usd)}
      </p>
    </div>
  )
}
