import { api } from '../api/client.ts'
import { Loading, ReviewBadge, Section } from '../components/common.tsx'
import { fileUrl, formatTime } from '../lib/format.ts'
import { useApi } from '../lib/hooks.ts'
import { jobHash, twinHash } from '../lib/route.ts'

export function TwinsPage() {
  const twins = useApi('twins', api.twins)
  return (
    <>
      <h1>Twins</h1>
      <p className="lead">
        Every stored twin version, newest first. A new version is built only when someone asks for
        one. A request for a machine reuses its newest approved version, or, if none is approved,
        its newest version not rejected. Approving never locks a twin: it can still be rebuilt.
      </p>
      {twins.data === undefined ? (
        <Loading error={twins.error} />
      ) : twins.data.length === 0 ? (
        <p className="muted">No twins yet. Start a job to build one.</p>
      ) : (
        twins.data.map((machine) => (
          <Section key={machine.machine_key} title={machine.machine_key}>
            <p className="muted">
              {machine.reusable_version
                ? `A request for this machine reuses v${machine.reusable_version}.`
                : 'Every version was rejected in review: a request builds a new one.'}
            </p>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th scope="col">Version</th>
                    <th scope="col">Built</th>
                    <th scope="col">Review</th>
                    <th scope="col">Run</th>
                    <th scope="col">USD</th>
                  </tr>
                </thead>
                <tbody>
                  {machine.versions.map((v) => (
                    <tr key={v.twin.twin_id}>
                      <th scope="row">
                        <a href={twinHash(v.twin.twin_id) ?? '#/twins'}>v{v.twin.version}</a>
                        {v.reusable ? <span className="muted small"> (reused by requests)</span> : null}
                      </th>
                      <td>{formatTime(v.twin.created_at)}</td>
                      <td>
                        <ReviewBadge status={v.review_status} />
                        {v.latest_review ? (
                          <div className="muted small">
                            {v.latest_review.reviewer}, {formatTime(v.latest_review.reviewed_at)}
                          </div>
                        ) : null}
                      </td>
                      <td>{v.run ? <a href={jobHash(v.run) ?? '#/jobs'}>{v.run.split('/')[3]}</a> : '-'}</td>
                      <td>
                        {v.twin.usd_path ? (
                          <a href={fileUrl(v.twin.usd_path)}>{v.twin.usd_path.split('/').pop()}</a>
                        ) : (
                          '-'
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Section>
        ))
      )}
    </>
  )
}
