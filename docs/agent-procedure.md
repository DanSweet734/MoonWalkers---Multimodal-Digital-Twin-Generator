# Agent procedure: building a twin with the MoonWalkers tools

This guide is for an AI agent (in the PoC, Claude Code; decision 0003) that is connected to the
project's `moonwalkers` MCP server (decision 0013). It turns one machine photo into a functional
digital twin: a body and a spindle on a revolute joint, scaled, with every fact cited. A person then
reviews the twin. Each step below names the tool to use. The tools' own descriptions give their
arguments.

## Rules
- **Cite every fact.** Each value, dimension and capability needs a source with a locator (page,
  view or table) and a short verbatim quote. Never invent a number: if a source does not say it,
  leave it out or record it as "not confirmed" (CLAUDE.md, rule 1).
- **Label your reasoning.** Anything a source does not state, such as which dimension a drawing
  number measures or which parts turn, is written with `[INFERENCE]` in the fact's locator, an
  issue, or the joint's `method`.
- **Disagreeing sources:** name both, pick one, and say which and why (`add_issue`), as
  `docs/methodology.md` asks.
- **Follow the decision records.** Where one already settles a choice, follow it and cite it in
  the issue. For example, decision 0002 gives the HA5C's maximum speed from the Haas UK product
  page, not the 2006 manual. If the sources you have contradict a decision, say so and ask the
  person.
- **Ask the person** when a judgement changes the twin and the sources do not settle it. Show them
  the evidence and the preview images, then record their choice.
- **Install nothing.** The server never installs packages. If something is missing, say so.
- **Never review.** Twins are stored as `needs_review`. A person approves or rejects them, in the
  dashboard (decision 0015). You can read a version's `review_status`, but you have no tool to set
  it. Requests reuse the newest approved version, else the newest not rejected; a rejected version
  is never reused.

## 0. Before you start
1. In Claude Code, `/mcp` should list `moonwalkers` as connected. Claude Code's documentation says
   interactive sessions ask the person to approve a project server the first time. In Daniel's
   VS Code session on 2026-10-18 it loaded without asking (decision 0013).
2. Call `check_knowledge_base()`. It reports the data folder and `generator_root`. If
   `generator_root` is null, new geometry cannot be generated: ask the person to set
   `MOONWALKERS_GEN_ROOT` (`docs/setup/generators.md`) and restart.

## 1. Reuse first
- Call `check_knowledge_base(manufacturer, model)`. Its note says which version a request would
  reuse: the newest approved one, else the newest one not rejected in review.
- If there is one and the person did not ask for a rebuild, call `request_twin(manufacturer,
  model)`. Report its message, which says the stored twin was reused, plus the twin id and USD
  path, and stop.
- If they asked for a rebuild, or every version was rejected, build a new version: in step 2,
  start the run with `new_version=true`.

## Jobs started in the dashboard
Someone can upload a photo in the dashboard (decision 0014, `docs/setup/dashboard.md`). If the
machine has a reusable twin and no new version was asked for, the platform reuses it at once and
the job is done. Otherwise the job waits for you:
1. **`list_jobs()`** shows open jobs, with each one's `run`, `stage` and `next_step`. The person
   may also name the run, for example "Build the twin for the dashboard job
   machines/haas-ha5c/runs/2026-10-19_run-001".
2. **The job already has its request and photo.** The request names the machine and says whether
   a new version was asked for. So skip `start_run` and `add_input`, and start at step 3 with that
   `run`.
3. **The photo's provenance** is the uploader's text, in the source's title (ending "(uploaded
   through the dashboard)"), and its line in `SOURCES.md`. If the photo is unclear, or its
   provenance is missing, ask the person before building.
4. **Carry on with steps 3 to 6.** The job's page in the dashboard shows each step as you take
   it.

## 2. Start a run and add the photo
1. **The inputs must already be in the data folder,** under `data/machines/<machine>/inputs/`,
   each with a line in that folder's `SOURCES.md` (URL, date retrieved, SHA-256, license note;
   `data/README.md`). If one is missing, tell the person; downloading files is outside these
   tools.
   - **Some sites block scripts.** haascnc.com answers curl and WebFetch with a Cloudflare
     challenge (HTTP 403), as found while building the TH240 (worklog 2026-10-18). Ask the person
     to open the page in their browser and save it ("Webpage, Complete") into
     `inputs/documents/`. Then hash the saved HTML and log it in `SOURCES.md`, saying it was saved
     in a browser. Files the page links to, such as layout drawings on another host, may still
     download normally.
2. `start_run(manufacturer, model, new_version)` returns `run`, which every other tool takes.
3. `add_input(run, path, source_id, title, retrieved_at, license_note)` adds the photo:
   - the path is relative to the data folder;
   - put the photo's original URL in the title;
   - take `retrieved_at` and the license note from `SOURCES.md`.

   Documents (manuals, catalogues, drawings) are not inputs while their pipeline, A, C or D, is
   not in: `add_input` refuses them (decision 0021). Read them yourself, and cite them in step 3.

## 3. Read the documents and record cited notes
1. **`add_reference_source`, once per document you use.**
   - For a downloaded file, use `kind="url"` with its original URL, and pass `local_copy` (the
     file under `data/`) so the copy you read is hashed.
   - For something a person told you, use `kind="user_input"`.
   - Reading notes (`identify_machine`, `add_fact`, `add_control`) can cite **only** sources
     recorded this way. The photo from `add_input` is a job input: if a note comes from the photo,
     record the photo with `add_reference_source` too.
2. **Read the PDFs.** The Read tool cannot render PDFs here, so extract text with pypdf. From
   `backend/`:
   ```
   uv run python -c "from pypdf import PdfReader; r = PdfReader('../data/machines/<machine>/inputs/documents/<file>.pdf'); print(r.pages[N - 1].extract_text())"
   ```
   Things to watch for:
   - Give locators as PDF page numbers. If the printed page number differs, give both.
   - pypdf may show symbols such as `±` and `°` as an unreadable character. Restore them from
     context, and say so in your report.
   - A drawing's text does not show what a dimension line spans. pypdf can report where each
     text item sits on the page, via `page.extract_text(visitor_text=...)`, which places a
     dimension in its view. What the line spans is still `[INFERENCE]`, unless the person confirms
     it.
   - **Web pages** are saved as HTML in `inputs/documents/` (for the HA5C, the Haas UK product
     page). Search them with grep, or strip the tags with Python's `re` and `html` modules. Cite
     the page's URL, with the saved copy as `local_copy`.
3. **`identify_machine`**, quoting the sources that name the machine.
4. **`add_fact`** for each value, in SI units with the value as written in `original`. Pipeline B
   uses:
   - `center_height` (m): the spindle axis height above the base. **Required:** it sets the
     scale.
   - `max_spindle_speed` (rad/s): the joint's maximum velocity.
   - `overall_width`, `overall_height`, `overall_depth` (m): size checks against the model. Say in
     the locator what each dimension spans, for example whether a height includes a handle.
5. **`add_control`** for how the machine is driven, for example an indexing program from the
   manual. Pipeline B's joint is `spindle_rotation`: list it in `drives_joints`.
   - **To make the twin run a program** (success level 3, decision 0016), use kind
     `program_interpreter` and put a program from the manual in `spec["program"]["rows"]`.
     Write one row per step, as the manual prints it: `[step, step_size_deg, feed_deg_s,
     loop_count, g_code]`. For a G96 subroutine call, the third column is the Step# to jump to.
   - **Cite the page and quote the rows,** for example the HA5C manual's Example #3, PDF p. 39.
   - **The tool checks the program at once** against the manual's limits and codes. The build
     then writes `programs/<behaviour>/` in the run folder, which holds `program.usdc` and the
     runner for Isaac Sim.
   - Ready-made programs from the HA5C manual: `uv run python -m moonwalkers.control list`.
6. **`add_issue`** for disagreements, assumptions and doubts a reviewer should see.

## 4. Generate and inspect the geometry
1. **`generate_geometry(run)`.** It takes about a minute on the GPU the first time, and reuses the
   run's mesh after that. Open the returned views PNG with your Read tool.
2. **Decide the axes from the views:** which generator axis points up, and which one the spindle
   nose faces.
3. **`inspect_geometry(run, up, front)`.** Open its views, then check:
   - **`warnings` first.** They say when the tip slabs measured something other than the spindle.
   - **`tip_slabs`:** centres that agree across depths mean the tip is a round nose; that gives the
     spindle axis (y, z). The slabs start at the mesh's front-most point, so they find the spindle
     only if it reaches furthest forward. On the HA5C it does. On the TH240 the base's feet reach
     further, and the warnings said the slabs were not round and reached the bottom of the mesh.
   - **`circle_scan`:** circles fitted to slices over the front of the mesh. Slices marked
     `round` show where a round part (platter, disc, nose) is, and its centre and radius.
   - **If the warnings fire, or the slab axis is not on the round moving part in the views:** call
     `inspect_geometry` again with `circle_x`, two or three x positions inside the round moving
     part, taken from the round scan slices. The round fits' centre becomes the axis
     (`axis_source: "circle_fits"`), and the profile is measured about it. Say in the joint's
     `method` that the axis came from circle fits, with their x positions (decision 0012, "The
     fix").
   - **`profile`:** along +x it shows the body's front face (`r_max` jumps to the window), any
     flange or disc in front of it, and the nose.
   - **The base:** the lowest point should be a flat base, not a foot or a stray bit of mesh.
4. **What turns?** If the documents do not say which front parts move with the spindle (a nose
   only, or a flange too), say so, and ask the person to choose.

## 5. Define the joint and the scale
1. **`add_joint(run, up, front, spindle_axis_yz, spindle_radius, spindle_start_x, method)`.**
   - `spindle_axis_yz` is the inspection's `axis_yz`: from the slabs, or from the circle fits.
   - `spindle_radius` lies between the moving part's radius and the radius of whatever stays put.
   - `spindle_start_x` sits just in front of the face the moving part starts from.
   - `method` explains the numbers you used, with `[INFERENCE]` for judgement. It becomes a cited
     source of the twin.
2. **`set_scale(run)`** uses the cited `center_height`. Pass `base_z` only if the base is not the
   lowest point.
3. **`preview_twin(run)`** stores nothing. Open the assembled, body and spindle PNGs, and read
   the size checks: a difference above 10% is a warning.
4. You can call `add_joint` and `set_scale` again until the preview is right. Once you submit, the
   run is fixed.

## 6. Submit and report
1. **`submit_twin(run)`** stores the result and a new twin version (needs review), exports
   `twin.usdc` and two check files, and validates them. If the machine already has a twin and the
   run is not a new version, it reuses the stored twin instead and says so.
2. **Report to the person:**
   - the twin id and the USD path;
   - what was cited, and what is `[INFERENCE]`;
   - the size checks and the twin's issues;
   - the validation result;
   - the next step: the Isaac Sim check in `docs/setup/isaac-sim-check.md`, section 6, using this
     run's files, then a review in the dashboard (the twin's page);
   - with a program: its folder `programs/<behaviour>/` and section 7 of that guide (level 3).
3. **A second request** for the same machine, `request_twin(manufacturer, model)`, should reuse
   the stored twin and say so. Report its message.
4. **Record the session** in `docs/worklog/<date>.md` (CLAUDE.md, "Documentation workflow"):
   - the tools you called, in order;
   - your choices and why, and the results;
   - anything that went wrong.

   Do not commit, push or open pull requests unless the person asks.

## When a tool fails
Tool errors say what is wrong. The common ones:

| Error | What to do |
|---|---|
| "add a reference source first" | Call `add_reference_source` before `identify_machine` or `add_fact` |
| "citations of unknown sources" | Cite a `source_id` recorded with `add_reference_source`, not the photo from `add_input` |
| "the geometry spec is not complete" | Call both `add_joint` and `set_scale` |
| "already built its twin" / "already assembled" / "already generated" | The run folder is fixed: start a new run (`new_version=true` for a rebuild) |
| "the image-to-3D generator is not configured" | The person must set `MOONWALKERS_GEN_ROOT` for the server |
| "Pipeline B (PoC) takes exactly one machine photo" | Add exactly one photo with `add_input` |
| "Pipeline D (...) ... is not in yet" (or A, C) | The document's pipeline is not in yet: cite it with `add_reference_source` and record its facts with `add_fact` |

Claude Code asks the person before each tool call unless they allow the tool. Only
`check_knowledge_base` and `list_jobs` are read-only. `request_twin` stores nothing when it reuses a
twin. The other tools write only inside the run folder, except `submit_twin`, which also writes the
knowledge base.

## The Phase 4 end-to-end check
`docs/poc-plan.md`, Phase 4, asks for a run in which Claude Code drives these tools to build the
HA5C twin.
1. Set `MOONWALKERS_GEN_ROOT` (`docs/setup/generators.md`, step 6) and restart VS Code.
2. Open a **new** Claude Code session in this repository, so the agent has none of the building
   session's memory, and approve the `moonwalkers` server.
3. Give it a prompt like this:

   > Use the MoonWalkers MCP tools to build a new version of the Haas HA5C twin from the Haas UK
   > photo in data/machines/haas-ha5c/inputs/, following docs/agent-procedure.md. Read the
   > documents in that folder yourself and cite every fact. Do not copy facts from
   > pipelines/b/haas_ha5c.reference.json; afterwards, compare your facts with it and report any
   > difference. Then show that a second request for the HA5C reuses the stored twin. Write a
   > summary of the session in today's worklog. Do not commit.
