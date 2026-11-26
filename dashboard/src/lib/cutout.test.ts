import assert from 'node:assert/strict'
import { test } from 'node:test'

import {
  boxFrom,
  change,
  cutoutFrom,
  cutoutSummary,
  draftFrom,
  draftProblems,
  editText,
  finishShape,
  near,
  sameCutout,
  start,
  svgPoints,
  toFraction,
  undo,
  type Draft,
} from './cutout.ts'

const SAM = {
  method: 'sam',
  box: [0.1, 0.2, 0.9, 0.95],
  points: [{ x: 0.5, y: 0.5, keep: true }],
  min_piece: 0.1,
  edits: [{ op: 'add', points: [[0.1, 0.1], [0.2, 0.1], [0.2, 0.2]], note: 'the pendant' }],
}

test('a pointer position is a fraction of the photo, kept inside it', () => {
  const rect = { left: 100, top: 50, width: 400, height: 200 }
  assert.deepEqual(toFraction(300, 100, rect), [0.5, 0.25])
  assert.deepEqual(toFraction(50, 400, rect), [0, 1])
  assert.deepEqual(toFraction(100 + 400 / 3, 50, rect), [0.3333, 0])
})

test('a box runs from its top left to its bottom right, and a thin one is refused', () => {
  assert.deepEqual(boxFrom([0.9, 0.8], [0.1, 0.2]), [0.1, 0.2, 0.9, 0.8])
  assert.equal(boxFrom([0.5, 0.5], [0.505, 0.9]), null)
})

test('a click near the first point closes a polygon', () => {
  assert.ok(near([0.1, 0.1], [0.105, 0.1]))
  assert.ok(!near([0.1, 0.1], [0.15, 0.1]))
})

test('a polygon needs 3 points and a line 2, as the backend does', () => {
  assert.equal(finishShape('add', [[0, 0], [1, 1]]), null)
  assert.deepEqual(finishShape('remove', [[0, 0], [1, 0], [1, 1]], 0.05, ' the rafter '), {
    op: 'remove',
    points: [[0, 0], [1, 0], [1, 1]],
    note: 'the rafter',
  })
  assert.equal(finishShape('add-line', [[0, 0]]), null)
  assert.deepEqual(finishShape('add-line', [[0, 0], [0.5, 0.123456]], 0.024), {
    op: 'add',
    points: [[0, 0], [0.5, 0.1235]],
    width: 0.024,
  })
  assert.equal(finishShape('remove-line', [[0, 0], [1, 1]], 0.9)?.width, 0.2) // at most 0.2
  // a double click on the last point counts once
  assert.equal(finishShape('add', [[0, 0], [1, 0], [1, 0.0005]]), null)
  assert.deepEqual(finishShape('add-line', [[0, 0], [0.5, 0.5], [0.5, 0.5]])?.points, [
    [0, 0],
    [0.5, 0.5],
  ])
  assert.equal(finishShape('box', [[0, 0], [1, 1], [0, 1]]), null)
})

test('a saved cut-out becomes a draft and back, unchanged', () => {
  const draft = draftFrom(SAM)
  assert.equal(draft.method, 'sam')
  assert.equal(draft.minPiece, 0.1)
  assert.deepEqual(cutoutFrom(draft), SAM)
})

test('no cut-out, or one that cannot be read, starts from the automatic removal', () => {
  for (const value of [null, undefined, 'sam', { method: 'lasso' }]) {
    const draft = draftFrom(value)
    assert.equal(draft.method, 'auto')
    assert.equal(cutoutFrom(draft), null) // the default: saved as null
  }
})

test('only the fields a method takes are saved', () => {
  const draft: Draft = { ...draftFrom(SAM), method: 'crop' }
  assert.deepEqual(cutoutFrom(draft), {
    method: 'crop',
    min_piece: 0.1,
    box: [0.1, 0.2, 0.9, 0.95],
    edits: SAM.edits,
  })
  const auto: Draft = { ...draft, method: 'auto' }
  assert.deepEqual(cutoutFrom(auto), { method: 'auto', min_piece: 0.1, edits: SAM.edits })
})

test('a draft says what stops it from being saved', () => {
  assert.deepEqual(draftProblems(draftFrom(SAM)), [])
  assert.deepEqual(draftProblems({ ...draftFrom(SAM), box: null }), [
    'Draw a box around the machine first.',
  ])
  assert.equal(draftProblems({ ...draftFrom(null), method: 'mask' }).length, 1)
  assert.equal(draftProblems({ ...draftFrom(null), minPiece: 2 }).length, 1)
})

test('drafts that save the same cut-out are the same', () => {
  const a = draftFrom(SAM)
  assert.ok(sameCutout(a, { ...a, mask: 'ignored for sam.png' }))
  assert.ok(!sameCutout(a, { ...a, edits: [] }))
})

test('svg points are in the photo\'s pixels', () => {
  assert.equal(svgPoints([[0.5, 0.25], [1, 1]], 400, 200), '200,50 400,200')
})

test('each edit is described in words', () => {
  assert.equal(
    editText({ op: 'add', points: [[0, 0], [1, 1], [0, 1]], note: 'the guard' }, 0),
    '1. Add a region, 3 points: the guard',
  )
  assert.equal(
    editText({ op: 'remove', points: [[0, 0], [1, 1]], width: 0.024 }, 1),
    '2. Cut away a line, 2.4% of the width, 2 points',
  )
})

test('undo goes back one change at a time', () => {
  const first = draftFrom(SAM)
  let history = start(first)
  history = change(history, { ...first, edits: [] })
  history = change(history, { ...first, method: 'auto', edits: [] })
  history = undo(history)
  assert.equal(history.present.method, 'sam')
  assert.equal(history.present.edits.length, 0)
  history = undo(undo(history))
  assert.deepEqual(history.present, first)
})

test('the photo list says how each photo is cut out and whether it was previewed', () => {
  assert.equal(cutoutSummary({ cutout: null }), 'Cut-out: automatic; not previewed')
  assert.equal(
    cutoutSummary({ cutout: SAM, preview: 'stale' }),
    'Cut-out: SAM, with a box and points, 1 edit; changed since its preview',
  )
  assert.equal(
    cutoutSummary({ cutout: { method: 'auto', edits: [SAM.edits[0], SAM.edits[0]] }, preview: 'current' }),
    'Cut-out: Automatic removal, with edits, 2 edits; previewed',
  )
})
