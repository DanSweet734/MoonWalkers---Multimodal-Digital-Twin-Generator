# 0014 - The API and barebones dashboard: run folders as jobs, the agent builds, local only

- **Status:** proposed (Claude Code, Phase 5). Daniel chose the install, the job flow, review in
  the dashboard and the monochrome look on 2026-10-18; the design awaits his review in the Phase 5
  PR.
- **Date:** 2026-10-18
- **Decided by:** team (Daniel)

## Context
Phase 5 of `docs/poc-plan.md` asks for:
- FastAPI endpoints for jobs, twins and sources;
- a dashboard to upload photos, see job status, and see a twin with its sources and review status.

What was already settled:
- **Stack.** Decision 0001 fixed FastAPI and a React dashboard, "barebones first".
- **Agent.** Decision 0003 makes Claude Code the PoC's agent, driving the platform through the MCP
  server of decision 0013.
- **Building.** A Pipeline B build needs judgement: which axes, what turns, which facts. The MCP
  tools leave those to the agent and the person.
- **Shape.** The README's planned flow is "Dashboard -> Backend API -> ... Agent", with a job store.

Facts, quotes and measurements are in `docs/research/2026-10-18-api-and-dashboard.md`.

## Options considered
1. **Who builds a job uploaded in the dashboard.**
   - (a) **The job waits for Claude Code.** The API saves the photo and starts the run, and reuses
     a stored twin at once when that applies. Otherwise the person asks Claude Code to build the
     job, and the dashboard follows its steps.
   - (b) **The API starts Claude Code headless** (`claude -p`) per job. More automatic, but the
     agent's question to the person (which parts turn) has no way back to the dashboard yet.
     Permissions would have to be pre-allowed, and every job would use Daniel's Claude plan.
   - (c) **The API runs the generator itself** on upload. The GPU would then be shared between two
     processes, for one step of a build the agent finishes anyway [INFERENCE].
2. **One process or two.**
   - (a) A separate API process on the same data folder.
   - (b) The MCP server over Streamable HTTP, mounted in the API. One process, but it changes
     decision 0013's stdio setup, and the API must be running before Claude Code can work.
3. **The job store.**
   - (a) Run folders, read through the same `moonwalkers.workspace` code the MCP tools use. A
     job's stage comes from the files its steps leave.
   - (b) A separate job table, which the agent's tools would also have to update.
4. **TypeScript types.**
   - (a) `openapi-typescript`: refused next to TypeScript 6 (ERESOLVE, observed).
   - (b) `json-schema-to-typescript`: 15 packages, 15.4 MB, with tuple support not confirmed.
   - (c) A small generator of our own, reading the API's OpenAPI schema, with a drift test.
5. **Protection.**
   - (a) A login: more than a single-user PoC needs.
   - (b) Local only (127.0.0.1), with the checks a browser cannot get around: Host, a custom header
     and Origin.
   - (c) Nothing: any web page open in the same browser could upload files [INFERENCE].
6. **Dashboard libraries.**
   - (a) None beyond React: `fetch`, a hash router and polling.
   - (b) A router, a data-fetching library and a UI kit: more installs for a barebones page.

## Decision
Daniel chose 1a (the job waits for Claude Code), the FastAPI install with our own type script
(4c), and a plain monochrome look. The rest are Claude Code's proposals: 2a, 3a, 5b and 6a.

- **Packages.** `backend/src/moonwalkers/api/`, on `fastapi>=0.146,<0.147`. `uvicorn` and
  `python-multipart` are direct dependencies.
  - Start it with `uv run python -m moonwalkers.api [--data DIR] [--port 8000]`. It listens on
    127.0.0.1 only.
  - The data folder is found as the MCP server finds it (`moonwalkers.workspace.default_data_dir`).
- **Shared workspace.** The run-folder code moved from `moonwalkers.mcp` to `moonwalkers.workspace`
  so the API and the agent share it:
  - `runs` (the `Workspace`);
  - `status` (each job's stage, from its files);
  - `files` (images and outputs);
  - `inputs` (uploads).

  `start_run` now takes the next number when another process made the same folder first.
- **Endpoints.**

  | Endpoint | What it does |
  |---|---|
  | `GET /api/status` | The data folder, and how many twins and open jobs it holds |
  | `GET /api/jobs`, `GET /api/jobs/{machine}/{run}` | Jobs (run folders with `request.json`) with their steps, reading notes so far, images and files |
  | `POST /api/jobs` | Upload one photo (JPEG or PNG, at most 25 MB) with the machine, where the photo came from, a license note and `new_version` |
  | `GET /api/twins`, `GET /api/twins/{manufacturer}/{model}` | Versions newest first, with review status and which one a request would reuse |
  | `GET /api/twins/{manufacturer}/{model}/versions/{version}` | One version: its results, each source with what cites it (item, locator, quote), images and files |
  | `POST .../versions/{version}/reviews` | Approve or reject a version (decision 0015) |
  | `GET /api/sources` | Every cited document once, with the twins citing it |
  | `GET /api/files/{path}` | A file under `machines/<machine>/inputs/` or `.../runs/`, by its data-folder path |

  The interactive documentation is at `/api/docs`.
- **Uploads.**
  - The photo goes to `inputs/photos/<local date>_<name>` with a `SOURCES.md` line. It is never
    overwritten, and identical bytes reuse the file already there.
  - The run is started and the photo added, as `start_run` and `add_input` would.
  - The request then goes to `Orchestrator.reuse`. If the machine has a reusable twin and no new
    version was asked for, the job is answered at once and `request.job_result.json` is written.
  - Otherwise the job waits, and its page shows the prompt to give Claude Code.
- **The agent's side.** A read-only MCP tool, `list_jobs`, lists open jobs with the next step. The
  agent continues a dashboard job from `add_reference_source` (`docs/agent-procedure.md`). That
  makes 16 tools.
- **Protection (5b).**
  - Starlette's `TrustedHostMiddleware` allows only `localhost` and `127.0.0.1`.
  - A write needs the `X-MoonWalkers-Client` header, is refused if marked
    `Sec-Fetch-Site: cross-site`, and is refused from an `Origin` off this computer.
  - Files are served only from inputs and run folders, by type. Saved web pages go as
    `text/plain`; every file but a PDF gets `Content-Security-Policy: sandbox`.
  - The built dashboard gets its own Content-Security-Policy and `X-Frame-Options: DENY`.
- **Dashboard (6a).**
  - Pages: jobs, with the upload form; one job, refreshed every 2 s while open; twins; one twin,
    with the review form; sources.
  - Data comes through `fetch` (`src/api/client.ts`), with types from `src/api/types.gen.ts`.
  - In development, Vite forwards `/api` to port 8000. After `npm run build`, the API serves the
    dashboard at `/`.
- **Types (4c).** `uv run python -m moonwalkers.api.typescript` writes `types.gen.ts`, and
  `tests/test_api_typescript.py` fails when it is out of date.
- **Tests.**
  - Backend: pytest through FastAPI's test client.
  - Dashboard: `npm test` runs the pure modules with Node 24's own test runner; nothing is
    installed for it.

## Consequences
- **No GPU work and no agent in the API.** A dashboard job needs a person to start Claude Code on
  it. The upload page says so and gives the prompt. Building from the dashboard alone (option 1b)
  is a later step.
- **Two processes, one data folder.**
  - The API and the MCP server write different files: the API writes uploads, new run folders and
    reviews; the agent writes the rest of a run and new twins.
  - Each process has its own lock. Two writers on the same file at the same moment are still not
    guarded against (decision 0008).
- **One source of truth for a job's stage.** The dashboard and `list_jobs` read the same files, so
  they cannot disagree. A job that failed midway shows as in progress at its last step, with the
  time of its last change.
- **No CORS, no login.** Anyone who can run programs on this computer can use the API. Sharing it
  on a network needs authentication first [INFERENCE].
- **Our own type generator** is 175 lines we maintain. If `openapi-typescript` supports
  TypeScript 6 later, switching means one npm package and deleting `api/typescript.py`.
- **Reversing it.** The API only reads the workspace and calls the orchestrator. Removing it, or
  moving to option 1b or 2b, leaves the pipeline, the orchestrator and the knowledge base as they
  are.
