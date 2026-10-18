import { api } from '../api/client.ts'
import { Loading, SourceName } from '../components/common.tsx'
import { fileUrl, formatTime, shortHash } from '../lib/format.ts'
import { useApi } from '../lib/hooks.ts'
import { twinHash } from '../lib/route.ts'

export function SourcesPage() {
  const sources = useApi('sources', api.sources)
  return (
    <>
      <h1>Sources</h1>
      <p className="lead">
        Every document, photo and statement a stored twin cites, listed once. Open a twin to see
        which facts cite each one, with the page and the words quoted.
      </p>
      {sources.data === undefined ? (
        <Loading error={sources.error} />
      ) : sources.data.length === 0 ? (
        <p className="muted">No sources yet.</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th scope="col">Source</th>
                <th scope="col">Kind</th>
                <th scope="col">Retrieved</th>
                <th scope="col">SHA-256</th>
                <th scope="col">Cited by</th>
              </tr>
            </thead>
            <tbody>
              {sources.data.map((listing) => (
                <tr key={`${listing.source.uri}|${listing.source_ids.join(',')}`}>
                  <th scope="row">
                    <SourceName source={listing.source} />
                    <div className="muted small">
                      {listing.source_ids.map((id) => (
                        <code key={id}>{id} </code>
                      ))}
                      {listing.local_file ? (
                        <>
                          {'· '}
                          <a href={fileUrl(listing.local_file)} target="_blank" rel="noreferrer">
                            saved copy
                          </a>
                        </>
                      ) : null}
                    </div>
                  </th>
                  <td>
                    {listing.source.kind}
                    {listing.source.input_type ? ` (${listing.source.input_type})` : ''}
                  </td>
                  <td>{formatTime(listing.source.retrieved_at)}</td>
                  <td>
                    <code>{shortHash(listing.source.sha256)}</code>
                  </td>
                  <td>
                    {listing.twins.map((id) => (
                      <div key={id}>
                        <a href={twinHash(id) ?? '#/twins'}>{id}</a>
                      </div>
                    ))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}
