import { useId, useState, type ReactNode } from 'react'
import type { Evidence } from '../lib/types'

interface Props {
  evidence: Evidence[]
  children: ReactNode
  className?: string
  /** Shown when there is no evidence to display. */
  emptyText?: string
}

/** Shows the evidence behind a claim or citation on hover and on keyboard focus. */
export function EvidenceHover({ evidence, children, className = '', emptyText = 'No evidence found for this.' }: Props) {
  const [open, setOpen] = useState(false)
  const id = useId()
  return (
    <span
      className={`evidence-hover ${className}`}
      tabIndex={0}
      aria-describedby={open ? id : undefined}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
      onKeyDown={(event) => event.key === 'Escape' && setOpen(false)}
    >
      {children}
      {open && (
        <span role="tooltip" id={id} className="evidence-pop">
          {evidence.length === 0 && <span className="muted">{emptyText}</span>}
          {evidence.map((item) => (
            <span key={item.evidence_id} className="evidence-item">
              <strong>{item.title || item.project || item.evidence_id}</strong>
              <span className="muted">
                {' '}
                {item.type}
                {item.date ? `, ${item.date}` : ''} ({item.evidence_id})
              </span>
              <span className="evidence-text">{item.text.length > 420 ? `${item.text.slice(0, 420)}...` : item.text}</span>
              {item.outcome && <span className="evidence-outcome">Outcome: {item.outcome}</span>}
            </span>
          ))}
        </span>
      )}
    </span>
  )
}
