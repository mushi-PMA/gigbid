import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { AnnotatedParagraph } from '../../../components/AnnotatedParagraph'
import { ApprovalPanel } from '../../../components/ApprovalPanel'
import { EmptyState } from '../../../components/EmptyState'
import { ErrorState } from '../../../components/ErrorState'
import { Icon } from '../../../components/Icon'
import { Loading } from '../../../components/Loading'
import { RiskBadge } from '../../../components/RiskBadge'
import { approvalsApi } from '../../../lib/api/endpoints'
import { useAsync } from '../../../lib/api/hooks'
import { label, money, percent, runPath } from '../../../lib/format'
import type { Evidence, ProposalRequest } from '../../../lib/types'

const splitParagraphs = (text: string) => text.split(/\n\s*\n/)

function evidencePool(request: ProposalRequest): Map<string, Evidence> {
  const pool = new Map<string, Evidence>()
  for (const item of request.evidence ?? []) pool.set(item.evidence_id, item)
  for (const claim of request.claims) for (const item of claim.evidence ?? []) pool.set(item.evidence_id, item)
  return pool
}

export function ProposalStudio() {
  const { threadId = '' } = useParams()
  const { data, error, loading, reload } = useAsync(() => approvalsApi.get(threadId), [threadId])

  if (loading && !data) return <Loading label="Loading the proposal" />
  if (error?.status === 404 && !data) {
    return (
      <div className="page">
        <EmptyState title="Nothing is waiting for approval here">
          It may already be handled. <Link to="/approvals">See all pending approvals</Link> or{' '}
          <Link to={runPath(threadId)}>open the run viewer</Link>.
        </EmptyState>
      </div>
    )
  }
  if (error && !data) return <ErrorState error={error} onRetry={reload} />
  if (!data) return null
  if (data.request.kind !== 'proposal') {
    return (
      <div className="page">
        <EmptyState title="This approval is a message reply">
          <Link to={`/messages/${encodeURIComponent(data.request.thread_id)}`}>Open it in Messages</Link>
        </EmptyState>
      </div>
    )
  }
  return <StudioEditor threadId={threadId} request={data.request} />
}

function StudioEditor({ threadId, request }: { threadId: string; request: ProposalRequest }) {
  const originalText = request.draft.cover_letter
  const originalAnswers = useMemo(() => request.draft.screening_answers.map((a) => a.answer), [request])
  const [paragraphs, setParagraphs] = useState(() => splitParagraphs(originalText))
  const [answers, setAnswers] = useState(originalAnswers)
  const [editing, setEditing] = useState(false)
  const [regenerating, setRegenerating] = useState<number | null>(null)
  const [problem, setProblem] = useState('')
  const pool = useMemo(() => evidencePool(request), [request])

  useEffect(() => {
    setParagraphs(splitParagraphs(originalText))
    setAnswers(originalAnswers)
  }, [originalText, originalAnswers])

  const text = paragraphs.join('\n\n')
  const changed = text !== originalText || answers.some((a, i) => a !== originalAnswers[i])
  const violations = request.compliance?.violations ?? []
  const unplaced = violations.filter((v) => !paragraphs.some((p) => p.includes(v.text)))
  const supported = request.claims.filter((claim) => claim.status === 'supported').length

  async function regenerate(index: number) {
    setRegenerating(index)
    setProblem('')
    try {
      const result = await approvalsApi.regenerate(threadId, index)
      setParagraphs((current) => current.map((p, i) => (i === index ? result.text : p)))
    } catch (err) {
      setProblem(err instanceof Error ? err.message : 'Could not rewrite this paragraph.')
    } finally {
      setRegenerating(null)
    }
  }

  return (
    <div className="page">
      <div className="crumbs">
        <Link className="back-link" to="/approvals"><Icon name="back" size={16} />All approvals</Link>
        <Link className="back-link" to={`/jobs/${encodeURIComponent(request.job.job_id)}`}>Job details</Link>
      </div>
      <h1>Proposal for {request.job.title}</h1>

      <div className="studio">
        <div className="stack">
          <section className="card" aria-labelledby="draft-heading">
            <div className="page-head">
              <h2 id="draft-heading">Cover letter</h2>
              <button type="button" aria-pressed={editing} onClick={() => setEditing((on) => !on)}>
                {editing ? 'Back to evidence view' : 'Edit draft'}
              </button>
            </div>
            <p className="hint"><Icon name="spark" size={14} />Hover a citation or an underlined claim to see its evidence.</p>

            {request.critique && (request.critique.issues.length > 0 || request.critique.instructions) && (
              <details className="note disclosure" aria-label="Critic comments">
                <summary>
                  Critic notes ({request.critique.issues.length + (request.critique.instructions ? 1 : 0)})
                </summary>
                <ul>
                  {request.critique.issues.map((issue) => <li key={issue}>{issue}</li>)}
                  {request.critique.instructions && <li>{request.critique.instructions}</li>}
                </ul>
              </details>
            )}

            {editing ? (
              <>
                <label htmlFor="draft-text">Cover letter text</label>
                <textarea id="draft-text" rows={16} value={text} onChange={(e) => setParagraphs(splitParagraphs(e.target.value))} />
                {request.draft.screening_answers.map((item, index) => (
                  <div key={item.question}>
                    <label htmlFor={`answer-${index}`}>{item.question}</label>
                    <textarea id={`answer-${index}`} rows={4} value={answers[index] ?? ''}
                      onChange={(e) => setAnswers((current) => current.map((a, i) => (i === index ? e.target.value : a)))} />
                  </div>
                ))}
              </>
            ) : (
              <div className="draft">
                {paragraphs.map((paragraph, index) => (
                  <div key={index} className="draft-paragraph">
                    <AnnotatedParagraph text={paragraph} claims={request.claims} evidence={pool} />
                    {violations.filter((v) => paragraph.includes(v.text)).map((v) => (
                      <p key={v.rule_id + v.text} className="inline-note compliance">
                        <strong>Compliance ({label(v.rule_id)}):</strong> {v.fix || `"${v.text}" may break a marketplace rule.`}
                      </p>
                    ))}
                    <button type="button" className="icon-button regen" disabled={regenerating !== null}
                      title="Regenerate this paragraph" onClick={() => void regenerate(index)}>
                      {regenerating === index ? <span className="spinner" aria-hidden="true" /> : <Icon name="refresh" size={15} />}
                      <span className="sr-only">{regenerating === index ? 'Rewriting' : 'Regenerate paragraph'} {index + 1}</span>
                    </button>
                  </div>
                ))}
                {request.draft.screening_answers.length > 0 && <h3>Screening answers</h3>}
                {request.draft.screening_answers.map((item, index) => (
                  <div key={item.question}>
                    <strong>{item.question}</strong>
                    <AnnotatedParagraph text={answers[index] ?? item.answer} claims={[]} evidence={pool} />
                  </div>
                ))}
              </div>
            )}

            {unplaced.length > 0 && (
              <div className="note">
                <strong>Compliance notes</strong>
                <ul>{unplaced.map((v) => <li key={v.rule_id + v.text}>{label(v.rule_id)}: {v.fix || v.text}</li>)}</ul>
              </div>
            )}
            {request.compliance && !request.compliance.allowed && (
              <p className="error-text" role="alert">Compliance blocked this draft: {request.compliance.blocked_reason}</p>
            )}
            <div role="alert">{problem && <p className="error-text">{problem}</p>}</div>
          </section>

          <ApprovalPanel
            threadId={threadId}
            dryRun={request.dry_run}
            editedText={changed ? text : null}
            editedAnswers={changed ? answers : null}
          />
        </div>

        <aside className="stack" aria-label="Why this draft">
          <section className="card">
            <h2>Why bid</h2>
            <div className="facts">
              <div className="fact"><span>Fit</span><strong>{percent(request.fit.score)}</strong></div>
              <div className="fact"><span>Price</span><strong>{money(request.price.amount, request.price.payment_type)}</strong></div>
              <div className="fact"><span>Connects</span><strong>{request.price.connects_cost}</strong></div>
            </div>
            <RiskBadge score={request.risk.score} />
            <ul className="reasons" style={{ marginTop: 14 }}>
              {request.decision.reasons.map((reason) => (
                <li key={reason}><Icon name="check" size={15} /><span>{reason}</span></li>
              ))}
            </ul>
            {request.price.rationale && (
              <details className="disclosure" style={{ marginTop: 12 }}>
                <summary>How the price was set</summary>
                <p className="small muted">{request.price.rationale}</p>
              </details>
            )}
          </section>
          <section className="card">
            <h2>Claims and evidence</h2>
            {request.claims.length === 0 && <p className="muted">No claims recorded.</p>}
            {request.claims.length > 0 && (
              <div className="claims-summary">
                <div className="fitbar-track" aria-hidden="true">
                  <div className="fitbar-fill" style={{ width: `${(100 * supported) / request.claims.length}%`, background: 'var(--ok)' }} />
                </div>
                <span><strong className="num">{supported} of {request.claims.length}</strong> supported</span>
              </div>
            )}
            <ul className="plain-list">
              {request.claims.map((claim) => (
                <li key={claim.text} className="claim-row" title={claim.reason || label(claim.status)}>
                  <span className={`status-dot ${claim.status}`} aria-hidden="true" />
                  <span><span className="sr-only">{label(claim.status)}: </span>{claim.text}</span>
                </li>
              ))}
            </ul>
          </section>
        </aside>
      </div>
    </div>
  )
}
