// The dashboard's pages, kept in the URL hash (#/jobs, #/twins/haas/ha5c/3, ...), so a page can be
// bookmarked or reloaded and no router library is needed.

export type Route =
  | { page: 'jobs' }
  | { page: 'job'; machine: string; run: string }
  | { page: 'twins' }
  | { page: 'twin'; manufacturer: string; model: string; version: number }
  | { page: 'sources' }
  | { page: 'not-found'; hash: string }

export function parseRoute(hash: string): Route {
  const parts = hash
    .replace(/^#\/?/, '')
    .split('/')
    .filter((part) => part !== '')
    .map(decode)
  if (parts.some((part) => part === null)) return { page: 'not-found', hash }
  const [section, ...rest] = parts as string[]
  if (section === undefined || (section === 'jobs' && rest.length === 0)) return { page: 'jobs' }
  if (section === 'jobs' && rest.length === 2) {
    return { page: 'job', machine: rest[0], run: rest[1] }
  }
  if (section === 'twins' && rest.length === 0) return { page: 'twins' }
  if (section === 'twins' && rest.length === 3 && /^[1-9][0-9]*$/.test(rest[2])) {
    return { page: 'twin', manufacturer: rest[0], model: rest[1], version: Number(rest[2]) }
  }
  if (section === 'sources' && rest.length === 0) return { page: 'sources' }
  return { page: 'not-found', hash }
}

export function routeHash(route: Route): string {
  switch (route.page) {
    case 'jobs':
      return '#/jobs'
    case 'job':
      return `#/jobs/${encode(route.machine)}/${encode(route.run)}`
    case 'twins':
      return '#/twins'
    case 'twin':
      return `#/twins/${encode(route.manufacturer)}/${encode(route.model)}/${route.version}`
    case 'sources':
      return '#/sources'
    case 'not-found':
      return route.hash
  }
}

/** The page for a run path from the API, "machines/<machine>/runs/<run>". */
export function jobHash(run: string): string | null {
  const parts = run.split('/')
  if (parts.length !== 4 || parts[0] !== 'machines' || parts[2] !== 'runs') return null
  return routeHash({ page: 'job', machine: parts[1], run: parts[3] })
}

/** The page for a twin id from the API, "manufacturer/model@vN". */
export function twinHash(twinId: string): string | null {
  const match = /^([a-z0-9-]+)\/([a-z0-9]+)@v([1-9][0-9]*)$/.exec(twinId)
  if (match === null) return null
  return routeHash({
    page: 'twin',
    manufacturer: match[1],
    model: match[2],
    version: Number(match[3]),
  })
}

function decode(part: string): string | null {
  try {
    return decodeURIComponent(part)
  } catch {
    return null
  }
}

function encode(part: string): string {
  return encodeURIComponent(part)
}
