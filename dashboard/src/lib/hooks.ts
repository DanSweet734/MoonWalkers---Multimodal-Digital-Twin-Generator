// React hooks: the current page from the URL hash, and data loaded from the API.

import { useCallback, useEffect, useRef, useState } from 'react'

import { parseRoute, type Route } from './route.ts'

export function useRoute(): Route {
  const [route, setRoute] = useState(() => parseRoute(window.location.hash))
  useEffect(() => {
    const update = () => setRoute(parseRoute(window.location.hash))
    window.addEventListener('hashchange', update)
    return () => window.removeEventListener('hashchange', update)
  }, [])
  return route
}

export interface Loaded<T> {
  data: T | undefined
  error: string | undefined
  reload: () => void
}

/**
 * Load `key`'s data with `load`, and again every `pollMs` while that is set (for example while a
 * job waits for the agent). A new key starts over; an error keeps the data last loaded.
 */
export function useApi<T>(key: string, load: () => Promise<T>, pollMs?: number): Loaded<T> {
  const [state, setState] = useState<{ key: string; data?: T; error?: string }>({ key })
  const [round, setRound] = useState(0)
  const loadRef = useRef(load)
  useEffect(() => {
    loadRef.current = load
  })
  useEffect(() => {
    let current = true
    const run = () =>
      loadRef.current().then(
        (data) => {
          if (current) setState({ key, data })
        },
        (error: unknown) => {
          if (!current) return
          const message = error instanceof Error ? error.message : String(error)
          setState((s) => ({ key, data: s.key === key ? s.data : undefined, error: message }))
        },
      )
    void run()
    const timer = pollMs ? window.setInterval(run, pollMs) : undefined
    return () => {
      current = false
      window.clearInterval(timer)
    }
  }, [key, pollMs, round])
  const reload = useCallback(() => setRound((r) => r + 1), [])
  const same = state.key === key
  return { data: same ? state.data : undefined, error: same ? state.error : undefined, reload }
}
