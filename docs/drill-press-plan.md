# Drill-press plan (integration phase)

**Goal:** a functional twin of a harder machine, meeting the advisors' four goals
(`docs/poc-report.md`, section 8):
- several moving parts cut from one model;
- sliding joints and a chain of joints;
- motions that move together: the downfeed handles turn as the quill slides;
- a way to describe a manual machine's control.

**Machine:** Grizzly T33901 14" benchtop drill press, approved by the advisors on Oct 22, 2026
(worklog 2026-10-22). **Written:** Oct 22, 2026, for Daniel's review. He answered its questions
the same day (below).

**Status:** approved (PR #15). Phases 0 to 5 are done (PRs #15, #16, #18, #19, #20, #21; PR #21
merged on 2026-10-28). Phase 6 is under way on `feat/phase-6-control-logic`: its research, decision
0025 (proposed), the controller and `grizzly/t33901@v7` are done (2026-10-30), and Daniel's Isaac
Sim check of level 3 is next. Stop at the end of each phase, open a pull request, and wait for
review before starting the next. The HA5C stays the reference twin: every
phase keeps it building, and its tests passing.

**Direction (Daniel, Oct 22, 2026):** "The goal is to allow multiple image input and allow for the
least amount of guessing. While working on that goal stand ins may be used." Every stand-in (a
part, a ratio, a value) is labelled as such in the twin and logged as an inaccuracy.

**Stand-ins, refined (Daniel, Oct 24, 2026):** a stand-in where the detail is visible in the twin
or needed for it to work; left out where it is hidden and unused. For example, the T33901's belt
positions sit under the closed belt cover, which the twin has no way to open, so they are left out.
On a machine whose belts show, they would get a labelled stand-in.

## Decided on review (Oct 22, 2026)
| Question | Answer |
|---|---|
| Contract before or after the box test? | After, unless Claude Code judged otherwise. **Claude Code's call: after** (reasons below) |
| The handle-to-quill ratio | A stand-in if it cannot be found. Researched the same day: not found (`docs/research/2026-10-22-t33901-handle-ratio-and-figures.md`) |
| Middle parts a photo cannot show | Stand-ins while working towards several images and the least guessing (the direction above) |
| The joint recorder and the quote checker | Keep them if they suit the project as a whole. **Kept** (reasons below) |
| The HA5C's acceleration and mill signals | In this plan if they fit, otherwise a plan of their own. **They fit Phase 6,** which works on control logic anyway |

**Why the contract comes after the box test.**
- Three teammates code against the contract, so it should change once, with evidence. The box
  test shows what Isaac Sim 6.2 can do. For example, it shows whether a lock is best written as a
  drive or as a limit, and whether mimic joints work at all.
- v0.1.0 already describes what the teammates' pipelines produce first: sources, identity, facts,
  prismatic joints and limits.
- The contract comes in Phase 2, so the teammates wait for one phase only.

**Why the two tools are kept.**
- **The joint recorder** turns the functional checks into numbers: how fast the spring returns
  the quill, where the stop ends its travel, and how closely the handles follow. The methodology
  asks for a functional-check measure, and the advisors said we define our own measures. It also
  answers the PoC report's item 11.
- **The quote checker** enforces rule 1 ("Every fact needs a source") cheaply. In the PoC, a
  one-off script compared an agent run's 26 quotes with the documents (worklog 2026-10-18). The
  checker makes that a standing tool for every reference file. It uses pypdf, already a dev
  dependency. If the agent's tools ever run it, pypdf moves to the main dependencies, which is
  asked first.

## What the manual gives
Source: the Grizzly T33901/T33902 manual,
`data/machines/grizzly-t33901/inputs/documents/grizzly-t33901-t33902-manual-2023.pdf`, from
https://cdn0.grizzly.com/manuals/t33901_m.pdf ("REVISED DECEMBER, 2023"). Page numbers are the
PDF's. Pages 8-9 are the T33901's data sheet. Pages 10-11 are the floor model T33902's, which
differs (for example "15 x 25-1/2 x 61-1/2 in."). The text was read with pypdf on 2026-10-19
(`docs/research/2026-10-19-open-questions-research.md`, section 6), and the text and photos again
on 2026-10-22 (`docs/research/2026-10-22-t33901-handle-ratio-and-figures.md`). Every quote is
checked again when the reference facts are written (Phase 5).

| Motion | What moves | Range | Driven, held or returned by | Pages |
|---|---|---|---|---|
| Quill slides | quill, spindle, chuck | "Spindle Travel ... 3-1/4 in." | the downfeed handles; "Spindle Return Spring: Automatically returns quill into headstock"; "Depth Stop: Stops spindle travel at predetermined drilling depth" | 7, 8 |
| Spindle turns | spindle, chuck | "12 Speed Settings: 340, 500, 530, 660, 740, 790, 1380, 1420, 1680, 1860, 2200, 2860 RPM" | "the configuration of V-belts and pulleys" | 9, 30 |
| Downfeed handles turn | the hub and its three handles | not given | the quill's rack and pinion ("Lubricate column rack and quill rack and pinion") | 7, 18, 35 |
| Table up and down | table bracket | "Vertical Table Travel ... 14-3/8 in." ("Floor-To-Table Height ... 9-5/8 - 24 in.") | the table height crank; the "Table Height Lock Handle" | 7, 9, 32 |
| Table around the column | table bracket and column rack | "Table Swivel Around Column ... 360 deg." | the "table lock handle" | 9, 32 |
| Table tilts | table arm and table | "Max. Table Tilt (Left/Right) ... 0 - 45 deg." | the tilt lock hex bolt | 9, 32 |
| Table around its centre | table | "Table Swivel Around Center ... 360 deg." | the "table pivot lock handle" | 9, 32 |

- **Sizes:**
  - p. 8: "15 x 25-1/2 x 39 in." (width x depth x height), "Swing ... 14 in.", "Max. Distance
    From Spindle to Column ... 7 in." and "Max. Distance From Spindle to Table ... 15-7/8 in.";
  - p. 9: "Distance From Spindle to Base ... 23-3/8 in.", "Quill Diameter ... 1.85 in.", "Column
    Diameter ... 3-1/8 in.", a table "11-1/4 in." by "11-1/4 in." by "1-1/16 in." thick, and a base
    "18 in." by "10-1/2 in.";
  - weight: "108 lbs." (p. 8).
- **Controls:** "ON/OFF Switch w/Disabling Key: Turns motor ON when moved up; turns motor OFF
  when moved down. Removal of yellow key disables switch so motor cannot start" (p. 6), plus the
  LED and laser switches.
- **The depth stop:** "a threaded rod attached to the quill with a depth stop nut that can be
  lowered or raised against a stop bracket" (p. 31), so it is a setting within the quill's travel.
- **From the manual's photos and its exploded view** (viewed on 2026-10-22; part numbers from
  pp. 49-50):
  - **The table's chain:**
    - the "COLUMN BRACKET" (106) clamps the column and carries the height crank's worm and
      14-tooth gear;
    - the "TABLE MOUNTING ARM" (121) turns in a horizontal bore of the bracket: the tilt, locked
      by a "HEX BOLT M16-2 X 30" (124), beside the "TABLE TILT SCALE" (118);
    - the "TABLE" (120) turns in the arm's far end, under its centre, locked by a folding handle
      (122).

    So the tilt comes before the turn about the centre, and the arm is a real part between them
    (photos p. 32; exploded view p. 48).
  - **The head:** three downfeed handles on one hub, on the right of the head as the operator sees
    it (photos pp. 6-7). Each handle is a "STUD-DE M12-1.75 X 178, 15" (part 102) with a "KNOB
    M12-1.75, D35" (101), so a bar is 178 mm long [INFERENCE: read from the stud's size]. The quill
    rack and the column rack are shown in p. 36's Figure 48.
  - **The whole machine:** two studio photos, from different front angles (p. 5).
- **The belt-speed chart is a label under the machine's belt cover,** not a page of the manual
  (p. 30). The manual gives one entry: "a belt combination of B-3 creates 790 RPM". A photo of the
  label would give the other eleven.
- **Not found, in the manual or in any public source we could reach on 2026-10-22:**
  - the handle-to-quill ratio. The parts list names a "PINION SHAFT" (p. 50), but gives no tooth
    count or pitch. The exploded view draws the pinion, but only its near side shows, and a drawing
    is not a specification. Grizzly's product and parts pages refuse scripts (HTTP 403). **A
    labelled stand-in is used, logged as an inaccuracy** (Daniel, 2026-10-22), until a measurement
    or Grizzly gives it (research note, "What would settle it");
  - the head's size;
  - the return spring's force: a "FLAT COIL SPRING" (p. 49), whose tension can be adjusted (p. 40).
- **[INFERENCE], still to check:**
  - The "table lock handle" of "Rotating Table Around Column" (p. 32) is the table height lock
    handle. The page's labels name only the "Table Height Lock Handle" and the "Table Pivot Lock
    Handle", and the exploded view draws only one lock handle on the bracket, a "FOLDING HANDLE
    M12-1.75 X 50, 90L" (105). **Supported on 2026-10-23:** p. 7 says the height lock handle
    "Loosens to allow adjustment of table position on column; tightens to lock table position"
    (`docs/research/2026-10-23-table-height-lock-and-mimic-chains.md`).
  - Whether the crank's worm holds the table when the height lock is loose: not confirmed. The
    manual gives no lead angle (same note). A similar drill press's table fell once its lock was
    loosened, so the twin assumes the T33901's does too (Daniel, 2026-10-23; decision 0018).
  - The column rack turns with the table bracket. Assembly seats the rack "firmly between collar
    and column base" (p. 22), and turning the table means "making sure to guide column rack with
    table" (p. 32). So the rack is the part between the turn around the column and the slide up it.
  - "Spindle to Column" is measured to the column's surface, since the swing is 14 in.

## Success levels
1. **A scaled model of the T33901, cut into its moving parts, with cited facts, opens in Isaac
   Sim.** It is built from several photos where they exist. Its sizes are compared with every
   cited dimension, and each difference, guess and stand-in is logged.
2. **The joints move as the manual describes, in Isaac Sim:**
   - the quill slides 3-1/4 in, the spring returns it to the top, and the depth stop ends its
     travel;
   - the spindle turns, and the handles turn as the quill slides;
   - the table slides up the column, turns around it, tilts 45° each way and turns about its
     centre, and each of these holds when locked.
3. **The manual's control drives it:** the keyed switch (no key, no start), a speed chosen from
   the twelve cited settings, and an operator's drilling stroke run in Isaac Sim. The stroke
   feeds down to the depth stop, then releases, and the spring returns the quill.

Plus: a box-and-cylinder drill press passes the level 2 checks first (Phase 1); a second request
reuses the stored twin and says so; the HA5C still builds and is reused as before.

## Phase 0 - Plan
- [x] Read the record: CLAUDE.md's "Current phase", `docs/poc-report.md` sections 6-8, the
      follow-up in `docs/worklog/2026-10-22.md`, section 6 of
      `docs/research/2026-10-19-open-questions-research.md`, and the manual's pages above
- [x] This plan, worklog, PR (Oct 22, 2026: branch `docs/drill-press-plan`, PR #15); stop for
      review
- [x] Daniel's answers recorded, and the ratio researched (Oct 22, 2026)
- [x] A PDF renderer and the multi-view model installed on his approval (Oct 22, 2026; "Installed
      on Daniel's approval", below)

## Phase 1 - A box-and-cylinder drill press proves the exporter
No generated mesh. As in the PoC's Phase 2, the test model goes down the exporter's real path.
Its sizes are the manual's where it gives them, and made up, labelled as such, where it does not:
the head, the hub, the rack, the bracket and the arm. The new behaviours are exporter
settings, as `DriveSettings` is today, not contract fields. The contract changes in Phase 2, with
this phase's evidence.
- [x] Research note, from primary sources, before any code
      (Oct 22, 2026: `docs/research/2026-10-22-sliding-joints-locks-and-coupling.md`, mostly from
      Isaac Sim 6.2's own schema files and demos. `PhysxMimicJointAPI` is deprecated, but
      `NewtonMimicAPI` cannot tie a turning joint to a sliding one. A Shift+drag pushes a part):
  - UsdPhysics prismatic joints, linear drives and their limits;
  - the two leads for coupled motion, `PhysxMimicJointAPI` and
    `PhysxPhysicsRackAndPinionJoint`: what NVIDIA documents for Isaac Sim 6.2, which joints each
    works with, and whether usd-core, which lacks the PhysX schemas, can write them by name;
  - ways to write a lock (a stiff drive at the setting, equal limits, a fixed joint switched on)
    and a spring return (a weak drive towards the top);
  - the depth stop as a limit. NVIDIA: "Articulation joints without limits cannot be configured
    with limits after attaching the stage" (`docs/research/2026-10-17-usd-physics-for-isaac-sim.md`),
    so the stop is written as a limit from the start;
  - how a person pushes a part during an Isaac Sim check [INFERENCE: we expect a mouse drag on a
    moving body; to confirm].
- [x] Exporter (`usd/exporter.py`)
      (Oct 22, 2026: `JointSettings` and `JointCoupling`; PhysX schemas written by name in
      `usd/physx_schemas.py`. Parts that no joint joins do not collide. The Phase 2 test twin is
      byte-identical, checked by a fixture test. Decisions 0017-0019):
  - prismatic joints, with linear drives and limits in metres; today they are refused;
  - a drive per joint (spin, hold, spring return, locked, free) instead of one drive for every
    joint;
  - a chain of seven joints. `_root_part` already accepts a tree, but only one joint has been
    checked in Isaac Sim;
  - coupled joints: the mimic joint if the research shows it works in Isaac Sim 6.2, otherwise
    the fallback chosen in decision 0019;
  - unchanged output for what exists: built at a fixed time, the Phase 2 test twin comes out
    identical, and the HA5C's tests pass.
- [x] Primitive parts made of several shapes, such as the hub with its three handles
      (`usd/geometry.py`). No contract change: `Part.primitive` is free-form.
      (Oct 22, 2026: the "compound" shape)
- [x] `moonwalkers.usd.primitive_drill_press <run>`: eight parts on seven joints, as the manual's
      photos show them
      (Oct 22, 2026: ten check files in
      `data/machines/moonwalkers-testdrillpress/runs/2026-10-22_run-001/`. The quill gets its
      spring in every file, because with the default drive gravity would pull it past its whole
      stroke):
  - the parts are the frame (base, column and head), the quill, the spindle with its chuck, the
    handle hub, the column rack, the table bracket, the table arm and the table;
  - the chains are frame, quill, spindle; frame, hub; and frame, rack, bracket, arm, table;
  - it writes one check file per behaviour, validates each, and writes `RUN.md`.

  The check files:
  - `spindle_spin`: at 340 RPM, the lowest cited speed, and at a slow speed for the eye. At 60
    frames a second, 340 RPM turns 34° a frame, close to an 8-sided cylinder's 45° symmetry, so
    it may look slow or reversed [INFERENCE];
  - `quill_stroke`: the quill is fed down, then released, and the spring returns it;
  - `depth_stop`: a feed past the stop ends at the stop;
  - `handles_follow`: the handles turn as the quill slides, at a stand-in ratio (not cited);
  - `table_free` and `table_locked`: each table motion moves within its cited range when free, and
    holds under gravity and a push when locked;
  - `all_motions`: everything in one file.

  As built, the coupling and the locks each got two files, one per method, so there are ten. Their
  names are in `docs/setup/isaac-sim-check.md`, section 8.
- [x] Validation: `moonwalkers.usd.validate` learns prismatic joints, chains, drives per joint and
      coupled joints. `omni_asset_validate` runs as well, and any finding about schemas that
      usd-core does not know is recorded.
      (Oct 22, 2026: ours finds 0 errors in all ten files. NVIDIA's finds "No issues found." in
      all ten, so it accepts the schemas written by name. Its one earlier warning, about
      co-located points in the hub, was fixed)
- [x] A joint recorder for Isaac Sim checks: a Script Editor snippet that writes every joint's
      position over time to a file. With it, the spring return, the stop and the coupling are
      measured, not only seen. It is also used on the HA5C's program files (the PoC report's
      item 11).
      (Oct 22, 2026: `usd/isaac_recorder.py`, copied into the run as `record_joints.py`. It reads
      `omni.physics.tensors` after each physics step and writes CSV. Its pure parts are tested;
      it has not yet run in Isaac Sim.
      Oct 23, 2026: it works in Isaac Sim 6.2.0, after a fix to how it gets its physics view. Its
      first recording measured the handles within 1% of their ratio and the spring's 0.83 s return.
      Using it on the HA5C's program files, item 11, is left for a later check)
- [x] Isaac Sim 6.2.0 check by Daniel, from a checklist per file (a new section in
      `docs/setup/isaac-sim-check.md`)
      (Oct 22, 2026: the checklist is section 8, and the files are ready.
      Oct 23, 2026: Daniel checked run-001 in Isaac Sim 6.2.0. Nothing shook or flew apart:
      - the mimic coupling and the locks by equal limits work;
      - the spring and the depth stop work, the stop to the measured 2.88 in;
      - three problems, fixed in run-002: the slow spindle fell asleep; the rack and pinion
        jammed, probably its sign; the free table's height sagged;
      - the recorder wrote nothing ("Failed to get a valid attached USD stage id"), also fixed.

      Re-check of run-002, the same day: all three fixes work, and the rack and pinion is a working
      fallback. The fixed recorder then made its first recording)
- [x] Decision records 0017, 0018 and 0019; worklog; PR
      (Oct 23, 2026: all three hold the check and the re-check. Branch
      `feat/phase-1-drill-press-exporter`, PR #16. The records are accepted at its review)

## Phase 2 - Contract v0.2.0, and how the teammates' pipelines run
- [x] Decision record 0020: contract v0.2.0, only for what v0.1.0 cannot describe. Field names
      are chosen in the record.
      (Oct 23, 2026: written and proposed. Three optional fields on `Joint`: `mode`,
      `adjustable_stop` and `follows`. Stored "0.1.0" results stay valid as they are. Daniel
      reviewed it the same day: two inferences researched, links may now chain but not loop, and
      `stop` renamed. Oct 24, 2026: accepted by Daniel and merged (PR #18); the owners' review is
      still open)
  - **Linked joints:** a follower joint moves with a leader at a ratio, as the handles follow the
    quill. A stand-in ratio is allowed, labelled as one.
  - **Joint modes:** driven, spring return to a rest position, locked at a setting, or free; and
    an adjustable stop inside a joint's limits (the depth stop).
  - **Unchanged:** v0.1.0 already has prismatic joints, limits in metres, a parent and a child on
    every joint, and `state_machine` and `lookup_table` behaviours (worklog 2026-10-22).
  - **Stored results:** the HA5C's v1-v3 and the TH240's v1 results say `schema_version` "0.1.0",
    the only value the contract accepts today. The record decides how they keep loading and
    building.
  - Discussed with Ava, Kiran and Sarkis before it is merged (CLAUDE.md, "Who owns what").
- [x] Build it:
  - the contract, its JSON Schema (`moonwalkers.contracts.json_schema`) and the dashboard's types
    (`moonwalkers.api.typescript`);
    (Oct 23, 2026: done, with 31 new contract tests. The exporter writes each result's own
    version, and the Phase 2 test twin differs from its 2026-10-22 files only by the two
    provenance lines. The eight stored results load and the four stored twins build)
  - the exporter reading the new fields; the dashboard showing modes and links;
    (Oct 23, 2026: done. `contract_settings`, plus `starts` and `coupling_method` for checks; 21
    exporter tests. The dashboard shows each joint's mode, stop and link with their citations)
  - the box-and-cylinder drill press rewritten to use them; at a fixed time, its stages match
    Phase 1's.
    (Oct 23, 2026: run `2026-10-23_run-003`. `all_motions` matches Phase 1's physics; the other
    files differ only in three intended ways: the handles always follow the quill, the table is
    locked by its handles, and the loosened table drops. Decision 0020, Consequences. Daniel's
    short re-check is in `docs/setup/isaac-sim-check.md`, section 8)
- [x] Decision record 0021: how Pipelines A, C and D run outside their tests. It answers:
  - **Where they start.** The agent's tools build only through Pipeline B, and the dashboard takes
    only a machine photo (worklog 2026-10-22). Candidates: an MCP tool and a command line first.
    The dashboard waits for this record.
  - **Stubs stay in the tests.** Each stub returns the HA5C's fixture for any job
    (`pipelines/fixture_stub.py`), so a drill-press document routed to a stub would get HA5C
    facts. Until an owner's pipeline is in, its input is refused as not available yet
    (`PipelineUnavailableError`).
  - **One twin from several results.** The orchestrator already builds one job's twin from every
    routed result, and the exporter refuses a part id found in two results. What happens when two
    results give one fact different values? Which results may carry parts and joints? Decision
    0009 leaves merging open.
  - **Environment:** the backend's own, or a separate one called as a subprocess, as the
    generators are (`generators/`).
  - Agreed with the owners.

  (Oct 23, 2026: written and proposed, on Daniel's word to finish Phase 2. Found while reading:
  `add_input` already took any input type, so a drill-press document could reach a stub and get
  HA5C facts. Chosen: a command line now, and `add_input` refusing a document whose pipeline is
  not in; the stubs only in the tests; one result per twin carries parts and joints; disagreeing
  facts listed for the reviewer; the backend's environment by default. Oct 24, 2026: accepted by
  Daniel and merged (PR #18); the owners' review is still open)
- [x] Build our side of what the record chooses, tested with a fake pipeline rather than the stubs
      (Oct 23, 2026: `Pipeline.stub`, `default_pipelines()` without stubs, `stub_pipelines()` for
      the tests; the orchestrator's two rules; `add_input`'s refusal; `python -m
      moonwalkers.pipelines list | run`. 22 new tests, on fake pipelines)
- [x] A short guide for the pipeline owners: the contract, `create_pipeline()`, citations, tests,
      and how to try a pipeline on the T33901's manual (worklog 2026-10-22, "Next step")
      (Oct 23, 2026: `docs/pipeline-guide.md`. Its example Pipeline D was run through the command
      line on the real manual)
- [x] Worklog; PR
      (Oct 23, 2026: worklog 2026-10-23; branch `feat/phase-2-contract-and-pipelines`, PR #18.
      Oct 24, 2026: Daniel's Isaac Sim re-check of run-003 confirmed the three changes: the table
      drops, the handles follow the quill in files 3 and 4, and `all_motions` is the same. Before
      the merge: decisions 0020 and 0021 with the owners)

## Phase 3 - Several photos per run, and the mesh
Today Pipeline B takes "exactly one machine photo" (`pipelines/b/pipeline.py`), and so do the
`add_input` tool and the dashboard's upload. This phase works towards Daniel's goal: several
images, and the least guessing.

### Hand-off (2026-10-24, from the Phase 2 chat)
- **Deadline:** done before Monday, 2026-10-26 (Daniel, Saturday 2026-10-24). "I think we have
  time to do this properly, just not enough time to wait for team mates that often take the
  weekends off."
- **Order** (Daniel, 2026-10-24). Stop for review at the end, as in every phase.
  1. **The core:** several photos per run through Pipeline B and the agent's tools: decision 0022,
     `request.json`, `add_input`, Pipeline B.
  2. **The T33901 mesh.**
  3. **The dashboard's multi-photo upload,** last.
- **Phase 2 is merged** (PR #18, 2026-10-24), on Daniel's word, before the pipeline owners'
  review.
  - Decisions 0020 and 0021 are accepted, with the owners' review still open. A change they ask
    for gets its own record.
  - `add_input` refuses a document whose pipeline (A, C or D) is not in. Decision 0022 keeps that
    rule while it lets several photos in.
- **Daniel's photos** (2026-10-24), in `data/machines/grizzly-t33901/inputs/photos/`. Each has a
  line in `inputs/SOURCES.md` with its origin and SHA-256. That file's photo section is the record,
  and supersedes what an earlier version of this hand-off said. Daniel re-saved the AVIF and WebP
  files as PNG and replaced the originals, and recorded every origin.

  | File | What it shows (as viewed on 2026-10-24) | From (`SOURCES.md`) |
  |---|---|---|
  | `front_operator_left.jpeg` (was `front_left.jpeg`) | The whole machine, from the front-left corner (see the labels below) | Home Depot's T33901 listing |
  | `front_operator_right.png` (was `front_right.png`) | The whole machine, from the front-right corner: the handle hub, the table crank and the column rack | Home Depot's T33901 listing (re-saved from AVIF) |
  | `top_with_cover_removed.png` | The belt cover open: three stepped pulleys, two belts. The speed chart inside the lid shows, but is unreadable at this size | Home Depot's T33901 listing (re-saved from WebP) |
  | `Underneath_behind_quill.png` | Under the head: a round light, most likely the LED work light [INFERENCE], the laser's caution label, the chuck guard and the chuck | Lowe's T33901 listing (re-saved from AVIF) |
  | `table_top.png` | The table: four slots and a centre hole | A YouTube video of several Grizzly drill presses, its T33901 section |
  | `motor_sticker.png` | The motor's plate: "3/4HP", "120V", "60Hz", "7.5A", pole "4", phase "1", R.P.M. "1720", class "B" | The same video |
  | `spindle_speeds.png` | The manual's own "Figure 30. Drill bit speed chart (RPMs)" (PDF p. 29) | The manual |
  | `spindle_speed_chart.jpg` | **The T33904's** belt chart, readable. Not the T33901's (below) | J&B Tools' T33904 page |

  - **The motor plate agrees with the manual:** the data sheet (p. 8: "3/4 HP", "1720 RPM"),
    p. 15 ("7.5 Amps"), and the machine's label (p. 54: "Motor: 3/4 HP, 120V, 1-Phase, 60 Hz
    Full-Load Current Rating: 7.5A").
  - **`spindle_speeds.png` is not the belt chart.** It gives speeds by bit and material, not which
    belt positions give which speed. It is useful for control logic (Phase 6), not as a
    substitute.
  - **`spindle_speed_chart.jpg` is the T33904's, not the T33901's.** The label on its head reads
    "MODEL T33904 20" FLOOR DRILL PRESS w/LED LIGHT & LASER GUIDE". Its B-3 gives 610 RPM where
    the T33901's gives 790 (p. 30), and only 340 of its twelve speeds is in the T33901's list
    (p. 9), so its values do not apply. It shows the chart's format: belt positions lettered A-D
    and numbered 1-4, which the T33901 likely shares [INFERENCE: from "B-3" on p. 30].
- **The labels name sides as Daniel sees the machine, facing its front** (the operator's view).
  - Checked on `front_left.jpeg`: the handles, on the operator's right (manual, pp. 6-7), reach
    out on the image's right, and the motor's side shows.
  - The switch is on the head's front face ("Figure 1. Power controls.", p. 6), not on its right
    side, as an earlier version of this hand-off said (corrected on 2026-10-24, Phase 3).
  - The generator's `left` is the machine's own left, which is the operator's right
    (`docs/setup/generators.md`).
  - So Daniel's "front_left" is the machine's own front-right corner, and "front_right" is its
    front-left corner, the handles' side.
  - Renamed on 2026-10-24 to their views in decision 0022, which say whose left is meant:
    `front_operator_left.jpeg` and `front_operator_right.png` (same bytes; Daniel allowed it).
- **The belt chart:**
  - only "a belt combination of B-3 creates 790 RPM" is cited (p. 30);
  - the readable chart Daniel found is the T33904's (above). Research a readable copy of the
    T33901's own before guessing, from other photos, videos or Q&A pages;
  - pulley diameters are not confirmed anywhere yet.

### Items
- [x] Collect T33901 photos into `inputs/`, logging each in `SOURCES.md`:
  - the manual's own: two studio photos of the whole machine (p. 5) and close-ups of the head,
    the hub, the depth stop and the table (pp. 6-7, 31-32, 36). They are copyrighted and for
    internal research only (`SOURCES.md`). Extract them with pypdfium2;
  - Grizzly's site has no T33901 page (Daniel, 2026-10-23); listings exist at Home Depot and
    Lowe's;
  - others from public sources, with their URLs.

  (Oct 24, 2026: Daniel collected eight, with their origins, and re-saved the AVIF and WebP files
  as PNG (Hand-off, above). The same day, 19 of the manual's photos were extracted unchanged with
  pypdfium2 into `inputs/photos/manual/`: the two studio photos (p. 5) and the figures of pp. 6-7,
  30-32 and 36. Figure 2 is the same image as Figure 33, so it is kept once. Daniel's two corner
  photos were renamed to their views, `front_operator_left.jpeg` and `front_operator_right.png`)
- [x] Decision record 0022: several photos per run. It decides:
  - how each photo is labelled with the side it shows (Daniel's labels are the operator's view);
  - which photos feed the generator and which serve as evidence for the cuts, the joints and the
    size checks;
  - how `add_input`, `request.json` and the dashboard's upload take several photos;
  - how a run records what no photo shows, so that guesses are logged.

  (Oct 24, 2026: `docs/decisions/0022-several-photos-per-run.md`, accepted by Daniel as proposed)
- [x] The multi-view generator (Hunyuan3D-2mv): installed, with its image order checked and one
      run on the repository's examples (Oct 22, 2026, on Daniel's approval;
      `docs/setup/generators.md`). `left` is the machine's own left. Three views are enough.
- [x] Try corner views, such as the manual's two studio photos and Daniel's front corners, which no
      example uses
      (Oct 24, 2026: four scratch runs on Daniel's two front corners. The multi-view model keeps
      them as a grid turned 45°; the single-image model turns the machine square to an axis.
      `docs/research/2026-10-24-several-photos-and-corner-views.md`, section 2)
- [ ] The belt-speed label under the belt cover, and a full stroke of the handles, are worth a
      photo each if any source has one: they would replace a guess (the eleven missing speeds) and
      a stand-in (the handle ratio)
      (Oct 24, 2026: `top_with_cover_removed.png` shows the label, unreadable. The readable chart
      Daniel found is the T33904's, which does not apply. Researched the same day: no readable
      copy of the T33901's or the T33902's is reachable by script, and the manual's own photo of
      the lid is smaller still. What is left by hand: research note, section 3)
- [x] **First, the core:** Pipeline B and the agent's tools (`add_input`, `request.json`) take
      several photos. The HA5C's one-photo runs still build, and documents stay refused while
      their pipeline is not in (decision 0021)
      (Oct 24, 2026: the request's `photos` map, `pipelines/b/photos.py`, both models in the
      adapter, `yaw_deg` and the footprint angle, `add_input`'s `view` and `use`, the job status's
      photos. The four HA5C and TH240 run folders with a mesh still reuse it, unchanged. 34 new
      backend tests)
- [x] **Second:** generate the T33901 mesh from the best input there is, and record which sides it
      had to guess
      (Oct 24, 2026: run `grizzly-t33901/runs/2026-10-24_run-001`, the two colour corners on the
      multi-view model, 22 photos as evidence. Guessed: the back. Front turned +49.1°, squared with
      `--yaw 49.1`; proportions within 5% of the data sheet. Its `MESH.md` and the research note,
      section 4. It is Phase 4's test mesh)
- [x] **Last:** the dashboard's upload takes several photos
      (Oct 24, 2026: each photo with its view, use and origin, checked before anything is saved;
      the job page lists them. 8 new API tests and 6 dashboard tests. Checked in the real app on
      a scratch data folder, `docs/setup/dashboard.md`, section 3, step 6)
- [x] Worklog; PR
      (Oct 24, 2026: worklog 2026-10-24; branch `feat/phase-3-several-photos`, PR #19. Still open: the
      belt chart, above)

## Phase 4 - A spike on cutting a model into parts
Time-boxed to one session. It compares ways to cut one mesh into several parts.

### Hand-off (2026-10-24, from the Phase 3 chat)
- **Start** from `main` after PR #19, on branch `feat/phase-4-part-cutting-spike` (created from
  `main` the same day). Phase 4 starts in a new chat.
- **The T33901 mesh:** `data/machines/grizzly-t33901/runs/2026-10-24_run-001/generator/mesh.glb`
  (40,000 faces, watertight; generator axes +Y up, +Z front). Its `MESH.md` says how it was made.
  - **To see it square:** `uv run python -m moonwalkers.pipelines.b inspect
    ../data/machines/grizzly-t33901/runs/2026-10-24_run-001 --up +y --front +z --yaw 49.1`.
    The corner photos left the front turned +49.1° (decision 0022).
  - **Guessed:** the back. The front and both sides were seen only at an angle, from the two front
    corners. The tip-slab warnings are expected: the base is the front-most part.
  - **Which way it faces once squared** (checked in the Phase 3 chat; easy to get mirrored):
    - +X is the machine's front;
    - +Y is the machine's own left, which is the operator's right: the side with the handle hub
      (Fig. 3) and the table crank (Fig. 6). The handles reach out to +Y;
    - +Z is up.

    In the inspection's `views.png`, the "left" panel is the camera at +Y, so it shows the
    handles' side (`mesh_tools.VIEWS`). The footprint angle alone cannot tell front from back:
    +49.1° was chosen because the base reaches forward of the column, and corners give about +45°.
  - **Squared bounds, in model units:** min (-0.6620, -0.2962, -1.0002), max (+0.5812, +0.4698,
    +0.9949); extents 1.2431 deep, 0.7660 wide, 1.9950 tall. The data sheet's 15 x 25-1/2 x 39 in
    (p. 8) fit those proportions within 5%. No scale is set yet: that is Phase 5 (decision 0024).
  - **`MESH.md` is in `data/`, which is not in git.** The same facts are in
    `docs/research/2026-10-24-several-photos-and-corner-views.md`, section 4.
  - **The run shows as an open job,** "In progress: mesh generated" with next step "reading
    notes", in `list_jobs` and the dashboard. That is expected. Phase 4 cuts copies of the mesh in
    scratch folders and builds nothing; whether Phase 5 continues this run or starts a new one is
    Phase 5's call (its photos are fixed now that its mesh exists).
- **Evidence for the cuts:** 22 photos in the run's `request.json`, use `evidence`. The figures
  that show moving parts are:
  - Figs. 3 and 4: the head's two sides, the handle hub, the depth stop and the spring housing;
  - Fig. 35: the depth stop;
  - Figs. 36-38: the table's chain (height crank, pivot lock, height lock, tilt scale, column
    rack, tilt bolt);
  - Figs. 46 and 48: the quill lowered, and the racks.

  The parts and their order come from the exploded view (p. 48) and the parts list (pp. 49-50),
  summarised in "What the manual gives", above.
- **The synthetic test mesh:** the Phase 1 box-and-cylinder drill press
  (`moonwalkers.usd.primitive_drill_press`) has the same parts as separate primitives. Fused into
  one mesh, with each face labelled by its part, it gives the score for each method.
- **Daniel's directions to keep:**
  - the least guessing;
  - no moving part is cut from the back, which the generator guessed;
  - stand-ins only where visible or needed, and the rest left out (the rule at the top of this
    plan).
- **Installs:** method (c), a learned model, needs Daniel's approval first, with its license and
  size (CLAUDE.md rule 3), and runs in its own environment, as the generators do.
- **The MCP server** has Phase 3's tools: Daniel restarted it on 2026-10-24. The T33901's machine
  key is `grizzly/t33901` whatever the manufacturer's spelling (decision 0009's alias).
  - A running server keeps the tools it started with. After changing the server's code, ask
    Daniel to restart it (`/mcp`, or a new session) before testing through it.
  - Until then, scripts can call the same code directly (`Workspace`, `PipelineB`), as Phase 3
    did for run-001.
- **Tools and gotchas from Phase 3:**
  - **The manual's figures:** the photos are in `inputs/photos/manual/`, the embedded JPEGs
    unchanged. The exploded view (p. 48) is vector art: render it with pypdfium2
    (`page.render(scale, grayscale=True)`) and save it with `mesh_tools.write_png`. `write_png`
    takes only a greyscale H x W uint8 array. How it was done on 2026-10-22:
    `docs/research/2026-10-22-t33901-handle-ratio-and-figures.md`.
  - **The Read tool** shows PNG and JPEG, not PDF.
  - **The Phase 3 chat's scratch scripts are gone** (they lived in that session's scratch folder):
    the corner experiments, the photo extraction, the T33901 run, and the dashboard check in
    headless Edge. Their methods are in the worklog of 2026-10-24 and in the research note.
- **Housekeeping:**
  - PR #19's branch `feat/phase-3-several-photos` was kept: Daniel did not ask to delete it.
  - Phase 3's deadline (before Monday, 2026-10-26) was met. Daniel has not given one for Phase 4.
- [x] **Test meshes:**
  - the box-and-cylinder drill press as one mesh, so the right part is known for every face. It is
    the easy case [INFERENCE: a generated mesh fuses its parts into one surface; this one does
    not];
  - the generated T33901 mesh from Phase 3, judged against the manual's photos.

  (Oct 24, 2026: `pipelines/b/synthetic_parts.py` builds the drill press separate, as here, and
  also fused into one surface and rounded, since the separate build scores every method that
  looks at the mesh's own shape at 1.000)
- [x] **Methods:**
  - (a) several cuts in the geometry spec: an ordered list of shapes (cylinder, box, plane) per
    part, where the first match wins. It extends decision 0012 and needs no install;
  - (b) splitting by the mesh's own shape (sharp edges, thin necks, separate pieces). It needs no
    install [INFERENCE: likely weak where the generator fused parts];
  - (c) a learned part-segmentation or articulation model. Project-context Topic 13 names
    Articulate-Anything and URDF-Anything as aimed at articulation, untested on industrial
    machines; newer candidates come from the spike's research. Any install is asked first, with
    its license and size, and runs in its own environment, as the generators do;
  - (d) marking the parts on the photos and carrying the marks onto the mesh. Several photos make
    this less of a guess [INFERENCE: not researched].

  (Oct 24, 2026: (a), (b) and (d) built and run with `python -m moonwalkers.pipelines.b.part_spike`;
  (c) researched only, by Daniel's choice: P3-SAM and PartField, with their licences and sizes)
- [x] **Measures:**
  - the share of faces put in the right part (synthetic mesh);
  - open edges and seams;
  - time taken;
  - installs and licenses;
  - whether the result can be cited and reviewed.

  (Oct 24, 2026: on the rounded synthetic mesh, (a) 0.996 of the area in the right part, (b)
  0.733-0.923, (d) 0.947 with perfect marks from two front corners. On the T33901, (a) cut eight
  parts in five passes; the mesh is one piece for (b); the two photos were placed on it with a
  silhouette IoU of 0.80 for (d). Research note, section 6)
- [x] Research note (`docs/research/2026-10-24-part-cutting-spike.md`); decision record 0023
      ((a) cuts, with (d)'s camera fit drawing the cuts over the photos for review; accepted by
      Daniel on 2026-10-26, with his answers on stand-ins); worklog; PR #20

## Phase 5 - Pipeline B builds several parts and joints (levels 1 and 2)

### Hand-off (2026-10-26, from the Phase 4 chat)
- **Start** from `main` after PR #20 (merge commit `2f3f638`), on branch
  `feat/phase-5-several-parts-and-joints`, created from `main` on 2026-10-26. Its first commit holds
  this hand-off and is not on `main` yet. Phase 5 starts in a new chat.
- **Read first:**
  - decision 0023, including "Daniel's answers" at its end;
  - `docs/research/2026-10-24-part-cutting-spike.md`: section 4 (the T33901's measurements and
    errors), section 6 (the measures) and section 8 (the review: the table and the crank);
  - decisions 0012 (the geometry spec and the run folder) and 0022 (`yaw_deg`, the photos);
  - the items below.
- **What Phase 4 left in code, and what Phase 5 does with it** (all in `pipelines/b/`):

  | Module | What it is | For Phase 5 |
  |---|---|---|
  | `part_cuts.py` | (a): `CylinderCut`, `BoxCut`, `HalfSpaceCut`, `PartCut`, `assign`, `split`, `seams` | the cut list in the geometry spec (decision 0023) |
  | `part_spike.py` | the spike's runner; `T33901_CUTS` (the draft cut list, with each shape's evidence), `T33901_PASSES`, `render_parts`, `photo_overlay`, `write_rgb_png` | start the T33901's spec from `T33901_CUTS`; move the views and the overlay into the inspection |
  | `photo_marks.py` | (d): orthographic `Camera`, `render`, `carry`, `fill_unseen`, `fit_camera`, `in_photo` | `fit_camera` and `in_photo` place each fed photo for the overlay; `carry` waits |
  | `mesh_tools.py` | `face_groups` (union-find) and `read_png` (all five PNG filters), added beside the old tools | used by the above |
  | `synthetic_parts.py` | the Phase 1 drill press as one labelled mesh (separate, fused, rounded), `surface_nets`, `score` | a test mesh for the several-part spec |
  | `mesh_segments.py` | (b): pieces and sharp-edge regions | not used to cut (decision 0023) |

  The spike re-runs with `uv run python -m moonwalkers.pipelines.b.part_spike <out> --t33901
  ../data/machines/grizzly-t33901/runs/2026-10-24_run-001` (about 4.5 min). Its last output is
  in `data/machines/grizzly-t33901/part_cutting/2026-10-24_spike/` (`report.md`, `t33901_a.png`,
  `t33901_a_on_front_photo.png`, `t33901_a_on_left_photo.png`).
- **The T33901's frame and measurements** (model units, squared with up `+y`, front `+z`, yaw
  49.1):
  - +X is the front, +Y the machine's own left (the operator's right, the handles' side), +Z up;
  - the column's axis is at (-0.1385, +0.005), radius 0.079;
  - the spindle's axis is at (0.277, -0.022), from the chuck guard's round fits;
  - the depth stop's rod is at (0.334, -0.156);
  - the pinion's axis is along Y through about (x 0.229, z 0.497), where the handles' lines meet.
    The spring housing on -Y gives (0.252, 0.482);
  - the table's top is at z ≈ -0.231.

  The vertical axes came from circle fits on a copy turned so +Z became +X
  (`orientation_matrix("+y", "+z")` on the squared mesh), since `fit_circles` slices across X
  only.
- **The scale (decision 0024).** Two cited sizes already agree within 1%:
  - the column's "3-1/8 in." diameter (p. 9) gives 0.501 m per unit;
  - the "39 in." height (p. 8) gives 0.4965 for the squared height of 1.995.

  Spindle to column measures 5-6% short of the cited 7 in at either scale (research note,
  section 4).
- **Stand-ins (Daniel, 2026-10-26):** the chuck, the table and the crank, plus the rack (below).
  - **The rack.** Asked "The column rack ... would get a stand-in too ... Is that right?" and
    "May I merge PR #20?", Daniel replied "Yes let's merge PR #20". That is read as a yes to both
    [INFERENCE: one reply to two questions]. Say so in this phase's first report, so he can
    correct it.
  - **The exporter already takes stand-ins.** It meshes each part by its own format
    (`usd/exporter.py`, `_part_mesh`), so `geometry_format="primitive"` parts (boxes, cylinders,
    compounds; `usd/geometry.py`) can sit beside the cut mesh parts. Read in the code; not tried in
    a build.
  - **Shapes beyond boxes and cylinders.** Primitives cannot cut holes, so they cannot make the
    table's slots and centre hole, its rounded corners, or the crank's S-shaped arm.
    [INFERENCE] `synthetic_parts.surface_nets` turns a signed distance into a closed mesh with no
    install. A rounded square minus the slots and the hole is easy to write as a signed distance
    (`max(a, -b)` subtracts b), and could be saved as a GLB stand-in. Not tried.
  - **Numbering.** 0024-0026 are reserved in the table below. A separate record for stand-ins
    would be 0027, unless it is part of the geometry spec's record.
- **Carried from Phase 4's hand-off, still true:**
  - run-001 shows as an open job ("mesh generated"). Whether this phase continues it or starts a
    new run with the same photos is this phase's call;
  - a running MCP server keeps the tools it started with: after changing its code, ask Daniel to
    restart it (`/mcp`, or a new session) before testing through it;
  - the manual's figures are in `inputs/photos/manual/`, and `SOURCES.md` lists every photo.
- **The environment** (found in Phase 4):
  - the backend has numpy and trimesh, but no scipy, networkx, scikit-image, rtree, shapely,
    Pillow, embreex or manifold3d. These trimesh calls fail, as checked on 2026-10-26:
    - `mesh.split()`: "no graph engines available!";
    - proximity and ray casting: no `rtree`;
    - voxel marching cubes: no `skimage`;
    - booleans: "No boolean backend: `pip install manifold3d`".

    Phase 4 wrote what it needed (above). Any of these would be an install, asked first;
  - Pillow 12.3.0 is in the generator's environment (`C:\mw-gen\hunyuan3d-2\.venv`). It was used
    once, read-only with `-I`, to check `read_png`;
  - the quick tests (`-m "not gpu and not slow"`) take about 2 min, 586 passing at Phase 4's
    end. The slow tests are the fused mesh at 4 mm, about 30 s each, and the spike end to end,
    about 70 s;
  - Windows PowerShell 5.1 splits a `gh pr create --body` argument at its double quotes. Write
    the body to a file in the session's scratch folder and use `--body-file`;
  - the Bash tool's safety check failed for a while on 2026-10-24 ("no verdict"). The PowerShell
    tool still worked.
- **Daniel's way of reviewing** (Phase 4): he looked at the coloured views and judged parts
  against the photos, and caught the table and the crank that way. Put the views and the photo
  overlays in the run folder and in the PR.
- **Housekeeping:** PR #20's branch `feat/phase-4-part-cutting-spike` was kept, since Daniel did
  not ask to delete it. No deadline was given for Phase 5.

### Hand-off (2026-10-27, from the first Phase 5 chat to the second)
- **Done in the first session** (worklog 2026-10-27; commits on this branch): steps 1-5 of the
  order of work Daniel was given.
  - The T33901's reference facts and the quote checker.
  - Decisions 0024 (the scale is the overall height; masses stay placeholders) and 0027 (joints
    and stand-ins in the spec), both **proposed**, for Daniel's review.
  - The several-part spec, stand-ins, views, check files and size checks in Pipeline B.
  - **`grizzly/t33901@v1` built** in run `2026-10-24_run-001`: 11 parts (4 stand-ins), 10 joints
    (3 fixed), six check files, `views/`, `record_joints.py`. Its `RUN.md` lists what to look for
    in each file. **Daniel's Isaac Sim check is pending.**
- **Told Daniel in the first report:** his "Yes let's merge PR #20" was read as a yes to the column
  rack's stand-in too.
- **Left for the second session** (steps 6-7):
  - **The MCP tools** (item below). Today `add_joint` and `set_scale` write decision 0012's spec
    parts (`workspace/runs.py`, `set_spec_part`, `spec_state`), `preview_twin` calls the
    single-spindle preview, and `inspect_geometry` fits circles across x only. The pipeline, the
    CLI and the views already take a `PartsSpec` (`pipelines/b/parts_spec.py`), so the tools need
    to write one: the cut list, parts (cut, stand-in, removed), joints and the scale fact, then
    preview it with `inspection.preview_parts_spec`. Old runs must keep working.
  - `docs/agent-procedure.md`, the README status, CLAUDE.md, then the PR. The PR describes the
    views; they are in `data/` (not in git), and the overlays hold copyrighted photos.
- **The T33901's spec:** `data/machines/grizzly-t33901/part_cutting/2026-10-27_spec/`.
  `compose_spec.py` writes it from cited inches and measured model units, and
  `geometry_spec_next.json` is its current output. It differs from v1 only where stand-in pieces
  met end to end; they now overlap. A next version goes in a new run folder: copy `request.json`
  and `generator/` from run-001, so the mesh is reused by its key and not regenerated.
- **NVIDIA's validator on v1:** 0 errors, 3 warnings (non-manifold points in the chuck and the
  crank). Fixed in the code and the next spec; a dry run of the next spec gave "No issues found."
  (worklog 2026-10-27).
- **Time:** a build takes about 2.5 min, most of it placing the two fed photos for the overlays
  (about a minute each). A preview with `--no-photos` takes about 40 s.
- **Still true from the hand-off above:** the MCP server keeps the tools it started with; ask
  Daniel to restart it (`/mcp`) before testing changed tools through it. Write `gh pr create`
  bodies to a file (`--body-file`).
- **Daniel's review and Isaac Sim check of v1 (2026-10-27,** recorded in run-001's `RUN.md`):
  - decisions 0024 and 0027 accepted ("look good");
  - the table "looks fantastic", its locks hold, and loosened it drops and tilts, as expected;
  - **the quill sags** below the top in every file he opened ("a noticeable gap");
  - **the downfeed handles are "very noticeably wrong"** (he called them "the crank": "three
    handles that all connect to a central joint"); the Phase 1 box model's were "far more
    accurate";
  - **PNGs in the PR: approved.** "Yes let's upload a few small PNGs under docs in the private
    repo" (an exception to CLAUDE.md rule 5, for review images only).
- **So the second session first builds v2,** then does steps 6-7:
  1. in `compose_spec.py` (decision 0027, updates; run-001's `RUN.md`, "Daniel's follow-up"):
     - a balanced stand-in for the downfeed hub and its three handles, replacing the generated
       hub and its stray faces;
     - the rest of the generated table height crank cut out: its arm lies at y 0.10-0.12, behind
       the column's back, and Daniel's screenshot shows two cranks;
     - a stand-in table pivot lock handle (the cited "FOLDING HANDLE M10-1.5 X 28, 70L"),
       replacing the generated arm's two prongs;
     - the head wall's holes where the hub was cut, covered by the stand-in hub or logged;
     - look at every `part_<id>.png`, not only `parts.png`, before building;
  2. a new run folder `2026-10-27_run-002` (or the day's date) with run-001's `request.json` and
     `generator/`, the new spec, built as `new_version`; check that both validators are clean;
  3. if the joint recorder shows the quill still sagging (v1: about 20 mm, ringing for about
     4 s, in Daniel's recording of `twin.usdc`), the spring's stand-in values or the masses
     (decision 0024, update);
  4. Daniel's Isaac Sim re-check of v2, with `adjustable_stop.usdc` and `all_motions.usdc`, which
     he has not opened yet;
  5. then the MCP tools, the agent procedure, the PR with a few PNGs of v2's views under `docs/`.

### Items
- [x] Reference facts for the T33901, like `pipelines/b/haas_ha5c.reference.json`, with every
      quote checked against its PDF page
      (Oct 27, 2026: `pipelines/b/grizzly_t33901.reference.json`, 36 facts; 42 of 42 quotes on
      their cited pages)
- [x] A quote checker: it confirms every quote in a reference file is on its cited page, using
      the PDF's text, and runs on the HA5C's file and the T33901's. pypdf's text splits words at
      line breaks with a hyphen ("prede- termined", p. 7; "con - trolled", p. 30), so the checker
      must join them (worklog 2026-10-23)
      (Oct 27, 2026: `python -m moonwalkers.pipelines.b.quotes`. The HA5C's: 15 of 16 checkable
      quotes; the miss is the drawing's stacked fraction, which pypdf cannot read as written)
- [x] Decision record 0024: facts and scale. Which cited dimension sets the scale (candidates: the
      7 in from spindle to column, the 39 in height, the 23-3/8 in from spindle to base). With
      several photos, cited dimensions can also check one another. Then how the cited 108 lb is
      split between the parts, or whether the placeholder density stays (decision 0010).
      (Oct 27, 2026: proposed, and accepted by Daniel the same day. The overall height,
      0.496536 m per model unit; the column's diameter agrees within 0.8%. Masses stay
      placeholders, since no source splits the weight. That nothing at levels 1-2 depends on them
      was corrected the same day: the unbalanced downfeed hub sagged the quill through its link
      (decision 0024, updates). Oct 28: real masses asked for and not built, for the reasons
      in its last update)
- [x] The machine key: "Grizzly Industrial, Inc." normalises to `grizzly-industrial/t33901`
      (`kb/keys.py`), but the data folder is `grizzly-t33901`. Add a `grizzly` alias, with the
      source of the short name (decision 0009).
      (Oct 24, 2026: done early, in Phase 3's PR #19, on Daniel's word. Both names now give
      `grizzly/t33901`; the source of the short name is the "GRIZZLY LOGO LABEL", manual p. 54)
- [x] A geometry spec for several parts (decision 0023): each part with its cuts, and joints of any
      type and axis, with limits, modes and links. The HA5C's existing specs still build.
      (Oct 27, 2026: `pipelines/b/parts_spec.py`, decision 0027, accepted by Daniel the same day.
      The inspection's views,
      pieces, overlays and circle fits along any axis are in `part_views.py` and `inspect
      --preview --spec`, `--circles-along`)
  - Decision 0023 (accepted by Daniel on 2026-10-26) makes the cuts an ordered cut list
    (`part_cuts`), each shape with a note naming its evidence. The spike's T33901 list
    (`part_spike.T33901_CUTS`) is a draft to start from.
  - The inspection gains what the spike did by hand: circle fits along any axis, coloured views
    of the parts, each part's pieces, and the cuts drawn over each fed photo.
  - Logged for this phase (research note of 2026-10-24, sections 4 and 8): the handle fused to
    the wall; spindle to column 5-6% short; the spindle 1.4 cm off the column's plane.
- [x] **Labelled stand-ins** where the mesh hides or gets wrong a part that shows (Daniel,
      2026-10-26, review of PR #20; decision 0023, "Daniel's answers"). Each is cited and
      logged as an inaccuracy. How a stand-in takes a cut part's place in the spec is decided
      in this phase.
  - **The chuck,** inside the guard the generator made solid. The data sheet gives "JT3 Key
    Chuck" and "1/8 - 5/8 in." (p. 8), not its outer size, which comes from Figs. 4, 46 and 48.
  - **The table,** to match the photos: "11-1/4 in." square and "1-1/16 in." thick (p. 9), centred
    under the spindle, with the rim, the four slots in an X and the centre hole of `table_top.png`
    and Fig. 36. The generated one is 0.586 by 0.614 units, skewed, and 0.055 off the spindle.
  - **The crank,** to match Fig. 36 and the colour photos: a flat S-shaped arm with its handle
    pointing out, down and to the front. No size is cited.
  - **The column rack,** visible in Figs. 36, 37 and 48, under Daniel's rule. His "Yes let's merge
    PR #20" is read as a yes to this too (hand-off above): say so in the first report.

  (Oct 27, 2026: all four, matched to the photos against cited sizes, each its own part named
  "Stand-in: ...", with a warning; the generated table, crank and chuck end are cut out. The
  chuck guard is its own part, fixed to the quill, so it can be hidden to see the chuck. Said in
  the first report: the rack read as a yes)
  - **The downfeed hub and its three handles** (added after Daniel's Isaac Sim check, 2026-10-27):
    the generated hub is "very noticeably wrong", and its weight off its axis likely makes the
    quill sag. A balanced stand-in from the cited stud and knob (p. 50) in v2 (decision 0027,
    update).
    (Oct 27, 2026: in v3, with the table pivot lock handle, the crank's leftover arm cut out and
    the holes patched; decision 0027, "Update: v2 and v3")
  - **The table pivot lock handle** (Daniel's screenshot of v1: two prongs where the photos show
    one handle): the cited "FOLDING HANDLE M10-1.5 X 28, 70L" (p. 50) in v3.
  - **The depth stop's rod** (Daniel's re-check of v3: a gap behind it when the quill moves
    down): one M12 rod through the head's ring in v4 (decision 0027, "Update: v4").
  - **The quill, the column inside the bracket, the depth stop nut and its bracket** (Daniel's
    check of v4): in v5 (decision 0027, "Update: v5").
- [x] **Left as generated, logged:** the depth stop's nut and bracket stay one ring, with the head
      ("the depth stop ring can stay in the head for now", Daniel, 2026-10-26). The back stays
      guessed: no photo of it exists in any source Daniel or Claude Code could find, and there is
      no T33901 to photograph (Daniel, 2026-10-26).
      (Oct 28, 2026: the ring no longer stays: in v5 it is cut out, the nut a stand-in riding on
      the rod and the stop bracket a stand-in on the head, on Daniel's word. The back stays
      guessed)
- [x] MCP tools: `add_joint` and `inspect_geometry` stop assuming one spindle about +X, and new
      tools are added if needed. Old runs still work. `docs/agent-procedure.md` is updated.
      (Oct 28, 2026: decision 0028, accepted by Daniel the same day. Seven tools set a several-part spec piece by piece,
      `fit_circles` measures along any axis, `preview_twin` previews either kind and lists the
      holes to patch. `add_joint` and `set_scale` are unchanged. The procedure's section 5b)
- [x] Size checks against every cited dimension: width, depth, height, spindle to column, spindle
      to table, spindle to base
      (Oct 27, 2026: width, depth, height, column, spindle to column, base length and width, all
      within 6%. Spindle to table and to base cannot be measured: the spindle's end is inside
      the guard the generator made solid; decision 0024)
      (Oct 27-28, 2026, v3 to v6: width -7.0% and depth -6.0%, since v1's generated handle that
      pointed out along +Y had stretched both; the others as v1. All under 10%)
- [x] Build `grizzly/t33901@v1`. Isaac Sim check of levels 1 and 2. Log every inaccuracy and
      stand-in as an issue in the twin, in `RUN.md`, and in the phase report's table.
      (Levels 1 and 2 reached by v4 and v5, below; every inaccuracy and stand-in is an issue in
      each twin and in its `RUN.md`. The phase report's table is Phase 7's)
      (Oct 27, 2026: built in run-001 and logged in the twin and `RUN.md`. Both validators: 0
      errors. Daniel's Isaac Sim check the same day: level 1; the table and its locks as
      expected; the quill sags and the downfeed handles are wrong, so **v2 follows**)
      (Oct 27, 2026, second session: **`grizzly/t33901@v3`** in run `2026-10-27_run-002`, both
      validators clean in all seven files. v2, run `2026-10-27_run-001`, is superseded: NVIDIA's
      validator warned about the table arm. **Daniel's Isaac Sim re-check of v3 is next**, with a
      joint recording; its `RUN.md` lists what to look for)
      (Oct 28, 2026: Daniel's re-check of v3 with recordings: **the quill rests at the top**
      (0.000 mm), the handles follow within 0.2%, level 2 for the quill, its spring and the
      handles. His two leftovers, the crank's nub and the gap behind the depth stop's rod, are
      fixed in **`grizzly/t33901@v4`**, run `2026-10-28_run-001`, both validators clean.
      Not opened yet: `adjustable_stop.usdc`, `all_motions.usdc`)
      (Oct 28, 2026: Daniel's check of v4 with recordings: the depth stop stops the quill at
      41.3 mm where its check file sets it, the spring returns it, the table's locks hold at
      their settings: **level 2**. His two gaps when parts move, below the head and in the column,
      and the depth stop nut on the rod are in **`grizzly/t33901@v5`**, run `2026-10-28_run-002`,
      both validators clean. Masses: asked for, not built (decision 0024, update))
      (Oct 28, 2026: Daniel's check of v5 with recordings: level 2, the table loosened moving
      through all its cited travel. **`grizzly/t33901@v6`**, run `2026-10-28_run-003`: v5 with the
      parts fixed to the frame grey, as he asked; both validators clean)
- [x] Worklog with run details (versions, time); PR
      (Oct 28, 2026: worklogs 2026-10-26 to 10-28; PR #21, approved and merged by Daniel's word
      on 2026-10-28, merge commit `a8d179a`)

## Phase 6 - Control logic (level 3), for the drill press and the HA5C

### Hand-off (2026-10-28, from the Phase 5 chat)
- **Start** from `main` after PR #21 (merge commit `a8d179a`, merged 2026-10-28), on branch
  `feat/phase-6-control-logic`, created from `main` the same day. Its first commit holds this
  hand-off and is not on `main` yet. Phase 6 starts in a new chat. PR #21's branch
  `feat/phase-5-several-parts-and-joints` was kept: Daniel did not ask to delete it.
- **Read first:**
  - decision 0016 (indexing programs drive a joint) and its code in `control/` (`program.py`,
    `interpreter.py`, `export.py`, `isaac_runner.py`, `python -m moonwalkers.control`);
  - decisions 0018 (springs, stops and locks), 0019 (the handles follow the quill) and 0020
    (contract v0.2.0's modes, stops and links): how the twin's joints are simulated;
  - decisions 0024 and 0027 with their updates: the T33901 twin as built, and why its masses stay
    placeholders;
  - the items below; for the HA5C, `docs/research/2026-10-19-open-questions-research.md`,
    section 3 (Parameters 18 and 44).
- **The twin to build on: `grizzly/t33901@v6`** (run `2026-10-28_run-003`).
  - v6 is v5's spec (`data/machines/grizzly-t33901/part_cutting/2026-10-27_spec/
    geometry_spec_v5.json`, written by `compose_spec.py` there) with the exporter colouring parts
    held to the frame grey. 17 parts (11 stand-ins), 16 joints (9 fixed); both validators clean.
  - Daniel checked v4 and v5 in Isaac Sim with recordings: level 2 (the runs' `RUN.md`).
  - Reviews: v2 rejected; v1 and v3-v6 not reviewed, so a request reuses v6, the newest not
    rejected (decision 0015). The HA5C's v3 and the TH240's v1 are approved.
  - **Its moving joints,** as Phase 6's control will drive them:

    | Joint | Type, parent -> child, axis | Limits | Contract behaviour | Simulated as (exporter) |
    |---|---|---|---|---|
    | `quill_travel` | prismatic, frame -> quill, -z | 0 to 0.08255 m (3-1/4 in) | `spring_return` to 0; `adjustable_stop` at the full stroke | a position drive of the acceleration type, stiffness 600, damping 49, aimed 0.03 m past the top (`SPRING_PRELOAD`, decision 0018) |
    | `spindle_rotation` | revolute, quill -> chuck, -z | none | `driven`; `max_velocity_fact` = max_spindle_speed (2860 RPM) | the default drive; `checks/spin.usdc` turns it at 30 deg/s for the eye |
    | `downfeed_handles` | revolute, frame -> handle_hub, +y | -0.05 to 4.76 rad | `follows` quill_travel at 57.09 rad per m (270 deg over the stroke, a stand-in ratio) | `PhysxMimicJointAPI`, which works both ways (decision 0019) |
    | `table_around_column`, `table_height`, `table_tilt`, `table_around_center` | revolute, prismatic, revolute, revolute | cited | `locked` | equal limits; `checks/unlocked.usdc` loosens all four (by design: Daniel asked on 2026-10-28) |

    The fixed joints hold stand-ins to their parts: the guard, the quill tube, the rod and its nut
    on the quill; the rack on the collar; the crank on the bracket; the pivot lock handle on the
    arm; the column section and the depth stop bracket on the frame.
- **What Phase 6 will meet, found in Phase 5:**
  - **The program runner drives revolute joints only.** `control/export.py` takes the twin's
    revolute joint that a behaviour drives and writes its program in degrees on an angular drive,
    and `isaac_runner.py` sets angular drive targets. A drilling stroke drives the prismatic
    quill in metres on a linear drive, so both need a linear case.
  - **The quill already has a drive: its spring.** [INFERENCE] A stroke program must move that
    drive's target (the operator's hand) and then hand back to the spring's preloaded target, or
    the two fight. The depth stop is the quill's limit replaced at the stop's position
    (`exporter.stopped_limits`); the twin's stop is at the full stroke, where the stand-in nut
    sits. `checks/adjustable_stop.usdc` moves the stop but not the nut (open below).
  - **The handles follow through the mimic, both ways:** driving the quill turns them; a stroke
    that drove the handles instead would move the quill.
  - **The spring return bounces before it rests** (v3: four bounces, still after 3.4-3.9 s; v4:
    five, 5.7 s; Phase 1's box model: 0.83 s). [INFERENCE] The stand-in handles' convex hull makes
    their placeholder inertia large. A program that waits for the quill to come home must allow
    for it. Real masses would need a contract change discussed with the pipeline owners first
    (decision 0024, last update); Daniel: "Good call keeping mass as placeholders" (2026-10-28).
  - **The control's facts are cited already** in `pipelines/b/grizzly_t33901.reference.json`:
    `switch` ("Paddle Safety Switch w/Disabling Key", p. 8), `spindle_speeds` (the twelve, p. 9),
    `min_spindle_speed`, `max_spindle_speed`, `motor_speed`. Its `control` list is empty:
    decision 0025's behaviours go there, each quoting its page (p. 6 for the keyed switch), checked
    with `python -m moonwalkers.pipelines.b.quotes`. An issue there already says the speed chart
    under the belt cover was not readable.
  - **A build with control is a new run folder:** copy `request.json` and `generator/` from
    `2026-10-28_run-003` (the mesh is reused by its key) and `geometry_spec_v5.json`; dry-run in a
    scratch copy of the data folder (`build --data`), check both validators, then build (v7). A
    `program_interpreter` behaviour with `spec["program"]` gets `programs/<behaviour>/` in the
    run (decision 0016).
- **Daniel's way of checking** (Phase 5): Isaac Sim Full 6.2.0. He opens the files a run's
  `RUN.md` lists, runs `record_joints.py` (Window > Script Editor, Run, then Play) and reports in
  chat. The recorder writes `recordings/<file>_<date>_<time>.csv` beside the file opened
  (`checks/recordings/` for check files): `time_s`, then each joint in m or rad, at 60 Hz.
  Record his words and the recordings' numbers in the run's `RUN.md` (the quill's rest, bounce
  peaks, the handles' ratio, where each table joint went). His term: "downfeed handles". A picture
  helped when a term was new (the hub: `part_cutting/2026-10-27_spec/hub_photo_and_twin.png`).
- **Left open from Phase 5** (this plan's "Still open"): the masses; the depth stop nut's place in
  `checks/adjustable_stop.usdc`; the handle ratio; the back.
- **Not tried in Phase 5:** the dashboard's twin page with a several-part twin (17 parts, 16
  joints); an agent building the T33901 through the new tools (Phase 7, procedure section 5b).
- **The environment, still true:**
  - the backend has numpy and trimesh, and none of scipy, networkx, scikit-image, rtree,
    shapely, Pillow, embreex or manifold3d; any of them would be an install, asked first;
  - Pillow 12.3.0 is in the generator's environment (`C:\mw-gen\hunyuan3d-2\.venv`), used
    read-only with `-I` to crop and measure photos;
  - pypdf reads the manual's text (its "fontTools is required" warning is harmless), and
    pypdfium2 renders pages;
  - the quick tests take about 3 min (647 passing at Phase 5's end), the slow ones about 3.5 min
    (4);
  - `gh pr create` and `gh pr edit` take the body from a file (`--body-file`);
  - the MCP server (24 tools) keeps the tools it started with: after changing its code, ask Daniel
    to restart it (`/mcp`) before testing through it.
- **The HA5C's part** is as the items below say: research Parameters 18 and 44 first.

### Daniel's answers (2026-10-30), and the order of work
He agreed to this order, stopping for checks:
1. research both machines;
2. decision 0025;
3. a runner tested outside Isaac Sim;
4. a build with control;
5. his Isaac Sim check of level 3;
6. the HA5C;
7. the PR.

His calls:
- time a stroke on any benchtop drill press, with stand-ins ready if that is not possible;
- move the depth stop's nut to where the photos show it;
- live controls in the Property panel;
- "Just the drill press for now" in Isaac Sim. Read as: the HA5C's work stays, and its Isaac
  Sim check waits until it is deemed necessary.

Worklog 2026-10-30.

### Items
- [x] Decision record 0025 (proposed 2026-10-30, `docs/decisions/0025-control-logic-for-a-manual-machine.md`;
      research: `docs/research/2026-10-30-control-logic-research.md`): how `ControlBehavior` describes a manual machine:
  - the keyed switch as a `state_machine`: key in or out, switch up or down, and the motor runs
    only with the key in and the switch up (p. 6);
  - the spindle speed as a `lookup_table` of the twelve cited speeds (p. 9). Only one belt
    arrangement is cited ("B-3 creates 790 RPM", p. 30). The rest are on the label under the belt
    cover, so they stay unknown until a photo of it is found.
    - **Decided by Daniel (2026-10-24, review of PR #19): belt positions are left out** of the
      T33901's twin. They are under the closed belt cover, and the twin has no way to open it. The
      control offers the twelve cited speeds, and only B-3 = 790 RPM names its belt position.
      Where belts are visible, on another machine, a labelled stand-in would be used (the rule
      at the top of this plan). The T33904's order carried over, with its ambiguity, is in the
      research note of 2026-10-24, section 3, if it is ever needed;
  - the operator's drilling stroke as a program that drives the quill, as decision 0016's
    programs drive a joint.

  `spec` is free-form for each kind, so none of this should need a contract change. If it does,
  that is its own record and version bump. **Done without one:** a `state_machine` switch, a
  `lookup_table` of speeds and a `command_set` of the operator's commands with two scenarios
  (`drilling-stroke`, `no-key-no-start`). The stroke's untimed values are labelled stand-ins until
  Daniel times a stroke.
- [x] An interpreter or runner for these behaviours, tested outside Isaac Sim (2026-10-30).
      `control/isaac_controls.py` is one controller: Isaac Sim runs it on each physics step, and
      `control/manual.py` plans every scenario with it. A build writes `programs/operator-controls/`
      (decision 0025). Also: the joint recorder records velocities, `python -m moonwalkers.control
      compare` measures a recording, and the exporter writes a cited top speed.
- [x] A build with control: `grizzly/t33901@v7` (run `2026-10-30_run-001`, spec
      `part_cutting/2026-10-27_spec/geometry_spec_v7.json`), with the depth stop and nut at 43 mm
- [ ] Isaac Sim check of level 3 for the drill press (`docs/setup/isaac-sim-check.md`, section 9)
  - **v7, checked by Daniel on 2026-10-31.**
    - The switch, the twelve speeds (790, 1420 and 2860 RPM held exactly), both scenarios and the
      live controls ("Raw USD Properties") work as planned.
    - The quill swung about the hand (±12 mm, about every 2.8 s) and bounced on release. The cause
      is the stand-in hub's placeholder inertia, reflected through the link, 125 times the quill's.
  - **Daniel chose option (a):** the spring is simulated on the handles' pinion, where the T33901
    has it (p. 40; decision 0025, update). `grizzly/t33901@v8` (run `2026-10-31_run-001`, the v7
    spec) awaits his re-check.
- [ ] **The HA5C controller's acceleration and its signals to a mill** (advisors, Oct 22, 2026:
      model them if possible; if not, record why and bring it back to the stakeholders).
  - **Research done (2026-10-30;** research note, section 5): the 2006, 2012 and 2017 manuals
    give no HA5C value for Parameter 18 or 44. All three say Parameter 18 is "usually 2X"
    Parameter 19, which means full speed in about 0.5 s [INFERENCE]. That is the basis for a stand-in.
  - **Research first.** Look for the HA5C's values of Parameters 18 and 44 beyond the 2006 and 2012
    manuals, which give none (`docs/research/2026-10-19-open-questions-research.md`, section 3).
  - **Acceleration.** [INFERENCE] The manuals describe the mechanism, so it can be modelled:
    moves speed up and slow down instead of starting at full feed. With a cited value, use it.
    Without one, use a stand-in, labelled and logged, and bring the missing value back to the
    stakeholders.
  - **Mill signals.** The interpreter already logs the manual's signal codes (G86, G87, G89, G92,
    G93) as events with no motion (decision 0016). Show them in Isaac Sim, and try one step per
    simulated Cycle Start (decision 0016, option 2b).
  - Decision record 0026, which amends 0016. Isaac Sim check of a program with acceleration.
- [ ] Worklog; PR

## Phase 7 - The agent builds it, and the phase report
- [ ] A fresh Claude Code session builds the T33901 from a dashboard job with several photos,
      through the tools and the updated procedure. A summary of its transcript goes in the
      worklog, and the quote checker checks every quote.
- [ ] A second request reuses the stored twin; the HA5C still builds and is reused
- [ ] The phase report, like `docs/poc-report.md`: results per level, the decisions, the table of
      known inaccuracies and stand-ins, and open questions
- [ ] README status; CLAUDE.md's "Current phase" points to the next step; PR

## Decision records this plan needs
They are numbered in the order the plan reaches them. The PoC report's section 8 lists the
drill press's seven decisions, and its items 2 and 3 share one record here, because the same box
test settles both.

| No. | Title | Phase | From |
|---|---|---|---|
| 0017 | Sliding joints, other axes and a chain of joints in the exporter | 1 | Report section 8, items 2 and 3 |
| 0018 | Springs, stops and locks | 1 | Item 5 |
| 0019 | Coupled motion: the downfeed handles follow the quill | 1 | Item 4 |
| 0020 | Contract v0.2.0: linked joints and joint modes | 2 | This plan |
| 0021 | How Pipelines A, C and D run outside their tests | 2 | This plan |
| 0022 | Several photos per run | 3 | Daniel's direction, Oct 22, 2026 |
| 0023 | Several moving parts from one mesh | 4 | Item 1 |
| 0024 | The drill press's facts and scale | 5 | Item 7 |
| 0025 | Control logic for a manual machine | 6 | Item 6 |
| 0026 | The HA5C controller's acceleration and mill signals (amends 0016) | 6 | Advisors, Oct 22, 2026 |
| 0027 | Joints and stand-ins in the geometry spec | 5 | This plan |
| 0028 | MCP tools for a several-part spec | 5 | This plan |

## Not in this plan
- Pipelines A, C and D themselves: they are their owners'.
- Neo4j and Celery, several users, Codex, video and scenes (report, sections 7.4 and 8).
- The lab's photos, which come later (advisors, Oct 22, 2026).

## Installed on Daniel's approval (Oct 22, 2026)
He approved a PDF renderer and the multi-view generator, and left the choice of each to Claude
Code.
- **pypdfium2 5.14.0,** a backend dev dependency, renders PDF pages and figures. It is permissive
  ("BSD-3-Clause, Apache-2.0") and pinned in `uv.lock`. Why not PyMuPDF (AGPL) or poppler (a system
  tool): research note.
- **The multi-view model, `hunyuan3d-dit-v2-mv`** (4.93 GB, SHA-256 checked). One run through our
  adapter on the repository's example images worked: 58.5 s, 6.09 GB of VRAM.
- **Its image order is settled:** `left` shows the machine's own left side, and three views are
  enough (`docs/setup/generators.md`, "Which side each image shows"). Corner views, like the
  manual's, are untried.

## Still open
- **The handle ratio.** It can be settled only by:
  - a measurement on a real T33901: the handles' angle over the full 3-1/4 in stroke;
  - Grizzly's technical support (contacting them is Daniel's call);
  - photos or a video of a full stroke (research note).

  Until then, a labelled stand-in.
- **The back of the T33901.** No photo of it exists in any source found, and there is no T33901
  to photograph (Daniel, 2026-10-26). The generator's guess stays, logged as such, until the lab's
  photos come or a source turns up.
- **The parts' masses.** The manual gives only the total, 108 lb; authoring per-part estimates
  needs a contract change, discussed with the pipeline owners first. Left until the stakeholders
  ask or Phase 6 needs forces (Daniel, 2026-10-28; decision 0024, update). Meanwhile the spring
  return bounces before resting.
- **The depth stop nut's place in a check file.** From v7 the nut and the stop agree at 43 mm,
  where the photos show them (decision 0025). In `checks/adjustable_stop.usdc` the stop still moves
  and the nut stays put (decision 0027, "Update: v5").
