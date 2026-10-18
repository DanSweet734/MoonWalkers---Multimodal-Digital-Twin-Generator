# MoonWalkers dashboard

A barebones web page for people (decision 0014):
- **Jobs:** upload a machine photo and follow the job as the agent builds it.
- **Twins:** each version with its facts, sources, citations and files, and its reviews.
- **Sources:** every cited document, with the twins that cite it.

It talks only to the MoonWalkers API (`backend/src/moonwalkers/api`). How to run both, and what to
check by hand: `docs/setup/dashboard.md`.

## Commands
Run these from `dashboard/`:
- `npm ci`: install the exact packages in `package-lock.json`.
- `npm run dev`: http://localhost:5173, with `/api` forwarded to the API on port 8000.
- `npm run build`: type-check (app and tests), then build into `dist/`, which the API serves at `/`.
- `npm run lint`: Oxlint.
- `npm test`: the unit tests (`src/**/*.test.ts`), run by Node's own test runner.

## Layout
| Path | What it holds |
|---|---|
| `src/api/types.gen.ts` | TypeScript types generated from the API's models. Don't edit it; from `backend/`, run `uv run python -m moonwalkers.api.typescript` |
| `src/api/client.ts` | The API calls. Writes send the `X-MoonWalkers-Client` header, which the API requires |
| `src/lib/` | Routes in the URL hash, wording and formatting (`route.ts`, `format.ts`, with tests), and React hooks (`hooks.ts`) |
| `src/components/` | Badges, citations, notes tables, images and file lists |
| `src/pages/` | One file per page |
| `src/index.css` | The monochrome style: white, grays and black. State is shown in words and border styles, not color |

## Conventions
- **No libraries beyond React.** `fetch` for data, the URL hash for pages, polling for live job
  status.
- **TypeScript strict,** with erasable syntax only, so Node can run the tests without a build
  step. Import local files with their extension (`./format.ts`).
- **Pure logic** goes in `src/lib/` with a `*.test.ts` next to it.
