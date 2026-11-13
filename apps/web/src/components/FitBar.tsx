import { percent } from '../lib/format'

export function FitBar({ score }: { score: number | null | undefined }) {
  if (score == null) return <span className="muted">Not scored</span>
  return (
    <div className="fitbar" role="img" aria-label={`Fit ${percent(score)}`}>
      <div className="fitbar-track">
        <div className="fitbar-fill" style={{ width: percent(score) }} />
      </div>
      <span className="fitbar-value">{percent(score)}</span>
    </div>
  )
}
