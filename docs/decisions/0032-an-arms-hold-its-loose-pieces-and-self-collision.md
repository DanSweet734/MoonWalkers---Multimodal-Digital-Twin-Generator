# 0032 - An arm's hold, its loose pieces and its self-collision

- **Status:** accepted by Daniel on 2026-11-10 ("I think decisions 0031 and 0032 are good so I
  accept them"). The three choices in it are Daniel's (2026-11-10). Proposed by Claude Code in the
  lab's machines plan, Phase 2.
- **Date:** 2026-11-10
- **Decided by:** team (Daniel), proposed by Claude Code
- **Applies:** decisions 0010 (export), 0017 (joints, unjoined pairs), 0020 (the exporter decides
  how to simulate), 0023 and 0027 (cut parts), 0031 (the arm)

## Context
Daniel's Isaac Sim checks of the box arm and of `igus/rebel6dof02@v1` (2026-11-10; worklog of
that date, both runs' `RUN.md`) found four things that the drill press never showed:

1. **The default drive sags.** The exporter holds a driven joint with stiffness 100 and damping
   20 (`usd/exporter.py`, `DriveSettings`: w = 10 rad/s, acceleration drive). On the box arm the
   links sagged 1.1 to 1.5 degrees under gravity, beyond the scorecard's 1-degree target, and
   moved 3.4 degrees when pushed by hand. Stiffness 10000 and damping 200 held within 0.06
   degrees, and 0.09 when pushed (recordings `pose_hold_default_2026-11-10_004900.csv`,
   `pose_hold_stiff_2026-11-10_005040.csv`). Daniel: "If we want the joints unmovable and
   pose_hold_stiff uses stiffer drives then yes."
2. **Loose bits float.** "There were also floating points on the mesh that didn't travel with
   the arm when it moved, leading to a few yellow dots floating around as it moved." The cut list
   gives every face above the foot's seam that no link's shape holds to link 1, so five loose
   bits of the generated mesh (11 to 32 faces, 10 to 18 mm, near the hand and the forearm) turn
   with joint 1 only.
3. **The cables.** "Multiple wires hanging down when in reality there was one or two, and those
   wires not connecting, detaching at certain points." The generator made several strands of the
   hand's cables. Some are separate pieces in links 1 and 2, and some are fused to the links' and
   the foot's surfaces. In the photos one or two cables hang loose from the wrist to the table.
4. **The arm folds through itself.** "The arm folded through itself and the base." By decision
   0017, parts that no joint joins directly do not collide (`PhysicsFilteredPairsAPI`), because
   a convex hull can enclose a part that sits inside another, like the drill press's spindle in
   its head.

## Options considered
**The hold** (1):
1. Raise the exporter's default for every twin. This changes the HA5C's and the T33901's
   behaviour, and tests that assert 100 and 20, with no check that asked for it.
2. A per-joint drive in the contract. The contract says what the machine does, not how it is
   simulated (decision 0020), and a change needs a version bump and the pipeline owners.
3. **A per-twin setting in Pipeline B's several-part spec** (`hold_drive`: stiffness, damping,
   why). The build passes it to the exporter as the drive for driven joints, in the twin and its
   check files. Spec files without it build as before.

**The loose bits and the cables** (2, 3; Daniel chose "Remove, log"):
1. Remove each piece by a box in the cut list. Boxes round long strands also take the links'
   faces, since a strand's box overlaps the upper arm.
2. **A cut part keeps only its largest connected piece** (`loose_pieces: "remove"`), with no
   coordinates to measure. The rest is cut out and counted in the assembly record.
3. Find strands by thickness (a thin tube). Tried in scratch: the generated links are thin
   double-walled shells, so half of each link's faces read as thin. Rejected.
4. **For strands fused to a surface:** keep each body inside cylinders about its own axis, then
   send the rest to a removed part. The radii come from the faces' distances to joint 1's axis,
   which show a gap between body and strand.
5. A labelled rigid cable stand-in. It would swing stiffly with the hand and pass through the arm
   and table. Daniel did not choose it.
6. Keep them, logged. Daniel did not choose it.

**Self-collision** (4; Daniel chose "Check file first"):
1. Turn collisions on in the twin now.
2. **A check file first** (`self_collision` "check": `checks/self_collision.usdc`, where the parts
   no joint joins collide while the driven joints turn). Collisions go on in the twin only once
   that check shows the hulls neither jam nor fly apart in the modelled pose.
3. Keep them off, logged.

## Decision
- **The hold:** option 3. `PartsSpec.hold_drive` (`pipelines/b/parts_spec.py`), read by
  `build.hold_drive`. `set_spec_frame` (MCP) takes it. The arm uses stiffness 10000 and damping
  200: w = 100 rad/s, critically damped, the drill press's lock values and the box arm's stiff
  check. A simulation setting chosen by us, not a fact about the arm [INFERENCE].
- **Loose pieces:** option 2, `SpecPart.loose_pieces = "remove"`, with option 4 for fused strands.
  The faces carry the label `<part> (loose pieces)` (`parts_spec.loose_label`), drawn as removed
  in the views. They are counted in `removed_faces`, and an info issue on the part says how many
  faces were cut.
- **Self-collision:** option 2. `PartsSpec.self_collision` is "off" (the default, decision 0017),
  "check" or "on". The exporter takes `collide_unjoined` (`export_twin`, `build_stage`). Joined
  parts still do not collide, as before. `set_spec_frame` takes it.
- **The duplicate thumb:** logged on the hand. The hand stays as generated until Phase 7 models
  the L20 (Daniel, 2026-11-10).

`igus/rebel6dof02@v2` (run `2026-11-10_run-001`, spec written by
`data/machines/igus-rebel6dof02/part_cutting/2026-11-10_spec/compose_v2.py`) applies all four.

## Consequences
- The HA5C and the T33901 build as before: their specs give neither setting. The control
  programs' exports (`control/export.py`, `control/controls_export.py`) still hold with
  `DriveSettings.hold`; an arm's program, when one comes, needs the twin's hold passed through.
- Fused strands still need measured shapes per machine (option 4). For v2, two strands fused
  along link 2's side by joint 2's housing remain, with short stubs on link 1's dome, because
  they lie inside those links' own shapes. They are logged on link 1.
- Removing fused strands leaves open loops where they met a body. One, on the column's front, is
  patched flat (the generator made no surface under the strand); the small ones are left open
  and reported by the preview.
- A twin's collisions between unjoined parts follow the setting in its spec, so a later machine
  with nested parts (a spindle in a head) keeps the default.
- Reversing it: delete the three fields from a spec, and it builds as before.

## Update (2026-11-10): Daniel's check of v2, and v3
- **v2 in Isaac Sim** (Daniel): `twin.usdc` could not be moved "at all with shift + drag at
  least from what I could see"; `checks/self_collision.usdc` showed "no jumping or flying apart,
  no folding in on itself, and no more floating dots ... along with most of the hanging wires".
- **So the twin collides** (`self_collision` "on" from v3), as the decision says once that check
  is clean. With "on", there is no separate collision file: the twin and every check file
  collide, and `checks/spin.usdc` is the scenario `self_collision.usdc` was.
- **v3** (run `2026-11-10_run-002`, `part_cutting/2026-11-10_spec/compose_v3.py`): the strands
  v2 left are cut by measured boxes (option 1, which works where a strand stands clear of the
  body). Each box was measured on projections of a part's face centres with a 0.1 grid, then
  checked by counting every part's faces inside it. The strand over joint 2's housing left a
  hole, patched flat. Left, logged: a short stub against the housing's end ring and a knot on
  link 1's dome, fused to those surfaces.
- **Tried and dropped for finding strands:** curvature (how far a face's normal turns within
  0.03 units). The generated surface is noisy and double-walled, so half of each link turns
  sharply.
