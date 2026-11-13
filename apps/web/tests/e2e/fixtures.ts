import type { Page, Request } from '@playwright/test'

export interface Reply {
  status?: number
  json?: unknown
  body?: string
  contentType?: string
}
export type Handler = Reply | ((request: Request) => Reply)

export interface Call {
  method: string
  path: string
  body: unknown
}

export const THREAD_ID = 'bid:u1:job-1'
export const ENCODED_THREAD_ID = encodeURIComponent(THREAD_ID)

export const user = { user_id: 'u1', email: 'sam@example.com', display_name: 'Sam', persona: 'ai_ml_engineer' }

export const defaultSettings = {
  persona: null,
  autonomy: 'suggest',
  weekly_connects_budget: 20,
  timezone: 'UTC',
  rates: { hourly_floor: 40, fixed_floor: 300, target_hourly_rate: 70 },
  saved_searches: [],
  filters: { min_budget: 100, payment_types: ['fixed', 'hourly'] },
  marketplace: 'gigsim',
}

const evidence = {
  evidence_id: 'persona:cs:cs-aiml-03',
  type: 'case_study',
  project: 'Retail churn model',
  title: 'Churn model for a retailer',
  text: 'Built a gradient boosting model that cut customer churn by 18 percent in one quarter.',
  skills: ['Machine Learning'],
  date: '2024-05',
  client_industry: 'Retail',
  outcome: 'Churn down 18 percent',
  source: 'case_studies/churn.md',
  score: 0.91,
}

export const proposalRequest = {
  kind: 'proposal',
  job: { job_id: 'job-1', title: 'Churn prediction for a shop' },
  draft: {
    job_id: 'job-1',
    cover_letter:
      'I built a churn model that cut churn by 18% for a retailer. [persona:cs:cs-aiml-03]\n\nI can start next week and share weekly updates.',
    screening_answers: [{ question: 'Why you?', answer: 'I have done this before.', evidence_ids: [] }],
    claims: [],
  },
  claims: [
    {
      text: 'I built a churn model that cut churn by 18% for a retailer.',
      evidence_ids: [evidence.evidence_id],
      status: 'supported',
      reason: 'Matches the retail churn case study.',
      evidence: [evidence],
    },
  ],
  risk: { score: 0.1, client_quality: 0.8, is_scam: false, injection_detected: false, flags: [], explanation: '' },
  fit: { score: 0.82, matches: [], matched_skills: [], missing_skills: [], reasons: [] },
  decision: { action: 'bid', reasons: ['Strong match with past retail work.'], fit_score: 0.82, risk_score: 0.1 },
  price: {
    payment_type: 'fixed', amount: 900, market_p25: 600, market_p50: 800, market_p75: 1100, floor: 300,
    connects_cost: 12, connects_worth_it: true, rationale: 'Near the market middle.',
  },
  critique: { approve: true, grounding_ok: true, issues: ['Add a closing question.'], instructions: '' },
  compliance: { allowed: true, blocked_reason: '', violations: [] },
  dry_run: {
    payload: { cover_letter: 'I built a churn model...', amount: 900, payment_type: 'fixed' },
    marketplace: { dry_run: true },
    connects_cost: 12,
  },
  payload: { cover_letter: 'I built a churn model...' },
}

export const approvalItem = { thread_id: THREAD_ID, kind: 'proposal', title: 'Churn prediction for a shop', request: proposalRequest }

export const healthyHealth = { api: true, marketplace: true, servers: {}, degraded: false, queued_jobs: 0, message: '' }

/**
 * Answers every /api/ request from `handlers` ("METHOD /decoded/path") and records the calls.
 * Requests for source files that happen to contain "/api/" in their path fall through to the dev server.
 */
export async function mockApi(page: Page, handlers: Record<string, Handler> = {}) {
  const calls: Call[] = []
  const all: Record<string, Handler> = {
    'GET /api/health': { json: healthyHealth },
    'GET /api/auth/me': { json: user },
    'GET /api/settings': { json: defaultSettings },
    'GET /api/jobs': { json: [] },
    'GET /api/approvals': { json: [] },
    'GET /api/integrations': { json: { gigsim: { connected: true }, upwork: { connected: false } } },
    'GET /api/memory': { json: [] },
    [`GET /api/runs/${THREAD_ID}/stream`]: {
      contentType: 'text/event-stream',
      body: 'event: run_started\ndata: {"type":"run_started","run_id":"r1"}\n\nevent: node\ndata: {"type":"node","node":"scout","status":"running","seconds":0.4,"tokens":120}\n\n',
    },
    [`GET /api/runs/${THREAD_ID}`]: { json: { thread_id: THREAD_ID, events: [], history: [], trace_url: null } },
    ...handlers,
  }

  await page.route('**/api/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    if (!url.pathname.startsWith('/api/')) return route.fallback()
    const path = decodeURIComponent(url.pathname)
    const method = request.method()
    const body = method === 'GET' ? undefined : request.postDataJSON()
    calls.push({ method, path, body })
    const handler = all[`${method} ${path}`]
    if (!handler) return route.fulfill({ status: 404, json: { detail: `no mock for ${method} ${path}` } })
    const reply = typeof handler === 'function' ? handler(request) : handler
    return route.fulfill({
      status: reply.status ?? 200,
      contentType: reply.contentType,
      body: reply.body,
      json: reply.json,
    })
  })
  return calls
}

export const callsTo = (calls: Call[], method: string, path: string) =>
  calls.filter((call) => call.method === method && call.path === path)
