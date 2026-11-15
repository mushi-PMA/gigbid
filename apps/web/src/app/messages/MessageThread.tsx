import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ApprovalPanel } from '../../components/ApprovalPanel'
import { ErrorState } from '../../components/ErrorState'
import { Icon } from '../../components/Icon'
import { Loading } from '../../components/Loading'
import { messagesApi } from '../../lib/api/endpoints'
import { useAsync } from '../../lib/api/hooks'
import { formatTime, label, runPath } from '../../lib/format'
import type { MessageRequest } from '../../lib/types'

export function MessageThread() {
  const { threadId = '' } = useParams()
  const { data, error, loading, reload } = useAsync(() => messagesApi.get(threadId), [threadId], 10_000)
  const [notice, setNotice] = useState('')
  const [problem, setProblem] = useState('')

  async function draftReply() {
    setProblem('')
    try {
      await messagesApi.draft(threadId, data?.messages.find((m) => m.job_id)?.job_id ?? '')
      setNotice('Drafting a reply. It will appear below for your approval.')
      window.setTimeout(reload, 4000)
    } catch (err) {
      setProblem(err instanceof Error ? err.message : 'Could not start the draft.')
    }
  }

  if (loading && !data) return <Loading label="Loading the conversation" />
  if (error && !data) return <ErrorState error={error} onRetry={reload} />
  if (!data) return null

  return (
    <div className="page">
      <p>
        <Link className="back-link" to="/messages"><Icon name="back" size={16} />All messages</Link>
      </p>
      <div className="page-head">
        <h1>Conversation</h1>
        <div className="button-row">
          <button type="button" onClick={() => void draftReply()}>
            Draft reply
          </button>
          <Link className="button" to={runPath(data.graph_thread_id)}>
            Open run viewer
          </Link>
        </div>
      </div>
      <div role="status">{notice && <p className="ok-text">{notice}</p>}</div>
      <div role="alert">{problem && <p className="error-text">{problem}</p>}</div>

      {data.analysis && (
        <section className="card" aria-labelledby="intent-heading">
          <h2 id="intent-heading">What the client wants</h2>
          <p>
            <span className="badge">{label(data.analysis.intent)}</span> {data.analysis.summary}
          </p>
          {data.analysis.injection_detected && <p className="error-text">This message tried to give instructions to the agents. It was ignored.</p>}
        </section>
      )}

      <section className="card" aria-labelledby="messages-heading">
        <h2 id="messages-heading">Messages</h2>
        {data.messages.length === 0 && <p className="muted">No messages in this thread.</p>}
        <ul className="chat">
          {data.messages.map((message) => (
            <li key={message.message_id} className={`bubble from-${message.sender}`}>
              <div className="muted small">
                {message.sender === 'client' ? 'Client' : 'You'} {formatTime(message.sent_at)}
              </div>
              {message.text}
            </li>
          ))}
        </ul>
      </section>

      {data.pending_approval && <ReplyApproval request={data.pending_approval} graphThreadId={data.graph_thread_id} />}
      {!data.pending_approval && (
        <p className="muted">No reply is waiting. Press "Draft reply" to get a suggestion you can approve, edit or reject.</p>
      )}
    </div>
  )
}

function ReplyApproval({ request, graphThreadId }: { request: MessageRequest; graphThreadId: string }) {
  const original = request.reply.text
  const [text, setText] = useState(original)
  useEffect(() => setText(original), [original])

  return (
    <>
      <section className="card" aria-labelledby="reply-heading">
        <h2 id="reply-heading">Suggested reply</h2>
        <label htmlFor="reply-text">Reply text (you can edit it)</label>
        <textarea id="reply-text" rows={8} value={text} onChange={(e) => setText(e.target.value)} />
        {request.reply.proposed_slots.length > 0 && (
          <>
            <h3>Interview slots offered</h3>
            <div className="meta">{request.reply.proposed_slots.map((slot) => <span key={slot} className="badge"><Icon name="clock" size={13} />{formatTime(slot)}</span>)}</div>
          </>
        )}
        {request.compliance.violations.map((v) => (
          <p key={v.rule_id + v.text} className="inline-note compliance">
            <strong>Compliance ({label(v.rule_id)}):</strong> {v.fix || v.text}
          </p>
        ))}
      </section>
      <ApprovalPanel threadId={graphThreadId} dryRun={request.dry_run} editedText={text !== original ? text : null} />
    </>
  )
}
