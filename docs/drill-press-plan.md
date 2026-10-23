# Drill-press plan (integration phase)

**Goal:** a functional twin of a harder machine, meeting the advisors' four goals
(`docs/poc-report.md`, section 8):
- several moving parts cut from one model;
- sliding joints and a chain of joints;
- motions that move together: the downfeed handles turn as the quill slides;
- a way to describe a manual machine's control.

**Machine:** Grizzly T33901 14" benchtop drill press, approved by the advisors on Oct 22, 2026
(worklog 2026-10-22). **Written:** Oct 22, 2026, for Daniel's review.

**Status: proposed.** Nothing in it is built yet. Stop at the end of each phase, open a pull
request, and wait for review before starting the next. The HA5C stays the reference twin: every
phase keeps it building, and its tests passing.

## What the manual gives
Source: the Grizzly T33901/T33902 manual,
`data/machines/grizzly-t33901/inputs/documents/grizzly-t33901-t33902-manual-2023.pdf`, from
https://cdn0.grizzly.com/manuals/t33901_m.pdf ("REVISED DECEMBER, 2023"). Page numbers are the
PDF's. Pages 8-9 are the T33901's data sheet. Pages 10-11 are the floor model T33902's, which
differs (for example "15 x 25-1/2 x 61-1/2 in."). The text was read with pypdf on 2026-10-19
(`docs/research/2026-10-19-open-questions-research.md`, section 6), and again on 2026-10-22 for
this plan. Every quote is checked again when the reference facts are written (Phase 4).

| Motion | What moves | Range | Driven, held or returned by | Pages |
|---|---|---|---|---|
| Quill slides | quill, spindle, chuck | "Spindle Travel ... 3-1/4 in." | the downfeed handles; "Spindle Return Spring: Automatically returns quill into headstock"; "Depth Stop: Stops spindle travel at predetermined drilling depth" | 7, 8 |
| Spindle turns | spindle, chuck | "12 Speed Settings: 340, 500, 530, 660, 740, 790, 1380, 1420, 1680, 1860, 2200, 2860 RPM" | "the configuration of V-belts and pulleys" | 9, 30 |
| Downfeed handles turn | the hub and its three handles | not given | the quill's rack and pinion ("Lubricate column rack and quill rack and pinion") | 7, 18, 35 |
| Table up and down | table bracket | "Vertical Table Travel ... 14-3/8 in." ("Floor-To-Table Height ... 9-5/8 - 24 in.") | the table height crank; the "Table Height Lock Handle" | 7, 9, 32 |
| Table around the column | table bracket and column rack | "Table Swivel Around Column ... 360 deg." | the "table lock handle" | 9, 32 |
| Table tilts | table | "Max. Table Tilt (Left/Right) ... 0 - 45 deg." | the tilt lock hex bolt | 9, 32 |
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
- **Not in the manual's text:**
  - the handle-to-quill ratio: the parts list names a "PINION SHAFT" (p. 50), but no tooth count
    or pitch;
  - the head's size and the downfeed handles' length;
  - the return spring's force: a "FLAT COIL SPRING" (p. 49), whose tension can be adjusted (p. 40);
  - which belt arrangement gives which speed: p. 30 says to move the V-belts onto the desired
    sheaves. Whether a figure gives the arrangement for each speed is to be checked by eye.
- **[INFERENCE], to check against the manual's figures:**
  - The "table lock handle" of "Rotating Table Around Column" (p. 32) is the table height lock
    handle, which "Loosens to allow adjustment of table position on column" (p. 7).
  - The column rack turns with the table bracket. Assembly seats the rack "firmly between collar
    and column base" (p. 22), and turning the table means "making sure to guide column rack with
    table" (p. 32). So the rack is a real part between the turn around the column and the slide up
    it.
  - Which comes first on the table, the tilt or the turn about its centre, is not stated.
  - "Spindle to Column" is measured to the column's surface, since the swing is 14 in.

## Success levels
1. **A scaled model of the T33901, cut into its moving parts, with cited facts, opens in Isaac
   Sim.** Its sizes are compared with every cited dimension, and each difference is logged.
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
- [x] This plan, worklog, PR (Oct 22, 2026: branch `docs/drill-press-plan`); stop for review

## Phase 1 - A box-and-cylinder drill press proves the exporter
No generated mesh. As in the PoC's Phase 2, the test model goes down the exporter's real path.
Its sizes are the manual's where it gives them, and made up, labelled as such, where it does not
(the head, the handles, the rack, the bracket, the tilt piece). The new behaviours are exporter
settings, as `DriveSettings` is today, not contract fields. The contract changes in Phase 2, with
this phase's evidence.
- [ ] Research note, from primary sources, before any code:
  - UsdPhysics prismatic joints, linear drives and their limits;
  - whether two motions between the same two visible parts need a part between them: the rack
    between the column and the bracket, and a tilt piece between the bracket and the table;
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
- [ ] Exporter (`usd/exporter.py`):
  - prismatic joints, with linear drives and limits in metres; today they are refused;
  - a drive per joint (spin, hold, spring return, locked, free) instead of one drive for every
    joint;
  - a chain of seven joints. `_root_part` already accepts a tree, but only one joint has been
    checked in Isaac Sim;
  - coupled joints: the mimic joint if the research shows it works in Isaac Sim 6.2, otherwise
    the fallback chosen in decision 0019;
  - unchanged output for what exists: built at a fixed time, the Phase 2 test twin comes out
    identical, and the HA5C's tests pass.
- [ ] Primitive parts made of several shapes, such as the hub with its three handles
      (`usd/geometry.py`). No contract change: `Part.primitive` is free-form.
- [ ] `moonwalkers.usd.primitive_drill_press <run>`: eight parts on seven joints. The parts are
      the frame (base, column and head), the quill, the spindle with its chuck, the handle hub, the
      column rack, the table bracket, a tilt piece and the table. It writes one check file per
      behaviour, validates each, and writes `RUN.md`:
  - `spindle_spin`: at 340 RPM, the lowest cited speed, and at a slow speed for the eye. At 60
    frames a second, 340 RPM turns 34° a frame, close to an 8-sided cylinder's 45° symmetry, so
    it may look slow or reversed [INFERENCE];
  - `quill_stroke`: the quill is fed down, then released, and the spring returns it;
  - `depth_stop`: a feed past the stop ends at the stop;
  - `handles_follow`: the handles turn as the quill slides, at a made-up ratio (not cited);
  - `table_free` and `table_locked`: each table motion moves within its cited range when free, and
    holds under gravity and a push when locked;
  - `all_motions`: everything in one file.
- [ ] Validation: `moonwalkers.usd.validate` learns prismatic joints, chains, drives per joint and
      coupled joints. `omni_asset_validate` runs as well, and any finding about schemas that
      usd-core does not know is recorded.
- [ ] Proposed: a joint recorder for Isaac Sim checks. A Script Editor snippet writes every
      joint's position over time to a file, so the spring return, the stop and the coupling are
      measured rather than only seen. It also answers the PoC report's item 11: how closely the
      HA5C spindle follows a program, with and without the runner.
- [ ] Isaac Sim 6.2.0 check by Daniel, from a checklist per file (a new section in
      `docs/setup/isaac-sim-check.md`)
- [ ] Decision records 0017, 0018 and 0019; worklog; PR

## Phase 2 - Contract v0.2.0, and how the teammates' pipelines run
- [ ] Decision record 0020: contract v0.2.0, only for what v0.1.0 cannot describe. Field names
      are chosen in the record.
  - **Linked joints:** a follower joint moves with a leader at a cited ratio, as the handles
    follow the quill.
  - **Joint modes:** driven, spring return to a rest position, locked at a setting, or free; and
    an adjustable stop inside a joint's limits (the depth stop).
  - **Unchanged:** v0.1.0 already has prismatic joints, limits in metres, a parent and a child on
    every joint, and `state_machine` and `lookup_table` behaviours (worklog 2026-10-22).
  - **Stored results:** the HA5C's v1-v3 and the TH240's v1 results say `schema_version` "0.1.0",
    the only value the contract accepts today. The record decides how they keep loading and
    building.
  - Discussed with Ava, Kiran and Sarkis before it is merged (CLAUDE.md, "Who owns what").
- [ ] Build it:
  - the contract, its JSON Schema (`moonwalkers.contracts.json_schema`) and the dashboard's types
    (`moonwalkers.api.typescript`);
  - the exporter reading the new fields; the dashboard showing modes and links;
  - the box-and-cylinder drill press rewritten to use them; at a fixed time, its stages match
    Phase 1's.
- [ ] Decision record 0021: how Pipelines A, C and D run outside their tests. It answers:
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
- [ ] Build our side of what the record chooses, tested with a fake pipeline rather than the stubs
- [ ] A short guide for the pipeline owners: the contract, `create_pipeline()`, citations, tests,
      and how to try a pipeline on the T33901's manual (worklog 2026-10-22, "Next step")
- [ ] Worklog; PR

## Phase 3 - Photos, and a spike on cutting a model into parts
- [ ] Collect T33901 photos from public sources into `inputs/`, logging each URL in `SOURCES.md`.
      The Grizzly product page has not been tried (worklog 2026-10-22).
- [ ] If there are photos from several sides, first check the multi-view model's image order with
      the repository's example images (CLAUDE.md; `docs/setup/generators.md`, "Adding the
      multi-view model later"). Then choose single- or multi-view for this machine.
- [ ] Generate a mesh (Hunyuan3D-2, decision 0011)
- [ ] **Spike, time-boxed to one session:** compare ways to cut one mesh into several parts.
  - **Test meshes:**
    - the box-and-cylinder drill press as one mesh, so the right part is known for every face. It
      is the easy case [INFERENCE: a generated mesh fuses its parts into one surface; this one
      does not];
    - the generated T33901 mesh, judged against the manual's figures.
  - **Methods:**
    - (a) several cuts in the geometry spec: an ordered list of shapes (cylinder, box, plane) per
      part, where the first match wins. It extends decision 0012 and needs no install;
    - (b) splitting by the mesh's own shape (sharp edges, thin necks, separate pieces). It needs
      no install [INFERENCE: likely weak where the generator fused parts];
    - (c) a learned part-segmentation or articulation model. Project-context Topic 13 names
      Articulate-Anything and URDF-Anything as aimed at articulation, and untested on industrial
      machines; newer candidates come from the spike's research. Any install is asked first,
      with its license and size, and runs in its own environment like the generators;
    - (d) marking the parts on the photo and carrying the marks onto the mesh [INFERENCE: not
      researched].
  - **Measures:**
    - the share of faces put in the right part (synthetic mesh);
    - open edges and seams;
    - time taken;
    - installs and licenses;
    - whether the result can be cited and reviewed.
- [ ] Research note; decision record 0022; worklog; PR

## Phase 4 - Pipeline B builds several parts and joints (levels 1 and 2)
- [ ] Reference facts for the T33901, like `pipelines/b/haas_ha5c.reference.json`, with every
      quote checked against its PDF page
- [ ] Proposed: a quote checker. It confirms every quote in a reference file is on its cited page,
      using the PDF's text, and runs on the HA5C's file and the T33901's.
- [ ] Decision record 0023: facts and scale. Which cited dimension sets the scale (candidates: the
      7 in from spindle to column, the 39 in height, the 23-3/8 in from spindle to base). Then
      how the cited 108 lb is split between the parts, or whether the placeholder density stays
      (decision 0010).
- [ ] The machine key: "Grizzly Industrial, Inc." normalises to `grizzly-industrial/t33901`
      (`kb/keys.py`), but the data folder is `grizzly-t33901`. Add a `grizzly` alias, with the
      source of the short name (decision 0009).
- [ ] A geometry spec for several parts (decision 0022): each part with its cuts, and joints of any
      type and axis, with limits, modes and links. The HA5C's existing specs still build.
- [ ] MCP tools: `add_joint` and `inspect_geometry` stop assuming one spindle about +X, and new
      tools are added if needed. Old runs still work. `docs/agent-procedure.md` is updated.
- [ ] Size checks against every cited dimension: width, depth, height, spindle to column, spindle
      to table, spindle to base
- [ ] Build `grizzly/t33901@v1`. Isaac Sim check of levels 1 and 2. Log every inaccuracy as an
      issue in the twin, in `RUN.md`, and in the phase report's table.
- [ ] Worklog with run details (versions, time); PR

## Phase 5 - Control logic for a manual machine (level 3)
- [ ] Decision record 0024: how `ControlBehavior` describes a manual machine:
  - the keyed switch as a `state_machine`: key in or out, switch up or down, and the motor runs
    only with the key in and the switch up (p. 6);
  - the spindle speed as a `lookup_table` of the twelve cited speeds (p. 9), with the belt
    arrangement for each if a figure gives it;
  - the operator's drilling stroke as a program that drives the quill, as decision 0016's
    programs drive a joint.

  `spec` is free-form for each kind, so none of this should need a contract change. If it does,
  that is its own record and version bump.
- [ ] An interpreter or runner for these behaviours, tested outside Isaac Sim. A build writes their
      program folder with the twin (decision 0016).
- [ ] Isaac Sim check: level 3
- [ ] Worklog; PR

## Phase 6 - The agent builds it, and the phase report
- [ ] A fresh Claude Code session builds the T33901 from a dashboard job through the tools,
      following the updated procedure. A summary of its transcript goes in the worklog, and every
      quote is checked.
- [ ] A second request reuses the stored twin; the HA5C still builds and is reused
- [ ] The phase report, like `docs/poc-report.md`: results per level, the decisions, the table of
      known inaccuracies, and open questions
- [ ] README status; CLAUDE.md's "Current phase" points to the next step; PR

## Decision records this plan needs
They are numbered in the order the plan reaches them. The PoC report's section 8 lists the
drill press's seven decisions, and its items 2 and 3 share one record here, because the same box
test settles both.

| No. | Title | Phase | Report, section 8 |
|---|---|---|---|
| 0017 | Sliding joints, other axes and a chain of joints in the exporter | 1 | 2 and 3 |
| 0018 | Springs, stops and locks | 1 | 5 |
| 0019 | Coupled motion: the downfeed handles follow the quill | 1 | 4 |
| 0020 | Contract v0.2.0: linked joints and joint modes | 2 | - |
| 0021 | How Pipelines A, C and D run outside their tests | 2 | - |
| 0022 | Several moving parts from one mesh | 3 | 1 |
| 0023 | The drill press's facts and scale | 4 | 7 |
| 0024 | Control logic for a manual machine | 5 | 6 |

## Alongside the drill press (advisors, Oct 22, 2026)
- **The HA5C controller's acceleration and its signals to a mill:** model them if possible; if
  not, record why and bring it back to the stakeholders (CLAUDE.md).
  - The manuals give no HA5C values for acceleration (Parameters 18 and 44;
    `docs/research/2026-10-19-open-questions-research.md`, section 3).
  - [INFERENCE] So acceleration cannot be modelled from the sources as they stand. The mill
    signals (G86-G93, the remote Cycle Start) might be modelled as events.
  - Proposed: a short research item in Phase 5, which works in `moonwalkers.control` anyway.
- **How closely the HA5C spindle follows a program** (report, item 11): measured with Phase 1's
  joint recorder, if Daniel keeps it.

## Not in this plan
- Pipelines A, C and D themselves: they are their owners'.
- Neo4j and Celery, several users, Codex, video and scenes (report, sections 7.4 and 8).
- The lab's photos, which come later (advisors, Oct 22, 2026).

## Open questions for Daniel
1. **Contract after the box test.** Contract v0.2.0 is proposed for Phase 2, after Isaac Sim shows
   what works. Until then the teammates build on v0.1.0, which already describes everything but
   linked joints and joint modes. Should the contract come first instead?
2. **The handle ratio.** The manual does not give it. Use a stand-in ratio, logged as an
   inaccuracy, until a source or a measurement gives it?
3. **Hidden middle parts.** A photo may not show the column rack or what joins the table to its
   bracket. Should small stand-in parts there be logged as inaccuracies?
4. **Two proposals:** the joint recorder (Phase 1) and the quote checker (Phase 4). Keep or drop?
5. **The HA5C acceleration item:** in this plan's Phase 5, or a plan of its own?
