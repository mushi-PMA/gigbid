import { useState, type FormEvent } from 'react'
import { settingsApi } from '../lib/api/endpoints'
import { useAsync } from '../lib/api/hooks'
import { formatTime } from '../lib/format'
import { ErrorState } from './ErrorState'
import { Loading } from './Loading'

/** Shows connected accounts and lets the user connect GigSim (token is optional) or Upwork. */
export function ConnectAccounts() {
  const { data, error, loading, reload } = useAsync(() => settingsApi.integrations(), [])
  const [token, setToken] = useState('')
  const [message, setMessage] = useState('')
  const [problem, setProblem] = useState('')

  async function saveToken(event: FormEvent) {
    event.preventDefault()
    setMessage('')
    setProblem('')
    try {
      await settingsApi.connectGigsim(token.trim())
      setToken('')
      setMessage('GigSim token saved.')
      reload()
    } catch (err) {
      setProblem(err instanceof Error ? err.message : 'Could not save the token.')
    }
  }

  async function connectUpwork() {
    setProblem('')
    try {
      window.location.href = await settingsApi.upworkConnectUrl()
    } catch (err) {
      setProblem(err instanceof Error ? err.message : 'Could not start the Upwork connection.')
    }
  }

  return (
    <section className="card" aria-labelledby="accounts-heading">
      <h2 id="accounts-heading">Connected accounts</h2>
      {loading && !data && <Loading />}
      {error && !data && <ErrorState error={error} onRetry={reload} />}
      {data && (
        <ul className="plain-list">
          <li>
            GigSim: <strong>{data.gigsim.connected ? 'connected' : 'not connected'}</strong>
            {data.gigsim.account && <span className="muted"> ({data.gigsim.account})</span>}
          </li>
          <li>
            Upwork: <strong>{data.upwork.connected ? 'connected' : 'not connected'}</strong>
            {data.upwork.since && <span className="muted"> since {formatTime(data.upwork.since)}</span>}
          </li>
        </ul>
      )}
      <form onSubmit={saveToken}>
        <label htmlFor="gigsim-token">GigSim token (optional)</label>
        <div className="button-row">
          <input id="gigsim-token" value={token} onChange={(e) => setToken(e.target.value)} autoComplete="off" />
          <button type="submit" disabled={!token.trim()}>
            Save token
          </button>
        </div>
      </form>
      <div className="button-row">
        <button type="button" onClick={() => void connectUpwork()}>
          Connect Upwork
        </button>
      </div>
      <div role="status">{message && <p className="ok-text">{message}</p>}</div>
      <div role="alert">{problem && <p className="error-text">{problem}</p>}</div>
    </section>
  )
}
