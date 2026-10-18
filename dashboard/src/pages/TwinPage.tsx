import { useState, type FormEvent } from 'react'

import { api } from '../api/client.ts'
import type { Source, TwinDetail, TwinReview } from '../api/types.gen.ts'
import { Loading, ReviewBadge, Section, SourceName } from '../components/common.tsx'
import { FileList, Gallery } from '../components/media.tsx'
import {
  ControlList,
  FactsTable,
  IdentityBlock,
  IssueList,
  JointsList,
  PartsTable,
  ScaleBlock,
} from '../components/notes.tsx'
import { fileUrl, formatTime, shortHash } from '../lib/format.ts'
import { useApi } from '../lib/hooks.ts'
import { jobHash } from '../lib/route.ts'

interface Props {
  manufacturer: string
  model: string
  version: number
}

export function TwinPage({ manufacturer, model, version }: Props) {
  const twin = useApi(`twin:${manufacturer}/${model}@${version}`, () =>
    api.twin(manufacturer, model, version),
  )
  if (twin.data === undefined) return <Loading error={twin.error} />
  return <TwinView detail={twin.data} where={{ manufacturer, model, version }} reload={twin.reload} />
}

function TwinView({ detail, where, reload }: { detail: TwinDetail; where: Props; reload: () => void }) {
  const { twin } = detail.version
  const sources = new Map<string, Source>(
    detail.results.flatMap((r) => r.sources.map((s) => [s.source_id, s] as const)),
  )
  return (
    <>
      <p className="crumbs">
        <a href="#/twins">Twins</a> / {twin.machine_key}
      </p>
      <h1>{twin.twin_id}</h1>
      <div className="banner">
        <ReviewBadge status={detail.version.review_status} />
        <span>
          {detail.version.reusable
            ? 'A request for this machine reuses this version.'
            : 'Requests for this machine do not reuse this version.'}
        </span>
      </div>
      <dl className="facts-list">
        <dt>Built</dt>
        <dd>{formatTime(twin.created_at)}</dd>
        <dt>USD file</dt>
        <dd>
          {twin.usd_path ? (
            <>
              <a href={fileUrl(twin.usd_path)}>{twin.usd_path}</a>{' '}
              <span className="muted small">(open in Isaac Sim: docs/setup/isaac-sim-check.md)</span>
            </>
          ) : (
            '-'
          )}
        </dd>
        <dt>Run folder</dt>
        <dd>
          {detail.version.run ? (
            <a href={jobHash(detail.version.run) ?? '#/jobs'}>{detail.version.run}</a>
          ) : (
            '-'
          )}
        </dd>
        <dt>Built from</dt>
        <dd>{(twin.built_from ?? []).map((id) => <code key={id}>{id} </code>)}</dd>
        {twin.notes ? (
          <>
            <dt>Notes</dt>
            <dd>{twin.notes}</dd>
          </>
        ) : null}
      </dl>

      <Section title="Review">
        <ReviewHistory reviews={detail.reviews} />
        <ReviewForm where={where} onDone={reload} />
      </Section>

      <Section title="Model">
        <Gallery images={detail.images} />
      </Section>

      {detail.results.map((result) => (
        <div key={result.result_id}>
          <Section title={`What Pipeline ${result.pipeline} found`}>
            <p className="muted small">
              Result <code>{result.result_id}</code> by {result.produced_by},{' '}
              {formatTime(result.produced_at)}. Values are in SI units, as the contract stores them.
            </p>
            {result.identity ? <IdentityBlock identity={result.identity} sources={sources} /> : null}
            <h3>Facts</h3>
            <FactsTable facts={result.facts ?? []} sources={sources} />
            <h3>Parts</h3>
            <PartsTable parts={result.parts ?? []} sources={sources} />
            {result.scale ? (
              <>
                <h3>Scale</h3>
                <ScaleBlock scale={result.scale} sources={sources} />
              </>
            ) : null}
            <h3>Joints</h3>
            <JointsList joints={result.joints ?? []} sources={sources} />
            <h3>Control</h3>
            <ControlList control={result.control ?? []} sources={sources} />
            <h3>Issues for the reviewer</h3>
            <IssueList issues={result.issues ?? []} />
          </Section>
        </div>
      ))}

      <Section title="Sources">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th scope="col">Source</th>
                <th scope="col">Kind</th>
                <th scope="col">Retrieved</th>
                <th scope="col">SHA-256</th>
                <th scope="col">Cited for</th>
              </tr>
            </thead>
            <tbody>
              {detail.sources.map((use) => (
                <tr key={`${use.source.source_id}|${use.source.uri}`}>
                  <th scope="row">
                    <SourceName source={use.source} />
                    <div className="muted small">
                      <code>{use.source.source_id}</code>
                      {use.local_file ? (
                        <>
                          {' · '}
                          <a href={fileUrl(use.local_file)} target="_blank" rel="noreferrer">
                            saved copy
                          </a>
                        </>
                      ) : null}
                      {use.source.license_note ? ` · ${use.source.license_note}` : ''}
                    </div>
                  </th>
                  <td>
                    {use.source.kind}
                    {use.source.input_type ? ` (${use.source.input_type})` : ''}
                  </td>
                  <td>{formatTime(use.source.retrieved_at)}</td>
                  <td>
                    <code>{shortHash(use.source.sha256)}</code>
                  </td>
                  <td>
                    {use.cited_by.length === 0 ? (
                      <span className="muted">not cited</span>
                    ) : (
                      <ul className="citations">
                        {use.cited_by.map((c, i) => (
                          <li key={i}>
                            {c.item}
                            {c.locator ? <span className="locator">, {c.locator}</span> : null}
                            {c.quote ? <q>{c.quote}</q> : null}
                          </li>
                        ))}
                      </ul>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      <Section title="Files">
        <FileList files={detail.outputs} />
      </Section>
    </>
  )
}

function ReviewHistory({ reviews }: { reviews: TwinReview[] }) {
  if (reviews.length === 0) {
    return <p className="muted">Not reviewed yet. Every new twin needs a person's review.</p>
  }
  return (
    <ol className="reviews">
      {reviews.map((r) => (
        <li key={r.number}>
          <ReviewBadge status={r.decision} /> by {r.reviewer}, {formatTime(r.reviewed_at)}
          <p>{r.reason}</p>
        </li>
      ))}
    </ol>
  )
}

function ReviewForm({ where, onDone }: { where: Props; onDone: () => void }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | undefined>()

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    const data = new FormData(form)
    setBusy(true)
    setError(undefined)
    try {
      await api.review(where.manufacturer, where.model, where.version, {
        decision: data.get('decision') === 'rejected' ? 'rejected' : 'approved',
        reviewer: String(data.get('reviewer') ?? ''),
        reason: String(data.get('reason') ?? ''),
      })
      form.reset()
      onDone()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="form" onSubmit={submit}>
      <fieldset>
        <legend>Your decision</legend>
        <label className="check">
          <input type="radio" name="decision" value="approved" required /> Approve
        </label>
        <label className="check">
          <input type="radio" name="decision" value="rejected" /> Reject (requests stop reusing this
          version)
        </label>
      </fieldset>
      <label>
        Your name
        <input name="reviewer" required maxLength={100} />
      </label>
      <label>
        Reason
        <textarea
          name="reason"
          required
          maxLength={2000}
          rows={3}
          placeholder="What you checked and what you saw, for example in Isaac Sim"
        />
      </label>
      <div>
        <button type="submit" disabled={busy}>
          {busy ? 'Saving…' : 'Record review'}
        </button>
      </div>
      <p className="muted small">Reviews are added, never changed: the newest one decides.</p>
      {error ? (
        <p className="error" role="alert">
          {error}
        </p>
      ) : null}
    </form>
  )
}
