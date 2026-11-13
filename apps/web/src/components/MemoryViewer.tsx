import { useState, type FormEvent } from 'react'
import { memoryApi } from '../lib/api/endpoints'
import { useAsync } from '../lib/api/hooks'
import { label } from '../lib/format'
import { EmptyState } from './EmptyState'
import { ErrorState } from './ErrorState'
import { Loading } from './Loading'

function describeValue(value: Record<string, unknown>): string {
  const text = value.rule ?? value.text ?? value.summary ?? value.description
  return typeof text === 'string' ? text : JSON.stringify(value)
}

/** What GigBid has learned about the user. Each item can be deleted, and a style rule can be pinned. */
export function MemoryViewer() {
  const { data, error, loading, reload } = useAsync(() => memoryApi.list(), [])
  const [rule, setRule] = useState('')
  const [problem, setProblem] = useState('')

  async function pin(event: FormEvent) {
    event.preventDefault()
    setProblem('')
    try {
      await memoryApi.pinStyleRule(rule.trim())
      setRule('')
      reload()
    } catch (err) {
      setProblem(err instanceof Error ? err.message : 'Could not pin the rule.')
    }
  }

  async function forget(namespace: string, key: string) {
    setProblem('')
    try {
      await memoryApi.forget(namespace, key)
      reload()
    } catch (err) {
      setProblem(err instanceof Error ? err.message : 'Could not delete this item.')
    }
  }

  return (
    <section className="card" aria-labelledby="memory-heading">
      <h2 id="memory-heading">What GigBid has learned</h2>
      {loading && !data && <Loading />}
      {error && !data && <ErrorState error={error} onRetry={reload} />}
      {data && data.length === 0 && (
        <EmptyState title="Nothing learned yet">Edit a draft or reject one and GigBid will remember your style.</EmptyState>
      )}
      {data && data.length > 0 && (
        <ul className="plain-list">
          {data.map((item) => (
            <li key={`${item.namespace}/${item.key}`} className="memory-item">
              <div>
                <span className="badge">{label(item.namespace)}</span> {describeValue(item.value)}
              </div>
              <button type="button" onClick={() => void forget(item.namespace, item.key)}>
                Delete<span className="sr-only"> {label(item.namespace)} item {item.key}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      <form onSubmit={pin}>
        <label htmlFor="style-rule">Pin a style rule</label>
        <div className="button-row">
          <input id="style-rule" value={rule} onChange={(e) => setRule(e.target.value)} placeholder="For example: keep it under 200 words" />
          <button type="submit" disabled={!rule.trim()}>
            Pin rule
          </button>
        </div>
      </form>
      <div role="alert">{problem && <p className="error-text">{problem}</p>}</div>
    </section>
  )
}
