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

**Status:** approved (PR #15). Phases 0 to 2 are done (PRs #15, #16, #18). Phase 3 is built and
waits for Daniel's review (PR #19); Phase 4 is next. Stop at the end of each phase, open a pull request, and wait for review before
starting the next. The HA5C stays the reference twin: every
phase keeps it building, and its tests passing.

**Direction (Daniel, Oct 22, 2026):** "The goal is to allow multiple image input and allow for the
least amount of guessing. While working on that goal stand ins may be used." Every stand-in (a
part, a ratio, a value) is labelled as such in the twin and logged as an inaccuracy.

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
- [ ] **Test meshes:**
  - the box-and-cylinder drill press as one mesh, so the right part is known for every face. It is
    the easy case [INFERENCE: a generated mesh fuses its parts into one surface; this one does
    not];
  - the generated T33901 mesh from Phase 3, judged against the manual's photos.
- [ ] **Methods:**
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
- [ ] **Measures:**
  - the share of faces put in the right part (synthetic mesh);
  - open edges and seams;
  - time taken;
  - installs and licenses;
  - whether the result can be cited and reviewed.
- [ ] Research note; decision record 0023; worklog; PR

## Phase 5 - Pipeline B builds several parts and joints (levels 1 and 2)
- [ ] Reference facts for the T33901, like `pipelines/b/haas_ha5c.reference.json`, with every
      quote checked against its PDF page
- [ ] A quote checker: it confirms every quote in a reference file is on its cited page, using
      the PDF's text, and runs on the HA5C's file and the T33901's. pypdf's text splits words at
      line breaks with a hyphen ("prede- termined", p. 7; "con - trolled", p. 30), so the checker
      must join them (worklog 2026-10-23)
- [ ] Decision record 0024: facts and scale. Which cited dimension sets the scale (candidates: the
      7 in from spindle to column, the 39 in height, the 23-3/8 in from spindle to base). With
      several photos, cited dimensions can also check one another. Then how the cited 108 lb is
      split between the parts, or whether the placeholder density stays (decision 0010).
- [ ] The machine key: "Grizzly Industrial, Inc." normalises to `grizzly-industrial/t33901`
      (`kb/keys.py`), but the data folder is `grizzly-t33901`. Add a `grizzly` alias, with the
      source of the short name (decision 0009).
- [ ] A geometry spec for several parts (decision 0023): each part with its cuts, and joints of any
      type and axis, with limits, modes and links. The HA5C's existing specs still build.
- [ ] MCP tools: `add_joint` and `inspect_geometry` stop assuming one spindle about +X, and new
      tools are added if needed. Old runs still work. `docs/agent-procedure.md` is updated.
- [ ] Size checks against every cited dimension: width, depth, height, spindle to column, spindle
      to table, spindle to base
- [ ] Build `grizzly/t33901@v1`. Isaac Sim check of levels 1 and 2. Log every inaccuracy and
      stand-in as an issue in the twin, in `RUN.md`, and in the phase report's table.
- [ ] Worklog with run details (versions, time); PR

## Phase 6 - Control logic (level 3), for the drill press and the HA5C
- [ ] Decision record 0025: how `ControlBehavior` describes a manual machine:
  - the keyed switch as a `state_machine`: key in or out, switch up or down, and the motor runs
    only with the key in and the switch up (p. 6);
  - the spindle speed as a `lookup_table` of the twelve cited speeds (p. 9). Only one belt
    arrangement is cited ("B-3 creates 790 RPM", p. 30). The rest are on the label under the belt
    cover, so they stay unknown until a photo of it is found;
  - the operator's drilling stroke as a program that drives the quill, as decision 0016's
    programs drive a joint.

  `spec` is free-form for each kind, so none of this should need a contract change. If it does,
  that is its own record and version bump.
- [ ] An interpreter or runner for these behaviours, tested outside Isaac Sim. A build writes their
      program folder with the twin (decision 0016).
- [ ] Isaac Sim check of level 3 for the drill press
- [ ] **The HA5C controller's acceleration and its signals to a mill** (advisors, Oct 22, 2026:
      model them if possible; if not, record why and bring it back to the stakeholders).
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
