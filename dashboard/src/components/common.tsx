import type { ReactNode } from 'react'

import type { Citation, Source } from '../api/types.gen.ts'
import { fileUrl, reviewText, stageText, type ReviewStatus, type Stage } from '../lib/format.ts'

export function StageBadge({ stage }: { stage: Stage }) {
  return <span className={`badge stage-${stage}`}>{stageText(stage)}</span>
}

export function ReviewBadge({ status }: { status: ReviewStatus }) {
  return <span className={`badge review-${status}`}>{reviewText(status)}</span>
}

export function ErrorNote({ error }: { error: string | undefined }) {
  if (!error) return null
  return (
    <p className="error" role="alert">
      {error}
    </p>
  )
}

/** Shown until the first answer arrives; an error replaces it. */
export function Loading({ error }: { error: string | undefined }) {
  return error ? <ErrorNote error={error} /> : <p className="muted">Loading…</p>
}

export function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="section">
      <h2>{title}</h2>
      {children}
    </section>
  )
}

/** A source's title, linked to the web page it came from or to its copy in the data folder. */
export function SourceName({ source, localFile }: { source: Source; localFile?: string | null }) {
  const name = source.title || source.source_id
  if (source.kind === 'url' && /^https?:\/\//.test(source.uri)) {
    return (
      <a href={source.uri} target="_blank" rel="noreferrer">
        {name}
      </a>
    )
  }
  const file = localFile ?? (source.kind === 'file' ? source.uri : null)
  if (file) {
    return (
      <a href={fileUrl(file)} target="_blank" rel="noreferrer">
        {name}
      </a>
    )
  }
  return <span>{name}</span>
}

/** Where each item came from: the source, the place in it, and the words quoted. */
export function Citations({
  citations,
  sources,
}: {
  citations: Citation[] | undefined
  sources: Map<string, Source>
}) {
  if (!citations || citations.length === 0) return <span className="muted">none</span>
  return (
    <ul className="citations">
      {citations.map((c, i) => {
        const source = sources.get(c.source_id)
        return (
          <li key={`${c.source_id}-${i}`}>
            {source ? <SourceName source={source} /> : <code>{c.source_id}</code>}
            {c.locator ? <span className="locator">, {c.locator}</span> : null}
            {c.quote ? <q>{c.quote}</q> : null}
          </li>
        )
      })}
    </ul>
  )
}
