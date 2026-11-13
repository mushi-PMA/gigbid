import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError } from './client'

export interface AsyncState<T> {
  data: T | null
  error: ApiError | null
  loading: boolean
  reload: () => void
}

/** Loads data on mount and whenever `deps` change. Set `pollMs` to refresh quietly in the background. */
export function useAsync<T>(load: () => Promise<T>, deps: unknown[], pollMs?: number): AsyncState<T> {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [loading, setLoading] = useState(true)
  const loadRef = useRef(load)
  loadRef.current = load

  const run = useCallback((quiet: boolean) => {
    if (!quiet) setLoading(true)
    return loadRef.current().then(
      (value) => {
        setData(value)
        setError(null)
        setLoading(false)
      },
      (err: unknown) => {
        setError(err instanceof ApiError ? err : new ApiError(0, String(err)))
        setLoading(false)
      },
    )
  }, [])

  useEffect(() => {
    void run(false)
    if (!pollMs) return
    const timer = window.setInterval(() => void run(true), pollMs)
    return () => window.clearInterval(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  const reload = useCallback(() => void run(true), [run])
  return { data, error, loading, reload }
}
