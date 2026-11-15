import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { approvalsApi } from '../lib/api/endpoints'
import { runPath } from '../lib/format'
import type { DryRun } from '../lib/types'

interface Props {
  threadId: string
  /** The preview built by the server for the original draft. */
  dryRun: DryRun | null
  /** The text the user wrote, or null when it is unchanged. Shown in the preview and sent as an edit. */
  editedText: string | null
  editedAnswers?: string[] | null
}

function previewText(dryRun: DryRun | null): string {
  const sent = dryRun?.payload ?? dryRun?.would_send ?? {}
  return String(sent.cover_letter ?? sent.text ?? '')
}

/** Dry-run preview plus the three decisions: approve, approve with edits, or reject with a reason. */
export function ApprovalPanel({ threadId, dryRun, editedText, editedAnswers = null }: Props) {
  const navigate = useNavigate()
  const dialog = useRef<HTMLDialogElement>(null)
  const [reason, setReason] = useState('')
  const [reasonError, setReasonError] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const edited = editedText !== null || editedAnswers !== null
  const connects = dryRun?.connects_cost ?? dryRun?.cost

  async function send(body: Parameters<typeof approvalsApi.decide>[1]) {
    setBusy(true)
    setError('')
    try {
      await approvalsApi.decide(threadId, body)
      navigate(runPath(threadId))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save your decision.')
      setBusy(false)
    }
  }

  function approve() {
    void send(
      edited
        ? { action: 'edit', reason: '', edited_text: editedText ?? undefined, edited_answers: editedAnswers ?? undefined }
        : { action: 'approve', reason: '' },
    )
  }

  function reject() {
    if (!reason.trim()) {
      setReasonError('Please say why you reject this. The reason helps GigBid learn.')
      return
    }
    void send({ action: 'reject', reason: reason.trim() })
  }

  return (
    <section className="card approval-panel" aria-labelledby="approval-heading">
      <h2 id="approval-heading">Your decision</h2>
      {dryRun && (
        <div className="dry-run">
          <p>
            Connects cost: <strong>{typeof connects === 'number' ? connects : (connects ?? 'unknown')}</strong>
          </p>
          <details className="disclosure">
            <summary>Preview exactly what will be sent</summary>
            <pre className="preview" aria-label="Message preview">
              {editedText ?? previewText(dryRun)}
            </pre>
            <details className="disclosure" style={{ marginTop: 10 }}>
              <summary>Marketplace payload</summary>
              <pre className="preview">{JSON.stringify(dryRun.marketplace ?? dryRun.payload ?? dryRun.would_send, null, 2)}</pre>
            </details>
          </details>
        </div>
      )}
      <p className="muted small">Nothing is sent until you approve.</p>
      {edited && <p className="note">You changed the text. Approving will send your edited version.</p>}
      <div className="button-row">
        <button type="button" className="primary" disabled={busy} onClick={approve}>
          {edited ? 'Approve my edited version' : 'Approve and send'}
        </button>
        <button type="button" className="danger" disabled={busy} onClick={() => dialog.current?.showModal()}>
          Reject
        </button>
      </div>
      <div role="alert">{error && <p className="error-text">{error}</p>}</div>

      <dialog ref={dialog} aria-labelledby="reject-title" className="modal">
        <form
          method="dialog"
          onSubmit={(event) => {
            event.preventDefault()
            reject()
          }}
        >
          <h3 id="reject-title">Reject this draft</h3>
          <label htmlFor="reject-reason">Reason (required)</label>
          <textarea
            id="reject-reason"
            rows={4}
            value={reason}
            aria-invalid={reasonError ? true : undefined}
            aria-describedby={reasonError ? 'reject-error' : undefined}
            onChange={(event) => {
              setReason(event.target.value)
              setReasonError('')
            }}
          />
          <div id="reject-error" role="alert">
            {reasonError && <p className="error-text">{reasonError}</p>}
          </div>
          <div className="button-row">
            <button type="button" onClick={() => dialog.current?.close()}>
              Cancel
            </button>
            <button type="submit" className="danger" disabled={busy}>
              Confirm rejection
            </button>
          </div>
        </form>
      </dialog>
    </section>
  )
}
