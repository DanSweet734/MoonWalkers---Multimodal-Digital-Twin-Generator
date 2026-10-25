// Which side each machine photo shows, in the words a person uses facing the machine's front
// (decision 0022). The backend checks the same rules (pipelines/b/photos.py); these only let the
// upload form say what is wrong before anything is sent.

import type { JobPhoto } from '../api/types.gen.ts'

export type PhotoView = NonNullable<JobPhoto['view']>
export type PhotoUse = JobPhoto['use']

export interface ViewChoice {
  view: PhotoView
  label: string
}

/** In the order a person walks round the machine, starting in front of it. */
export const VIEW_CHOICES: ViewChoice[] = [
  { view: 'front', label: 'Front' },
  { view: 'front_operator_right', label: 'Front-right corner (your right)' },
  { view: 'operator_right', label: 'Right side (your right)' },
  { view: 'back_operator_right', label: 'Back-right corner (your right)' },
  { view: 'back', label: 'Back' },
  { view: 'back_operator_left', label: 'Back-left corner (your left)' },
  { view: 'operator_left', label: 'Left side (your left)' },
  { view: 'front_operator_left', label: 'Front-left corner (your left)' },
  { view: 'detail', label: 'A close-up or part of the machine' },
]

const SIDES: PhotoView[] = ['front', 'operator_right', 'back', 'operator_left']
const CORNERS: PhotoView[] = [
  'front_operator_left',
  'front_operator_right',
  'back_operator_right',
  'back_operator_left',
]

export function viewText(view: PhotoView | null | undefined): string {
  if (!view) return 'View not given'
  return VIEW_CHOICES.find((c) => c.view === view)?.label ?? view
}

export function photoUseText(use: PhotoUse): string {
  return use === 'generator' ? 'Used to make the 3D model' : 'Kept as evidence'
}

/** A close-up is evidence; a view of the whole machine goes to the 3D generator. */
export function defaultUse(view: PhotoView | ''): PhotoUse {
  return view === 'detail' ? 'evidence' : 'generator'
}

export interface PhotoRow {
  view: PhotoView | ''
  use: PhotoUse
}

/** What the backend would refuse in these photos, in plain words; empty when they are fine. */
export function photoProblems(rows: PhotoRow[]): string[] {
  const problems: string[] = []
  if (rows.length > 1 && rows.some((r) => r.view === '')) {
    problems.push('With several photos, say where you stood for each one.')
  }
  const fed = rows.filter((r) => r.view !== '' && r.use === 'generator')
  if (rows.some((r) => r.view === 'detail' && r.use === 'generator')) {
    problems.push('A close-up cannot make the 3D model: keep it as evidence.')
  }
  const seen = new Set<string>()
  for (const row of fed) {
    if (seen.has(row.view)) {
      problems.push(
        `Two photos are both "${viewText(row.view as PhotoView)}". The 3D model takes one photo per view: keep the other as evidence.`,
      )
      break
    }
    seen.add(row.view)
  }
  const sides = fed.some((r) => SIDES.includes(r.view as PhotoView))
  const corners = fed.some((r) => CORNERS.includes(r.view as PhotoView))
  if (sides && corners) {
    problems.push(
      'The 3D model takes sides or corners, not both: keep the photos of one kind as evidence.',
    )
  }
  if (rows.length > 0 && rows.every((r) => r.view !== '' && r.use === 'evidence')) {
    problems.push('No photo makes the 3D model yet: one view of the whole machine needs to.')
  }
  return problems
}

/** The machine's sides the 3D generator sees from these views, and those it must guess. */
export function sidesSeen(views: PhotoView[]): { seen: string[]; guessed: string[] } {
  const shown: Record<string, string[]> = {
    front: ['front'],
    operator_right: ['right'],
    back: ['back'],
    operator_left: ['left'],
    front_operator_left: ['front', 'left'],
    front_operator_right: ['front', 'right'],
    back_operator_right: ['back', 'right'],
    back_operator_left: ['back', 'left'],
    detail: [],
  }
  const all = ['front', 'right', 'back', 'left']
  const seen = new Set(views.flatMap((v) => shown[v]))
  return { seen: all.filter((s) => seen.has(s)), guessed: all.filter((s) => !seen.has(s)) }
}

/** "front", "front and back", "front, right and left". */
export function listText(items: string[]): string {
  if (items.length < 2) return items.join('')
  return `${items.slice(0, -1).join(', ')} and ${items[items.length - 1]}`
}
