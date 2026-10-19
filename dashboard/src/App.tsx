import { api } from './api/client.ts'
import { useApi, useRoute } from './lib/hooks.ts'
import { routeHash, type Route } from './lib/route.ts'
import { JobPage } from './pages/JobPage.tsx'
import { JobsPage } from './pages/JobsPage.tsx'
import { SourcesPage } from './pages/SourcesPage.tsx'
import { TwinPage } from './pages/TwinPage.tsx'
import { TwinsPage } from './pages/TwinsPage.tsx'

const SECTIONS = [
  { label: 'Jobs', hash: '#/jobs', pages: ['jobs', 'job'] },
  { label: 'Twins', hash: '#/twins', pages: ['twins', 'twin'] },
  { label: 'Sources', hash: '#/sources', pages: ['sources'] },
]

export default function App() {
  const route = useRoute()
  return (
    <div className="app">
      <header className="topbar">
        <a className="brand" href="#/jobs">
          MoonWalkers
        </a>
        <nav aria-label="Main">
          {SECTIONS.map((s) => (
            <a
              key={s.hash}
              href={s.hash}
              aria-current={s.pages.includes(route.page) ? 'page' : undefined}
            >
              {s.label}
            </a>
          ))}
        </nav>
        <StatusLine />
      </header>
      <main key={routeHash(route)}>
        <Page route={route} />
      </main>
      <footer className="muted small">
        MoonWalkers proof of concept · runs on this computer only · every fact cites its source
      </footer>
    </div>
  )
}

function Page({ route }: { route: Route }) {
  switch (route.page) {
    case 'jobs':
      return <JobsPage />
    case 'job':
      return <JobPage machine={route.machine} run={route.run} />
    case 'twins':
      return <TwinsPage />
    case 'twin':
      return <TwinPage manufacturer={route.manufacturer} model={route.model} version={route.version} />
    case 'sources':
      return <SourcesPage />
    case 'not-found':
      return (
        <>
          <h1>Page not found</h1>
          <p>
            Nothing is at <code>{route.hash}</code>. <a href="#/jobs">Go to the jobs.</a>
          </p>
        </>
      )
  }
}

function StatusLine() {
  const status = useApi('status', api.status, 10000)
  if (status.error) {
    return (
      <p className="status error" role="status">
        {status.error}
      </p>
    )
  }
  if (!status.data) return <p className="status muted">Connecting…</p>
  const s = status.data
  return (
    <p className="status muted" title={s.data_dir}>
      {s.twin_versions} twin version{s.twin_versions === 1 ? '' : 's'} · {s.open_jobs} open job
      {s.open_jobs === 1 ? '' : 's'} · data folder {s.data_dir.split(/[\\/]/).slice(-2).join('/')}
    </p>
  )
}
