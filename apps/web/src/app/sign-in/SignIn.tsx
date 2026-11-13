import { useState, type FormEvent } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useSession } from '../../lib/session'

export function SignIn() {
  const { user, signIn, register } = useSession()
  const navigate = useNavigate()
  const [mode, setMode] = useState<'sign-in' | 'register'>('sign-in')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  if (user && !busy) return <Navigate to="/" replace />

  async function submit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      if (mode === 'register') {
        await register({ email, password, display_name: displayName })
        navigate('/onboarding')
      } else {
        await signIn(email, password)
        navigate('/')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong. Please try again.')
      setBusy(false)
    }
  }

  const registering = mode === 'register'
  return (
    <main className="auth-page" id="main">
      <div className="card auth-card">
        <h1>GigBid</h1>
        <p className="muted">Your freelance copilot. It finds jobs, drafts proposals and waits for your approval.</p>
        <div className="tabs" role="group" aria-label="Account">
          <button type="button" aria-pressed={!registering} onClick={() => setMode('sign-in')}>
            Sign in
          </button>
          <button type="button" aria-pressed={registering} onClick={() => setMode('register')}>
            Create account
          </button>
        </div>
        <form onSubmit={submit}>
          {registering && (
            <>
              <label htmlFor="display-name">Your name</label>
              <input id="display-name" required value={displayName} onChange={(e) => setDisplayName(e.target.value)} autoComplete="name" />
            </>
          )}
          <label htmlFor="email">Email</label>
          <input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
          <label htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            required
            minLength={registering ? 8 : undefined}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete={registering ? 'new-password' : 'current-password'}
          />
          <div role="alert">{error && <p className="error-text">{error}</p>}</div>
          <button type="submit" className="primary" disabled={busy}>
            {registering ? 'Create account' : 'Sign in'}
          </button>
        </form>
      </div>
    </main>
  )
}
