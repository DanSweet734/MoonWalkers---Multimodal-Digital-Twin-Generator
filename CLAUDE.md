# MoonWalkers Multimodal Agentic Digital Twin Generation Platform

CSUN capstone team (Daniel Sweet, Ava Harken, Sarkis Nazaryan, Shankar Kiran Ragavender) building a
platform where an AI agent turns machine information (photos, video, nameplates, brochures, drawings,
catalogs) into **functional digital twins** exported as OpenUSD (`.usd`) for NVIDIA Omniverse / Isaac Sim.
"Functional" = moving parts (joints) **and** control logic, confirmed by our advisors (Dr. Bingbing Li,
Dr. Thomas Lu). Full background: `docs/research/project-context.md` (read sections as needed, don't load it all).

## Current phase: the lab's machines plan, Phase 2, the ReBeL arm (the drill-press plan is done)
**Start here:** `docs/lab-machines-plan.md`, "Phase 2", whose hand-off comes first. Phase 2 runs on
branch `feat/lab-phase-2-rebel-arm`, from `main` after PR #28; its first commit is the hand-off.
The plan was approved on 2026-11-09 (PR #27; Daniel's answers in its "Decided on review").
**Phase 1 is done** (PR #28, merged on 2026-11-09 on Daniel's word):
- **Done in Phase 1:**
  - the photos are filed;
  - Daniel chose SAM for cutting the machine out, with crop boxes and drawn masks as options. The
    per-photo cut-out (decision 0029, accepted), its preview and `set_photo` (tool gap 1) are
    built;
  - tool gaps 2, 4, 5, 6 and 7 are closed (decision 0030, accepted). The MCP server has 28
    tools: `correct_issue`, and `fit_circles` with `within` and a direction; mesh warnings in
    `preview_twin`; `dry_run_twin`. The dashboard's upload adds picks from several folders.
  - Haas's sources are filed: the mill manuals and the Toolroom sheet fetched (its PDFs answer
    scripts), its three web pages saved by Daniel.
- **Next:** Phase 2, the ReBeL arm, levels 1 and 2. Restart the MCP server (`/mcp`) before an
  agent uses the new tools.

The history below is the record of the PoC and the drill-press plan.

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
    The manual is in `data/machines/grizzly-t33901/inputs/`, with Daniel's photos and the
    manual's own in `inputs/photos/` (listed in `inputs/SOURCES.md`).
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
- **Phase 2 is done** (PR #18, merged on 2026-10-24). Contract v0.2.0 (decision 0020): optional
  `mode`, `adjustable_stop` and `follows` on `Joint`, read by the exporter, shown by the dashboard,
  used by the drill press (run `2026-10-23_run-003`, checked in Isaac Sim by Daniel on
  2026-10-24). Decision 0021: the stubs run only in the tests, `add_input` refuses a document whose
  pipeline is not in, one result per twin carries the geometry, disagreeing facts are listed for
  the reviewer, `python -m moonwalkers.pipelines`, and the owners' guide `docs/pipeline-guide.md`.
  - **Both decisions are accepted by Daniel, with the pipeline owners' review still open:** Daniel
    merged before Ava, Kiran and Sarkis could answer, to start Phase 3. A change they ask for gets
    its own decision record.
  - **Daniel's direction (2026-10-23):** a loosened table drops, as a similar drill press's did
    (decision 0018).
- **Phase 3 is done** (PR #19, merged on 2026-10-24). Decision 0022 (accepted by Daniel): each
  machine photo's view in the operator's words and its use (generator or evidence) live in
  `request.json`; `pipelines/b/photos.py` alone maps them to the generator's slots; one photo
  runs the single-image model, two to four the multi-view model, and corner photos run as a grid
  turned 45°, squared by the spec's `yaw_deg`. The agent's `add_input` and the dashboard's upload
  take several photos. "Grizzly Industrial, Inc." and "Grizzly" give one key, `grizzly/t33901`
  (decision 0009's alias).
  - **Daniel's rule for unknown details (2026-10-24):** a labelled stand-in where the detail is
    visible or needed; left out where it is hidden and unused. So the T33901's belt positions,
    under its closed belt cover, are left out; its twelve speeds are cited.
- **Phase 4 is done** (PR #20, merged on 2026-10-26). Its spike compared four ways to cut the
  T33901 mesh `grizzly-t33901/runs/2026-10-24_run-001` (squared with `--yaw 49.1`) into moving
  parts: `docs/research/2026-10-24-part-cutting-spike.md`, re-run with
  `uv run python -m moonwalkers.pipelines.b.part_spike <out> --t33901 <run>`.
  - **Decision 0023 (accepted by Daniel, 2026-10-26):** an ordered cut list of cited shapes per
    part (`part_cuts`), with each fed photo placed on the mesh by its silhouette
    (`photo_marks.fit_camera`) so a reviewer sees the cuts drawn over it. Nothing was installed.
    Daniel chose to research learned segmenters only (P3-SAM, PartField).
  - **Daniel's answers (2026-10-26):**
    - labelled stand-ins for the chuck (hidden in the guard the generator made solid), and for
      the table and the crank, which the generator got wrong: "We should definitely match it to
      the photos". The column rack too: his "Yes let's merge PR #20" is read as a yes to that
      question as well, to be mentioned in Phase 5's first report;
    - the depth stop's fused ring stays with the head "for now" (replaced by stand-ins in
      Phase 5's v5, on his word);
    - the back stays guessed: no photo of it exists, and there is no T33901 to photograph.
- **Phase 5 is done** (PR #21, merged on 2026-10-28). Pipeline B builds the T33901 as several
  parts on several joints, with labelled stand-ins where the mesh hides or gets wrong a part that
  shows (decisions 0024, 0027 and 0028, accepted).
  - **`grizzly/t33901@v6`** (run `2026-10-28_run-003`; spec
    `part_cutting/2026-10-27_spec/geometry_spec_v5.json`, written by `compose_spec.py` there): 17
    parts (11 stand-ins, among them the balanced downfeed hub and handles, the quill, the depth
    stop's rod, nut and bracket, the table, the chuck), 16 joints (9 fixed), scaled by the cited
    39 in height. Both validators clean. Daniel's Isaac Sim checks of v4 and v5 with recordings:
    level 2. v2 rejected by Daniel; the others are not reviewed, so requests reuse v6.
  - Cut parts' holes are closed by the spec's `patches`; parts fixed to the frame are grey. The
    agent's MCP tools set a several-part spec piece by piece (decision 0028; procedure section
    5b).
  - **Build in a scratch copy of `data/` first** and run both validators before the real build:
    a real build stores a version for good (v2's lesson). Since 2026-11-09 one step does it:
    `... pipelines.b dry-run <run> --reference <file>`, or the MCP tool `dry_run_twin`.
  - Masses stay placeholders: the manual gives only the 108 lb total, and per-part masses need a
    contract change discussed with the pipeline owners first (decision 0024, update). The table
    is locked in every file but `checks/unlocked.usdc`, by design. Daniel's term: "downfeed
    handles". Review PNGs went under `docs/images/` by his exception to rule 5 (2026-10-27,
    review images only).
- **Phase 6 is done** (PR #22, merged on 2026-11-03; decisions 0025 and 0026 accepted by Daniel
  the same day): control logic, level 3, for the drill press and the HA5C.
  - **Daniel's calls (2026-10-30):**
    - work in the proposed order and stop for checks;
    - time a stroke on any benchtop drill press, with stand-ins ready;
    - set the depth stop and its nut where the photos show them (43 mm);
    - live controls in the Property panel;
    - only the drill press is checked in Isaac Sim for now.
  - **Done (2026-10-30):**
    - the research note `docs/research/2026-10-30-control-logic-research.md`;
    - decision 0025: three control behaviours in the T33901's reference file, and one
      controller (`control/isaac_controls.py`) that Isaac Sim runs and `control/manual.py` plans
      with;
    - `grizzly/t33901@v7` (run `2026-10-30_run-001`, spec `geometry_spec_v7.json`), with
      `programs/operator-controls/`.
  - **Daniel's check of v7 (2026-10-31):** the controls work, including the speed list. The quill
    swung about the hand: the stand-in hub's placeholder inertia, reflected through the link, was
    125 times the quill's. He chose option (a): the spring is simulated on the handles' pinion,
    where the T33901 has it (decision 0025, update; `usd/exporter.py`, `springs_on_pinions`).
  - **Level 3 met for the T33901 (Daniel's re-check of `grizzly/t33901@v8`, run
    `2026-10-31_run-001`, 2026-11-02):**
    - the stroke stays within 0.62 mm of the plan, and the quill returns in 0.28 s with no bounce;
    - the return is overdamped, logged in decision 0025;
    - his stroke timing, if he has it, replaces the stand-ins.
  - **The HA5C (decision 0026, 2026-11-02):**
    - the acceleration is a 540 deg/s^2 stand-in, from the manuals' "usually 2X";
    - the CNC relay follows Parameter 1 and the codes;
    - the controller waits for cycle start (a simulated mill, or a tick in the Property panel),
      with a step mode;
    - new v3 program folders under `data/machines/haas-ha5c/programs/2026-11-02_*`. Its Isaac Sim
      check waits until Daniel deems it necessary.
  - **For the stakeholders (2026-11-03, reviewed by Daniel):**
    - `docs/how-a-twin-is-built.md`: eight Mermaid diagrams;
    - `docs/tool-guide.md`: every tool by name, with its purpose, inputs and outputs;
    - both linked from the README.
- **Phase 7 is done** (PR #23, approved by Daniel on 2026-11-04): the plan is complete.
  - **The agent's build:** a fresh Claude Code session built `grizzly/t33901@v9` with its
    controls from a five-photo dashboard job through the MCP tools. 140 of 141 quotes are on their
    pages, and Daniel's Isaac Sim check reached level 3 on 2026-11-04.
  - **v10 and v11:** they fix his three findings in v9's stand-ins (a straight crank, a missing
    table height lock handle, a broken sheet under the table). They were built by the Phase 7
    chat from scripts in `part_cutting/2026-11-04_spec/`, not by the agent, each dry-run first.
    Daniel approved v11 on 2026-11-04, so requests reuse it.
  - **The record:** the plan's report is `docs/drill-press-report.md`: results per level, every
    run, the decisions, the table of inaccuracies and stand-ins, the open questions and the tool
    gaps the agent found. The advisors' page is https://claude.ai/artifact/RttTc4nE7DUYJ6NP2uEziK,
    which Daniel shares for the weekly meeting.
    Logged, not built: the crank passes into the base at the table's lowest setting (an issue for
    the next version), and v10 and v11 carry a stale issue from the agent's notes.
- **Next: the lab's machines** (meeting of 2026-11-05; report, section 7.1). The plan is drafted
  in `docs/lab-machines-plan.md`, below its hand-off, for Daniel's review (2026-11-09).
  - **Found while drafting it:** the hand reads "LINKERBOT", and LinkerBot publishes its own L20
    models; igus's documentation gives the arm's sizes, ranges and zero pose; the VF-3's
    trunnion runs as the mill's own axes [INFERENCE]. Research note, second update.
  - **Daniel photographed three, with nameplates:** a "ReBeL® 6-DoF Cobot with SCHUNK EGP Gripper
    and CobotPump" with a "Realhand L20 Dexterous Robotic Hand" attached, a Haas VF-3 and a Haas
    TM-1. The order is ours to choose. Public sources: `docs/research/2026-11-06-lab-machines.md`.
  - **Daniel's calls (2026-11-09):** all three machines; the order is the arm, the TM-1, the VF-3,
    then the hand; the hand is part of the arm's twin. The photos (2026-11-05, 29 JPEGs) wait in
    `data/machine photos (temp)/` until a plan files them by machine. Their findings are in the
    research note's update: a REBEL-6DOF-02 with no public model of that version, the L20 alone
    on the flange, an open TM-1, and a VF-3 with a Haas trunnion inside. Lab measurements must be
    planned ahead; video is a separate trip.
  - **The repository is public:** keep nameplates' serial numbers in `data/`, out of commits.
  - **Order of work (Daniel, 2026-11-06):** update the record (PR #25, merged 2026-11-09), then a
    setup guide for the teammates (`docs/setup/team-setup.md`), then the machines from photos. Video input for Pipeline B starts once the photo
    results are acceptable.
- **Direction from the advisors** (`docs/poc-report.md`, section 7):
  - build a more complete product before the lab's photos and real-world checks come;
  - get as close to the real machine as the sources allow, and log every inaccuracy;
  - use Claude Code and Anthropic's tools first; compatibility with other agents (Codex) comes
    later;
  - model the HA5C controller's acceleration and mill signals if possible. If not possible,
    record why and bring it back to the stakeholders;
  - **from the meeting of 2026-10-29** (report, section 7.1): an option to carry mass if a client
    requests it; the T33901 was a test machine, so its handle ratio stays a stand-in and its
    guessed back is acceptable for this stage, with that depth kept for a machine we own;
  - **from the meeting of 2026-11-05:** masses are a bonus, not a priority (Dr. Lu); when an agent
    cannot reach a source, the user is prompted, with an option to skip it (Dr. Li,
    `docs/agent-procedure.md`, step 2); the lab has no HA5C, so decision 0026's stand-ins stay.
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
- Contract: `backend/src/moonwalkers/contracts/pipeline_result.py` (Pydantic, SCHEMA_VERSION 0.2.0;
  results that say 0.1.0 stay valid, and may not use 0.2.0's joint fields, decision 0020).
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
First-time setup for a teammate (clone, tools, tests, branches): `docs/setup/team-setup.md`.
Daniel's machine, with Isaac Sim and the generators: `docs/setup/windows-dev-setup.md`.

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
  Its joints state their behaviour in contract v0.2.0 (mode, adjustable stop, link; decision 0020),
  which the exporter turns into drives, locks and couplings (`contract_settings`). A check adds
  only its scenario: contract changes, `JointSettings` (decisions 0017-0019), `starts` or
  `coupling_method`. Check in Isaac Sim: `docs/setup/isaac-sim-check.md`, section 8 (run-003).
- Build a twin from a photo (Pipeline B): the run folder `../data/machines/<machine>/runs/<run>` holds
  `request.json`. Run `uv run python -m moonwalkers.pipelines.b build <run> --reference <facts.json> --gen-root C:\mw-gen`.
  The first build generates the mesh and stops (exit 2) until `geometry_spec.json` exists. The HA5C's
  facts are in `src/moonwalkers/pipelines/b/haas_ha5c.reference.json`.
- Try a build without storing anything: `uv run python -m moonwalkers.pipelines.b dry-run <run> --reference <facts.json>`
  builds a copy in `data/scratch/<date>_dry-run-<NNN>/` and runs both validators on every file.
- Check how the machine is cut out of each photo before generating (decision 0029):
  `uv run python -m moonwalkers.pipelines.b cutouts <run> --gen-root C:\mw-gen` writes
  `<run>/cutouts/sheet.png` in seconds. A photo's `cutout` in `request.json` (SAM box and points,
  crop box, or drawn mask; fractions of the upright photo) replaces the automatic removal.
- Pipelines A, C and D outside their tests (decision 0021): `uv run python -m moonwalkers.pipelines list`
  shows which are in; `... run D --input-type pdf_catalog <file or URL>... --out <file>` runs one and
  writes its checked result, storing nothing. Stubs run only in the tests (`stub_pipelines()`).
  Owners' guide: `docs/pipeline-guide.md`.
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
- A manual machine's controls (level 3, decision 0025): a switch, a speed table and the operator's
  commands with scenarios, as three control behaviours (the T33901's are in its reference file).
  A build writes `programs/<command set>/` (`controls.usdc` with live controls in the Property
  panel, `run_controls.py`, a plan per scenario). For a stored twin:
  `uv run python -m moonwalkers.control controls --twin grizzly/t33901[@vN] [--file controls.json]`.
  Measure a joint recording against a plan:
  `uv run python -m moonwalkers.control compare <recording.csv> <folder>/trajectory_<scenario>.json`.
  Check in Isaac Sim: `docs/setup/isaac-sim-check.md`, section 9.
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
