import type { ReactNode } from 'react'

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="state empty">
      <h2>{title}</h2>
      {children && <div className="muted">{children}</div>}
    </div>
  )
}
