import assert from 'node:assert/strict'
import { test } from 'node:test'

import { fileKey, newPicks, type PickedFile } from './picks.ts'

const file = (name: string, size = 100, lastModified = 1): PickedFile => ({ name, size, lastModified })

test('a second pick adds to the photos already chosen', () => {
  const first = newPicks([], [file('front.jpg'), file('left.jpg')])
  assert.deepEqual(first.added.map((f) => f.name), ['front.jpg', 'left.jpg'])
  const second = newPicks(first.added, [file('manual/fig-1.png')])
  assert.deepEqual(second.added.map((f) => f.name), ['manual/fig-1.png'])
  assert.deepEqual(second.repeated, [])
})

test('a file picked again is left out and named', () => {
  const chosen = [file('front.jpg')]
  const { added, repeated } = newPicks(chosen, [file('front.jpg'), file('back.jpg')])
  assert.deepEqual(added.map((f) => f.name), ['back.jpg'])
  assert.deepEqual(repeated, ['front.jpg'])
})

test('two files of one name from two folders are both kept when they differ', () => {
  const { added } = newPicks([file('IMG_1.jpg', 100)], [file('IMG_1.jpg', 200)])
  assert.equal(added.length, 1)
})

test('a file twice in one pick is kept once', () => {
  const { added, repeated } = newPicks([], [file('a.jpg'), file('a.jpg')])
  assert.equal(added.length, 1)
  assert.deepEqual(repeated, ['a.jpg'])
})

test('the key holds the name, size and time', () => {
  assert.equal(fileKey(file('a.jpg', 5, 9)), 'a.jpg|5|9')
})
