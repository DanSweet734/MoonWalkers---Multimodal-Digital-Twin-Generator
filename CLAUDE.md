# MoonWalkers Multimodal Agentic Digital Twin Generation Platform

CSUN capstone team (Daniel Sweet, Ava Harken, Sarkis Nazaryan, Shankar Kiran Ragavender) building a
platform where an AI agent turns machine information (photos, video, nameplates, brochures, drawings,
catalogs) into **functional digital twins** exported as OpenUSD (`.usd`) for NVIDIA Omniverse / Isaac Sim.
"Functional" = moving parts (joints) **and** control logic, confirmed by our advisors (Dr. Bingbing Li,
Dr. Thomas Lu). Full background: `docs/research/project-context.md` (read sections as needed, don't load it all).

## Current phase: integration, starting with the Grizzly T33901 drill press
- **The PoC is complete.** An agent built a Haas HA5C twin from one photo, and it reached all three
  success levels: a scaled model with cited facts; a spindle joint that rotates; an indexing
  program that drives it. It was presented to the advisors on 2026-10-22, with positive feedback.
  The record is `docs/poc-report.md` (results, decisions 0001-0016, inaccuracies, open questions)
  and `docs/poc-plan.md`. The HA5C remains the reference twin.
- **Next machine, approved by the advisors on 2026-10-22: Grizzly T33901 drill press.** Its goals:
  - several moving parts cut from one model;
  - sliding (prismatic) joints and a chain of joints;
  - motions that move together: the downfeed handles turn as the quill slides;
  - a way to describe a manual machine's control.

  Start from:
  - `docs/poc-report.md`, section 8, the seven decisions it needs;
  - `docs/research/2026-10-19-open-questions-research.md`, section 6, the manual's cited facts.
    The manual is in `data/machines/grizzly-t33901/inputs/`; no photo has been collected yet.
- **The phase plan:** `docs/drill-press-plan.md`, written and approved on 2026-10-22 (PR #15,
  merged). Daniel's direction: several images per machine and the least guessing, with stand-ins
  (labelled, logged as inaccuracies) allowed on the way.
- **Phase 1 is done** (PR #16, merged on 2026-10-23). A box-and-cylinder drill press
  proves the exporter before any generated mesh: sliding joints, locks, the spring, the depth
  stop, coupled handles. Built and validated on 2026-10-22, with decisions 0017-0019 proposed.
  Daniel checked it in Isaac Sim on 2026-10-23. The mimic coupling and locks by equal limits are
  kept. Three fixes went into run `2026-10-23_run-002`: keep the articulation awake, the rack and
  pinion's sign, and the free table's height. His re-check the same day confirmed all three.
  The fixed joint recorder then made its first recording: the handles track within 1%, and
  the spring returns in 0.83 s. Decisions 0017-0019 are accepted.
- Every twin stays awake by default (PR #17, merged on 2026-10-23; decision 0017).
- **Now: Phase 2**, on branch `feat/phase-2-contract-and-pipelines` (started on 2026-10-23 from
  `main` at `ca25284`). It covers contract v0.2.0 (linked joints, joint modes) and how Pipelines A,
  C and D run outside their tests: decisions 0020 and 0021, `docs/drill-press-plan.md`, Phase 2.
  The contract change is discussed with Ava, Kiran and Sarkis before it is merged.
- **Direction from the advisors** (`docs/poc-report.md`, section 7):
  - build a more complete product before the lab's photos and real-world checks come;
  - get as close to the real machine as the sources allow, and log every inaccuracy;
  - use Claude Code and Anthropic's tools first; compatibility with other agents (Codex) comes
    later;
  - model the HA5C controller's acceleration and mill signals if possible. If not possible,
    record why and bring it back to the stakeholders.
- **Who owns what.**
  - Pipelines A, C and D belong to their owners (Ava, Kiran, Sarkis). They replace their stubs
    in `pipelines/<a|c|d>/` (`create_pipeline()`) on their own branches. Do not build them, and
    do not change the contract without a decision record.
  - Daniel and Claude Code own Pipeline B and the shared platform: contract, orchestrator,
    knowledge base, exporter, MCP server, API and dashboard.
- **Human review is expected.** Results default to `needs_human_review = true`.
  - People approve or reject a twin version in the dashboard, and reviews are separate
    append-only records.
  - A request reuses the newest approved version, else the newest not rejected.
  - Approving never locks a twin: it can still be rebuilt (decision 0015).
  - The agent never reviews.
- **Work in the phases of the current plan.** Stop at the end of each phase for review.

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
- **Claude Code is the agent** (decision 0003; the advisors confirmed on 2026-10-22 to use Claude
  Code first): the backend exposes its actions as MCP tools (add source,
  identify machine, check knowledge base, generate geometry, set scale, add joint, export, submit).
  Server: `moonwalkers.mcp`, registered in `.mcp.json` (decision 0013). The agent follows
  `docs/agent-procedure.md`.
- The API (`moonwalkers.api`, FastAPI, decision 0014) serves the dashboard on 127.0.0.1 only. It
  and the MCP server share the data folder through `moonwalkers.workspace` (run folders are the
  jobs). An upload either reuses a stored twin at once or waits for the agent, which finds it with
  the `list_jobs` tool. The API never runs the generator.
- Knowledge base: a simple JSON/SQLite store behind a `KnowledgeBase` interface; Neo4j comes later.
- Contract: `backend/src/moonwalkers/contracts/pipeline_result.py` (Pydantic, SCHEMA_VERSION 0.1.0).
- Units inside the contract are SI (m, rad, s, kg). Convert only at the USD export boundary.

## Repository layout (target)
- `backend/src/moonwalkers/` - Python package: `contracts/`, `pipelines/{a,b,c,d}/`, `orchestrator/`,
  `kb/`, `usd/` (exporter), `generators/` (image-to-3D adapters), `workspace/` (run folders, job
  status, uploads), `control/` (indexing programs), `api/` (FastAPI), `mcp/` (MCP server)
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
  adapter in `generators/`. Primary: Hunyuan3D-2mv (multi-view). Fallback, and what the PoC uses while
  there is one photo: Hunyuan3D-2 single-image (decision 0011). Setup: `docs/setup/generators.md`
  (`C:\mw-gen` on Daniel's machine, found through `MOONWALKERS_GEN_ROOT`).
  **The multi-view model is installed** (2026-10-22). Its image order was checked with the
  repository's example images. `left` is the machine's own left: stand facing the front, walk to
  your right, and take the photo. Manuals name sides the other way round, as the operator sees
  them. Fewer than four views work. Details: `docs/setup/generators.md`, "The multi-view model".
- PDF pages (figures, exploded views) render with pypdfium2, a dev dependency added on
  2026-10-22, and the backend's `write_png`. The Read tool cannot render PDFs here (no poppler).
- Twins stay awake by default: the exporter writes PhysX's `physxArticulation:sleepThreshold = 0`
  on the articulation root (decision 0017). Without it, a slow drive stops once PhysX puts the
  twin to sleep.
- Pipeline B method (decision 0012): a cited `geometry_spec.json` per run folder orients, splits and
  scales the generated mesh. One run folder holds one build, and its outputs are never overwritten.
  Twins with generated meshes are written as binary `.usdc`.
- Dashboard: React + TypeScript with Vite and npm; Oxlint for lint (decision 0007).

## Commands
First-time machine setup (uv, Python 3.12, Node.js LTS, GitHub CLI): `docs/setup/windows-dev-setup.md`.

Backend (run from `backend/`):
- Install/sync Python deps: `uv sync` (creates `backend/.venv` from `uv.lock`)
- Tests: `uv run pytest`; without GPU/slow tests: `uv run pytest -m "not gpu and not slow"`;
  the real generator test (needs the generator environment, about 70 s):
  `$env:MOONWALKERS_GEN_ROOT = "C:\mw-gen"; uv run pytest -m gpu`
- Lint and format: `uv run ruff check .` and `uv run ruff format .` (check only: `uv run ruff format --check .`)
- Regenerate the contract JSON Schema after a contract change: `uv run python -m moonwalkers.contracts.json_schema`
- Write the box-and-cylinder test twin (Phase 2 check): `uv run python -m moonwalkers.usd.primitive_twin ../data/machines/moonwalkers-testindexer/runs/<run>`
- Write the box-and-cylinder drill press (drill-press plan, Phase 1; ten check files, `RUN.md` and
  the joint recorder `record_joints.py`): `uv run python -m moonwalkers.usd.primitive_drill_press ../data/machines/moonwalkers-testdrillpress/runs/<run>`.
  Settings per joint (drives, locks, starts, couplings) are `JointSettings` (decisions 0017-0019).
  Check in Isaac Sim: `docs/setup/isaac-sim-check.md`, section 8.
- Build a twin from a photo (Pipeline B): the run folder `../data/machines/<machine>/runs/<run>` holds
  `request.json`. Run `uv run python -m moonwalkers.pipelines.b build <run> --reference <facts.json> --gen-root C:\mw-gen`.
  The first build generates the mesh and stops (exit 2) until `geometry_spec.json` exists. The HA5C's
  facts are in `src/moonwalkers/pipelines/b/haas_ha5c.reference.json`.
- Inspect a generated mesh, or try a spec without storing anything:
  `uv run python -m moonwalkers.pipelines.b inspect <run> --up +y --front +z`, then
  `... inspect <run> --preview --reference <facts.json>`. If the inspection warns that the tip
  slabs are not the spindle (something else is front-most), add `--circle-x X ...` with x positions
  inside the round moving part, taken from its circle scan (decision 0012, "The fix").
- Indexing programs (control logic, level 3, decision 0016): `uv run python -m moonwalkers.control list`
  (the HA5C manual's examples), `... show <program>`, and `... run <program> --twin haas/ha5c[@vN]`,
  which writes `data/machines/<machine>/programs/<date>_<program>_v<N>/` (open its `PROGRAM.md`).
  A build writes `programs/<behaviour>/` into the run when a control behaviour carries `spec["program"]`.
  Check in Isaac Sim: `docs/setup/isaac-sim-check.md`, section 7.
- Validate an exported twin (`.usda` or `.usdc`): `uv run python -m moonwalkers.usd.validate <file>`, then NVIDIA's `uv run omni_asset_validate <file>`
- Check a twin by eye in Isaac Sim: `docs/setup/isaac-sim-check.md`
- MCP server for the agent: Claude Code starts it from `.mcp.json` (approve it once per project). To
  start it by hand over stdio: `uv run python -m moonwalkers.mcp`. It needs `MOONWALKERS_GEN_ROOT`
  to generate new meshes.
- API and the built dashboard (127.0.0.1 only): `uv run python -m moonwalkers.api [--data <folder>] [--port 8000]`,
  then http://127.0.0.1:8000/ (API docs at `/api/docs`). With reloading: `uv run uvicorn moonwalkers.api.app:app --reload`.
  Running and checking it by hand: `docs/setup/dashboard.md`.
- Regenerate the dashboard's TypeScript types after changing an API or contract model:
  `uv run python -m moonwalkers.api.typescript` (writes `dashboard/src/api/types.gen.ts`; a test fails when it is stale)

Dashboard (run from `dashboard/`):
- Install deps: `npm ci` (exact versions from `package-lock.json`)
- Dev server: `npm run dev` (http://localhost:5173; forwards `/api` to the API on port 8000)
- Type-check and build: `npm run build` (into `dist/`, which the API serves at `/`)
- Lint (Oxlint): `npm run lint`
- Tests: `npm test` (Node's built-in test runner on `src/**/*.test.ts`; nothing to install)

## Code conventions
- Python: type hints everywhere, ruff for lint and format, pytest for tests, small pure functions.
- Every new module gets tests. Fix failing tests before committing; never delete a test to make it pass.
- No network calls in unit tests; use fixtures. Mark GPU or slow tests `@pytest.mark.gpu` / `slow`.
- TypeScript: strict mode, erasable syntax only; never hand-copy backend types: generate them from the
  API's OpenAPI schema, which includes the contract models (`moonwalkers.api.typescript`, decision 0014).
  Pure logic goes in `dashboard/src/lib/` with a `*.test.ts` beside it.

## Git workflow
- Never commit to `main` directly. One branch per task: `feat/...`, `fix/...`, `docs/...`, `chore/...`.
- Conventional Commits (`feat: add JSON knowledge base store`). Small, focused commits.
- Open a pull request with `gh pr create` when a phase or task is complete. PR description must list:
  what changed, how it was tested, docs updated, open questions.
- Never force-push, never rewrite pushed history. To bring `main` into a feature branch, merge it in
  (`git merge origin/main`) rather than rebasing.
- Keep one open phase PR at a time: start the next phase's branch from an up-to-date `main` after the
  previous PR is merged. GitHub treats a PR whose base is another PR's branch as a stack. A stack
  cannot be merged with `gh pr merge`; it needs the async merge API
  (`gh api --method PUT repos/{owner}/{repo}/pulls/{n}/merge-async -f merge_method=merge -f merge_action=direct_merge -f sha=<head sha>`).
  GitHub then rebases the next PR itself (seen on 2026-10-17; worklog of that date).
- Teammates' pipeline branches and PRs (for example `Sarkis`) run beside the phase PR and are
  theirs: do not commit to, rebase or delete them. A change that touches their pipeline folders
  or the contract is discussed with the owner first.

## Documentation workflow (do this for every task)
- Append a dated entry to `docs/worklog/YYYY-MM-DD.md`: goal, what you did, commands run, results
  (including failures), sources used, next step.
- Record any design choice in `docs/decisions/NNNN-title.md` using `docs/decisions/0000-template.md`.
- New research (a tool, model, or spec) goes in `docs/research/` with sources and access dates.
- Keep the README "Project status" table and `docs/poc-plan.md` checkboxes current.
- Methodology and rules: @docs/methodology.md
