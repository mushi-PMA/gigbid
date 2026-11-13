import { ApiError } from '../lib/api/client'

interface Props {
  error: ApiError
  onRetry?: () => void
}

export function ErrorState({ error, onRetry }: Props) {
  const marketplaceDown = error.status === 503
  return (
    <div className="state error" role="alert">
      <h2>{marketplaceDown ? 'Marketplace unavailable' : 'Something went wrong'}</h2>
      <p>
        {marketplaceDown
          ? 'The marketplace cannot be reached right now. New work is queued and will resume automatically.'
          : error.message}
      </p>
      {onRetry && (
        <button type="button" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  )
}
