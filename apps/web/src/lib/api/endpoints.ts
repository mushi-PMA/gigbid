import { api, unwrap } from './client'
import type { components } from './schema'
import type {
  AnalyticsView,
  ApprovalRequest,
  Integrations,
  JobDetailView,
  ThreadDetail,
} from '../types'

type Schemas = components['schemas']
export type Settings = Schemas['SettingsModel']
export type InboxItem = Schemas['InboxItem']
export type PipelineCard = Schemas['PipelineCard']
export type ThreadSummary = Schemas['ThreadSummary']
export type MemoryItem = Schemas['MemoryItem']
export type RunInfo = Schemas['RunInfo']
export type Health = Schemas['Health']
export type User = Schemas['UserOut']
export type Persona = NonNullable<Settings['persona']>
export type SavedSearch = Schemas['SavedSearch']
export interface ApprovalItem extends Omit<Schemas['ApprovalItem'], 'request'> {
  request: ApprovalRequest
}

export const authApi = {
  register: (body: Schemas['RegisterIn']) => unwrap(api.POST('/api/auth/register', { body })),
  login: (body: Schemas['LoginIn']) => unwrap(api.POST('/api/auth/login', { body })),
  logout: () => unwrap(api.POST('/api/auth/logout')),
  me: () => unwrap(api.GET('/api/auth/me')),
}

export const settingsApi = {
  get: () => unwrap(api.GET('/api/settings')),
  save: (body: Settings) => unwrap(api.PUT('/api/settings', { body })),
  integrations: () => unwrap(api.GET('/api/integrations')) as Promise<unknown> as Promise<Integrations>,
  connectGigsim: (token: string) => unwrap(api.POST('/api/integrations/gigsim', { params: { query: { token } } })),
  upworkConnectUrl: async () => {
    const data = (await unwrap(api.GET('/api/integrations/upwork/connect'))) as { authorization_url: string }
    return data.authorization_url
  },
  uploadPortfolio: (files: File[]) => {
    const form = new FormData()
    files.forEach((file) => form.append('files', file))
    return unwrap(
      api.POST('/api/portfolio/upload', { body: { files: [] }, bodySerializer: () => form }),
    ) as Promise<unknown> as Promise<{ saved: string[]; chunks: number }>
  },
}

export const jobsApi = {
  list: (includeSkipped: boolean) =>
    unwrap(api.GET('/api/jobs', { params: { query: { include_skipped: includeSkipped } } })),
  get: (jobId: string) =>
    unwrap(api.GET('/api/jobs/{job_id}', { params: { path: { job_id: jobId } } })) as Promise<unknown> as Promise<JobDetailView>,
  analyze: (jobId: string) => unwrap(api.POST('/api/jobs/{job_id}/analyze', { params: { path: { job_id: jobId } } })),
  skip: (jobId: string) => unwrap(api.POST('/api/jobs/{job_id}/skip', { params: { path: { job_id: jobId } } })),
  scout: () => unwrap(api.POST('/api/scout/run')),
}

export const approvalsApi = {
  list: () => unwrap(api.GET('/api/approvals')) as Promise<unknown> as Promise<ApprovalItem[]>,
  get: (threadId: string) =>
    unwrap(api.GET('/api/approvals/{thread_id}', { params: { path: { thread_id: threadId } } })) as Promise<unknown> as Promise<ApprovalItem>,
  decide: (threadId: string, body: Schemas['ApprovalIn']) =>
    unwrap(api.POST('/api/approvals/{thread_id}', { params: { path: { thread_id: threadId } }, body })),
  regenerate: (threadId: string, paragraphIndex: number) =>
    unwrap(
      api.POST('/api/proposals/{thread_id}/regenerate', {
        params: { path: { thread_id: threadId } },
        body: { paragraph_index: paragraphIndex, instruction: '' },
      }),
    ),
}

export const messagesApi = {
  threads: () => unwrap(api.GET('/api/threads')),
  get: (threadId: string) =>
    unwrap(api.GET('/api/threads/{thread_id}', { params: { path: { thread_id: threadId } } })) as Promise<unknown> as Promise<ThreadDetail>,
  draft: (threadId: string, jobId: string) =>
    unwrap(
      api.POST('/api/threads/{thread_id}/draft', {
        params: { path: { thread_id: threadId }, query: { job_id: jobId } },
      }),
    ),
}

export const runsApi = {
  get: (threadId: string) => unwrap(api.GET('/api/runs/{thread_id}', { params: { path: { thread_id: threadId } } })),
  replay: (threadId: string, checkpointId: string) =>
    unwrap(
      api.POST('/api/runs/{thread_id}/replay/{checkpoint_id}', {
        params: { path: { thread_id: threadId, checkpoint_id: checkpointId } },
      }),
    ),
}

export const pipelineApi = { list: () => unwrap(api.GET('/api/pipeline')) }
export const analyticsApi = {
  get: () => unwrap(api.GET('/api/analytics')) as Promise<unknown> as Promise<AnalyticsView>,
}

export const memoryApi = {
  list: () => unwrap(api.GET('/api/memory')),
  forget: (namespace: string, key: string) =>
    unwrap(api.DELETE('/api/memory/{namespace}/{key}', { params: { path: { namespace, key } } })),
  pinStyleRule: (rule: string) => unwrap(api.POST('/api/memory/style', { body: { rule } })),
}

export const healthApi = { get: () => unwrap(api.GET('/api/health')) }
