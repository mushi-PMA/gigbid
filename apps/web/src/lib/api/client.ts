import createClient from 'openapi-fetch'
import type { paths } from './schema'

// The cookie session is the main login. The token is kept in memory only, as a Bearer fallback.
let bearerToken: string | null = null
export const setBearerToken = (token: string | null) => {
  bearerToken = token
}

let onUnauthorized: () => void = () => {}
export const setUnauthorizedHandler = (handler: () => void) => {
  onUnauthorized = handler
}

export const api = createClient<paths>({
  baseUrl: import.meta.env.VITE_API_URL ?? '',
  credentials: 'include',
})

api.use({
  onRequest({ request }) {
    if (bearerToken) request.headers.set('Authorization', `Bearer ${bearerToken}`)
    return request
  },
  onResponse({ response, request }) {
    const isAuthCall = new URL(request.url, window.location.origin).pathname.startsWith('/api/auth/')
    if (response.status === 401 && !isAuthCall) onUnauthorized()
    return response
  },
})

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

function messageFromError(error: unknown, status: number): string {
  const detail = (error as { detail?: unknown } | undefined)?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail.map((d) => (d as { msg?: string }).msg ?? '').filter(Boolean).join('; ')
  }
  return `The request failed (status ${status}).`
}

/** Turns an openapi-fetch result into its data, or throws an ApiError with a friendly message. */
export async function unwrap<T>(
  request: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  let result
  try {
    result = await request
  } catch {
    throw new ApiError(0, 'Cannot reach the GigBid server. Check your connection and try again.')
  }
  if (result.error !== undefined || !result.response.ok) {
    throw new ApiError(result.response.status, messageFromError(result.error, result.response.status))
  }
  return result.data as T
}
