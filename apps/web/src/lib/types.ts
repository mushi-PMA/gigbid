// Shapes of the loosely typed parts of the API (the OpenAPI schema marks them as plain objects).
export interface Evidence {
  evidence_id: string
  type: string
  project: string
  title: string
  text: string
  skills: string[]
  date: string
  client_industry: string
  outcome: string
  source: string
  score: number
}

export type ClaimStatus = 'supported' | 'partly_supported' | 'unsupported'
export interface Claim {
  text: string
  evidence_ids: string[]
  status: ClaimStatus
  reason: string
  evidence?: Evidence[]
}

export interface Requirement {
  requirement_id: string
  text: string
  skills: string[]
}
export interface JobSpec {
  title: string
  summary: string
  deliverables: string[]
  requirements: Requirement[]
  required_skills: string[]
  nice_to_have_skills: string[]
  payment_type: 'fixed' | 'hourly'
  budget_min: number | null
  budget_max: number | null
  timeline: string
  screening_questions: string[]
  hidden_needs: string[]
}

export interface RiskReport {
  score: number
  client_quality: number
  is_scam: boolean
  injection_detected: boolean
  flags: { kind: string; evidence: string }[]
  explanation: string
}

export type Strength = 'strong' | 'partial' | 'none'
export interface RequirementMatch {
  requirement_id: string
  requirement: string
  evidence_ids: string[]
  strength: Strength
  reason: string
}
export interface FitReport {
  score: number
  matches: RequirementMatch[]
  matched_skills: string[]
  missing_skills: string[]
  reasons: string[]
}

export interface BidDecision {
  action: 'bid' | 'watch' | 'skip'
  reasons: string[]
  fit_score: number
  risk_score: number
}

export interface PriceQuote {
  payment_type: 'fixed' | 'hourly'
  amount: number
  market_p25: number | null
  market_p50: number | null
  market_p75: number | null
  floor: number
  connects_cost: number
  connects_worth_it: boolean
  rationale: string
}

export interface ScreeningAnswer {
  question: string
  answer: string
  evidence_ids: string[]
}
export interface ProposalDraft {
  cover_letter: string
  screening_answers: ScreeningAnswer[]
  claims: Claim[]
}

export interface Critique {
  approve: boolean
  grounding_ok: boolean
  issues: string[]
  instructions: string
}
export interface ComplianceVerdict {
  allowed: boolean
  blocked_reason: string
  violations: { rule_id: string; text: string; fix: string }[]
}

export interface DryRun {
  payload?: Record<string, unknown>
  marketplace?: unknown
  connects_cost?: number
  would_send?: Record<string, unknown>
  cost?: string
}

export interface ProposalRequest {
  kind: 'proposal'
  job: { job_id: string; title: string; connects_cost?: number }
  draft: ProposalDraft
  claims: Claim[]
  evidence?: Evidence[]
  risk: RiskReport
  fit: FitReport
  decision: BidDecision
  price: PriceQuote
  critique: Critique | null
  compliance: ComplianceVerdict | null
  dry_run: DryRun | null
  payload: { cover_letter: string; [key: string]: unknown }
}

export interface ChatMessage {
  message_id: string
  thread_id: string
  job_id?: string
  sender: 'client' | 'freelancer'
  text: string
  sent_at: string | null
}
export interface MessageRequest {
  kind: 'message'
  thread_id: string
  job_id: string
  messages: ChatMessage[]
  analysis: { intent: string; injection_detected: boolean; summary: string }
  reply: { text: string; proposed_slots: string[] }
  compliance: ComplianceVerdict
  payload: { thread_id: string; text: string }
  dry_run: DryRun | null
}
export type ApprovalRequest = ProposalRequest | MessageRequest

export interface ThreadDetail {
  thread_id: string
  graph_thread_id: string
  messages: ChatMessage[]
  status: string | null
  analysis: MessageRequest['analysis'] | null
  pending_approval: MessageRequest | null
}

export interface JobDetailView {
  job: { title?: string; description?: string; url?: string; skills?: string[]; category?: string }
  thread_id: string | null
  status: string | null
  status_reason: string
  job_spec: JobSpec | null
  risk: RiskReport | null
  fit: FitReport | null
  evidence: Evidence[]
  decision: BidDecision | null
  price: PriceQuote | null
  pending_approval: { kind: string } | null
  tokens: number
  usd: number
}

export interface RunEvent {
  type: 'run_started' | 'node' | 'awaiting_approval' | 'run_finished' | 'ping'
  run_id?: string
  trace_id?: string
  node?: string
  status?: string | null
  seconds?: number | null
  tokens?: number | null
}

export interface Integrations {
  gigsim: { connected: boolean; account?: string }
  upwork: { connected: boolean; since?: string | null }
}

export interface CostStats {
  p50_s: number | null
  p95_s: number | null
  mean_usd: number | null
}
export interface AnalyticsView {
  reply_and_hire_by_category: { category: string; sent: number; reply_rate: number; hire_rate: number }[]
  connects_by_outcome: Record<string, number>
  jobs_analysed: number
  cost_latency: {
    per_job_analysed: CostStats
    per_proposal: CostStats
    declared: {
      p95_latency_seconds_per_job_analysed?: number
      p95_latency_seconds_per_proposal?: number
      usd_per_job_analysed?: number
      usd_per_proposal?: number
    }
  }
  top_rejection_reasons: [string, number][]
}
