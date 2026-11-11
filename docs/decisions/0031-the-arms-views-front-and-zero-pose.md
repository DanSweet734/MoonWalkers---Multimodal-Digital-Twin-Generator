# 0031 - The arm's views, its front, its zero pose and the public models' role

- **Status:** accepted by Daniel on 2026-11-10 ("I think decisions 0031 and 0032 are good so I
  accept them"), after his Isaac Sim checks of v1 and v2. Proposed by Claude Code in the lab's
  machines plan, Phase 2; the views and the front are Daniel's (2026-11-09).
- **Date:** 2026-11-09
- **Decided by:** team (Daniel), proposed by Claude Code
- **Applies:** decisions 0022 (views), 0023 and 0027 (cut parts and joints), 0029 (cut-outs)

## Context
The ReBeL arm (`igus/rebel6dof02`) is the first machine whose joints all turn and whose parts
are posed: the lab photographed it bent, with the hand reaching forward. The twin needs three
choices the drill press never needed:

1. **Which photos feed the generator.** Daniel took ten photos on 2026-11-05: four sides, four
   corners, two from above (`data/machines/igus-rebel6dof02/inputs/SOURCES.md`).
2. **Which way is the front.** An arm has no operator's side, and the twin's +x must point
   somewhere fixed. Daniel's direction (2026-11-09, the plan's checklist): "where the fingertips
   point in the photographed pose, fixed to the base".
3. **What a joint's 0 means.** igus's ranges and its zero pose are given for the arm standing
   straight up (igus's technical documentation 08/2022, p. 2 "Joint Movement" and p. 6's
   drawing; the iRC_ROS URDF's joint origins). UsdPhysics measures a revolute joint's position
   from the pose the bodies are authored in, and the twin's bodies are cut from a mesh of the
   photographed pose. The contract's `Joint` has no field for a zero offset (SCHEMA_VERSION
   0.2.0).

## Options considered
1. **The views.**
   - (a) **The four sides to the multi-view model, the corners and the top views as evidence**
     (133252 operator_left, 133306 front, 133317 operator_right, 133326 back). The multi-view
     model takes front, left, back and right (`docs/setup/generators.md`); Daniel confirmed the
     four on 2026-11-09 ("Confirmed as listed").
   - (b) The corners as a grid turned 45° (decision 0022). The arm's corner photos are taken
     from above at differing heights, and the four sides are level, so (a).
2. **The front.**
   - (a) **Where the fingertips point, fixed to the base** (Daniel). Joint 1 is then 0 in the
     photographed pose by definition.
   - (b) igus's own joint 1 zero. Not confirmed: neither the documentation nor the URDF says
     where it points on the base, and nothing on the photographed base marks it.
3. **What a joint's 0 means.**
   - (a) **The photographed pose is the twin's 0, and igus's limits are shifted by each joint's
     angle in that pose:** igus angle = twin position + offset. The offsets are measured on the
     mesh from the fitted joint axes and written in each joint's note, in `RUN.md` and in this
     record. No contract change; the mesh is not bent.
   - (b) Re-pose the cut parts into igus's straight-up pose before export. Each part would turn
     about its fitted axis; the twin would then open in igus's zero pose and use igus's ranges as
     they are. But the twin would no longer look like any photo (photo-match scoring breaks), the
     cut faces would meet at new angles, and a wrong offset would bend the parts into each other.
   - (c) A `zero_offset` on `Joint` in the contract, read by the exporter. Clean, but a contract
     change needs a decision record, a version bump and the pipeline owners (CLAUDE.md, rule 6);
     the arm's level 3 (Phase 3) may show whether it is needed.
4. **Joints without a measured angle.** Joints 4 and 6 turn along their links, and 0° and 180°
   look alike on a generated mesh: (a) **take 0 and log it** as a warning on the joint, or (b)
   guess from the hand's thumb. (a): a guess would read as a measurement.

## Decision
- **Views:** 1(a). **Front:** 2(a), with igus's joint 1 zero logged as not confirmed.
- **Zero pose:** 3(a). The photographed pose is the twin's 0. The angles in that pose, measured
  on the generated mesh (run `2026-11-09_run-001`), and the twin's limits:

  | Joint | Angle in the photo (igus) | igus's range | The twin's range |
  |---|---|---|---|
  | 1 | 0 (the front's definition) | -179° to +179° | -179° to +179° |
  | 2 | -21.81° | -80° to +140° | -58.19° to +161.81° |
  | 3 | +118.82° | -80° to +140° | -198.82° to +21.18° |
  | 4 | 0, assumed (option 4a) | -179° to +179° | -179° to +179° |
  | 5 | +10.46° | -95° to +95° | -105.46° to +84.54° |
  | 6 | 0, assumed (option 4a) | -179° to +179° | -179° to +179° |

  The signs follow the URDF's axes [INFERENCE: igus's positive for joints 2, 3 and 5 leans
  towards +x, as the URDF's joint 2 origin of +30° and its limits imply]. The reference file
  (`pipelines/b/igus_rebel6dof02.reference.json`) holds igus's ranges as quoted; the run's spec
  holds the shifted ones.
- **The public models' role:** iRC_ROS's description gives the joints' axis directions and
  signs, and, in the box-and-cylinder arm only, the places of joints 4 and 6, which igus's
  drawing does not show. The twin's own axes and places are measured on the generated mesh. Its meshes are not used in the twin: they are what the twin is scored
  against (shape, axes and places; `pipelines/b/score.py` with `igus_rebel6dof02.score.json`),
  posed as the twin is. The hand's public models (LinkerBot's, Realhand's) wait for Phase 7.
- **Parts:** base, links 1 to 5, and the hand, which joint 6 turns. The URDF's link 6, the
  flange, is a 1.2 mm disc, so the twin merges it into the hand: seven bodies, not "seven parts
  and the hand" as the plan's checklist reads.

## Consequences
- The twin opens looking like the photos; Isaac Sim's joint positions are not igus's angles.
  Anyone driving it from igus's angles (Phase 3, level 3) subtracts the offsets above. Phase 3
  either does that in its controller or proposes option 3(c).
- A wrong angle on the mesh shifts that joint's whole range: joint 3's measured +118.82° depends
  on the fitted axes of joints 3 and 5 (joint 5's fits are partly round, an issue on the joint).
- Joints 4 and 6 may be off by up to 180° in their ranges. Both ranges span ±179°, so the twin
  still turns almost a whole turn either way; the end stops may be on the wrong side.
- Reversing to 3(b) or 3(c) needs no new measurements: the offsets above are the inputs.
