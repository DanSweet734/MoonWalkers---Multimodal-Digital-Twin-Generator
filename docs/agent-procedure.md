# Agent procedure: building a twin with the MoonWalkers tools

This guide is for an AI agent (in the PoC, Claude Code; decision 0003) that is connected to the
project's `moonwalkers` MCP server (decision 0013). It turns machine photos (one, or several with
their views, decision 0022) into a functional digital twin, scaled, with every fact cited: a body
and a spindle on a revolute joint (sections 4 and 5), or a machine of several parts on several
joints, such as a drill press (section 5b; decisions 0027 and 0028). A person then reviews the
twin. Each step below names the tool to use. The tools' own descriptions give their arguments.

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
2. **The job already has its request and photos.** The request names the machine, says whether
   a new version was asked for, and gives each photo's view and use when there are several. So
   skip `start_run` and `add_input`, and start at step 3 with that `run`.
3. **The photo's provenance** is the uploader's text, in the source's title (ending "(uploaded
   through the dashboard)"), and its line in `SOURCES.md`. If the photo is unclear, or its
   provenance is missing, ask the person before building.
4. **Carry on with steps 3 to 6.** The job's page in the dashboard shows each step as you take
   it.

## 2. Start a run and add the photos
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
   - **The person may skip a source you cannot reach** (Dr. Li, 2026-11-05). Offer both: they
     fetch it, or you go on without it. If they skip it, log an issue naming the source and the
     facts it would have given. Never fill the gap with a guess.
2. `start_run(manufacturer, model, new_version)` returns `run`, which every other tool takes.
3. `add_input(run, path, source_id, title, retrieved_at, license_note, view, use)` adds a photo:
   - the path is relative to the data folder;
   - put the photo's original URL in the title;
   - take `retrieved_at` and the license note from `SOURCES.md`.
4. **Several photos: give each its view** (decision 0022). The view says where the camera stood,
   in the **operator's** words, facing the machine's front: `front`, `back`, `operator_left`,
   `operator_right`, the corners `front_operator_left`, `front_operator_right`,
   `back_operator_left` and `back_operator_right`, or `detail` for a close-up.
   - **Read the view from the photo, and check it against the manual.** Manuals name sides as the
     operator does: the T33901's "Right headstock components" (p. 6) is `operator_right`. Find a
     part whose side the manual states (a handle, a crank, a switch) and see which side of the
     image it is on.
   - **Never use the generator's `left` and `right`:** they are the machine's own sides, the
     reverse. The platform translates, in one place (`pipelines/b/photos.py`).
   - **`use`:** the generator gets whole-machine views by default (`generator`). It takes one photo
     per view, and all sides or all corners, so mark extra photos `evidence`, such as a second
     photo of a view, or a greyscale copy. A `detail` is always evidence: it stays in the job for
     the reviewer and for later steps (cuts, joints, size checks).
   - **One photo** may leave the view out, as in the PoC. Two or more each need one.
   - `add_input` checks the photos as a whole each time, and its `generator_input` says which
     model and slots the generator will use. A refused photo changes nothing.
   - **A wrong view or use:** correct it with `set_photo(run, source_id, view, use, cutout)`
     before `generate_geometry`. It gives the photo's whole entry, so repeat the use and the
     cut-out you want to keep. After generation it is refused: start a new run.
   - **A nameplate or a motor plate** is a reference source (`add_reference_source`), not an input.
5. **Check how the machine is cut out of each photo** (decision 0029), before generating.
   - `preview_cutouts(run)` cuts the fed photos out as the generator will, in seconds. Open its
     `sheet` with your Read tool.
   - By default the generator keeps the photo's most salient object. On a plain background that
     is the machine. In a lab it is often a sign, a box or a monitor in front of it, or one
     panel of the machine (the lab's photos: `docs/research/2026-11-09-background-removal-spike.md`).
   - **When the cut-out is wrong,** give the photo a `cutout` with `set_photo`. Coordinates are
     fractions (0 to 1) of the photo turned upright, from its top left: read them off the photo.
     - `{"method": "sam", "box": [x0, y0, x1, y1], "points": [...]}`: a box around the
       machine, plus points with `keep` true on parts it loses and `keep` false on what to
       leave out (the wall, a sign). This is the usual choice.
     - `{"method": "crop", "box": [...]}`: the automatic removal inside the box only. It loses
       thin parts, such as an arm's forearm.
     - `{"method": "mask", "mask": "<PNG in the data folder>"}`: a mask a person drew, white
       on the machine. Ask the person for one where SAM leaves holes, as in shiny guards.
   - Preview again after each change. Specks are dropped by `min_piece` (default 0.02).
   - **Nothing fills in what stands in front of the machine.** Log it as an issue on the twin,
     naming the photo and what is hidden.

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
   - **A manual machine** (no program, an operator at the controls; decision 0025) takes three
     behaviours, recorded in this order. Each cites the manual's words for every rule:
     - a `state_machine` for its switch. Its spec holds `inputs` (each with two states, off then
       on, a Property-panel `attribute` and a `label`), `on_when`, `start_input`, `off_why` (why
       the motor stays off without each condition) and `not_described` (changes the manual does
       not describe, which a scenario may not make);
     - a `lookup_table` of its speeds. Its spec holds `joint`, `switch`, `rows` of `rpm` (with
       `belts` only where cited), `initial_rpm`, `table_why`, `change_only_when`,
       `change_refused_why`, `run_up_s`, `coast_down_s` and `direction`. Label every value no
       source gives in `stand_ins`;
     - a `command_set` of the operator's commands. Its spec holds `switch`, `speed`, `quill` (the
       joint the hand drives), `commands`, `release_why`, `live_pull_speed_m_s`, and `scenarios`
       of steps (`set`, `set_speed`, `pull`, `release`, `wait`), plus `default_scenario` and
       `stand_ins`.

     The T33901's three, in `pipelines/b/grizzly_t33901.reference.json`, are the example to
     follow. The tool checks each one's spec, and the command set against the two it names. The
     build plans every scenario: a step the manual does not allow fails the build, with its
     number. It then writes `programs/<command set>/`, which holds `controls.usdc` and its runner.
     Also add an `add_issue` warning for the stand-ins, as the T33901's reference does.
6. **`add_issue`** for disagreements, assumptions and doubts a reviewer should see. The summary
   numbers them (`issue_list`). **`correct_issue(run, number, ...)`** corrects one that turned out
   wrong, or withdraws it (`withdraw=True`), until the twin is built: after that the issues are
   part of its record for good.

## 4. Generate and inspect the geometry
1. **`generate_geometry(run)`.** It takes about a minute on the GPU the first time, and reuses the
   run's mesh after that. One photo runs the single-image model, two to four the multi-view model.
   Open the returned views PNG with your Read tool. Its report gives the `grid` (single, sides or
   corners), each photo's slot, `sides_guessed` and `expected_turn_deg`.
2. **Decide the axes from the views:** which generator axis points up, and which one the spindle
   nose faces.
3. **Corner photos turn the mesh.** The multi-view model takes corners as a grid turned 45°, so
   the machine's front points about +45° from +x, towards +y (measured: +48.5° on the T33901).
   A single photo from a corner can also come out turned. Measure the turn:
   - call `inspect_geometry(run, up, front)` and read `footprint_deg`, the base footprint's long
     axis, and the top view;
   - choose `yaw_deg`, where the machine's front points, from that angle (up to a multiple of 90°)
     and from `expected_turn_deg`;
   - call `inspect_geometry` again with `yaw_deg`. Once square, `footprint_deg` is near 0 or 90,
     and the front view shows the machine's front. Pass the same `yaw_deg` to `add_joint`, and say
     in its `method` how you measured it.
4. **`inspect_geometry(run, up, front, yaw_deg)`.** Open its views, then check:
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
5. **What turns?** If the documents do not say which front parts move with the spindle (a nose
   only, or a flange too), say so, and ask the person to choose.

## 5. Define the joint and the scale
1. **`add_joint(run, up, front, spindle_axis_yz, spindle_radius, spindle_start_x, method,
   yaw_deg)`.**
   - `yaw_deg` is the one you inspected with (0 unless the mesh came out turned).
   - `spindle_axis_yz` is the inspection's `axis_yz`: from the slabs, or from the circle fits.
   - `spindle_radius` lies between the moving part's radius and the radius of whatever stays put.
   - `spindle_start_x` sits just in front of the face the moving part starts from.
   - `method` explains the numbers you used, with `[INFERENCE]` for judgement. It becomes a cited
     source of the twin.
2. **`set_scale(run)`** uses the cited `center_height`. Pass `base_z` only if the base is not the
   lowest point.
3. **`preview_twin(run)`** stores nothing. Open the assembled, body and spindle PNGs, and read
   the size checks: a difference above 10% is a warning. `mesh_faults` lists what NVIDIA's
   validator would warn about in the body's or the spindle's mesh; it should be empty.
4. You can call `add_joint` and `set_scale` again until the preview is right. Once you submit, the
   run is fixed.

## 5b. A machine of several parts
For a machine whose moving parts are more than one spindle about +x (the T33901 drill press: the
quill, the spindle, the downfeed handles, the table on its column, its tilt and its turn). The spec
is set piece by piece, and `preview_twin` shows each change; nothing is stored until
`submit_twin`. The T33901's spec (`data/machines/grizzly-t33901/part_cutting/2026-10-27_spec/`,
decision 0027 and its updates) is a worked example.
1. **Read the parts list and the figures first** (the manual's exploded view and photos): which
   parts move, on what, how far, and what locks them. Each joint and stand-in cites them.
2. **Measure on the oriented mesh.** `inspect_geometry(run, up, front, yaw_deg)` for the views and
   the bounds; **`fit_circles(run, up, front, along, at, yaw_deg)`** for round parts along any
   axis (a column or a quill along z, a hub along y). Use the `round` fits; several slices along
   one part should agree. Write each measurement into the note of what it sets.
   - When a slice crosses several parts and the one to measure is not the largest (an arm's
     links), add `within`, ranges on some of the twin's axes (`{"x": [lo, hi]}`, model units),
     to keep only the surface around it.
   - For a round part at an angle, set `along` to its direction, `[dx, dy, dz]`: a slice across
     an axis cuts it in an ellipse. Each position in `at` is then the distance along that unit
     direction from the origin (lab's machines plan, tool gap 4).
3. **`set_spec_frame`:** up, front and yaw_deg as inspected; `origin_xy` where the twin's origin
   goes (the spindle's axis); `fixed_part` (the frame, which keeps every face no cut takes); and
   `method`.
4. **`set_cut_list`:** an ordered list; a face goes to the first entry whose shape holds its
   centre. Give each entry a note naming its evidence.
   - Faces of a part the mesh gets wrong go to a **removed** part, which a stand-in replaces.
   - An entry for the fixed part early in the list keeps its faces out of later, larger shapes
     (the head's wall behind a removed handle hub).
5. **`set_spec_part`** for every part: `cut`, `removed` or `stand_in`.
   - **Stand-ins** (Daniel's rule): a labelled stand-in where the mesh hides or gets wrong a part
     that shows or that a joint needs; left out where it is hidden and unused. Match it to the
     photos, scaled by a cited size in the same photo, and to the parts list's sizes. Name it
     "Stand-in: ...", cite its sizes and photos, and say in its note what is read from where.
     Sizes are in metres; `at` is in model units.
   - A stand-in that does not move on its own is held to its part by a **fixed joint**.
6. **`set_spec_joint`** for every joint: type, parent and child, axis and point (model units),
   limits in rad or m, and the contract's behaviour (mode, adjustable stop, link; decision 0020)
   with citations. **A lever that another joint follows must be balanced** about its axis. The
   T33901's v1 handles hung 47 mm off theirs, and through the link they sagged the quill by
   20 mm.
7. **`set_scale_length`:** the largest cited length whose two ends both show (decision 0024: the
   overall height). **`set_size_checks`:** every other cited length you can measure, with how.
8. **`preview_twin(run)`** (and `photos=true` once, about a minute a photo, to draw the parts over
   the fed photos):
   - **open every `part_<id>` view, not only `parts`.** A leftover shows only in its part's view:
     the T33901's v1 kept half a generated crank, seen only in `part_table_bracket.png`;
   - **`holes`:** open edges where removed faces met a cut part. Close each with a `patches`
     entry on that part (`near` = the hole's centre) through `set_spec_part`, or check in the
     views that a stand-in covers it. If a patch is refused or a hole stays, move the cut's edge:
     a patch cannot join two sheets of a part that touch at one point;
   - **a part NVIDIA's validator would warn about** is among the issues ("NVIDIA's asset
     validator would warn about ..."): zero-area faces, edges with more than two faces, or
     non-manifold points, the points given in model units after orienting, where the cut list's
     boxes are. Move the cut boundary or the stand-in's size that makes them, by a millimetre or
     two: the T33901's table rim at exactly 10 mm gave 40 zero-area faces, at 10.5 mm none;
   - the size checks, and the issues the twin will carry. An issue of yours that a later change
     made stale (v10's and v11's note of a flap that v10's cuts had removed) is withdrawn or
     corrected with `correct_issue`.
9. **Repeat** until every view is right, no hole is left, and no part has a mesh warning.
10. **Dry-run the build before `submit_twin`:** `dry_run_twin(run)`. A submitted version is
    stored for good. The dry run builds the run as `submit_twin` would, but in a new scratch copy
    of the data folder (`data/scratch/<date>_dry-run-<NNN>/`), and runs our validator and
    NVIDIA's on the twin, every check file and the controls. Nothing is stored for real.
    - Fix what it reports through the tools, and dry-run again until `clean` is true. The
      T33901's agent build needed three dry runs, by hand (worklog 2026-11-04).
    - **By hand, from `backend/`:**
      `uv run python -m moonwalkers.pipelines.b dry-run <run> --reference <run>/reference_facts.json`.
    - Then `submit_twin`.

## 6. Submit and report
1. **`submit_twin(run)`** stores the result and a new twin version (needs review), exports
   `twin.usdc` and its check files (two for a spindle; one per behaviour the joints state for
   several parts), and validates them. If the machine already has a twin and the
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
| "the geometry spec is not complete" | One spindle: call both `add_joint` and `set_scale`. Several parts: set what the message names (it says "still to set ..." or why the pieces do not make a spec, such as a joint joining a part not set yet) |
| "a single spindle's joint and scale cannot be added" / "start a new run for a spec of several parts" | A run's spec is of one kind: start a new run to switch |
| "no open edge loop within 0.02 model units" | A patch's `near` must be a hole's centre from `preview_twin`'s `holes` |
| "give measured_model_units" | Only the overall depth, width and height are measured by the pipeline; measure any other length yourself |
| "already built its twin" / "already assembled" / "already generated" | The run folder is fixed: start a new run (`new_version=true` for a rebuild) |
| "the image-to-3D generator is not configured" | The person must set `MOONWALKERS_GEN_ROOT` for the server |
| "no photo for the generator" | Add a whole-machine photo with use `generator` |
| "have no view" | With several photos, give each its `view` (start a new run if one was added without) |
| "both show ..." / "mix sides and corners" | The generator takes one photo per view, sides or corners: add the extra photo with use `evidence` |
| "Pipeline D (...) ... is not in yet" (or A, C) | The document's pipeline is not in yet: cite it with `add_reference_source` and record its facts with `add_fact` |

Claude Code asks the person before each tool call unless they allow the tool. Only
`check_knowledge_base`, `list_jobs` and `fit_circles` are read-only. `request_twin` stores nothing when it reuses a
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
