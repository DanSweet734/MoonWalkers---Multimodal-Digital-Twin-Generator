import assert from 'node:assert/strict'
import { test } from 'node:test'

import {
  errorDetail,
  extents,
  factValue,
  fileUrl,
  formatTime,
  isOpen,
  percent,
  reviewText,
  shortHash,
  speed,
  stageText,
  stepsDone,
  triple,
} from './format.ts'

test('stages and review statuses in words', () => {
  assert.equal(stageText('waiting_for_agent'), 'Waiting for the agent')
  assert.equal(reviewText('needs_review'), 'Needs review')
  assert.equal(isOpen('in_progress'), true)
  assert.equal(isOpen('reused'), false)
  const steps = [
    { step: 'photo', label: 'Photo added', done: true },
    { step: 'notes', label: 'Reading notes recorded', done: true },
    { step: 'preview', label: 'Preview rendered', done: false },
    { step: 'twin', label: 'Twin built', done: false },
  ] as const
  assert.equal(stepsDone([...steps]), '2 of 3 steps') // the optional preview is not counted
})

test('data-folder paths become file URLs, with each part encoded', () => {
  assert.equal(
    fileUrl('machines/haas-ha5c/inputs/photos/IMG 1#.jpg'),
    '/api/files/machines/haas-ha5c/inputs/photos/IMG%201%23.jpg',
  )
})

test('times, percentages and hashes', () => {
  assert.equal(formatTime('2026-10-18T20:09:44.725295Z', 'UTC'), 'Oct 18, 2026, 8:09 PM UTC')
  assert.equal(formatTime('not a time'), 'not a time')
  assert.equal(percent(0.85), '85%')
  assert.equal(shortHash('5ba3c704b582bc82f6ccfa7e11f246a593f1'), '5ba3c704b582')
  assert.equal(shortHash(null), '-')
})

test('values keep their SI units; speeds and sizes are also shown readably', () => {
  assert.equal(factValue({ value: 0.1016, unit: 'm' }), '0.1016 m')
  assert.equal(factValue({ value: true, unit: null }), 'yes')
  assert.equal(factValue({ value: '2 3/16-10' }), '2 3/16-10')
  assert.equal(speed(7.1558), '7.1558 rad/s (410 °/s)')
  assert.equal(extents([0, -0.1, 0], [0.297, 0.135, 0.255]), '297 mm deep × 235 mm wide × 255 mm high')
  assert.equal(extents(null, [1, 1, 1]), '-')
  assert.equal(triple([0, 0, 0.1016]), '(0, 0, 0.1016)')
})

test('error messages from the API', () => {
  assert.equal(errorDetail({ detail: 'no twin haas/ha5c@v9' }, 'x'), 'no twin haas/ha5c@v9')
  assert.equal(
    errorDetail({ detail: [{ loc: ['body', 'origin'], msg: 'Field required' }] }, 'x'),
    'origin: Field required',
  )
  assert.equal(errorDetail('<html>', '502 Bad Gateway'), '502 Bad Gateway')
  assert.equal(errorDetail({ detail: [] }, 'fallback'), 'fallback')
})
