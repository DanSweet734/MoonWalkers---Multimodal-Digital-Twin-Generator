import { useEffect, useRef, useState, type FormEvent } from 'react'

import { api } from '../api/client.ts'
import { Loading, Section, StageBadge } from '../components/common.tsx'
import { formatTime, isOpen, stepsDone } from '../lib/format.ts'
import { useApi } from '../lib/hooks.ts'
import { jobHash, twinHash } from '../lib/route.ts'

export function JobsPage() {
  // Every few seconds, so a job the agent starts or moves on shows up without a reload.
  const jobs = useApi('jobs', api.jobs, 5000)
  return (
    <>
      <h1>Jobs</h1>
      <p className="lead">
        A job builds, or finds, one machine's digital twin from one photo. If the machine already has a
        twin and you don't ask for a new version, the platform reuses it at once. Otherwise the job
        waits for the agent (Claude Code), which reads the documents, builds the twin, and asks you
        about anything it can't decide.
      </p>
      <NewJobForm />
      <Section title="All jobs">
        {jobs.data === undefined ? (
          <Loading error={jobs.error} />
        ) : jobs.data.length === 0 ? (
          <p className="muted">No jobs yet. Upload a photo above to start one.</p>
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
  const [preview, setPreview] = useState<string | null>(null)
  const previewUrl = useRef<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | undefined>()

  function choose(file: File | undefined) {
    if (previewUrl.current) URL.revokeObjectURL(previewUrl.current)
    previewUrl.current = file ? URL.createObjectURL(file) : null
    setPreview(previewUrl.current)
  }

  useEffect(
    () => () => {
      if (previewUrl.current) URL.revokeObjectURL(previewUrl.current)
    },
    [],
  )

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setBusy(true)
    setError(undefined)
    try {
      const detail = await api.createJob(new FormData(event.currentTarget))
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
            <input name="manufacturer" required maxLength={100} placeholder="Haas" />
          </label>
          <label>
            Model
            <input name="model" required maxLength={100} placeholder="HA5C" />
          </label>
        </div>
        <label>
          Machine photo (JPEG or PNG)
          <input
            name="photo"
            type="file"
            accept="image/jpeg,image/png"
            required
            onChange={(e) => choose(e.target.files?.[0])}
          />
        </label>
        {preview ? <img className="upload-preview" src={preview} alt="The photo to upload" /> : null}
        <label>
          Where the photo came from
          <input
            name="origin"
            required
            maxLength={500}
            placeholder="A URL, or who took it, where and when"
          />
          <span className="hint">Recorded as the photo's source, so the twin can cite it.</span>
        </label>
        <label>
          License note (optional)
          <input name="license_note" maxLength={300} placeholder="For example: internal research testing only" />
        </label>
        <label className="check">
          <input name="new_version" type="checkbox" value="true" />
          Build a new version even if this machine already has a twin
        </label>
        <div>
          <button type="submit" disabled={busy}>
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
