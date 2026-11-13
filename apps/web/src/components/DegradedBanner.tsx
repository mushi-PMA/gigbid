import { healthApi } from '../lib/api/endpoints'
import { useAsync } from '../lib/api/hooks'

/** Polls the health endpoint every 15 seconds and warns when the marketplace is down. */
export function DegradedBanner() {
  const { data } = useAsync(() => healthApi.get(), [], 15_000)
  if (!data || (!data.degraded && data.marketplace)) return null
  return (
    <div className="degraded" role="status">
      Marketplace unavailable: new work is queued and will resume automatically
      {data.queued_jobs ? ` (${data.queued_jobs} waiting)` : ''}.
    </div>
  )
}
