// Drawing and correcting a photo's cut-out (decision 0041): the method, SAM's box and points,
// and edits that add a region or a line to the cut-out or cut one away. The drawing is in
// fractions of the upright photo; the saved and previewed mask, made by the generator job, is
// the record. The geometry is in lib/cutout.ts.

import { useState, type KeyboardEvent, type PointerEvent } from 'react'

import { api } from '../api/client.ts'
import type { CutoutPreview, JobPhoto } from '../api/types.gen.ts'
import {
  boxFrom,
  change,
  cutoutFrom,
  draftFrom,
  draftProblems,
  editText,
  finishShape,
  isLineTool,
  isShapeTool,
  LINE_WIDTH,
  METHODS,
  near,
  sameCutout,
  start,
  svgPoints,
  toFraction,
  TOOLS,
  undo,
  type Draft,
  type Tool,
  type XY,
} from '../lib/cutout.ts'
import { fileUrl } from '../lib/format.ts'
import { viewText } from '../lib/views.ts'
import { ErrorNote } from './common.tsx'

const HELP: Record<Tool, string> = {
  box: 'Drag a box around the whole machine.',
  keep: 'Click on parts of the machine the cut-out loses.',
  leave: 'Click on things in front of or behind the machine that the cut-out keeps.',
  add: 'Click the corners of a region to add; click the first corner, double-click or press Enter to close it.',
  remove: 'Click the corners of a region to cut away; click the first corner, double-click or press Enter to close it.',
  'add-line': 'Click along a cable or hose to add it; double-click or press Enter to end the line.',
  'remove-line': 'Click along a line to cut away; double-click or press Enter to end it.',
}

interface Props {
  machine: string
  run: string
  photo: JobPhoto
  editable: boolean
  version: string // changes when the run folder does, so a new mask is fetched
  onChanged: () => void
  onClose: () => void
}

export function CutoutEditor({ machine, run, photo, editable, version, onChanged, onClose }: Props) {
  const [history, setHistory] = useState(() => start(draftFrom(photo.cutout)))
  const [tool, setTool] = useState<Tool>(() => (draftFrom(photo.cutout).method === 'sam' ? 'box' : 'add'))
  const [drawing, setDrawing] = useState<XY[]>([])
  const [drag, setDrag] = useState<{ from: XY; to: XY } | null>(null)
  const [lineWidth, setLineWidth] = useState(LINE_WIDTH)
  const [note, setNote] = useState('')
  const [size, setSize] = useState<{ w: number; h: number } | null>(null)
  const [showMask, setShowMask] = useState(true)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string>()
  const [result, setResult] = useState<CutoutPreview | null>(null)

  const draft = history.present
  const saved = draftFrom(photo.cutout)
  const unsaved = !sameCutout(draft, saved)
  const problems = draftProblems(draft)
  const tools = TOOLS.filter((t) => t.methods.includes(draft.method))
  const active = tools.some((t) => t.tool === tool) ? tool : tools[0].tool
  const masked = showMask && photo.mask != null
  const photoUrl = fileUrl(photo.source.uri)

  const update = (next: Draft) => setHistory((h) => change(h, next))
  const at = (e: PointerEvent<SVGSVGElement>): XY =>
    toFraction(e.clientX, e.clientY, e.currentTarget.getBoundingClientRect())

  function finish() {
    const edit = finishShape(active, drawing, lineWidth, note)
    if (edit) {
      update({ ...draft, edits: [...draft.edits, edit] })
      setNote('')
    }
    setDrawing([])
  }

  function onPointerDown(e: PointerEvent<SVGSVGElement>) {
    if (!editable || e.button !== 0) return
    const p = at(e)
    if (active === 'box') {
      e.currentTarget.setPointerCapture(e.pointerId)
      setDrag({ from: p, to: p })
    } else if (active === 'keep' || active === 'leave') {
      update({ ...draft, points: [...draft.points, { x: p[0], y: p[1], keep: active === 'keep' }] })
    } else if (!isLineTool(active) && drawing.length >= 3 && near(p, drawing[0])) {
      finish()
    } else {
      setDrawing([...drawing, p])
    }
  }

  function onPointerUp(e: PointerEvent<SVGSVGElement>) {
    if (!drag) return
    const box = boxFrom(drag.from, at(e))
    if (box) update({ ...draft, box })
    setDrag(null)
  }

  function onKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    if (e.key === 'Enter' && drawing.length > 0) {
      e.preventDefault()
      finish()
    } else if (e.key === 'Escape') {
      setDrawing([])
      setDrag(null)
    } else if (e.key === 'z' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault()
      setDrawing([])
      setHistory(undo)
    }
  }

  async function act(label: string, work: () => Promise<void>) {
    setBusy(label)
    setError(undefined)
    try {
      await work()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(null)
    }
  }

  const save = () =>
    api.setCutout(machine, run, photo.source.source_id, { cutout: cutoutFrom(draft) }).then(() => {
      setHistory(start(draft))
      onChanged()
    })
  const preview = () =>
    api.previewCutouts(machine, run).then((done) => {
      setResult(done)
      onChanged()
    })

  const w = size?.w ?? 1
  const h = size?.h ?? 1
  const r = Math.max(w, h) * 0.006
  const shown = drag ? boxFrom(drag.from, drag.to) : draft.box

  return (
    <div className="cutout-editor" onKeyDown={onKeyDown}>
      <div className="cutout-head">
        <h3>Cut-out: {viewText(photo.view)}</h3>
        <button type="button" onClick={onClose}>
          Close
        </button>
      </div>
      <p className="muted small">
        {photo.source.title ?? photo.source.uri}. Coordinates are fractions of the upright photo;
        the generator job draws the edits in order, a later one winning where two overlap, then
        drops pieces smaller than the share set below.
      </p>
      {!editable ? (
        <p className="callout">
          This run has generated its mesh, or is built, so its cut-outs no longer change (decision
          0029). Start a new run to change them.
        </p>
      ) : null}

      <div className="cutout-controls">
        <label>
          Method{' '}
          <select
            value={draft.method}
            disabled={!editable}
            onChange={(e) => update({ ...draft, method: e.target.value as Draft['method'] })}
          >
            {METHODS.filter((m) => m.method !== 'mask' || draft.mask).map((m) => (
              <option key={m.method} value={m.method}>
                {m.label}
              </option>
            ))}
          </select>
        </label>
        <fieldset className="cutout-tools" disabled={!editable}>
          <legend>Tool</legend>
          {tools.map((t) => (
            <label key={t.tool}>
              <input
                type="radio"
                name={`tool-${photo.source.source_id}`}
                checked={active === t.tool}
                onChange={() => {
                  setTool(t.tool)
                  setDrawing([])
                }}
              />{' '}
              {t.label}
            </label>
          ))}
        </fieldset>
        {isLineTool(active) ? (
          <label>
            Line width, % of the photo's width{' '}
            <input
              type="number"
              min={0.1}
              max={20}
              step={0.1}
              value={Number((lineWidth * 100).toFixed(1))}
              onChange={(e) => setLineWidth(Number(e.target.value) / 100)}
            />
          </label>
        ) : null}
        {isShapeTool(active) ? (
          <label>
            Note for the next edit{' '}
            <input
              value={note}
              maxLength={200}
              placeholder="what it covers, e.g. the pendant"
              onChange={(e) => setNote(e.target.value)}
            />
          </label>
        ) : null}
        <label>
          Smallest piece kept, share of the largest{' '}
          <input
            type="number"
            min={0}
            max={1}
            step={0.01}
            value={draft.minPiece}
            disabled={!editable}
            onChange={(e) => update({ ...draft, minPiece: Number(e.target.value) })}
          />
        </label>
        <label>
          <input
            type="checkbox"
            checked={showMask}
            disabled={photo.mask == null}
            onChange={(e) => setShowMask(e.target.checked)}
          />{' '}
          Dim what the last preview cut away
        </label>
      </div>
      <p className="small">{editable ? HELP[active] : null}</p>

      <div className={`cutout-stage${masked ? ' masked' : ''}`}>
        <img
          src={photoUrl}
          alt={`The ${viewText(photo.view)} photo`}
          onLoad={(e) => setSize({ w: e.currentTarget.naturalWidth, h: e.currentTarget.naturalHeight })}
        />
        {masked && photo.mask ? (
          <img
            className="kept"
            src={photoUrl}
            alt=""
            aria-hidden="true"
            style={{
              maskImage: `url("${fileUrl(photo.mask)}?v=${encodeURIComponent(version)}")`,
              maskMode: 'luminance',
              maskSize: '100% 100%',
            }}
          />
        ) : null}
        {size ? (
          <svg
            viewBox={`0 0 ${w} ${h}`}
            preserveAspectRatio="none"
            onPointerDown={onPointerDown}
            onPointerMove={(e) => drag && setDrag({ ...drag, to: at(e) })}
            onPointerUp={onPointerUp}
            onDoubleClick={() => drawing.length > 0 && finish()}
            aria-label="Draw on the photo"
          >
            {draft.edits.map((edit, i) =>
              edit.width != null ? (
                <g key={i} className={`edit ${edit.op}`}>
                  <polyline
                    className="band"
                    points={svgPoints(edit.points, w, h)}
                    strokeWidth={edit.width * w}
                  />
                  <polyline className="spine" points={svgPoints(edit.points, w, h)} />
                </g>
              ) : (
                <polygon key={i} className={`edit ${edit.op}`} points={svgPoints(edit.points, w, h)} />
              ),
            )}
            {draft.method === 'sam' || draft.method === 'crop'
              ? shown && (
                  <rect
                    className="box"
                    x={shown[0] * w}
                    y={shown[1] * h}
                    width={(shown[2] - shown[0]) * w}
                    height={(shown[3] - shown[1]) * h}
                  />
                )
              : null}
            {draft.method === 'sam'
              ? draft.points.map((p, i) => (
                  <g key={i} className={p.keep ? 'point keep' : 'point leave'}>
                    <circle cx={p.x * w} cy={p.y * h} r={r} />
                    <text x={p.x * w} y={p.y * h} fontSize={r * 1.6}>
                      {p.keep ? '+' : '×'}
                    </text>
                  </g>
                ))
              : null}
            {drawing.length > 0 ? (
              <polyline
                className={`drawing ${active.startsWith('add') ? 'add' : 'remove'}`}
                points={svgPoints(drawing, w, h)}
                strokeWidth={isLineTool(active) ? lineWidth * w : undefined}
              />
            ) : null}
          </svg>
        ) : null}
      </div>
      <p className="muted small">
        Shown: added regions light with a solid edge, regions cut away dark with a dashed edge;
        the box dashed; points to keep "+", to leave out "×".
        {photo.mask == null
          ? ' No preview has shown this photo yet.'
          : photo.preview === 'stale' || unsaved
            ? ' The dimmed mask is from the last preview, before the latest changes.'
            : ' The dimmed mask is the last preview of this cut-out.'}
      </p>

      {draft.edits.length > 0 ? (
        <ol className="edit-list">
          {draft.edits.map((edit, i) => (
            <li key={i}>
              {editText(edit, i).replace(/^\d+\. /, '')}{' '}
              {editable ? (
                <button
                  type="button"
                  className="link"
                  onClick={() => update({ ...draft, edits: draft.edits.filter((_, j) => j !== i) })}
                >
                  Delete
                </button>
              ) : null}
            </li>
          ))}
        </ol>
      ) : (
        <p className="muted small">No edits yet.</p>
      )}
      {draft.method === 'sam' ? (
        <p className="small">
          SAM: {draft.points.filter((p) => p.keep).length} points to keep,{' '}
          {draft.points.filter((p) => !p.keep).length} to leave out.{' '}
          {editable && draft.points.length > 0 ? (
            <button type="button" className="link" onClick={() => update({ ...draft, points: [] })}>
              Clear the points
            </button>
          ) : null}
        </p>
      ) : null}

      {problems.map((p) => (
        <p key={p} className="error">
          {p}
        </p>
      ))}
      <ErrorNote error={error} />
      {editable ? (
        <div className="cutout-actions">
          <button
            type="button"
            disabled={history.past.length === 0 || busy !== null}
            onClick={() => {
              setDrawing([])
              setHistory(undo)
            }}
          >
            Undo
          </button>
          <button
            type="button"
            disabled={!unsaved || problems.length > 0 || busy !== null}
            onClick={() => void act('Saving…', save)}
          >
            Save
          </button>
          <button
            type="button"
            disabled={problems.length > 0 || busy !== null}
            onClick={() =>
              void act('Cutting the photos out…', async () => {
                if (unsaved) await save()
                await preview()
              })
            }
          >
            {unsaved ? 'Save and preview' : 'Preview'}
          </button>
          <span className="muted small" aria-live="polite">
            {busy ?? (unsaved ? 'Not saved yet.' : 'Saved.')}
          </span>
        </div>
      ) : null}
      {result ? (
        <div className="small">
          <p>
            Cut out in {result.seconds.toFixed(1)} s (every photo the generator gets).{' '}
            <a href={fileUrl(result.sheet)} target="_blank" rel="noreferrer">
              Open the sheet
            </a>
          </p>
          <ul>
            {result.photos.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  )
}
