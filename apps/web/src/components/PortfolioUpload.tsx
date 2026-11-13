import { useState, type FormEvent } from 'react'
import { settingsApi } from '../lib/api/endpoints'

/** Upload portfolio files (.md, .txt or .pdf). GigBid reads them as evidence for proposals. */
export function PortfolioUpload() {
  const [files, setFiles] = useState<File[]>([])
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [problem, setProblem] = useState('')

  async function upload(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setMessage('')
    setProblem('')
    try {
      const result = await settingsApi.uploadPortfolio(files)
      setMessage(`Added ${result.saved.length} file(s). Your portfolio now has ${result.chunks} searchable parts.`)
      setFiles([])
      ;(event.target as HTMLFormElement).reset()
    } catch (err) {
      setProblem(err instanceof Error ? err.message : 'Upload failed.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="card" aria-labelledby="portfolio-heading">
      <h2 id="portfolio-heading">Portfolio files</h2>
      <p className="muted">Add case studies, a CV or notes. Allowed types: .md, .txt, .pdf (2 MB each).</p>
      <form onSubmit={upload}>
        <label htmlFor="portfolio-files">Choose files</label>
        <input id="portfolio-files" type="file" multiple accept=".md,.txt,.pdf" onChange={(e) => setFiles(Array.from(e.target.files ?? []))} />
        <div className="button-row">
          <button type="submit" disabled={busy || files.length === 0}>
            {busy ? 'Uploading...' : 'Upload files'}
          </button>
        </div>
      </form>
      <div role="status">{message && <p className="ok-text">{message}</p>}</div>
      <div role="alert">{problem && <p className="error-text">{problem}</p>}</div>
    </section>
  )
}
