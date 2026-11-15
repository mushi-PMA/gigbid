import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { EmptyState } from '../../../components/EmptyState'
import { ErrorState } from '../../../components/ErrorState'
import { FitBar } from '../../../components/FitBar'
import { Icon } from '../../../components/Icon'
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
      setNotice('Analysing. Follow it in the run viewer.')
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
    <div className="page wide-detail">
      <Link className="back-link" to="/"><Icon name="back" size={16} />Inbox</Link>
      <div className="page-head">
        <h1>{title}</h1>
        <div className="button-row">
          <button type="button" onClick={() => void analyze()}>
            <Icon name="refresh" size={16} />
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
        <span className={`badge status-${data.status ?? 'new'}`}>{label(data.status ?? 'new')}</span>
        {data.status_reason && <span className="muted small">{data.status_reason}</span>}
      </p>

      {!spec && !fit && <EmptyState title="Not analysed yet">Analyze to check risks and score your fit.</EmptyState>}

      <div className="studio">
        <div className="stack">
          {spec && (
            <section className="card" aria-labelledby="spec-heading">
              <h2 id="spec-heading">What the client wants</h2>
              {spec.summary && <p>{spec.summary}</p>}
              <div className="facts">
                <div className="fact"><span>Payment</span><strong>{label(spec.payment_type)}</strong></div>
                <div className="fact"><span>Budget</span><strong>{money(spec.budget_min)} to {money(spec.budget_max)}</strong></div>
                {spec.timeline && <div className="fact"><span>Timeline</span><strong>{spec.timeline}</strong></div>}
              </div>
              {spec.deliverables.length > 0 && (
                <>
                  <h3>Deliverables</h3>
                  <ul>{spec.deliverables.map((item) => <li key={item}>{item}</li>)}</ul>
                </>
              )}
              <h3>Skills</h3>
              <div className="meta">
                {[...spec.required_skills, ...spec.nice_to_have_skills].map((skill) => <span key={skill} className="badge">{skill}</span>)}
                {spec.required_skills.length + spec.nice_to_have_skills.length === 0 && <span className="muted">None listed</span>}
              </div>
              {spec.hidden_needs.length > 0 && (
                <details className="disclosure" style={{ marginTop: 14 }}>
                  <summary>Needs between the lines ({spec.hidden_needs.length})</summary>
                  <ul>{spec.hidden_needs.map((item) => <li key={item}>{item}</li>)}</ul>
                </details>
              )}
            </section>
          )}

          {fit && (
            <section className="card" aria-labelledby="fit-heading">
              <div className="page-head" style={{ marginBottom: 12 }}>
                <h2 id="fit-heading">How well you fit</h2>
                <div style={{ width: 200 }}><FitBar score={fit.score} /></div>
              </div>
              <RequirementMatrix matches={fit.matches} evidence={data.evidence} />
              {fit.missing_skills.length > 0 && (
                <p className="small muted" style={{ marginTop: 12 }}>Not shown yet: {fit.missing_skills.join(', ')}</p>
              )}
            </section>
          )}

          {risk && (
            <section className="card" aria-labelledby="risk-heading">
              <div className="page-head" style={{ marginBottom: 12 }}>
                <h2 id="risk-heading">Risk report</h2>
                <RiskBadge score={risk.score} />
              </div>
              {risk.injection_detected && (
                <p className="inline-note" style={{ marginBottom: 12 }}>The post tried to instruct the agents. Ignored.</p>
              )}
              {risk.flags.length === 0 && <p className="muted">No risk flags.</p>}
              <ul className="plain-list">
                {risk.flags.map((flag, index) => (
                  <li key={index}>
                    <strong>{label(flag.kind)}</strong>
                    <blockquote>{flag.evidence}</blockquote>
                  </li>
                ))}
              </ul>
              {risk.explanation && (
                <details className="disclosure" style={{ marginTop: 12 }}>
                  <summary>Assessment</summary>
                  <p className="small muted">{risk.explanation}</p>
                </details>
              )}
            </section>
          )}

          {job.description && (
            <details className="card">
              <summary>Original job post</summary>
              <p className="preview">{job.description}</p>
            </details>
          )}
        </div>

        <aside className="stack" aria-label="Decision">
          {decision && (
            <section className="card" aria-labelledby="decision-heading">
              <h2 id="decision-heading">Bid or skip</h2>
              <p>
                Recommendation: <span className={`badge action-${decision.action}`}>{decision.action}</span>
              </p>
              <ul className="reasons">
                {decision.reasons.map((reason) => (
                  <li key={reason}><Icon name="chevron" size={15} /><span>{reason}</span></li>
                ))}
              </ul>
            </section>
          )}
          {price && (
            <section className="card" aria-labelledby="price-heading">
              <h2 id="price-heading">Price</h2>
              <div className="facts">
                <div className="fact"><span>Suggested</span><strong>{money(price.amount, price.payment_type)}</strong></div>
                <div className="fact"><span>Your floor</span><strong>{money(price.floor, price.payment_type)}</strong></div>
                <div className="fact"><span>Connects</span><strong>{price.connects_cost}</strong></div>
              </div>
              {!price.connects_worth_it && <p><span className="badge risk-medium">Connects may not be worth it</span></p>}
              <p className="small muted">
                Market {money(price.market_p25)} · {money(price.market_p50)} · {money(price.market_p75)}
              </p>
              {price.rationale && (
                <details className="disclosure">
                  <summary>How it was set</summary>
                  <p className="small muted">{price.rationale}</p>
                </details>
              )}
            </section>
          )}
          <p className="muted small">
            Analysis so far: {data.tokens} tokens, {usd(data.usd)}
          </p>
        </aside>
      </div>
    </div>
  )
}
