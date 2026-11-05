# MoonWalkers drill-press plan: report (the Grizzly T33901)

**Status: final for the drill-press plan, 2026-11-04,** reviewed and approved by Daniel
(PR #23), at the end of the plan's Phase 7
([docs/drill-press-plan.md](drill-press-plan.md)). Written by Claude Code with Daniel Sweet. As in
the [PoC report](poc-report.md), each claim names its evidence: a decision record, a worklog, a
run's `RUN.md` or a program's `PROGRAM.md` (run folders are under `data/`, which is not in the
repository). Reasoning that no source states is labelled [INFERENCE].

**The answer, in short.** Yes, for a manual machine of several moving parts. The T33901 twin meets
all three of the plan's success levels in Isaac Sim 6.2. A fresh Claude Code session built it, and
its controls, from a dashboard job through the platform's tools.
- **Several parts from one generated mesh** (level 1): 19 parts on 18 joints, cut from one
  Hunyuan3D-2mv mesh made from two corner photos. 13 of the parts are labelled stand-ins where the
  mesh hides or gets wrong a part that shows. Every cited size the mesh shows is within 6%.
- **Sliding joints, a chain of joints, and motions that move together** (level 2): the quill
  slides, its spring returns it, the depth stop ends its travel, and the downfeed handles turn with
  it. The table slides, turns and tilts on a chain of four joints, and each motion holds when
  locked.
- **A manual machine's control** (level 3): the keyed switch, the twelve speeds and an operator's
  drilling stroke. In Isaac Sim the stroke stays within 0.63 mm of the plan, and the quill returns
  in 0.28 s.
- **The agent's build** (`grizzly/t33901@v9`): it read the manual itself, stated 26 facts and the
  three control behaviours, and wrote the 17-part spec piece by piece. 140 of its 141 quotes are on
  their cited pages, and both validators are clean. Daniel's look in Isaac Sim found three stand-in
  faults, fixed in v10 and v11 by Claude Code in another session.
- **Reuse:** a second request for the T33901 reuses v11, which Daniel approved. The
  HA5C still builds and is reused (v3, approved).
- **The main limits** (section 6): the back of the machine is guessed, the masses are
  placeholders, the handle ratio and several timings are stand-ins, and the HA5C's new control
  model has not been checked in Isaac Sim.

## 1. The question
The advisors approved the T33901 as the next machine on 2026-10-22, with four goals (PoC report,
section 8):
- several moving parts cut from one model;
- sliding (prismatic) joints and a chain of joints;
- motions that move together: the downfeed handles turn as the quill slides;
- a way to describe a manual machine's control.

Daniel's direction (2026-10-22): "allow multiple image input and allow for the least amount of
guessing. While working on that goal stand ins may be used." Refined on 2026-10-24: a labelled
stand-in where a detail is visible or needed, left out where it is hidden and unused.

The success levels ([docs/drill-press-plan.md](drill-press-plan.md), "Success levels"):
1. A scaled model of the T33901, cut into its moving parts, with cited facts, opens in Isaac Sim.
   Its sizes are compared with every cited dimension.
2. The joints move as the manual describes: the quill slides 3-1/4 in, the spring returns it, and
   the depth stop ends its travel; the spindle turns, and the handles turn with the quill; the
   table slides, turns around the column, tilts and turns about its centre, and each holds when
   locked.
3. The manual's control drives it: the keyed switch (no key, no start), a speed from the twelve
   cited settings, and an operator's drilling stroke to the depth stop and back.

Also: a box-and-cylinder drill press passes level 2 first; a second request reuses the stored
twin; the HA5C still builds and is reused. And from the advisors: model the HA5C controller's
acceleration and mill signals if possible, or record why not.

## 2. What was built
| Phase | What | Decisions | PR |
|---|---|---|---|
| 0 | The plan; a PDF renderer (pypdfium2) and the multi-view generator installed on Daniel's approval | - | #15 |
| 1 | A box-and-cylinder drill press proves the exporter: sliding joints, a chain, locks, the spring, the depth stop, the handles coupled to the quill; the joint recorder | 0017-0019 | #16 |
| - | Every twin stays awake in PhysX | 0017 | #17 |
| 2 | Contract v0.2.0: a joint's `mode`, `adjustable_stop` and `follows`; how Pipelines A, C and D run outside their tests | 0020, 0021 | #18 |
| 3 | Several photos per run, each with its view in the operator's words; the multi-view model, corner photos as a turned grid; several photos in the dashboard's upload | 0022 | #19 |
| 4 | A spike comparing four ways to cut a mesh into parts | 0023 | #20 |
| 5 | Pipeline B builds several parts and joints: the cut list, stand-ins, patches; the drill press's facts and scale; the quote checker; eight new MCP tools (24 in all). `grizzly/t33901@v1` to `v6` | 0024, 0027, 0028 | #21 |
| 6 | Control logic: a manual machine's switch, speeds and operator's commands; the HA5C's acceleration and mill signals. `v7` and `v8`; the stakeholder pages ([how a twin is built](how-a-twin-is-built.md), [the tool guide](tool-guide.md)) | 0025, 0026 | #22 |
| 7 | A fresh agent builds `v9` from a dashboard job; `v10` and `v11` from Daniel's checks; the reuse checks; this report | - | #23 |

At the end of Phase 6 the backend's quick suite had 696 tests passing, the slow suite 5, and the
dashboard 15 (plan, Phase 7 hand-off). Phase 7 changed no code.

## 3. Results
### Level 1: a scaled, cited model of parts opens in Isaac Sim: met
- **The mesh:** one Hunyuan3D-2mv mesh (40,000 faces) from the two Home Depot front corner photos,
  fed as a grid turned 45° (decision 0022). Its front came out turned +49.1°, measured from the
  base's footprint, and the spec turns it back.
- **The scale:** the cited overall height, 39 in (p. 8), over 1.9950 model units: 0.496536 m per
  unit (decision 0024).
- **First opened:** `v1` on 2026-10-27 (Daniel; decision 0027, "Isaac Sim check of v1").
- **The size checks of `v11`** (its `RUN.md`), every cited length the mesh shows:

  | Check | Model | Cited (manual) | Difference |
  |---|---|---|---|
  | Overall height | 0.9906 m | 39 in (p. 8) | 0 (sets the scale) |
  | Overall width | 0.3592 m | 15 in (p. 8) | -5.7% |
  | Overall depth | 0.6096 m | 25-1/2 in (p. 8) | -5.9% |
  | Column diameter | 0.0787 m | 3-1/8 in (p. 9) | -0.9% |
  | Spindle to column | 0.1676 m | 7 in (p. 8) | -5.7% |
  | Base length | 0.4836 m | 18 in (p. 9) | +5.8% |
  | Base width | 0.2766 m | 10-1/2 in (p. 9) | +3.7% |

### Level 2: the joints move as the manual describes: met
- **The box-and-cylinder drill press first** (Phase 1, run `moonwalkers-testdrillpress/runs/2026-10-23_run-002`):
  the handles tracked the quill within 1%, and the spring returned it in 0.83 s (decisions
  0017-0019). Three fixes came from that check: keeping the articulation awake, the rack and
  pinion's sign, and the free table's height.
- **The T33901** (decisions 0024 and 0027, their updates):
  - `v1` (2026-10-27): the quill sagged about 20 mm. The cause was the generated handle hub, whose
    weight sat 0.047 m off its axis and pushed the quill down through the link;
  - `v3` (2026-10-28): a balanced stand-in hub, and the quill rests at 0.000 mm;
  - `v4` (2026-10-28, with recordings): the depth stop stops the quill where its check file sets
    it, the spring returns it, and the table's locks hold;
  - `v5` (2026-10-28): loosened, the table drops to its bottom stop and moves through all of its
    cited travel. Level 2.
- **The joints of `v11`:** the quill (0 to 3-1/4 in, p. 8), the spindle (driven, up to 2860 RPM),
  the downfeed handles (following the quill), and the table's chain: around the column, up the
  column (9-5/8 to 24 in floor to table, p. 9), the tilt (±45°) and the turn about its centre.
  The four table motions are locked by equal limits; `checks/unlocked.usdc` loosens them all.
  Daniel's look at `v11` (2026-11-04): the table "still drops with everything riding along".
- **All the motions at once** (`checks/all_motions.usdc` of `v8`, 2026-11-02, with a recording):
  the quill came home from 23 mm with no bounce and the handles followed at 57.09 rad/m; the
  spindle turned at 30.0 deg/s; the four table joints held their settings exactly. Daniel:
  "All looks good" (worklog 2026-11-02).

### Level 3: the manual's control drives it: met
Decision 0025 gives the T33901 three control behaviours, each rule citing its page. A
`state_machine` is the keyed switch, a `lookup_table` the twelve speeds, and a `command_set` the
operator's commands, with scenarios. A build writes `programs/operator-controls/`: `controls.usdc`
with live controls in Isaac Sim's Property panel, a runner, and a plan per scenario.

| Check | Seen | Evidence |
|---|---|---|
| The keyed switch: no key, no start | The motor runs only plugged in, with the key in and the paddle up | `v7` (2026-10-31), decision 0025 |
| The twelve speeds | 790, 1420 and 2860 RPM held exactly. Three changes while plugged in were refused, quoting p. 30 | `v7`, second session |
| The drilling stroke on `v8` | The stop at 12.12 s (planned 12.13 s), resting at 43.01 mm; within 0.62 mm of the plan; home 0.28 s after the release, no bounce | `v8` (2026-11-02), decision 0025, "Re-check of v8" |
| The drilling stroke on the agent's `v9` | The stop at 12.12 s, 43.01 mm; within 0.63 mm; home 0.28 s, no bounce; 790.0 RPM | `v9` (2026-11-04), its `RUN.md` |
| The spring alone (`checks/spring_return.usdc`) | Home at 0.25 s from 43 mm, no bounce, at rest -0.009 mm (`v8`, `v9`) | the same |

- **One fix along the way.** In `v7` the quill swung about the hand (±12 mm, every 2.8 s). The
  stand-in hub's placeholder inertia, seen through the link, outweighed the quill's 125 times. The
  spring is now simulated on the handles' pinion, where the T33901 has it ("the spring housing is
  located on the left side of the headstock", p. 40). The contract still says the quill has a
  spring return (decision 0025, update of 2026-10-31).
- **The HA5C's acceleration and mill signals** (decision 0026), as the advisors asked:
  - modelled: a constant-acceleration ramp at 540 deg/s², a stand-in from the manuals' "usually
    2X";
  - the CNC relay, from Parameter 1 and the codes G86, G87, G92, G93 and G94;
  - the waits for the remote input, G89, G92 and step mode, answered by a simulated mill after
    1 s, or by a person ticking "Cycle Start" in the Property panel.

  The manual's Example #3 now takes 15.92 s, where it took 11.67 s. New program folders:
  `data/machines/haas-ha5c/programs/2026-11-02_*`. **Not checked in Isaac Sim yet:** Daniel's
  direction is to check the HA5C later, if deemed necessary.

### The agent's build (Phase 7, item 1)
- **The job.** Daniel uploaded five photos in the dashboard on 2026-11-04 (two corners for the
  generator, three details as evidence), with "new version" ticked. One photo was tagged
  `back_operator_left` where it shows the front and the operator's left. The agent caught it
  against the manual and asked, and Daniel said "Fix the view in place". No tool changes a view,
  so `request.json` was edited by hand before anything was generated; the twin carries an issue
  that says so.
- **The session** (`docs/worklog/2026-11-04.md`; transcript `78abbe7e`): a fresh Claude Code
  session, about an hour, 308 tool calls.
  - **The prompt** (`data/scratch/2026-11-03_phase-7/agent-prompt.md`) allowed the procedure, the
    decisions and the reference file's `control` section. It held back the reference file's facts
    and the T33901's earlier specs until after `submit_twin`.
  - **What the transcript shows:** none of the held-back files was opened before then. Besides
    `control`, the agent's early read of the reference file also wrote its `issues` to a scratch
    file. Two of those issues hold facts, which decisions 0024 and 0027 give too.
  - **Its MCP calls:** 26 `add_fact`, 4 `add_control`, 7 `add_issue`, 36 `set_spec_part`, 16
    `set_spec_joint`, 5 `set_cut_list` and 11 `preview_twin`, plus one or more of each of the
    others.
- **What it built:** `grizzly/t33901@v9`, 17 parts on 16 joints, scaled by the same 39 in.
  - **The checks:** both validators clean on all eight files; 140 of 141 quotes on their cited
    pages (the one not checked is the photo's "Grizzly" badge).
  - **The mesh:** the same as Phase 4's, vertex for vertex, from the same photos and seed 12345.
  - **Its own two dry runs** caught a table stand-in with zero-area faces and four non-manifold
    points, before anything was stored.
- **Against the reference file and the v7 spec** (compared by the agent after submitting):
  - the same facts where both have them, though the reference file has 15 more keys;
  - the same controls, except a 3 s wait after the release (v8: 5 s), justified by v8's 0.28 s
    return;
  - the same parts, joints, axes, modes, depth stop, link and scale.

  Where they differ: v7's table rim, crank and pivot lock fit the photos better, and the agent's
  depth rod and handle lean fit them better.
- **Daniel's check of `v9`** (2026-11-04): the controls as v8 (level 3), with three faults in the
  geometry:
  - the crank was straight where the photos show it curved;
  - the table height lock handle was missing. It had been missing in every version, since the
    generator made only its clamp;
  - a sheet of the generated pivot lock stayed on the table arm.
- **`v10` and `v11`** were built by Claude Code in the Phase 7 chat, from scripts, not through the
  agent's tools (`data/machines/grizzly-t33901/part_cutting/2026-11-04_spec/`). Both were dry-run
  first and are clean in both validators.
  - **`v10`:** v7's curved crank, pivot lock and table sizes, and a new stand-in height lock
    handle, the parts list's "FOLDING HANDLE M12-1.75 X 50, 90L" (p. 50, part 105) [INFERENCE: the
    bracket's lock, from its place in the list];
  - **`v11`:** the arm's ragged top under the table cut out, with a stand-in for its end collar.
    Daniel: "v11 looks a lot better".

### Reuse
- **The T33901:** after v9 was built, the agent's `request_twin` reused v9. On 2026-11-04 it now
  answers "Found an existing twin (v11, needs review) for grizzly/t33901; reused it." A dashboard
  upload of one photo, with no new version asked, was reused at once (job
  `grizzly-t33901/runs/2026-11-04_run-003`).
- **The HA5C still builds:** its v3 run, rebuilt in a scratch copy of the data folder, gives the
  same meshes byte for byte, the same 9 facts and 9 issues, and both validators clean.
- **The HA5C is reused:** `request_twin` answers "Found an existing twin (v3, approved) for
  haas/ha5c; reused it.", and so did a dashboard upload (job `haas-ha5c/runs/2026-11-04_run-001`).

## 4. Per-run record
Generator: Hunyuan3D-2 2.0.2 with the multi-view model `hunyuan3d-dit-v2-mv`, seed 12345, on an
RTX 4090. Two runs generated a mesh (54.0 s and 58.0 s); the others reuse run-001's mesh or v9's
identical one. Isaac Sim Full 6.2 (Kit 110.4.0) for every check. Reviews are Daniel's, in the
dashboard (decision 0015).

| Twin | Run folder | Built by | What changed | Success level (Daniel's check) | Review |
|---|---|---|---|---|---|
| `v1` | `2026-10-24_run-001` | Claude Code (CLI), Phase 5 | the first cut into parts | 1 (2026-10-27): the quill sags | needs review |
| `v2` | `2026-10-27_run-001` | Claude Code (CLI) | balanced hub, patches | not checked: NVIDIA's validator warned | **rejected** (Daniel, 2026-10-28) |
| `v3` | `2026-10-27_run-002` | Claude Code (CLI) | the warning fixed | 2 for the quill (2026-10-28) | needs review |
| `v4` | `2026-10-28_run-001` | Claude Code (CLI) | the depth rod as a stand-in | 2 (2026-10-28, recordings) | needs review |
| `v5` | `2026-10-28_run-002` | Claude Code (CLI) | stand-in quill, column section, nut and bracket | 2 (2026-10-28) | needs review |
| `v6` | `2026-10-28_run-003` | Claude Code (CLI) | parts fixed to the frame drawn grey | not checked (colours only) | needs review |
| `v7` | `2026-10-30_run-001` | Claude Code (CLI), Phase 6 | the controls; the depth stop at 43 mm | the controls work; the quill swings (2026-10-31) | needs review |
| `v8` | `2026-10-31_run-001` | Claude Code (CLI) | the spring on the pinion | **3** (2026-11-02) | needs review |
| `v9` | `2026-11-04_run-001` | **a fresh Claude Code session through the MCP tools,** from a dashboard job | everything, written anew | 3 for the controls; three stand-in faults (2026-11-04) | needs review |
| `v10` | `2026-11-04_run-002` | Claude Code (scripts), from v9 and v7 | crank, height lock handle, pivot lock, table | crank and lever right; the arm's underside broken (2026-11-04) | needs review |
| `v11` | `2026-11-04_run-004` | Claude Code (scripts), from v10 | the arm's collar top | "looks a lot better" (2026-11-04) | **approved** (Daniel, 2026-11-04): "Approved according to personal review" |

`2026-11-04_run-003` is the dashboard's reuse job, not a build. A request reuses `v11`, the newest
approved version.

The metrics of Dr. Li's agentic-pipeline deck were again not measured formally. This plan's own
measures are the size checks, the quote checker, the joint recorder and `compare`, which measures a
recording against its plan.

## 5. The decisions behind it
Each record in [docs/decisions/](decisions/) has the options, sources and costs in full. Claude
Code proposed each one, and Daniel reviewed and accepted it.

| No. | Decision | Status |
|---|---|---|
| [0017](decisions/0017-sliding-joints-and-chains-in-the-exporter.md) | Sliding joints, other axes and chains of joints in the exporter; every twin stays awake | accepted, 2026-10-23 |
| [0018](decisions/0018-springs-stops-and-locks.md) | A spring as a position drive with a preload (stand-in values), the depth stop as a limit, locks as equal limits | accepted, 2026-10-23 |
| [0019](decisions/0019-coupled-motion-handles-follow-the-quill.md) | The handles follow the quill by a PhysX mimic joint, with the rack and pinion as a fallback; the ratio is a stand-in | accepted, 2026-10-23 |
| [0020](decisions/0020-contract-v0-2-0-linked-joints-and-joint-modes.md) | Contract v0.2.0: a joint's `mode`, `adjustable_stop` and `follows`. The contract says what the machine does; the exporter decides how to simulate it | accepted, 2026-10-24; **the pipeline owners' review is still open** |
| [0021](decisions/0021-how-pipelines-a-c-and-d-run.md) | How Pipelines A, C and D run outside their tests; one result per twin carries the geometry; disagreeing facts are listed | accepted, 2026-10-24; **the owners' review is still open** |
| [0022](decisions/0022-several-photos-per-run.md) | Several photos per run, each with its view in the operator's words and its use; corner photos as a turned grid | accepted, 2026-10-24 |
| [0023](decisions/0023-several-moving-parts-from-one-mesh.md) | Parts are cut from the mesh by an ordered, cited cut list; the photos are drawn over for review. Learned segmenters were researched, not installed | accepted, 2026-10-26 |
| [0024](decisions/0024-drill-press-facts-and-scale.md) | The scale is the cited overall height; every other cited length is a size check; masses stay placeholders | accepted, 2026-10-27 |
| [0025](decisions/0025-control-logic-for-a-manual-machine.md) | A manual machine's control as three behaviours (switch, speed table, operator's commands); one controller for Isaac Sim and the plans; the spring on the pinion | accepted, 2026-11-03 |
| [0026](decisions/0026-ha5c-acceleration-and-mill-signals.md) | The HA5C's acceleration (540 deg/s², a stand-in) and its signals to a mill | accepted, 2026-11-03; its stand-ins go back to the stakeholders |
| [0027](decisions/0027-joints-and-stand-ins-in-the-geometry-spec.md) | Joints, stand-ins and patches in the geometry spec; a stand-in is a part of its own, named and warned | accepted, 2026-10-27 |
| [0028](decisions/0028-mcp-tools-for-a-several-part-spec.md) | The agent sets a several-part spec piece by piece through eight new MCP tools | accepted, 2026-10-28 |

## 6. Limits, stated plainly
- **The back is guessed.** The only whole-machine photos are front corners: no side, the back,
  the top or the underside is seen square on (v11's photo issue). No photo of the back exists, and
  there is no T33901 to photograph (Daniel, 2026-10-26). The estimate is accepted for this stage
  (meeting of 2026-10-29).
- **The generator gets small and thin parts wrong.** Of v11's 19 parts, 13 are stand-ins, among
  them every handle, the chuck, the quill and the table. A stand-in matches the photos and the
  cited sizes, but none is the machine's real shape (decision 0027).
- **Cutting a machine takes judgement and several passes.** Phase 5 took six versions. The agent's
  first build needed three dry runs and missed three things a person saw in Isaac Sim.
- **Placeholder physics.** Masses come from each part's convex hull at 1000 kg/m³. The spring's
  numbers and the hand are simulation choices. The hand follows its path exactly, with no force or
  cutting load.
- **Timings from no source.** The motor's run-up and coast-down and the operator's pull and hold
  are stand-ins until Daniel times a stroke on a real benchtop drill press (decision 0025).
- **The HA5C's control model** rests on stand-ins (decision 0026) and has not been run in Isaac
  Sim.
- **People stay in the loop.** The agent asked about a mistagged photo. Daniel's checks in Isaac
  Sim found what neither validator nor the agent's previews did. Of the eleven versions, v11 is
  approved and v2 rejected; the others have no review.

### Known inaccuracies and stand-ins, in one place
For `grizzly/t33901@v11` unless the row says otherwise. Each part's stand-in carries a warning in
the twin, with what it is read from. This table gathers them, the plan's "Still open" and the
issues of earlier versions. The HA5C's rows from the PoC (PoC report, section 6) still stand.

| What | How far off, or what it rests on | Evidence |
|---|---|---|
| Overall sizes | Width -5.7%, depth -5.9%; other cited lengths -5.9% to +5.8% (section 3) | v11's `RUN.md`; decision 0024 |
| The back, top and underside | Guessed by the generator: not measurable. Accepted for this stage (2026-10-29) | v11's photo issue; decision 0022 |
| The chuck guard | Clear plastic on the machine, an opaque solid in the twin | v11's issues; decision 0023 |
| Seams and patched holes | 751 open seam edges; 13 holes closed flat (frame 6, bracket 3, arm 2, quill 1, guard 1), the surface under them unknown | v11's issues; decision 0027 |
| Stand-in chuck | A JT3 key chuck of cylinders and three jaws; sizes read from Fig. 46 against the cited 1.85 in quill | v11's issues |
| Stand-in quill | The cited 1.85 in, a plain cylinder; its length inside the head inferred | v11's issues |
| Stand-in depth rod, nut and bracket | Sizes from Fig. 35, the photos and the mesh; no thread. The nut is set at 43 mm, measured from the photos (41.5-43.6 mm; the agent read 41.6 and 44 mm) | v11's issues; decision 0025 |
| Stand-in hub and downfeed handles | The cited studs and knobs (p. 50); the hub's size, the angles and the 28° lean read from photos; plain knobs | v11's issues; worklog 2026-11-04 |
| The handle-to-quill ratio | A stand-in: 270° over the stroke, 57.09 rad/m. No source gives the pinion. It stays one on this test machine (2026-10-29) | plan, "Still open"; decision 0019 |
| The handles at rest | 0.022 rad (1.3°) past the quill's top | decision 0025; v9's `RUN.md` |
| The spring | Stiffness 600, damping 49 and a 0.03 rad preload are stand-ins. The return is overdamped: a 14-20 mm drop in the first 1/60 s, then home in 0.25-0.28 s | decisions 0018, 0025 |
| Masses | Placeholders: only the 108 lb total is cited. An option to carry mass on a client's request is wanted (2026-10-29), and needs a contract change | decision 0024, update |
| Stand-in table | The cited 11-1/4 in square, 1-1/16 in and four 9/16 in slots; rim, gutter and corners from `table_top.png`, taken at an angle; depths and post estimated | v11's issues |
| Stand-in table crank | From Fig. 36 and the photos; no size cited. **Fixed, so at the table's lowest setting it passes up to 4 cm into the base.** The real crank turns as the table moves [INFERENCE]. This is in v10's and v11's `RUN.md`, but not yet an issue in the twin | v10's `RUN.md`; worklog 2026-11-04 |
| Stand-in pivot lock and height lock handles | The parts list's folding handles (parts 122 and 105); the levers' lengths read from "70L" and "90L" [INFERENCE] | v11's issues |
| Stand-in end collar of the table arm | A plain cylinder of the mesh's collar size; its axis is the mesh's, 13 mm off the table's turning axis | v11's issues |
| Stand-in column rack and column section | The rack's width, depth and teeth read from photos; the section fills where the mesh has no column | v11's issues |
| A stale issue in v10 and v11 | Both carry the agent's note of "a thin flap ... on the arm's end collar's +y side", which v10's cuts removed (0 faces there in v11, 31 in v9) | worklog 2026-11-04 |
| The depth stop in `checks/adjustable_stop.usdc` | The stop moves to half way, but the stand-in nut stays where the twin's stop is | plan, "Still open" |
| Belt positions | Left out: the cover is closed. Only 790 RPM's "B-3" is cited | decision 0025 |
| Motor run-up and coast-down | 1 s and 5 s straight ramps, stand-ins | decision 0025 |
| The stroke's pull and hold | 30.3 mm at 0.03 m/s, and 1 s at depth, stand-ins; a 3 s wait after the release (v9 on; 5 s in v7 and v8) | decision 0025; v9's `PROGRAM.md` |
| The spindle's direction | Clockwise seen from above [INFERENCE]: the manual does not say | decision 0025 |
| Switch changes the manual does not describe | Refused in a scenario, applied with a note in live use | decision 0025 |
| The HA5C's acceleration | 540 deg/s², a stand-in (2 × 270 deg/s); Parameter 44 left out | decision 0026 |
| The HA5C's relay and mill | Parameter 1 inferred (1, or 2 with G86-G93); G93's ¼ s pulse inferred; the mill answers after 1 s, a stand-in | decision 0026 |

## 7. Open questions, by priority
### 7.1 For the advisors
**Answered at the meeting of 2026-10-29.** These are the questions of the integration report of
2026-10-28, with the advisors' answers as Daniel reported them on 2026-11-04. He said the meeting
went well and the feedback was positive.
- **Masses:** "If possible we should have the option to carry mass if the client requests it." So
  an optional mass per part is wanted, not a change for every twin. It needs a contract change
  (an optional mass on a `Part` with its citations, v0.3.0), discussed with the pipeline owners
  first. No source gives the T33901's parts' masses, so its values would be labelled estimates.
- **The handles' gearing:** "This was just a test machine, leave this as a stand in and we'll go
  more in depth like this with a machine we actually own." The stand-in stays.
- **Photos of the back:** "No one can supply this, the estimate looks acceptable for this stage."
  The generator's guess stays, logged.
- **The lab's photos** (Dr. Li): after this week's meeting Daniel is to meet someone to "hopefully
  get photos of two machines, a Haas CNC machine and a type of robotic arm. These are the machines
  Dr. Li has put as our next candidates for real world comparisons." No photos or videos are in
  hand yet. The exact models are not confirmed until he has talked with Dr. Li and his assistant.
- **How twins are built:** the stakeholders asked for the specifics, with each tool's input and
  output (Daniel, 2026-11-03). Done: [how a twin is built](how-a-twin-is-built.md) and
  [the tool guide](tool-guide.md).

**Still to ask, at this week's meeting:**
1. **The HA5C's real parameters.** Can the lab, or a contact at Haas, give Parameters 1, 18, 19 and
   44 from a real HA5C control? They would replace decision 0026's stand-ins. Daniel: "This would
   have to be a question to ask the stakeholders this week."
2. **What comes next, while the photos are awaited:** the option to carry mass, closing the gaps
   the agent found so that it needs fewer checks by a person (7.3), or preparing for the next
   machines?

### 7.2 For Daniel and the team
1. **Reviews in the dashboard.** v11 is approved, so requests reuse it. v1, v3 to v10 have no
   review; none is needed for that, since a review only records which versions stand (decision
   0015).
2. **The stroke timing** on any benchtop drill press, to replace the four timing stand-ins
   (decision 0025, "Daniel's timing replaces the stand-ins").
3. **The HA5C's Isaac Sim check** of decision 0026, if deemed necessary
   (`docs/setup/isaac-sim-check.md`, section 7).
4. **The pipeline owners' review** of decisions 0020 and 0021 (Ava, Kiran, Sarkis).
5. **The stakeholder pages' Mermaid diagrams** have not been looked at as GitHub draws them.

### 7.3 Found in the agent's build: gaps in the tools
None fixed in this phase (worklog 2026-11-04):
1. No tool changes a photo's view in a job, though an upload can carry a wrong one (this job's
   did).
2. Issues can only be added, not corrected: the agent fixed one of its own by hand. A stale issue
   (section 6) has the same cause.
3. `add_reference_source` takes files only from the data folder, so the agent cited a decision
   record by its GitHub URL.
4. `fit_circles` fits whole slices, so along x or y it measures the whole machine.
5. `preview_twin` does not report zero-area faces or non-manifold points. Only the build and
   NVIDIA's validator do, which cost the agent two dry runs, and v10 and v11 one each.
6. The dashboard's file picker takes photos from one folder per upload, and its duplicate check
   looks only in `inputs/photos/` itself, not in `photos/manual/`. So the agent's job had five
   photos, where v8 had 24.
7. No tool runs the build in a scratch data folder. The agent and Claude Code did it from the
   command line, as decision 0028 expected.

## 8. Next
The plan's four goals are met for the T33901, and the HA5C keeps building. The next machines for
real-world comparison are a Haas CNC machine and a robotic arm, Dr. Li's candidates, once their
photos come. What comes before that is for the advisors and Daniel to choose (7.1, item 2). The record for a new chat: this report,
[docs/drill-press-plan.md](drill-press-plan.md) and CLAUDE.md's "Current phase".
