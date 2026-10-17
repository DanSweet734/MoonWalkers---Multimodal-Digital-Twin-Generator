# MoonWalkers Multimodal Agentic Digital Twin Generation Platform

CSUN capstone team (Daniel Sweet, Ava Harken, Sarkis Nazaryan, Shankar Kiran Ragavender) building a
platform where an AI agent turns machine information (photos, video, nameplates, brochures, drawings,
catalogs) into **functional digital twins** exported as OpenUSD (`.usd`) for NVIDIA Omniverse / Isaac Sim.
"Functional" = moving parts (joints) **and** control logic, confirmed by our advisors (Dr. Bingbing Li,
Dr. Thomas Lu). Full background: `docs/research/project-context.md` (read sections as needed, don't load it all).

## Current phase: proof of concept (PoC)
- Goal: show an AI agent can create a digital twin from one input type: **machine photos** (Pipeline B).
- Subject machine: **Haas HA5C** rotary indexer (one servo-driven spindle = one revolute joint; indexing
  program = control logic). Backup: Grizzly T33901 drill press.
- Pipelines A, C, D are **stubs** that return fixture data in the shared contract. Do not build them.
- Success levels: (1) scaled 3D model with cited facts opens in Isaac Sim; (2) spindle joint rotates;
  (3) an indexing program drives the joint. A second request for the same machine must reuse the stored
  twin and say so.
- Human review is expected: results default to `needs_human_review = true`.
- Work in the phases listed in `docs/poc-plan.md`. Stop at the end of each phase for review.

## Non-negotiable rules
1. **Every fact needs a source.** Spec values, dimensions, version numbers, and tool capabilities must
   cite a URL or file (with a page or quote when possible). Never invent numbers. If unsure, say
   "not confirmed" and ask. Label your own reasoning as `[INFERENCE]` in docs.
2. **Documentation is part of the work.** A task is not done until its docs are updated (see
   "Documentation workflow" below). Methodology matters as much as code.
3. **Ask before installing anything** (pip/uv/npm/winget packages, model weights, system tools).
   Explain what it is, why, its license, and its size first.
4. **Never read, print, or commit secrets.** API keys and tokens live in `.env` (gitignored) or the
   Hugging Face token cache. Use `example.env` for names only (not `.env.example`, which the
   `.env.*` patterns in `.gitignore` and the Claude Code deny rules would catch).
5. **Never commit large or generated files:** test media, model weights, generated meshes and `.usd`
   outputs stay in `data/` (gitignored). Commit only small fixtures under `backend/tests/fixtures/`.
6. **Respect the contract.** Pipelines return `PipelineResult`; only the orchestrator writes to the
   knowledge base. Change the contract only with a decision record and a version bump.

## Architecture (data flow)
Dashboard / AI agent (via MCP) -> Backend API -> Input Router -> Pipeline (A-D) -> `PipelineResult`
-> Agent Orchestrator -> Knowledge Base (store interface) + USD Exporter -> `.usd` -> Isaac Sim.
- For the PoC, **Claude Code is the agent**: the backend exposes its actions as MCP tools (add source,
  identify machine, check knowledge base, generate geometry, set scale, add joint, export, submit).
- Knowledge base: a simple JSON/SQLite store behind a `KnowledgeBase` interface; Neo4j comes later.
- Contract: `backend/src/moonwalkers/contracts/pipeline_result.py` (Pydantic, SCHEMA_VERSION 0.1.0).
- Units inside the contract are SI (m, rad, s, kg). Convert only at the USD export boundary.

## Repository layout (target)
- `backend/src/moonwalkers/` - Python package: `contracts/`, `pipelines/{a,b,c,d}/`, `orchestrator/`,
  `kb/`, `usd/` (exporter), `generators/` (image-to-3D adapters), `api/` (FastAPI), `mcp/` (MCP server)
- `backend/tests/` - pytest tests; `backend/tests/fixtures/` - small JSON/image fixtures
- `dashboard/` - React + TypeScript (Vite), barebones
- `data/` - local test data and outputs (gitignored, see `data/README.md`)
- `docs/` - methodology, decisions, worklog, research, setup guides

## Stack and environment
- Windows 11, one NVIDIA GeForce RTX 4090 (24 GB). Prefer cross-platform code (pathlib, no bash-only scripts).
- Python 3.12 managed with `uv`; FastAPI backend; Celery comes in the integration phase, not the PoC.
- OpenUSD via `usd-core` (`pxr`, includes `UsdPhysics`). Joints use standard UsdPhysics schemas:
  `ArticulationRootAPI`, `RevoluteJoint`, `DriveAPI`; body0 = parent, body1 = child. Export layout
  and rules: decision 0010 (`backend/src/moonwalkers/usd/`).
- Target the most recent Isaac Sim (6.2.0 as of Oct 16, 2026) for manual verification.
- Image-to-3D generators run in their **own** environment and are called as a subprocess through an
  adapter in `generators/`. Primary: Hunyuan3D-2mv (multi-view). Fallback: Stable Fast 3D (single image).
- Dashboard: React + TypeScript with Vite and npm; Oxlint for lint (decision 0007).

## Commands
First-time machine setup (uv, Python 3.12, Node.js LTS, GitHub CLI): `docs/setup/windows-dev-setup.md`.

Backend (run from `backend/`):
- Install/sync Python deps: `uv sync` (creates `backend/.venv` from `uv.lock`)
- Tests: `uv run pytest`; without GPU/slow tests: `uv run pytest -m "not gpu and not slow"`
- Lint and format: `uv run ruff check .` and `uv run ruff format .` (check only: `uv run ruff format --check .`)
- Regenerate the contract JSON Schema after a contract change: `uv run python -m moonwalkers.contracts.json_schema`
- Write the box-and-cylinder test twin (Phase 2 check): `uv run python -m moonwalkers.usd.primitive_twin ../data/machines/moonwalkers-testindexer/runs/<run>`
- Validate an exported twin: `uv run python -m moonwalkers.usd.validate <file.usda>`, then NVIDIA's `uv run omni_asset_validate <file.usda>`
- Check a twin by eye in Isaac Sim: `docs/setup/isaac-sim-check.md`
- API (dev, from Phase 5; FastAPI and uvicorn are not installed yet): `uv run uvicorn moonwalkers.api.app:app --reload`

Dashboard (run from `dashboard/`):
- Install deps: `npm ci` (exact versions from `package-lock.json`)
- Dev server: `npm run dev` (http://localhost:5173)
- Type-check and build: `npm run build`
- Lint (Oxlint): `npm run lint`

## Code conventions
- Python: type hints everywhere, ruff for lint and format, pytest for tests, small pure functions.
- Every new module gets tests. Fix failing tests before committing; never delete a test to make it pass.
- No network calls in unit tests; use fixtures. Mark GPU or slow tests `@pytest.mark.gpu` / `slow`.
- TypeScript: strict mode; generate types from `contracts/*.schema.json` rather than hand-copying.

## Git workflow
- Never commit to `main` directly. One branch per task: `feat/...`, `fix/...`, `docs/...`, `chore/...`.
- Conventional Commits (`feat: add JSON knowledge base store`). Small, focused commits.
- Open a pull request with `gh pr create` when a phase or task is complete. PR description must list:
  what changed, how it was tested, docs updated, open questions.
- Never force-push, never rewrite pushed history. To bring `main` into a feature branch, merge it in
  (`git merge origin/main`) rather than rebasing; stacked PRs are merged in order with merge commits.

## Documentation workflow (do this for every task)
- Append a dated entry to `docs/worklog/YYYY-MM-DD.md`: goal, what you did, commands run, results
  (including failures), sources used, next step.
- Record any design choice in `docs/decisions/NNNN-title.md` using `docs/decisions/0000-template.md`.
- New research (a tool, model, or spec) goes in `docs/research/` with sources and access dates.
- Keep the README "Project status" table and `docs/poc-plan.md` checkboxes current.
- Methodology and rules: @docs/methodology.md
