// A photo's cut-out as the dashboard draws it (decisions 0029 and 0041): the method, SAM's box
// and points, and edits (polygons and lines that add to the cut-out or cut away from it). Every
// coordinate is a fraction (0 to 1) of the photo turned upright, from its top left. Pure
// functions, tested with `npm test`.

import type { CutoutEditInput, CutoutInput, CutoutPoint, JobPhoto } from '../api/types.gen.ts'

export type Method = CutoutInput['method']
export type Box = [number, number, number, number]
export type XY = [number, number]
export type Tool = 'box' | 'keep' | 'leave' | 'add' | 'remove' | 'add-line' | 'remove-line'

/** What the editor holds while a person draws: always a whole cut-out, possibly not valid yet. */
export interface Draft {
  method: Method
  box: Box | null
  points: CutoutPoint[]
  mask: string | null
  minPiece: number
  edits: CutoutEditInput[]
}

export const MIN_PIECE = 0.02 // the backend's default (decision 0029)
export const LINE_WIDTH = 0.02 // [INFERENCE] about v3's conduits, 0.014 to 0.025 (decision 0041)
export const MAX_LINE_WIDTH = 0.2
const DIGITS = 4 // 0.0001 of a 4000-pixel photo is under half a pixel

export const TOOLS: { tool: Tool; label: string; methods: Method[] }[] = [
  { tool: 'box', label: 'Box around the machine', methods: ['sam', 'crop'] },
  { tool: 'keep', label: 'Point to keep', methods: ['sam'] },
  { tool: 'leave', label: 'Point to leave out', methods: ['sam'] },
  { tool: 'add', label: 'Add a region', methods: ['sam', 'crop', 'mask', 'auto'] },
  { tool: 'remove', label: 'Cut a region away', methods: ['sam', 'crop', 'mask', 'auto'] },
  { tool: 'add-line', label: 'Add a line (a cable)', methods: ['sam', 'crop', 'mask', 'auto'] },
  { tool: 'remove-line', label: 'Cut a line away', methods: ['sam', 'crop', 'mask', 'auto'] },
]

export const METHODS: { method: Method; label: string }[] = [
  { method: 'auto', label: 'Automatic removal, with edits' },
  { method: 'sam', label: 'SAM, with a box and points' },
  { method: 'crop', label: 'Automatic removal inside a box' },
  { method: 'mask', label: 'A mask drawn outside the tools' },
]

export function round(value: number): number {
  return Number(Math.min(1, Math.max(0, value)).toFixed(DIGITS))
}

/** A pointer position over the drawn photo, as fractions of it, kept inside it. */
export function toFraction(
  clientX: number,
  clientY: number,
  rect: { left: number; top: number; width: number; height: number },
): XY {
  return [round((clientX - rect.left) / rect.width), round((clientY - rect.top) / rect.height)]
}

/** The box two corners span, from its top left to its bottom right; null when too thin. */
export function boxFrom(a: XY, b: XY, least = 0.01): Box | null {
  const [x0, x1] = [Math.min(a[0], b[0]), Math.max(a[0], b[0])]
  const [y0, y1] = [Math.min(a[1], b[1]), Math.max(a[1], b[1])]
  return x1 - x0 < least || y1 - y0 < least ? null : [x0, y0, x1, y1]
}

/** Whether `p` is within `tolerance` (a fraction of the photo) of `q`: a click that closes a
 * polygon on its first point. */
export function near(p: XY, q: XY, tolerance = 0.012): boolean {
  return Math.hypot(p[0] - q[0], p[1] - q[1]) <= tolerance
}

export function isLineTool(tool: Tool): boolean {
  return tool === 'add-line' || tool === 'remove-line'
}

export function isShapeTool(tool: Tool): boolean {
  return tool === 'add' || tool === 'remove' || isLineTool(tool)
}

/** The edit a shape tool makes from the points clicked; null until it has enough (a polygon
 * 3, a line 2), as the backend requires. */
export function finishShape(
  tool: Tool,
  points: XY[],
  width = LINE_WIDTH,
  note = '',
): CutoutEditInput | null {
  if (!isShapeTool(tool)) return null
  const line = isLineTool(tool)
  // A double click that finishes a shape also clicks twice on its last point.
  const kept = points.filter((p, i) => i === 0 || !near(p, points[i - 1], 0.002))
  if (kept.length < (line ? 2 : 3)) return null
  const edit: CutoutEditInput = {
    op: tool === 'add' || tool === 'add-line' ? 'add' : 'remove',
    points: kept.map(([x, y]) => [round(x), round(y)]),
  }
  if (line) edit.width = Number(Math.min(MAX_LINE_WIDTH, Math.max(0.001, width)).toFixed(DIGITS))
  if (note.trim()) edit.note = note.trim().slice(0, 200)
  return edit
}

/** A cut-out the API returned (typed `unknown` by the generated types: the backend writes it
 * without empty fields) as a draft; null and anything unreadable start from the automatic
 * removal. */
export function draftFrom(value: unknown): Draft {
  const empty: Draft = { method: 'auto', box: null, points: [], mask: null, minPiece: MIN_PIECE, edits: [] }
  if (typeof value !== 'object' || value === null) return empty
  const c = value as Partial<CutoutInput>
  if (!METHODS.some((m) => m.method === c.method)) return empty
  return {
    method: c.method as Method,
    box: Array.isArray(c.box) && c.box.length === 4 ? (c.box.map(Number) as Box) : null,
    points: Array.isArray(c.points) ? c.points : [],
    mask: typeof c.mask === 'string' ? c.mask : null,
    minPiece: typeof c.min_piece === 'number' ? c.min_piece : MIN_PIECE,
    edits: Array.isArray(c.edits) ? c.edits : [],
  }
}

/** What stops a draft from being saved, in words; empty when it can be. */
export function draftProblems(draft: Draft): string[] {
  const problems: string[] = []
  if ((draft.method === 'sam' || draft.method === 'crop') && draft.box === null) {
    problems.push('Draw a box around the machine first.')
  }
  if (draft.method === 'mask' && !draft.mask) {
    problems.push('A mask cut-out needs its PNG; choose another method to draw one here.')
  }
  if (!(draft.minPiece >= 0 && draft.minPiece <= 1)) {
    problems.push('The smallest piece kept is a share from 0 to 1.')
  }
  return problems
}

/** The cut-out to save: only the fields its method takes. An automatic one with no edits is
 * the default, saved as null. */
export function cutoutFrom(draft: Draft): CutoutInput | null {
  if (draft.method === 'auto' && draft.edits.length === 0) return null
  const cutout: CutoutInput = { method: draft.method, min_piece: draft.minPiece }
  if (draft.method === 'sam' || draft.method === 'crop') cutout.box = draft.box
  if (draft.method === 'sam') cutout.points = draft.points
  if (draft.method === 'mask') cutout.mask = draft.mask
  if (draft.edits.length > 0) cutout.edits = draft.edits
  return cutout
}

/** Whether two drafts would save the same cut-out (so the editor knows what is unsaved). */
export function sameCutout(a: Draft, b: Draft): boolean {
  return JSON.stringify(cutoutFrom(a)) === JSON.stringify(cutoutFrom(b))
}

/** Points for an SVG polygon or polyline drawn in a viewBox the photo's size in pixels. */
export function svgPoints(points: XY[], width: number, height: number): string {
  return points.map(([x, y]) => `${x * width},${y * height}`).join(' ')
}

export function editText(edit: CutoutEditInput, index: number): string {
  const what = edit.width != null ? `line, ${percentOf(edit.width)} of the width` : 'region'
  const op = edit.op === 'add' ? 'Add' : 'Cut away'
  const note = edit.note ? `: ${edit.note}` : ''
  return `${index + 1}. ${op} a ${what}, ${edit.points.length} points${note}`
}

/** A photo's cut-out and its preview in a few words, for the job's photo list. */
export function cutoutSummary(photo: Pick<JobPhoto, 'cutout' | 'preview'>): string {
  const draft = draftFrom(photo.cutout)
  const method =
    cutoutFrom(draft) === null
      ? 'automatic'
      : (METHODS.find((m) => m.method === draft.method)?.label ?? draft.method)
  const edits = draft.edits.length === 1 ? ', 1 edit' : draft.edits.length ? `, ${draft.edits.length} edits` : ''
  const preview =
    photo.preview === 'current'
      ? 'previewed'
      : photo.preview === 'stale'
        ? 'changed since its preview'
        : 'not previewed'
  return `Cut-out: ${method}${edits}; ${preview}`
}

function percentOf(fraction: number): string {
  return `${Number((fraction * 100).toFixed(1))}%`
}

/** Undo for the editor: each change keeps the draft before it. */
export interface History {
  past: Draft[]
  present: Draft
}

export function start(draft: Draft): History {
  return { past: [], present: draft }
}

export function change(history: History, next: Draft): History {
  return { past: [...history.past, history.present].slice(-100), present: next }
}

export function undo(history: History): History {
  const previous = history.past.at(-1)
  return previous ? { past: history.past.slice(0, -1), present: previous } : history
}
