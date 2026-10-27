# 0027 - Joints and stand-ins in the geometry spec

- **Status:** proposed (by Claude Code, drill-press plan Phase 5, 2026-10-27), for Daniel's review
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
