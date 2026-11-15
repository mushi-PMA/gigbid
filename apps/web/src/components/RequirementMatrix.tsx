import { EvidenceHover } from './EvidenceHover'
import type { Evidence, RequirementMatch } from '../lib/types'

interface Props {
  matches: RequirementMatch[]
  evidence: Evidence[]
}

const strengthText = { strong: 'Strong', partial: 'Partial', none: 'None' }

/** Each job requirement next to the portfolio evidence that answers it. Hover or focus an id to read it. */
export function RequirementMatrix({ matches, evidence }: Props) {
  const byId = new Map(evidence.map((item) => [item.evidence_id, item]))
  if (matches.length === 0) return <p className="muted">No requirements were matched yet.</p>
  return (
    <div className="table-wrap">
      <table>
        <caption className="sr-only">Requirement to evidence matrix</caption>
        <thead>
          <tr>
            <th scope="col">Requirement</th>
            <th scope="col">Match</th>
            <th scope="col">Evidence</th>
          </tr>
        </thead>
        <tbody>
          {matches.map((match) => (
            <tr key={match.requirement_id} title={match.reason || undefined}>
              <td>
                {match.requirement}
                {match.reason && <span className="sr-only">. {match.reason}</span>}
              </td>
              <td>
                <span className={`badge strength-${match.strength}`}>{strengthText[match.strength]}</span>
              </td>
              <td>
                {match.evidence_ids.length === 0 && <span className="muted">None</span>}
                {match.evidence_ids.map((id) => {
                  const item = byId.get(id)
                  return (
                    <EvidenceHover key={id} className="chip" evidence={item ? [item] : []}>
                      {id.split(':').pop()}
                    </EvidenceHover>
                  )
                })}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
