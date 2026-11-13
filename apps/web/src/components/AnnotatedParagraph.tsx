import type { ReactNode } from 'react'
import { EvidenceHover } from './EvidenceHover'
import { findEvidence } from '../lib/format'
import type { Claim, Evidence } from '../lib/types'

interface Props {
  text: string
  claims: Claim[]
  evidence: Map<string, Evidence>
}

const CITATION = /\[([A-Za-z0-9_.:-]+)\]/g

/** Text with each citation shown as a chip that reveals its evidence. Inside a claim the chip is plain text. */
function withCitations(text: string, evidence: Map<string, Evidence>, interactive: boolean): ReactNode[] {
  const parts: ReactNode[] = []
  let last = 0
  for (const match of text.matchAll(CITATION)) {
    const start = match.index ?? 0
    const found = findEvidence(match[1], evidence)
    parts.push(text.slice(last, start))
    parts.push(
      !found ? (
        match[0]
      ) : interactive ? (
        <EvidenceHover key={start} className="chip citation" evidence={[found]}>
          {match[0]}
        </EvidenceHover>
      ) : (
        <span key={start} className="chip citation">
          {match[0]}
        </span>
      ),
    )
    last = start + match[0].length
  }
  parts.push(text.slice(last))
  return parts
}

/** One paragraph of the draft. Every claim gets its evidence on hover and on focus, and every citation too. */
export function AnnotatedParagraph({ text, claims, evidence }: Props) {
  const spans = claims
    .map((claim) => ({ claim, start: text.indexOf(claim.text.trim()) }))
    .filter((item) => item.start >= 0 && item.claim.text.trim())
    .sort((a, b) => a.start - b.start)

  const parts: ReactNode[] = []
  let cursor = 0
  for (const { claim, start } of spans) {
    if (start < cursor) continue // overlaps the previous claim
    const end = start + claim.text.trim().length
    const evidenceFor = (claim.evidence ?? claim.evidence_ids.map((id) => evidence.get(id)).filter(Boolean)) as Evidence[]
    parts.push(...withCitations(text.slice(cursor, start), evidence, true))
    parts.push(
      <EvidenceHover
        key={start}
        className={`claim claim-${claim.status}`}
        evidence={evidenceFor}
        emptyText="No evidence supports this claim. Check it before you send."
      >
        {withCitations(text.slice(start, end), evidence, false)}
      </EvidenceHover>,
    )
    cursor = end
  }
  parts.push(...withCitations(text.slice(cursor), evidence, true))
  return <p className="paragraph">{parts}</p>
}
