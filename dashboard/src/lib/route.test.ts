import assert from 'node:assert/strict'
import { test } from 'node:test'

import { jobHash, parseRoute, routeHash, twinHash } from './route.ts'

test('an empty or unknown hash', () => {
  assert.deepEqual(parseRoute(''), { page: 'jobs' })
  assert.deepEqual(parseRoute('#/'), { page: 'jobs' })
  assert.deepEqual(parseRoute('#/nowhere'), { page: 'not-found', hash: '#/nowhere' })
  assert.deepEqual(parseRoute('#/twins/haas/ha5c/0'), {
    page: 'not-found',
    hash: '#/twins/haas/ha5c/0',
  })
  assert.deepEqual(parseRoute('#/jobs/%E0%A4%A'), { page: 'not-found', hash: '#/jobs/%E0%A4%A' })
})

test('every page round-trips through its hash', () => {
  const routes = [
    { page: 'jobs' },
    { page: 'job', machine: 'haas-ha5c', run: '2026-10-18_run-001' },
    { page: 'twins' },
    { page: 'twin', manufacturer: 'haas', model: 'ha5c', version: 3 },
    { page: 'sources' },
  ] as const
  for (const route of routes) {
    assert.deepEqual(parseRoute(routeHash(route)), route)
  }
})

test('run paths and twin ids from the API become page links', () => {
  assert.equal(
    jobHash('machines/haas-ha5c/runs/2026-10-18_run-001'),
    '#/jobs/haas-ha5c/2026-10-18_run-001',
  )
  assert.equal(jobHash('kb/twins/haas'), null)
  assert.equal(twinHash('haas/ha5c@v3'), '#/twins/haas/ha5c/3')
  assert.equal(twinHash('grizzly-industrial/t33901@v12'), '#/twins/grizzly-industrial/t33901/12')
  assert.equal(twinHash('haas/ha5c'), null)
})
