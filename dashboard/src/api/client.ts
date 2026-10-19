// Calls to the MoonWalkers API (backend/src/moonwalkers/api). The types come from types.gen.ts,
// generated from the API's own models, so they are never copied by hand.

import { errorDetail } from '../lib/format.ts'
import type {
  ApiStatus,
  JobDetail,
  MachineTwins,
  ReviewRequest,
  RunStatus,
  SourceListing,
  TwinDetail,
  TwinReview,
} from './types.gen.ts'

// The API refuses writes without this header, so other web pages cannot make changes.
const WRITE_HEADERS = { 'X-MoonWalkers-Client': 'dashboard' }

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, init)
  } catch {
    throw new ApiError(0, 'The API is not reachable. Start it from backend/: uv run python -m moonwalkers.api')
  }
  if (!response.ok) {
    const fallback = `${response.status} ${response.statusText}`.trim()
    let body: unknown = null
    try {
      body = await response.json()
    } catch {
      // not JSON: keep the status line
    }
    throw new ApiError(response.status, errorDetail(body, fallback))
  }
  return (await response.json()) as T
}

const part = encodeURIComponent

export const api = {
  status: () => request<ApiStatus>('/api/status'),
  jobs: () => request<RunStatus[]>('/api/jobs'),
  job: (machine: string, run: string) =>
    request<JobDetail>(`/api/jobs/${part(machine)}/${part(run)}`),
  createJob: (form: FormData) =>
    request<JobDetail>('/api/jobs', { method: 'POST', body: form, headers: WRITE_HEADERS }),
  twins: () => request<MachineTwins[]>('/api/twins'),
  twin: (manufacturer: string, model: string, version: number) =>
    request<TwinDetail>(`/api/twins/${part(manufacturer)}/${part(model)}/versions/${version}`),
  review: (manufacturer: string, model: string, version: number, review: ReviewRequest) =>
    request<TwinReview>(
      `/api/twins/${part(manufacturer)}/${part(model)}/versions/${version}/reviews`,
      {
        method: 'POST',
        body: JSON.stringify(review),
        headers: { ...WRITE_HEADERS, 'Content-Type': 'application/json' },
      },
    ),
  sources: () => request<SourceListing[]>('/api/sources'),
}
