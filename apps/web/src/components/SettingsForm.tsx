import { useEffect, useState, type FormEvent } from 'react'
import { settingsApi, type Persona, type SavedSearch, type Settings } from '../lib/api/endpoints'
import { useAsync } from '../lib/api/hooks'
import { ErrorState } from './ErrorState'
import { Loading } from './Loading'

export const PERSONAS: { value: Persona; title: string; text: string }[] = [
  { value: 'ai_ml_engineer', title: 'AI and ML engineer', text: 'Models, data pipelines and evaluation work.' },
  { value: 'fullstack_web_dev', title: 'Full-stack web developer', text: 'Web apps, APIs and front ends.' },
  { value: 'data_analyst', title: 'Data analyst', text: 'Dashboards, reports and analysis.' },
]

const toNumber = (value: string): number | null => (value.trim() === '' ? null : Number(value))
const fromNumber = (value: number | null | undefined) => (value == null ? '' : String(value))

interface Props {
  /** Onboarding shows the persona picker and skips autonomy. Settings shows both. */
  mode: 'onboarding' | 'settings'
  onSaved?: () => void
}

/** Persona, rates, filters, saved searches, Connects budget and autonomy. Saves everything with one PUT /api/settings. */
export function SettingsForm({ mode, onSaved }: Props) {
  const { data, error, loading, reload } = useAsync(() => settingsApi.get(), [])
  const [form, setForm] = useState<Settings | null>(null)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const [saveError, setSaveError] = useState('')

  useEffect(() => {
    if (data) setForm(data)
  }, [data])

  if (loading && !form) return <Loading label="Loading settings" />
  if (error && !form) return <ErrorState error={error} onRetry={reload} />
  if (!form) return null

  const update = (changes: Partial<Settings>) => setForm({ ...form, ...changes })
  const searches = form.saved_searches ?? []
  const updateSearch = (index: number, changes: Partial<SavedSearch>) =>
    update({ saved_searches: searches.map((s, i) => (i === index ? { ...s, ...changes } : s)) })

  async function save(event: FormEvent) {
    event.preventDefault()
    if (!form) return
    setSaving(true)
    setMessage('')
    setSaveError('')
    try {
      await settingsApi.save(form)
      setMessage('Settings saved.')
      onSaved?.()
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Could not save settings.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={save} className="stack">
      <section className="card" aria-labelledby="persona-heading">
        <h2 id="persona-heading">Your profile</h2>
        <fieldset className="persona-grid">
          <legend className="sr-only">Choose a persona</legend>
          {PERSONAS.map((persona) => (
            <label key={persona.value} className={`persona-card ${form.persona === persona.value ? 'selected' : ''}`}>
              <input
                type="radio"
                name="persona"
                value={persona.value}
                checked={form.persona === persona.value}
                onChange={() => update({ persona: persona.value })}
              />
              <strong>{persona.title}</strong>
              <span className="muted small">{persona.text}</span>
            </label>
          ))}
          <label className={`persona-card ${form.persona == null ? 'selected' : ''}`}>
            <input type="radio" name="persona" value="own" checked={form.persona == null} onChange={() => update({ persona: null })} />
            <strong>My own profile</strong>
            <span className="muted small">Upload your own portfolio files below.</span>
          </label>
        </fieldset>
      </section>

      <section className="card" aria-labelledby="rates-heading">
        <h2 id="rates-heading">Rates and filters</h2>
        <div className="grid-3">
          <div>
            <label htmlFor="hourly-floor">Lowest hourly rate (USD)</label>
            <input id="hourly-floor" type="number" min="0" value={fromNumber(form.rates?.hourly_floor)}
              onChange={(e) => update({ rates: { ...form.rates, hourly_floor: toNumber(e.target.value) } })} />
          </div>
          <div>
            <label htmlFor="target-rate">Target hourly rate (USD)</label>
            <input id="target-rate" type="number" min="0" value={fromNumber(form.rates?.target_hourly_rate)}
              onChange={(e) => update({ rates: { ...form.rates, target_hourly_rate: toNumber(e.target.value) } })} />
          </div>
          <div>
            <label htmlFor="fixed-floor">Lowest fixed price (USD)</label>
            <input id="fixed-floor" type="number" min="0" value={fromNumber(form.rates?.fixed_floor)}
              onChange={(e) => update({ rates: { ...form.rates, fixed_floor: toNumber(e.target.value) } })} />
          </div>
          <div>
            <label htmlFor="min-budget">Smallest budget to show (USD)</label>
            <input id="min-budget" type="number" min="0" value={fromNumber(form.filters?.min_budget)}
              onChange={(e) => update({ filters: { ...form.filters, min_budget: toNumber(e.target.value) ?? 0 } })} />
          </div>
        </div>
        <fieldset>
          <legend>Payment types</legend>
          {(['fixed', 'hourly'] as const).map((type) => {
            const chosen = form.filters?.payment_types ?? ['fixed', 'hourly']
            return (
              <label key={type} className="inline-check">
                <input
                  type="checkbox"
                  checked={chosen.includes(type)}
                  onChange={(e) =>
                    update({
                      filters: {
                        min_budget: form.filters?.min_budget ?? 0,
                        ...form.filters,
                        payment_types: e.target.checked ? [...chosen, type] : chosen.filter((t) => t !== type),
                      },
                    })
                  }
                />
                {type === 'fixed' ? 'Fixed price' : 'Hourly'}
              </label>
            )
          })}
        </fieldset>
      </section>

      <section className="card" aria-labelledby="budget-heading">
        <h2 id="budget-heading">Connects budget{mode === 'settings' ? ' and autonomy' : ''}</h2>
        <label htmlFor="connects-budget">Weekly Connects budget</label>
        <input id="connects-budget" type="number" min="0" value={fromNumber(form.weekly_connects_budget)}
          onChange={(e) => update({ weekly_connects_budget: toNumber(e.target.value) ?? 0 })} />
        <label htmlFor="timezone">Time zone</label>
        <input id="timezone" value={form.timezone ?? ''} onChange={(e) => update({ timezone: e.target.value })} />
        {mode === 'settings' && (
          <>
            <label htmlFor="autonomy">Autonomy</label>
            <select id="autonomy" value={form.autonomy ?? 'suggest'} onChange={(e) => update({ autonomy: e.target.value as Settings['autonomy'] })}>
              <option value="suggest">Suggest only</option>
              <option value="auto_skip_low_fit">Skip low-fit jobs automatically</option>
            </select>
            <p className="muted small">Sending is never automatic. Every proposal and reply waits for your approval.</p>
          </>
        )}
      </section>

      <section className="card" aria-labelledby="searches-heading">
        <h2 id="searches-heading">Saved searches</h2>
        {searches.length === 0 && <p className="muted">No saved searches yet.</p>}
        {searches.map((search, index) => (
          <div key={index} className="search-row">
            <div>
              <label htmlFor={`search-name-${index}`}>Name</label>
              <input id={`search-name-${index}`} value={search.name} onChange={(e) => updateSearch(index, { name: e.target.value })} />
            </div>
            <div>
              <label htmlFor={`search-query-${index}`}>Words to look for</label>
              <input id={`search-query-${index}`} value={search.query ?? ''} onChange={(e) => updateSearch(index, { query: e.target.value })} />
            </div>
            <div>
              <label htmlFor={`search-skills-${index}`}>Skills (comma separated)</label>
              <input id={`search-skills-${index}`} value={(search.skills ?? []).join(', ')}
                onChange={(e) => updateSearch(index, { skills: e.target.value.split(',').map((s) => s.trim()).filter(Boolean) })} />
            </div>
            <div>
              <label htmlFor={`search-hours-${index}`}>Check every (hours)</label>
              <input id={`search-hours-${index}`} type="number" min="1" value={search.every_hours ?? 4}
                onChange={(e) => updateSearch(index, { every_hours: Number(e.target.value) || 4 })} />
            </div>
            <button type="button" onClick={() => update({ saved_searches: searches.filter((_, i) => i !== index) })}>
              Remove<span className="sr-only"> search {search.name}</span>
            </button>
          </div>
        ))}
        <button type="button" onClick={() => update({ saved_searches: [...searches, { name: 'New search', query: '', skills: [], category: '', every_hours: 4 }] })}>
          Add a search
        </button>
      </section>

      <div className="button-row">
        <button type="submit" className="primary" disabled={saving}>
          {saving ? 'Saving...' : 'Save settings'}
        </button>
      </div>
      <div role="status">{message && <p className="ok-text">{message}</p>}</div>
      <div role="alert">{saveError && <p className="error-text">{saveError}</p>}</div>
    </form>
  )
}
