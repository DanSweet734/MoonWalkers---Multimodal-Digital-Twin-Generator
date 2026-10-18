// How the dashboard words and formats what the API returns. Pure functions, tested with
// `npm test` (Node's test runner).

import type { Fact, JobStep, RunStatus, TwinVersion } from '../api/types.gen.ts'

export type Stage = RunStatus['stage']
export type ReviewStatus = TwinVersion['review_status']

const STAGES: Record<Stage, string> = {
  no_photo: 'No photo',
  waiting_for_agent: 'Waiting for the agent',
  in_progress: 'In progress',
  built: 'Built',
  reused: 'Reused',
  unreadable: 'Unreadable',
}

const REVIEWS: Record<ReviewStatus, string> = {
  draft: 'Draft',
  needs_review: 'Needs review',
  approved: 'Approved',
  rejected: 'Rejected',
}

export function stageText(stage: Stage): string {
  return STAGES[stage]
}

export function reviewText(status: ReviewStatus): string {
  return REVIEWS[status]
}

/** Jobs not built or reused yet, whose page keeps checking for the agent's progress. */
export function isOpen(stage: Stage): boolean {
  return stage === 'no_photo' || stage === 'waiting_for_agent' || stage === 'in_progress'
}

export function stepsDone(steps: JobStep[]): string {
  const counted = steps.filter((s) => s.step !== 'preview')
  return `${counted.filter((s) => s.done).length} of ${counted.length} steps`
}

/** The URL the API serves a data-folder file at, for a path relative to the data folder. */
export function fileUrl(path: string): string {
  return '/api/files/' + path.split('/').map(encodeURIComponent).join('/')
}

export function formatTime(iso: string, timeZone?: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return new Intl.DateTimeFormat('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    timeZone,
    timeZoneName: 'short',
  }).format(date)
}

export function percent(confidence: number): string {
  return `${Math.round(confidence * 100)}%`
}

export function shortHash(sha256: string | null | undefined): string {
  return sha256 ? sha256.slice(0, 12) : '-'
}

/** A fact's value with its unit, as the contract stores it (SI). */
export function factValue(fact: Pick<Fact, 'value' | 'unit'>): string {
  const value = typeof fact.value === 'boolean' ? (fact.value ? 'yes' : 'no') : String(fact.value)
  return fact.unit ? `${value} ${fact.unit}` : value
}

/** rad/s also in deg/s, which the Haas documents use. A conversion, not another fact. */
export function speed(radPerSecond: number): string {
  const degrees = (radPerSecond * 180) / Math.PI
  return `${round(radPerSecond, 4)} rad/s (${round(degrees, 1)} °/s)`
}

/** A part's size from its bounds in the twin frame: x front (depth), y left (width), z up. */
export function extents(
  min: [number, number, number] | null | undefined,
  max: [number, number, number] | null | undefined,
): string {
  if (!min || !max) return '-'
  const [depth, width, height] = max.map((m, i) => m - min[i])
  return `${mm(depth)} deep × ${mm(width)} wide × ${mm(height)} high`
}

export function triple(values: [number, number, number] | null | undefined): string {
  return values ? `(${values.map((v) => round(v, 4)).join(', ')})` : '-'
}

/** The message in an API error body: FastAPI sends {"detail": "..."} or a list of problems. */
export function errorDetail(body: unknown, fallback: string): string {
  if (typeof body === 'object' && body !== null && 'detail' in body) {
    const detail = (body as { detail: unknown }).detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      const problems = detail.map((d) => {
        const item = d as { loc?: unknown[]; msg?: unknown }
        const where = Array.isArray(item.loc) ? item.loc.filter((l) => l !== 'body').join('.') : ''
        return where ? `${where}: ${String(item.msg)}` : String(item.msg)
      })
      if (problems.length > 0) return problems.join('; ')
    }
  }
  return fallback
}

function mm(metres: number): string {
  return `${Math.round(metres * 1000)} mm`
}

function round(value: number, digits: number): string {
  return String(Number(value.toFixed(digits)))
}
