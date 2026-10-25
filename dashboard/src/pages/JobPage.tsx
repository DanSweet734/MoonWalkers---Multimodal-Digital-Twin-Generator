import { useState } from 'react'

import { api } from '../api/client.ts'
import type { JobDetail, Source } from '../api/types.gen.ts'
import { ErrorNote, Loading, Section, StageBadge } from '../components/common.tsx'
import { FileList, Gallery, Photo, PhotoList } from '../components/media.tsx'
import { ControlList, FactsTable, IdentityBlock, IssueList } from '../components/notes.tsx'
import { fileUrl, formatTime, isOpen } from '../lib/format.ts'
import { useApi } from '../lib/hooks.ts'
import { twinHash } from '../lib/route.ts'

export function JobPage({ machine, run }: { machine: string; run: string }) {
  const [open, setOpen] = useState(true)
  // Every 2 s while the job is open, so the agent's steps show up as it takes them.
  const job = useApi(
    `job:${machine}/${run}`,
    async () => {
      const detail = await api.job(machine, run)
      setOpen(isOpen(detail.job.stage))
      return detail
    },
    open ? 2000 : undefined,
  )
  if (job.data === undefined) return <Loading error={job.error} />
  return <JobView detail={job.data} error={job.error} />
}

function JobView({ detail, error }: { detail: JobDetail; error: string | undefined }) {
  const { job, notes } = detail
  const result = job.requests[0]?.result
  const twin = job.twin_id ? twinHash(job.twin_id) : null
  const sources = new Map<string, Source>((notes?.sources ?? []).map((s) => [s.source_id, s]))
  return (
    <>
      <p className="crumbs">
        <a href="#/jobs">Jobs</a> / {job.machine}
      </p>
      <h1>
        {job.machine_key ?? job.machine} <span className="muted">· {job.name}</span>
      </h1>
      <ErrorNote error={error} />
      <div className="banner" aria-live="polite">
        <StageBadge stage={job.stage} /> <span>{job.stage_label}</span>
        {twin && job.twin_id ? (
          <>
            {' · '}
            <a href={twin}>Open {job.twin_id}</a>
          </>
        ) : null}
      </div>
      {result ? <p className="message">{result.message}</p> : null}
      {result?.twin.usd_path ? (
        <p>
          <a className="button-link" href={fileUrl(result.twin.usd_path)}>
            Download the twin (USD)
          </a>{' '}
          <span className="muted small">
            {result.twin.twin_id}, {result.twin.usd_path.split('/').pop()}: opens in Isaac Sim
          </span>
        </p>
      ) : null}
      {detail.agent_prompt ? <AgentPrompt prompt={detail.agent_prompt} /> : null}

      <Section title="Steps">
        <ol className="steps">
          {job.steps.map((step) => (
            <li key={step.step} className={step.done ? 'done' : 'todo'}>
              <span className="mark" aria-hidden="true">
                {step.done ? '✓' : '○'}
              </span>
              <span className="visually-hidden">{step.done ? 'Done: ' : 'Not yet: '}</span>
              {step.label}
              {step.step === 'preview' ? <span className="muted"> (optional)</span> : null}
              {step.detail ? <div className="muted small">{step.detail}</div> : null}
            </li>
          ))}
        </ol>
        <p className="muted small">
          Job <code>{job.job_id ?? '-'}</code>
          {job.new_version ? ', a new version was asked for' : ''}. Last change{' '}
          {formatTime(job.updated_at)}. Run folder <code>data/{job.run}</code>.
        </p>
      </Section>

      {job.photos && job.photos.length > 1 ? (
        <Section title={`Photos (${job.photos.length})`}>
          <PhotoList photos={job.photos} />
        </Section>
      ) : job.photo ? (
        <Section title="Photo">
          <Photo photo={job.photo} />
        </Section>
      ) : null}

      {notes ? (
        <Section title="Reading notes so far">
          {notes.identity ? <IdentityBlock identity={notes.identity} sources={sources} /> : null}
          <h3>Facts</h3>
          <FactsTable facts={notes.facts ?? []} sources={sources} />
          <h3>Control</h3>
          <ControlList control={notes.control ?? []} sources={sources} />
          <h3>Issues for the reviewer</h3>
          <IssueList issues={notes.issues ?? []} />
        </Section>
      ) : null}

      <Section title="Images">
        <Gallery images={detail.images} />
      </Section>
      <Section title="Files">
        <FileList files={detail.outputs} />
      </Section>
      {job.requests.length > 1 ? (
        <Section title="Requests in this run folder">
          <ul>
            {job.requests.map((r) => (
              <li key={r.file}>
                <code>{r.file}</code> (job <code>{r.job_id}</code>):{' '}
                {r.result ? r.result.message : 'not run yet'}
              </li>
            ))}
          </ul>
        </Section>
      ) : null}
    </>
  )
}

function AgentPrompt({ prompt }: { prompt: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <div className="callout">
      <p>
        <strong>Waiting for the agent.</strong> In Claude Code, opened in this project, ask:
      </p>
      <pre className="prompt">{prompt}</pre>
      <button
        type="button"
        onClick={() =>
          void navigator.clipboard.writeText(prompt).then(
            () => setCopied(true),
            () => setCopied(false),
          )
        }
      >
        {copied ? 'Copied' : 'Copy'}
      </button>
      <p className="muted small">
        This page follows the agent's steps as it works. Its question about the machine, if any,
        comes in Claude Code.
      </p>
    </div>
  )
}
