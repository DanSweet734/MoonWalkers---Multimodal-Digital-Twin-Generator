# 0027 - Joints and stand-ins in the geometry spec

- **Status:** accepted (by Daniel, 2026-10-27: "Decisions 0024 and 0027 look good."). Proposed by
  Claude Code in the drill-press plan's Phase 5.
- **Date:** 2026-10-27
- **Decided by:** team (Daniel)
- **Amends:** decision 0012 (the geometry spec), with decision 0023 (its cut list)

## Context
Decision 0023 made the cuts an ordered list in the geometry spec. Phase 5 also needs the spec to
state joints of any type and axis, with limits, modes and links (contract v0.2.0, decision 0020),
and to put labelled stand-ins where the mesh hides or gets wrong a part that shows. Daniel's
answers of 2026-10-26 (decision 0023, end) name four: the chuck, the table, the crank and the
column rack; the table and the crank "match it to the photos". The plan leaves to this phase how a
stand-in takes a cut part's place.

What exists:
- The contract carries any number of parts and joints. A `Part` is a mesh file or a
  `geometry_format="primitive"` shape, and the exporter meshes each part by its own format.
- Primitives are boxes and cylinders, boxes square to the axes, with no holes. They cannot make
  the table's slots and hole, or the crank's turned arm.
- The backend has numpy and trimesh, but no boolean or image library (plan, Phase 5 hand-off).
  `synthetic_parts.surface_nets` meshes a signed distance with no install.
- The Phase 1 drill press (`usd/primitive_drill_press.py`) states the same seven motions in
  contract v0.2.0, in code.

## Options considered
1. **Where a joint's behaviour is written.**
   - (a) **In the spec, beside the joint's measured axis:** the contract's own `JointMode`,
     `AdjustableStop` and `JointLink`, whose citations name the reference file's sources (the
     manual). One place per joint. The quote checker reads the spec too.
   - (b) In the reference facts, with the spec holding only geometry, joined by joint id. "What
     the documents say" stays in one file, but a joint is split across two.
   - (c) In code per machine, as Phase 1. Not something the agent can write.
2. **How a stand-in's shape is written.**
   - (a) As a contract primitive. It is exported as it is, but it cannot cut holes or turn a box.
   - (b) **As a named shape in the spec, meshed by Pipeline B into a GLB like the cut parts:**
     `solids` (boxes and cylinders, each turned and repeated, enough for a rack's teeth, a chuck or
     a crank) and `slotted_table` (a signed distance: rim, gutter, plate, slots, hole and post).
     The contract and the exporter do not change.
   - (c) A general shape language (unions, cuts, transforms). More than four stand-ins need, and
     harder for the agent to write and a reviewer to read.
3. **How a stand-in sits in the twin.**
   - (a) **As a part of its own,** named "Stand-in: ..." and carrying a warning issue with its id.
     A stand-in that moves is a joint's child (the table, the chuck). One that rides on another
     part is held to it by a fixed joint (the rack on the collar, the crank on the bracket).
   - (b) Merged into the mesh of the part it belongs to. One body less, but nothing in the twin
     would say which faces are made up.
4. **The faces a stand-in replaces.**
   - (a) **A `removed` part in the cut list:** its faces are cut out of the twin and counted in an
     info issue.
   - (b) Left under the stand-in. Both would show where they differ, which is why the table and
     the crank get stand-ins at all.
5. **Units.**
   - (a) **A stand-in's sizes in metres,** since they are cited sizes and keep their value whatever
     the scale; **where it goes (`at`) in model units on the mesh,** scaled with it.
   - (b) Everything in metres in the twin frame. Then a placement measured on the mesh would have
     to be converted by hand, and would move if the scale changed.

## Decision
1a, 2b, 3a, 4a and 5a: Claude Code's proposals.

### The spec (`pipelines/b/parts_spec.py`, `PartsSpec`)
A spec with `parts` is this kind; any other is decision 0012's single spindle, which still builds
(the HA5C's and TH240's run folders are unchanged).

| Field | What it holds |
|---|---|
| `up`, `front`, `yaw_deg` | the generator's axes and the turn that squares the mesh (decisions 0012, 0022) |
| `origin_xy`, `base_z` | the twin's origin, in model units: on the base plane under this point (the spindle) |
| `scale` | a cited length's fact key, the same length measured in model units, and how (decision 0024) |
| `fixed_part` | the part that keeps every face no cut takes |
| `cuts` | decision 0023's ordered cut list |
| `parts` | each `cut`, `stand_in` or `removed`, with a `note` naming its evidence and an optional `inaccuracy` |
| `joints` | each with its type, parent, child, axis and a point on it (model units), limits (rad or m), an optional cited speed (`max_velocity_fact`), and the contract's mode, adjustable stop and link, all cited |
| `size_checks` | other cited lengths, each with its measurement and how it was taken |
| `decided_by`, `method` | who wrote it and how, as in decision 0012 |

A stand-in also has `shape` (`stand_ins.py`), `at`, `turn_deg` (about +Z), `replaces` (the removed
part) and `citations` (its cited sizes and the photos it is matched to); it must have citations.
A cut part may have `patches` (added on 2026-10-27, "Update: v2 and v3" below).

### What a build makes of it
- **Parts:** one GLB per twin part in `meshes/`. A cut part cites the fed photos and the spec. A
  stand-in cites the spec and its own citations, and has no generator.
- **Joints:** each cites the spec (`joints[<id>]`) and its own citations.
- **Issues:** a warning per stand-in (its note, and the faces it replaces) and per logged
  inaccuracy; an info per removed part and per cut part in more than one piece; the seams; the
  placeholder masses; the size checks.
- **Check files** (`build.check_files`): one per behaviour the joints state, as the Phase 1 drill
  press had: `spin` (driven joints at 30 deg/s), `spring_return` (each spring's joint starts at
  its far end), `adjustable_stop` (the stop set half way, fed past it), `unlocked` (every lock
  loosened), `locked_at_setting` (30 deg, or half way up a slide) and `all_motions`. A twin whose
  joints state no behaviour keeps the PoC's `spin` and `quarter_turn`.
- **Views** (`views/`, decision 0023): the cuts and the parts in colour, each part alone, and the
  parts, stand-ins included, over each fed photo. Also the joint recorder (`record_joints.py`).
- **Pieces must overlap, not meet end to end.** NVIDIA's asset validator warns about points on top
  of each other, and welding them leaves non-manifold points, another warning (found on
  `grizzly/t33901@v1`, below). So `shape_mesh` refuses pieces that share a point.

### Values used for the T33901 (`grizzly/t33901@v1`, run `2026-10-24_run-001`)
The spec is `geometry_spec.json` in the run folder. Measurements are on the squared mesh; sizes
read from photos are scaled by a cited size in the same photo.

| Part | Kind | From |
|---|---|---|
| `frame` | cut | everything else: base, column, head with the depth stop's fused ring, motor |
| `quill` | cut | the guard's collar and the depth stop's rod (decision 0023's quill, less the guard) |
| `chuck_guard` | cut, fixed to the quill | the guard (r 0.112 about the spindle, z 0.137-0.29), its own part so it can be hidden in Isaac Sim to see the chuck; the exporter has no transparency |
| `chuck` | stand-in, replaces `generated_chuck` | a JT3 key chuck from the generated tip (z 0.07, below the guard as in the photos) to the spindle nose at 25-1/2 in above the floor (15-7/8 + 9-5/8 in, cited). Nose 1.6, sleeve 2.3, body 1.95, top 2.15 in across, read from Fig. 48 against the cited 1.85 in quill; three jaws show it turning |
| `handle_hub` | cut | decision 0023's hub and handles |
| `column_collar` | cut | the "COLUMN COLLAR" (p. 50) |
| `column_rack` | stand-in, fixed to the collar | a toothed bar 3/4 by 0.3 in, teeth every 1/8 in (Figs. 37, 48, against the cited column), from the column base's flange (z -0.77) to the collar, at 82 deg from +X, where the mesh's column bulges (+60 to +105 deg) |
| `table_bracket` | cut | the bracket and the height lock handle |
| `table_crank` | stand-in, replaces `generated_crank`, fixed to the bracket | Fig. 36 and the colour photo: a 1.2 in hub on the bracket's boss (x -0.190, z -0.364), a flat arm 0.6 by 0.25 in leaving it backwards and curving down 5 in, a 3.5 in tapered grip pointing out (+Y). Posed as both photos show it |
| `table_arm` | cut | the arm and the pivot lock handle |
| `table` | stand-in, replaces `generated_table` | the cited 11-1/4 in square, 1-1/16 in thick, four 9/16 in T-slots; from `table_top.png`: rim 3/4 in, gutter 1/2 in, corners 1-1/2 in, diagonal slots from 1.6 in out, 1 in hole. Estimated, not visible: the gutter 3/8 and slots 1/2 in deep, a 1-1/2 in post into the arm. Centred under the spindle at the generated table's height (top z -0.230) |

| Joint | Type | Axis, through | Limits | Behaviour |
|---|---|---|---|---|
| `quill_travel` | prismatic, frame to quill | down the spindle's axis | 0 to 3-1/4 in (p. 8) | spring return to the top (p. 7); adjustable stop at the full stroke (pp. 7, 31) |
| `spindle_rotation` | revolute, quill to chuck | down the spindle's axis, at the nose | none | driven (p. 30); max 2860 RPM (p. 8) |
| `chuck_guard_mount` | fixed, quill to guard | | | |
| `downfeed_handles` | revolute, frame to hub | +Y through the handles' meeting point (x 0.229, z 0.497) | -0.05 to 4.76 rad | follows the quill, 270 deg over the stroke: a stand-in ratio (decision 0019) |
| `table_around_column` | revolute, frame to collar | the column's axis | none (360 deg, p. 9) | locked by the height lock handle (p. 7) |
| `column_rack_mount` | fixed, collar to rack | | | the rack sits "between collar and column base" (p. 22) |
| `table_height` | prismatic, rack to bracket | up the column | -0.138 to +0.227 m: the cited 9-5/8 to 24 in floor-to-table (p. 9) about the modelled 15.06 in | locked (pp. 7, 32) |
| `table_tilt` | revolute, bracket to arm | +X along the arm (y 0.005, z -0.371) | +/-45 deg (p. 9) | locked by the hex bolt (p. 32) |
| `table_around_center` | revolute, arm to table | +Z through the table's centre, under the spindle | none (360 deg, p. 9) | locked by the pivot lock handle (p. 7) |
| `table_crank_mount` | fixed, bracket to crank | | | the crank does not turn: the height joint moves the table |

## Consequences
- **A spec can describe a whole machine** in one cited, reviewable file. The T33901's is about 30 KB
  of JSON, written by a scratch script that turned inches into metres. The agent will write one
  through its tools (Phase 5's MCP item).
- **Stand-ins are visibly labelled:** by name, by a warning, and by their own prims in the USD.
  None of them is the machine's real shape. Each note says what it rests on.
- **Fixed joints inside the articulation are new** in our twins: three on the T33901. UsdPhysics
  and both validators accept them; Isaac Sim has not run them yet (Daniel's check).
- **The table stand-in is heavy:** 112,000 faces at its 2 mm grid, against 40,000 for the whole
  generated mesh. The grid can be coarser if Isaac Sim or a reviewer finds it slow.
- **Stand-in shapes are code.** A machine needing another kind (a vice, a wheel with spokes) gets a
  new kind in `stand_ins.py`, or `solids` where boxes and cylinders will do.
- **Reversing it:** the `parts` field and three modules; decision 0012's specs never used them.

## The first build: `grizzly/t33901@v1` (2026-10-27)
- Both validators find no errors in the twin or its six check files. Ours gives five infos: the
  mimic coupling, and the four locks.
- NVIDIA's gives three warnings: non-manifold points in the `chuck` (3) and the `table_crank` (12
  points, 4 edges). They came from welding pieces that met end to end, a first fix for its earlier
  warning about points on top of each other. The pieces now overlap and the weld is gone, so the
  next version is clean of both (dry run of 2026-10-27). They are render meshes only: colliders are
  convex hulls. v1 stands, since run folders are never changed (decision 0012).

## Isaac Sim check of `grizzly/t33901@v1` (Daniel, 2026-10-27)
Reported in chat; recorded in the run's `RUN.md`. Files opened: `twin.usdc`, `spin.usdc`,
`spring_return.usdc`, `unlocked.usdc`, `locked_at_setting.usdc`.
- **The table** "looks fantastic". Locked, it could not be moved at all; loosened, it "fell and
  tilted to the side due to it's weight", as decision 0018 and the check's look-for expect.
- **The chuck** turns with "the three pieces on the end", its jaws.
- **The quill sags:** it does not return "flush" to the top. Its likely cause and what changes are
  in decision 0024's update.
- **The downfeed handles** are "very noticeably wrong": "three handles that all connect to a
  central joint that is then connected to the main body. The shape looks like it is almost
  connected to the depth stop ring. It looked far more accurate on the low poly test model we
  made." (Daniel called them "the crank"; he confirmed they are the downfeed handles, the name
  to use from now on.) The generated hub is the one decision 0023 logged: one
  handle's root fused to the head's wall, in front of the depth stop's ring as seen from the front.
- **The fixed joints** raised no problem in the files he opened.
- **Success level:** 1. Level 2 waits for the quill to stay up.

### Update: the downfeed handles get a stand-in
Under Daniel's rule (a labelled stand-in where the mesh gets wrong a part that shows), the hub and
its three handles join the stand-ins, in the next version:
- each handle from the parts list: "STUD-DE M12-1.75 X 178, 15" (a 12 mm bar, 178 mm long
  [INFERENCE: read from the stud's size]) with a "KNOB M12-1.75, D35" (p. 50), three at 120 deg
  on a hub, as Phase 1's box model had them;
- the hub's size from the photos (Figs. 3, 48), against a cited size;
- at the measured pinion axis, the handles at the generated handles' angles;
- balanced, so its weight sits on its axis (decision 0024's update).

### Update: his follow-up the same day (recording and screenshots in run-001)
- **Isaac Sim Full 6.2.0.**
- **The recording** (`twin.usdc`): the quill settles about 20 mm (0.79 in) below the top, after
  ringing for about 4 s, and the handles follow it within 0.1% of the link's ratio (decision 0024,
  update).
- **Two more things the mesh gets wrong,** from his screenshots:
  - **two table height cranks:** the stand-in, and the generated arm that the cut list missed
    (it lies almost in the bracket's side plane, at y 0.10-0.12, where the removal box began at
    0.11). A cut list fix, not a new stand-in: a removal box behind the column's back
    (x below -0.235), from y 0.09, z -0.66 to -0.33, checked in `part_table_bracket.png`;
  - **two prongs under the table,** where the photos show one table pivot lock handle. Under
    Daniel's rule, a stand-in: the parts list's "FOLDING HANDLE M10-1.5 X 28, 70L" (part 122,
    p. 50), a lever about 70 mm long [INFERENCE: read from "70L"], held to the table arm by a
    fixed joint and shaped from Fig. 36 and the colour photo.
- **The head's wall** shows black holes where the generated hub's faces were cut out. With the
  hub a stand-in, its disc covers the holes around the pinion's axis; any left, such as the fused
  handle's root, are patched or logged in v2.
- **Process:** each part's own view (`views/part_<id>.png`) is looked at before a build, not only
  `parts.png`. The bracket's view showed the leftover arm.

## Update: v2 and v3 (2026-10-27, the second Phase 5 session)
The four fixes above went into the spec (`compose_spec.py` in
`data/machines/grizzly-t33901/part_cutting/2026-10-27_spec/`). Each part's own view was looked at
before the build, and a dry run in a scratch copy of the data folder came before the real one.

### What the spec gained
| Part | Kind | From |
|---|---|---|
| `generated_handles` | removed | v1's cut part `handle_hub`: one generated handle points straight out along +Y to y 0.47, one's root is fused to the wall |
| `handle_hub` | stand-in, replaces `generated_handles` | three handles at 120 degrees, each the cited "STUD-DE M12-1.75 X 178, 15" (read as 15 mm threaded into the hub and the knob [INFERENCE]) with a "KNOB M12-1.75, D35", on a hub on the "PINION SHAFT" (p. 50). From `front_operator_right.png` against the cited column (41 px for 3-1/8 in): the hub 60 mm across and 30 mm thick on a 40 mm boss, its face 70 mm off the wall; the knobs 35 mm at their ends (the cited D35, 16-20 px), 26 mm at their roots, 80 mm long. The angles 58, 178 and 298 degrees from the front towards up and a splay of 20 degrees out from the head, from an orthographic fit of the photo's three handle vectors (rms 3 px; camera azimuth 42 degrees, against the silhouette fit's 43.9; splay 23) and of Fig. 46's (splay 18, handles turned 30 degrees mod 120 by the lowered quill) |
| `generated_pivot_lock` | removed | the arm's two prongs, and the outer one's back, a flap beside the collar |
| `table_pivot_lock` | stand-in, fixed to the arm | the cited "FOLDING HANDLE M10-1.5 X 28, 70L" (p. 50) in the clamp's ears at the front of the arm's end collar (round about x 0.2815, y 0.008, r 0.082): a 10 mm screw 28 mm long, the handle's head on +Y, a lever about 70 mm long [INFERENCE: "70L"] hanging down; the ears 24 by 30 by 26 mm from Fig. 36 against the column |

- **The handles' axis** moved to the pinion between its two round ends in the mesh: the spring
  housing on -Y (x 0.252, z 0.482) and the round bar where the generated handles leave the +Y wall
  (x 0.273, z 0.478), so (0.262, 0.480), 3.7 cm from v1's point nearest the generated handles'
  lines. The hub's centre is 55 mm out from the wall (y 0.171).
- **The head's wall** stays in `frame`, by a cut list entry before the handles' removal: up to
  y 0.090 behind x 0.30 and 0.068 in front of it. v1's boxes took wall faces from y 0.07.
- **The crank's arm** lies at x -0.38 to -0.34, y 0.03 to 0.09, down to z -0.65 (not y 0.10-0.12,
  as v1's follow-up guessed). A cylinder r 0.128 keeps the bracket's round body, then a box behind
  x -0.235 takes the arm.
- **The overlay check** (`views/on_left_photo.png`): the stand-in's handles point as the photo's do
  (up about 10 degrees toward the front, back nearly level, down vertical). The hub lands about 30
  px low and to the front of the photo's hub, as v1's generated hub did: the fit's misfit nearest
  the camera (decision 0023), not the stand-in's place on the mesh.

### Patches: holes closed flat (`HolePatch`)
- **Why:** a removed part leaves a hole where its faces met a cut part. Where no stand-in covers
  it, Isaac Sim shows it black (Daniel's screenshots of v1). Options: (a) log the holes;
  (b) a stand-in plate over each, a part of its own; (c) **close the hole in the cut part itself.**
  Chosen: (c), since a hole is not a part, and (a) leaves what Daniel saw.
- **How:** a cut part's `patches` each name a point near a hole (model units) and a note. The
  pipeline closes the part's open edge loop whose centre is within 0.02 model units of the point
  by a fan of triangles from the loop's centre, wound as the faces around it
  (`parts_spec.patch_hole`). A loop that passes one point twice (two openings touching there) is
  split there first (`simple_loops`): fanned from one centre, the spoke to that point had four
  faces, a non-manifold edge in NVIDIA's validator (v2, below). Each patched part gets a warning
  ("Patched: ..."), since the surface under the faces is not known.
- **Used on the T33901:** the fused handle root on the head's wall; the bracket's boss face under
  the crank (v1's dark ring round the crank's hub), its back where the crank's arm left it, and a
  slit at its top front; the arm's top under the table (open in v1). The generated handles' root
  at the pinion is inside the stand-in's boss.
- **What it cannot fix:** two sheets of a part touching at one point (a "bowtie" vertex). The cut
  list must not make one: the prongs' removal box at y 0.055 made two, at 0.05 none.

### The builds
- **v2** (run `2026-10-27_run-001`): ours 0 errors and 0 warnings; NVIDIA's 0 errors and 2 warnings
  in every file, a non-manifold edge and points in the table arm, from the fan above. Superseded,
  not for the Isaac Sim check; it stays as built (decision 0012).
- **v3** (run `2026-10-27_run-002`): 12 parts (6 stand-ins), 11 joints (4 fixed). **Both
  validators clean** in `twin.usdc` and the six check files (NVIDIA's: "No issues found.").
  The stand-in hub's surface centroid is on the handles' axis (v1's generated hub: 0.047 m off).
  Size checks: width -7.0% and depth -6.0% (v1: +1.6% and -4.7%, stretched by the generated handle
  that pointed out along +Y); the others as v1. Daniel re-checked it on 2026-10-28 (below).

## Update: v4 (2026-10-28, after Daniel's re-check of v3)
Daniel's re-check of v3 (run `2026-10-27_run-002`, its `RUN.md`): the quill rests at the top,
the handles "look a lot better", the pivot lock handle "looks clean", "almost no holes". Two
things left, both fixed in **`grizzly/t33901@v4`** (run `2026-10-28_run-001`, both validators
clean after a dry run):
- **The depth stop's rod.** Generated, it was a cut piece of the quill, fused to the head's
  corner along its height and missing inside the ring (the stop bracket and nut, fused, kept with
  the head; decision 0023). Lowered, it showed holes in the head and a gap in the rod. Now
  `generated_depth_rod` is removed and `depth_rod` is a stand-in held to the quill: one rod 12 mm
  across (the thread of the cited "DEPTH STOP NUT M12-1.75", p. 49, part 48 [INFERENCE]; the
  generated rod is 14 mm) from the guard collar's arm through the ring to the generated rod's top,
  its axis from round fits of the generated rod, as Fig. 35 and `front_operator_left.jpeg` show
  it. Three patches close the head: the ring's bottom and top and a slot behind the rod. At the
  full stroke the rod's top goes into the ring, since the nut stays fused in it (logged).
- **The crank's nub:** the generated arm's root behind the bracket (y 0.00 to 0.04, below where
  the v3 box began) is cut out, and the bracket's back patched.
- **The views' palette** grows from 12 to 20 colours: v4's 13 parts made the views fall back to
  random colours, three pairs alike in `views/parts.png`. Later builds get a colour per part.
- v4: 13 parts (7 stand-ins), 12 joints (5 fixed).

## Update: v5 (2026-10-28, after Daniel's check of v4)
Daniel's check of v4 with recordings (run `2026-10-28_run-001`, its `RUN.md`): the depth stop
stops the quill where its check file sets it, the spring returns it, the table's locks hold.
Two gaps when parts move: below the head when the quill is lowered, and in the column where the
bracket was when the table is raised. His answers: "Let's close that seam in v5, is ther a stand
in we can put for when the quill is lowered so it isn't only supported by the guide?" and "Sure
a depth stop nut on the rod sounds like a good addition!" **`grizzly/t33901@v5`** (run
`2026-10-28_run-002`, both validators clean after a dry run): 17 parts (11 stand-ins), 16 joints
(9 fixed).

| Part | Kind | From |
|---|---|---|
| `quill_tube` | stand-in, fixed to the quill | the cited "Quill Diameter ... 1.85 in." (p. 9), from inside the collar up into the head by the cited 3-1/4 in stroke and 1 in more [INFERENCE: its length inside the head], as Fig. 46 shows the lowered quill. The head's underside and the collar's top are patched round it |
| `column_section` | stand-in, fixed to the frame | the cited "Column Diameter ... 3-1/8 in." (p. 9), from z -0.52 to -0.264 about the column's axis, where the bracket hid the column and the mesh has none |
| `generated_depth_stop_nut` | removed | the ring round the rod (z 0.555-0.625, r 0.036-0.040), a separate piece of the mesh, which v1-v4 kept fixed in the head. At the nut's place in `front_operator_left.jpeg`, so the nut, not the bracket |
| `depth_stop_nut` | stand-in, fixed to the rod | "DEPTH STOP NUT M12-1.75" and "QUICK-RELEASE BUTTON" (p. 49, parts 48 and 50): 36 mm across (the ring) and 26 mm tall (the photo, against the rod's length on the mesh), the button to the front [INFERENCE]. Set 3-1/4 in above the bracket, the twin's stop; the photos show about 2 in |
| `depth_stop_bracket` | stand-in, fixed to the frame | "DEPTH STOP BRACKET" (p. 49, part 54), at the head's bottom corner where the photo and Fig. 35 show it (z 0.41-0.47 along the rod): 18 by 27 mm, reaching 12 mm into the head |

- **The stop and the nut agree only at the full stroke:** `checks/adjustable_stop.usdc` sets the
  stop half way, and the nut stays where the twin's stop is. A check file that moved a stand-in
  would need the exporter to know which part shows a stop; not done.
- **The seam where the quill's collar met the head** (an open question of PR #21) is closed: the
  head's underside and the collar's top are patched, and the stand-in quill fills the space
  between them when the quill is lowered.

## Update: v5 checked, and v6's colours (2026-10-28)
- **Daniel's check of v5** with recordings (run `2026-10-28_run-002`, its `RUN.md`): the quill
  returns with the stand-in quill below the head, the table holds at its settings, and loosened
  it drops to its bottom stop and moves through all of its cited travel. Level 2.
- **Colours:** "That fill in specifically is orange like our moving parts though? ... should we
  segment that as gray to match the rest of the drill press?" Until then the exporter coloured the
  root part grey and every other part orange. A part held to the root through fixed joints only
  never moves, so it is now grey too (`usd/exporter.py`, `fixed_with_root`): on the T33901 the
  stand-in column section and the stand-in depth stop bracket. **`grizzly/t33901@v6`** (run
  `2026-10-28_run-003`) is v5's spec with these colours, both validators clean after a dry run.
