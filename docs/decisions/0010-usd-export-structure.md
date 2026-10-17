# 0010 - How twins are written as OpenUSD for Isaac Sim

- **Status:** accepted (proposed by Claude Code in Phase 2; Daniel reviewed and approved on 2026-10-17)
- **Date:** 2026-10-17
- **Decided by:** team (Daniel)

## Context
Phase 2 of `docs/poc-plan.md` needs an exporter that writes a twin as a `.usda` with correct units,
parts as meshes, and a revolute joint with an articulation root and an angular drive, plus a way to
check the file before opening Isaac Sim 6.2.0. Every source below is quoted, with access dates, in
`docs/research/2026-10-17-usd-physics-for-isaac-sim.md`. Each choice cites its source there.

## Options considered
1. **Primitive parts.** (a) UsdGeom Cube/Cylinder prims; (b) generated polygon meshes. (b) sends test
   shapes down the same path as Pipeline B's meshes in Phase 3, which is the point of testing with
   primitives first [INFERENCE].
2. **Fixed base.** (a) A fixed joint from the root part to the world; (b) a kinematic base. NVIDIA
   recommends the fixed joint "because it best expresses the intention".
3. **Articulation root.** (a) On the twin's top prim, an ancestor of the world joint; (b) on the
   world joint itself. OpenUSD and NVIDIA allow both; Isaac Sim's GUI tutorial uses the top prim.
4. **Colliders on moving parts.** (a) Triangle mesh; (b) convex hull; (c) convex decomposition;
   (d) SDF. NVIDIA describes triangle meshes as for static or kinematic objects. A convex hull is
   exact for a box or cylinder; real meshes are decided in Phase 3.
5. **Mass.** (a) Author mass or density; (b) leave it to the default 1000 kg/m^3 on the collider
   volume. No source gives the HA5C spindle's mass, so (b), labelled as a placeholder.
6. **Drive type.** (a) "force"; (b) "acceleration", whose spring "is for the acceleration at the joint
   (rather than the force)". (b) makes the response independent of the placeholder masses.
7. **Physics scene.** (a) None; (b) inside the twin's root; (c) a sibling of the root. With (c),
   opening the file directly simulates, and a stage that references the twin does not inherit it.
8. **Provenance.** (a) A sidecar JSON next to the `.usda`; (b) USD `customData` on the root, every
   part and every joint. (b) travels with the file.
9. **Scale.** (a) `xformOp:scale` on bodies; (b) baked into mesh points. UsdPhysics: joint space
   "is a translation and orientation only, scaling is not supported."
10. **Validation.** (a) Only NVIDIA's `omni_asset_validate`; (b) only our own pxr checks; (c) both.
    Observed: each catches problems the other misses (table in the research note).

## Decision
Implemented in `backend/src/moonwalkers/usd/`:
- **Stage:** `.usda` text, `metersPerUnit = 1`, `kilogramsPerUnit = 1`, `upAxis = Z`, default prim
  named from the machine key (`haas/ha5c` becomes `/haas_ha5c`), `kind = component`, `assetInfo`
  name and version.
- **Parts:** one Xform per part at identity, with `PhysicsRigidBodyAPI` when the twin has joints, and
  a child Mesh: welded points, flat face-varying normals, `subdivisionScheme = none`,
  `PhysicsCollisionAPI` + `PhysicsMeshCollisionAPI` (`convexHull` on moving parts; `none` for static
  twins). Mass is not authored.
- **Primitives:** `Part.primitive` dictionaries `{"shape": "box", "size_m", "center_m"}` and
  `{"shape": "cylinder", "radius_m", "length_m", "axis", "center_m", "segments"}`, validated
  strictly. Files (glb, obj, usd) are refused until Phase 3 adds a mesh loader.
- **Joints:** under a `joints` scope. A `fixed_to_world` fixed joint has body1 = the root part (the
  one part that is no joint's child). Revolute joints have body0 = parent and body1 = child. Their
  frame is the contract's `origin_m` in both bodies, turned so the frame's X axis lies along the
  contract axis, with `physics:axis = "X"`. Limits are converted to degrees and left unlimited when
  absent. Fixed joints between parts are supported; prismatic joints are refused for now.
- **Articulation root:** `PhysicsArticulationRootAPI` on the twin's top prim.
- **Drive:** `PhysicsDriveAPI:angular`, type "acceleration".
  - Position mode: stiffness 100, damping 20 (critically damped at 10 rad/s, [INFERENCE] tuning).
  - Velocity mode: stiffness 0, damping 20.
  - Targets are converted from radians to degrees.
- **Scene:** `/PhysicsScene` beside the root, gravity left at the defaults (earth gravity, opposite
  the up axis).
- **Provenance:** root `customData["moonwalkers"]` holds the twin record and, per result, its
  sources, identity, facts, scale, control behaviours and issues. Each part and joint holds its own
  citations as `source_id | locator | "quote"` lines.
- **Validation:** `moonwalkers.usd.validate` checks the stage metadata, runs OpenUSD's UsdPhysics
  parser plus direct joint-relationship checks, and checks joint frames in world space, convex
  colliders, mesh topology and provenance. `omni_asset_validate` (dev dependency) runs as well; both
  pass on the test twin and are run in the test suite.

## Consequences
- The same exporter serves the box-and-cylinder test twin now and the HA5C meshes in Phase 3. Phase 3
  only adds a mesh loader and the scale factor from `ScaleCalibration`.
- Masses are not real until a source gives them; behaviour that depends on mass is not meaningful yet.
- Writing the cited maximum speed (410 deg/s) needs PhysX's `maxJointVelocity`, which usd-core does
  not define; deferred to Phase 6.
- The drive tuning is our assumption and may change after the Isaac Sim check.
- Changing any of these means editing `exporter.py` and its tests; the contract is untouched.

## Review and Isaac Sim check (2026-10-17)
- **Daniel's review:** keep the drive tuning; use the default density whenever no source gives a
  mass or density; prismatic joints may be needed later (for example on the backup drill press).
- **Isaac Sim 6.2.0** (App Version 6.2.0, Kit 110.4.0, omni.physx 110.4.4) opened both test files
  with nothing else needed, and they behaved as expected. `spin.usda` turned steadily at 30 deg/s
  with the base still. In `quarter_turn.usda` the spindle turned 90 deg and settled in about two
  seconds (Daniel's estimate). The log shows 0 errors.
- **Follow-up for Phase 3:** Isaac Sim warns that the stage "has no usable time-code range", which
  "prevents time-accumulating sensors and controllers from producing output", and advises: "Author
  distinct startTimeCode and endTimeCode values in the root layer before playing." The exporter
  will author a time range when the HA5C is exported, so the next Isaac Sim check covers it.
