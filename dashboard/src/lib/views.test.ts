import assert from 'node:assert/strict'
import { test } from 'node:test'

import {
  defaultUse,
  listText,
  photoProblems,
  sidesSeen,
  VIEW_CHOICES,
  viewText,
  type PhotoRow,
} from './views.ts'

const row = (view: PhotoRow['view'], use = defaultUse(view)): PhotoRow => ({ view, use })

test('every view has a label in the operator\'s words', () => {
  assert.equal(VIEW_CHOICES.length, 9)
  assert.equal(viewText('operator_right'), 'Right side (your right)')
  assert.equal(viewText('front_operator_left'), 'Front-left corner (your left)')
  assert.equal(viewText(null), 'View not given')
})

test('a close-up is evidence by default', () => {
  assert.equal(defaultUse('detail'), 'evidence')
  assert.equal(defaultUse('back'), 'generator')
  assert.equal(defaultUse(''), 'generator')
})

test('one photo needs no view, and good sets have no problems', () => {
  assert.deepEqual(photoProblems([row('')]), [])
  assert.deepEqual(
    photoProblems([row('front_operator_left'), row('front_operator_right'), row('detail')]),
    [],
  )
  assert.deepEqual(photoProblems([row('front'), row('front', 'evidence'), row('back')]), [])
})

test('the rules the backend enforces are explained before uploading', () => {
  assert.match(photoProblems([row('front'), row('')])[0], /say where you stood/)
  assert.match(photoProblems([row('front'), row('front')])[0], /one photo per view/)
  assert.match(photoProblems([row('front'), row('front_operator_right')])[0], /sides or corners/)
  assert.match(photoProblems([row('detail', 'generator')])[0], /close-up cannot/)
  assert.match(photoProblems([row('detail'), row('back', 'evidence')])[0], /No photo makes/)
})

test('the sides seen and guessed follow from the views', () => {
  assert.deepEqual(sidesSeen(['front_operator_left', 'front_operator_right']), {
    seen: ['front', 'right', 'left'],
    guessed: ['back'],
  })
  assert.deepEqual(sidesSeen(['front']), { seen: ['front'], guessed: ['right', 'back', 'left'] })
})

test('lists read as a sentence', () => {
  assert.equal(listText(['back']), 'back')
  assert.equal(listText(['front', 'back']), 'front and back')
  assert.equal(listText(['front', 'right', 'left']), 'front, right and left')
})
