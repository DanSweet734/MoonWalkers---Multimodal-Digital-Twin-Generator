import type { JobPhoto, RunFile, Source } from '../api/types.gen.ts'
import { fileUrl } from '../lib/format.ts'
import { photoUseText, viewText } from '../lib/views.ts'

/** Rendered views and screenshots; each opens full size in a new tab. */
export function Gallery({ images }: { images: RunFile[] }) {
  if (images.length === 0) return <p className="muted">No images yet.</p>
  return (
    <ul className="gallery">
      {images.map((image) => (
        <li key={image.path}>
          <figure>
            <a href={fileUrl(image.path)} target="_blank" rel="noreferrer">
              <img src={fileUrl(image.path)} alt={image.label} loading="lazy" />
            </a>
            <figcaption>{image.label}</figcaption>
          </figure>
        </li>
      ))}
    </ul>
  )
}

/** The job's input photo, with where it came from. */
export function Photo({ photo }: { photo: Source }) {
  return (
    <figure className="photo">
      <a href={fileUrl(photo.uri)} target="_blank" rel="noreferrer">
        <img src={fileUrl(photo.uri)} alt={photo.title ?? 'The input photo'} />
      </a>
      <figcaption>
        {photo.title ?? photo.uri}
        {photo.license_note ? ` · ${photo.license_note}` : ''}
      </figcaption>
    </figure>
  )
}

/** A job's photos with where each was taken and what it is used for (decision 0022): those
 * the 3D generator gets first, then the evidence. */
export function PhotoList({ photos }: { photos: JobPhoto[] }) {
  const ordered = [
    ...photos.filter((p) => p.use === 'generator'),
    ...photos.filter((p) => p.use === 'evidence'),
  ]
  return (
    <ul className="gallery">
      {ordered.map(({ source, view, use }) => (
        <li key={source.source_id}>
          <figure>
            <a href={fileUrl(source.uri)} target="_blank" rel="noreferrer">
              <img src={fileUrl(source.uri)} alt={source.title ?? 'An input photo'} loading="lazy" />
            </a>
            <figcaption>
              <strong>{viewText(view)}</strong> · {photoUseText(use)}
              <br />
              {source.title ?? source.uri}
              {source.license_note ? ` · ${source.license_note}` : ''}
            </figcaption>
          </figure>
        </li>
      ))}
    </ul>
  )
}

const KIND_LABELS: Record<RunFile['kind'], string> = {
  usd: 'Twin',
  check: 'Isaac Sim check files',
  notes: 'Run notes',
  record: 'Records (JSON)',
  mesh: 'Meshes',
  log: 'Logs',
  image: 'Images',
}

/** The run folder's files, grouped by kind. USD files and meshes download; the rest open. */
export function FileList({ files }: { files: RunFile[] }) {
  if (files.length === 0) return <p className="muted">No files yet.</p>
  const kinds = [...new Set(files.map((f) => f.kind))]
  return (
    <dl className="files">
      {kinds.map((kind) => (
        <div key={kind}>
          <dt>{KIND_LABELS[kind]}</dt>
          <dd>
            <ul>
              {files
                .filter((f) => f.kind === kind)
                .map((f) => (
                  <li key={f.path}>
                    <a href={fileUrl(f.path)} target="_blank" rel="noreferrer">
                      {f.label}
                    </a>
                  </li>
                ))}
            </ul>
          </dd>
        </div>
      ))}
    </dl>
  )
}
