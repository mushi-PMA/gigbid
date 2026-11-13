import { label, percent } from '../lib/format'

interface Props {
  score: number | null | undefined
  flags?: string[]
}

/** Risk score as a coloured badge, with the flag names next to it. */
export function RiskBadge({ score, flags = [] }: Props) {
  if (score == null) return <span className="badge">Risk not checked</span>
  const level = score >= 0.6 ? 'high' : score >= 0.3 ? 'medium' : 'low'
  return (
    <span className="badge-group">
      <span className={`badge risk-${level}`}>
        Risk {level} ({percent(score)})
      </span>
      {flags.map((flag) => (
        <span key={flag} className="badge flag">
          {label(flag)}
        </span>
      ))}
    </span>
  )
}
