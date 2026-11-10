import { useEffect, useRef, useState, type FormEvent } from 'react'

import { api } from '../api/client.ts'
import { Loading, Section, StageBadge } from '../components/common.tsx'
import { formatTime, isOpen, stepsDone } from '../lib/format.ts'
import { useApi } from '../lib/hooks.ts'
import { fileKey, newPicks } from '../lib/picks.ts'
import { jobHash, twinHash } from '../lib/route.ts'
import {
  defaultUse,
  listText,
  photoProblems,
  sidesSeen,
  photoUseText,
  VIEW_CHOICES,
  type PhotoUse,
  type PhotoView,
} from '../lib/views.ts'

export function JobsPage() {
  // Every few seconds, so a job the agent starts or moves on shows up without a reload.
  const jobs = useApi('jobs', api.jobs, 5000)
  return (
    <>
      <h1>Jobs</h1>
      <p className="lead">
        A job builds, or finds, one machine's digital twin from its photos: one, or several with
        where each was taken. If the machine already has a twin and you don't ask for a new version,
        the platform reuses it at once. Otherwise the job waits for the agent (Claude Code), which
        reads the documents, builds the twin, and asks you about anything it can't decide.
      </p>
      <NewJobForm />
      <Section title="All jobs">
        {jobs.data === undefined ? (
          <Loading error={jobs.error} />
        ) : jobs.data.length === 0 ? (
          <p className="muted">No jobs yet. Upload photos above to start one.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th scope="col">Run</th>
                  <th scope="col">Machine</th>
                  <th scope="col">Stage</th>
                  <th scope="col">Last change</th>
                  <th scope="col">Twin</th>
                </tr>
              </thead>
              <tbody>
                {jobs.data.map((job) => {
                  const twin = job.twin_id ? twinHash(job.twin_id) : null
                  return (
                    <tr key={job.run}>
                      <th scope="row">
                        <a href={jobHash(job.run) ?? '#/jobs'}>{job.name}</a>
                      </th>
                      <td>{job.machine_key ?? job.machine}</td>
                      <td>
                        <StageBadge stage={job.stage} />
                        <div className="muted small">
                          {isOpen(job.stage) ? `${job.stage_label} (${stepsDone(job.steps)})` : job.stage_label}
                        </div>
                      </td>
                      <td>{formatTime(job.updated_at)}</td>
                      <td>{twin && job.twin_id ? <a href={twin}>{job.twin_id}</a> : '-'}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Section>
    </>
  )
}

function NewJobForm() {
  const [photos, setPhotos] = useState<ChosenPhoto[]>([])
  const [repeated, setRepeated] = useState<string[]>([])
  const urls = useRef<string[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | undefined>()
  const problems = photoProblems(photos)
  const fed = photos.filter((p) => p.view !== '' && p.use === 'generator')
  const coverage = sidesSeen(fed.map((p) => p.view as PhotoView))

  function forget() {
    for (const url of urls.current) URL.revokeObjectURL(url)
    urls.current = []
  }

  // Each pick adds to the photos chosen, so they can come from several folders (tool gap 6).
  function choose(files: FileList | null) {
    const { added, repeated: again } = newPicks(
      photos.map((p) => p.file),
      Array.from(files ?? []),
    )
    const chosen = added.map((file) => {
      const url = URL.createObjectURL(file)
      urls.current.push(url)
      return { key: fileKey(file), file, url, view: '' as const, use: defaultUse(''), origin: '' }
    })
    setRepeated(again)
    setPhotos((current) => [...current, ...chosen])
  }

  function remove(index: number) {
    const gone = photos[index]
    if (gone === undefined) return
    URL.revokeObjectURL(gone.url)
    urls.current = urls.current.filter((url) => url !== gone.url)
    setPhotos((current) => current.filter((_, i) => i !== index))
  }

  function update(index: number, change: Partial<ChosenPhoto>) {
    setPhotos((current) =>
      current.map((photo, i) => {
        if (i !== index) return photo
        const next = { ...photo, ...change }
        // A new view resets the use to that view's default; a chosen use stays as chosen.
        return change.view === undefined ? next : { ...next, use: defaultUse(next.view) }
      }),
    )
  }

  function sameOriginForAll() {
    setPhotos((current) => current.map((photo) => ({ ...photo, origin: current[0]?.origin ?? '' })))
  }

  useEffect(() => forget, [])

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (problems.length > 0) return
    setBusy(true)
    setError(undefined)
    const form = new FormData(event.currentTarget) // manufacturer, model, license note, new version
    for (const photo of photos) {
      form.append('photo', photo.file)
      form.append('origin', photo.origin)
      form.append('view', photo.view)
      form.append('use', photo.view === '' ? '' : photo.use)
    }
    try {
      const detail = await api.createJob(form)
      window.location.hash = jobHash(detail.job.run) ?? '#/jobs'
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      setBusy(false)
    }
  }

  return (
    <Section title="Start a job">
      <form className="form" onSubmit={submit}>
        <div className="row">
          <label>
            Manufacturer
            <input name="manufacturer" required maxLength={100} placeholder="Grizzly" />
          </label>
          <label>
            Model
            <input name="model" required maxLength={100} placeholder="T33901" />
          </label>
        </div>
        <label>
          Machine photos (JPEG or PNG)
          {photos.length > 0 ? `: ${photos.length} chosen, add more or remove any below` : ''}
          <input
            type="file"
            accept="image/jpeg,image/png"
            multiple
            required={photos.length === 0}
            onChange={(e) => {
              choose(e.target.files)
              e.target.value = '' // so the next pick, even of the same folder, adds again
            }}
          />
          <span className="hint">
            One photo works. Several make a better model: the 3D generator uses up to four views of
            the whole machine, and close-ups are kept as evidence. Each pick adds to the photos
            chosen, so they can come from several folders.
          </span>
        </label>
        {repeated.length > 0 ? (
          <p className="hint" role="status">
            Already chosen, so not added again: {listText(repeated)}.
          </p>
        ) : null}
        {photos.length > 1 ? <WhereToStand /> : null}
        {photos.map((photo, i) => (
          <fieldset key={photo.key} className="photo-row">
            <legend>
              Photo {i + 1} of {photos.length}: {photo.file.name}{' '}
              <button type="button" className="link" onClick={() => remove(i)}>
                Remove
              </button>
            </legend>
            <img className="upload-preview" src={photo.url} alt={`Photo ${i + 1} to upload`} />
            <div className="photo-fields">
              <label>
                Where you stood, facing the machine's front
                <select
                  value={photo.view}
                  required={photos.length > 1}
                  onChange={(e) => update(i, { view: e.target.value as PhotoView | '' })}
                >
                  <option value="">{photos.length > 1 ? 'Choose…' : 'Not given (one photo only)'}</option>
                  {VIEW_CHOICES.map((choice) => (
                    <option key={choice.view} value={choice.view}>
                      {choice.label}
                    </option>
                  ))}
                </select>
              </label>
              {photo.view !== '' ? (
                <label>
                  Use
                  <select
                    value={photo.use}
                    onChange={(e) => update(i, { use: e.target.value as PhotoUse })}
                  >
                    <option value="generator" disabled={photo.view === 'detail'}>
                      {photoUseText('generator')}
                    </option>
                    <option value="evidence">{photoUseText('evidence')}</option>
                  </select>
                </label>
              ) : null}
              <label>
                Where this photo came from
                <input
                  required
                  maxLength={500}
                  value={photo.origin}
                  onChange={(e) => update(i, { origin: e.target.value })}
                  placeholder="A URL, or who took it, where and when"
                />
              </label>
              {i === 0 && photos.length > 1 ? (
                <button type="button" className="link" onClick={sameOriginForAll}>
                  Use this origin for every photo
                </button>
              ) : null}
            </div>
          </fieldset>
        ))}
        {photos.length > 1 && fed.length > 0 ? (
          <p className="hint">
            The 3D model gets {fed.length} photo{fed.length === 1 ? '' : 's'} and sees the{' '}
            {listText(coverage.seen)} of the machine.{' '}
            {coverage.guessed.length > 0
              ? `It guesses the ${listText(coverage.guessed)}, and the job records that.`
              : 'It sees every side.'}
          </p>
        ) : null}
        <label>
          License note (optional)
          <input name="license_note" maxLength={300} placeholder="For example: internal research testing only" />
          <span className="hint">Applies to every photo. Each photo's origin is recorded as its source.</span>
        </label>
        <label className="check">
          <input name="new_version" type="checkbox" value="true" />
          Build a new version even if this machine already has a twin
        </label>
        {problems.length > 0 ? (
          <ul className="error" role="alert">
            {problems.map((problem) => (
              <li key={problem}>{problem}</li>
            ))}
          </ul>
        ) : null}
        <div>
          <button type="submit" disabled={busy || problems.length > 0}>
            {busy ? 'Uploading…' : 'Start job'}
          </button>
        </div>
        {error ? (
          <p className="error" role="alert">
            {error}
          </p>
        ) : null}
      </form>
    </Section>
  )
}

interface ChosenPhoto {
  key: string
  file: File
  url: string // a blob: URL for the preview
  view: PhotoView | ''
  use: PhotoUse
  origin: string
}

/** A top view: the machine's front faces the person, who names sides as they see them. */
function WhereToStand() {
  const spots: [string, number, number][] = [
    ['Front', 160, 186],
    ['Front-left', 52, 168],
    ['Front-right', 268, 168],
    ['Left side', 40, 104],
    ['Right side', 280, 104],
    ['Back-left', 52, 34],
    ['Back-right', 268, 34],
    ['Back', 160, 18],
  ]
  return (
    <figure className="view-sketch">
      <svg viewBox="0 0 320 210" role="img" aria-labelledby="where-to-stand">
        <title id="where-to-stand">
          Seen from above: the machine in the middle, its front towards you. Left and right are
          yours as you face the front.
        </title>
        <rect x="120" y="62" width="80" height="84" fill="none" stroke="currentColor" strokeWidth="2" />
        <text x="160" y="108" textAnchor="middle" fontSize="12" fill="currentColor">
          machine
        </text>
        <line x1="124" y1="142" x2="196" y2="142" stroke="currentColor" strokeWidth="5" />
        <text x="160" y="160" textAnchor="middle" fontSize="11" fill="currentColor">
          its front
        </text>
        {spots.map(([label, x, y]) => (
          <g key={label}>
            <circle cx={x} cy={y - 4} r="4" fill="currentColor" />
            <text x={x} y={y + 12} textAnchor="middle" fontSize="11" fill="currentColor">
              {label}
            </text>
          </g>
        ))}
      </svg>
      <figcaption>
        Where to stand for each view, seen from above. Left and right are yours, facing the front, as
        manuals name them.
      </figcaption>
    </figure>
  )
}
