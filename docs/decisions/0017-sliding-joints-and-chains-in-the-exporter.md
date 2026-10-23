# 0017 - Sliding joints, other axes and a chain of joints in the exporter

- **Status:** proposed (Claude Code, drill-press plan Phase 1). Waiting for Daniel's Isaac Sim check
  of the box-and-cylinder drill press.
- **Date:** 2026-10-22
- **Decided by:** team (Daniel)
- **Amends:** decision 0010 (prismatic joints were refused; one drive went on every joint)

## Context
The drill press slides its quill and table, and its table turns, tilts and turns again on a chain
of parts (`docs/drill-press-plan.md`; `docs/poc-report.md`, section 8, items 2 and 3). Decision
0010's exporter refused prismatic joints and wrote one angular drive on every revolute joint. The
sources are quoted in `docs/research/2026-10-22-sliding-joints-locks-and-coupling.md`.

## Options considered
1. **Sliding joints.**
   - (a) `UsdPhysics.PrismaticJoint`, which usd-core 26.8 defines, with a linear `DriveAPI`.
     Its limits are "Units: distance", so metres on our stages.
   - (b) A generic D6 joint with one free axis. That is more general, but nothing needs it yet.
2. **Axes.** Turn the joint frame's X axis onto the contract's axis, and write `physics:axis = X`.
   This is what decision 0010 does for revolute joints, so prismatic joints share one frame rule.
3. **Drives.**
   - (a) One drive for every joint, as before.
   - (b) A drive per joint, set at export time.
   - (c) Drives from the contract, but v0.1.0 has no field for them (decision 0020).
4. **Two motions between two visible parts** (the bracket slides up the column and turns around
   it; the table tilts and turns on the bracket):
   - (a) an invisible link between the two motions;
   - (b) the real part between them, which the manual's photos and exploded view show: the column
     rack, and the table mounting arm;
   - (c) one joint with two degrees of freedom.
5. **Collisions between a machine's own parts.** PhysX articulations collide with themselves by
   default (`physxArticulation:enabledSelfCollisions = 1` in Isaac Sim 6.2's PhysX schema). Joined
   parts do not collide, because a joint's `collisionEnabled` falls back to false. But a convex hull
   can enclose a part that is not directly joined, such as the spindle inside the head.
   - (a) Leave self-collision on.
   - (b) Turn it off with PhysX's own `enabledSelfCollisions`, which usd-core does not define.
   - (c) Filter every pair of parts that no joint joins, with `UsdPhysics.FilteredPairsAPI`, which
     usd-core defines.

## Decision
1a, 2, 3b, 4b and 5c, in `backend/src/moonwalkers/usd/exporter.py`:
- **Prismatic joints:** written with limits and linear drive targets in metres. A prismatic joint
  without settings gets a hold at 0, with stiffness 100 and damping 20.
- **`JointSettings`:** one per joint id, passed to `export_twin` and `build_stage`. Each gives the
  joint's own drive, or none, and may also give limits, a starting position and a coupling
  (decisions 0018 and 0019). These are export settings, not contract fields, until decision 0020.
- **Chains:** the exporter already walked a tree to one root (`_root_part`). Now any joint type may
  be in it.
- **Filtered pairs:** every two parts that no joint joins directly get `PhysicsFilteredPairsAPI`.
  A twin of two parts, like the HA5C, gets none, so its file does not change.
- **Unchanged output:** built at a fixed time, the Phase 2 test twin is byte for byte what the
  exporter wrote before. A test compares it with fixtures saved on 2026-10-22
  (`backend/tests/fixtures/test_twin/`).
- **Primitives:** a "compound" of boxes and cylinders now makes one part, such as the hub with its
  three handles (`usd/geometry.py`). It needs no contract change.

## Consequences
- The box-and-cylinder drill press exports with seven joints, and both validators pass its ten
  check files (ours, and NVIDIA's `omni_asset_validate`: "No issues found").
- **A vertical slide sags with the default drive.** With an "acceleration" drive, stiffness 100
  balances gravity 9.81 / 100 = 0.098 m from the target [INFERENCE: not run in Isaac Sim]. That is
  more than the quill's whole stroke. The drill press's checks give the quill its spring
  (decision 0018). A twin that Pipeline B builds later needs its joint modes from the contract
  (decision 0020).
- **The parts never touch each other.** A raised table can pass through the chuck, which the real
  one cannot. The joints and limits stop motion, not contact. This is logged as an inaccuracy in
  the twin.
- Compound parts get one convex hull, so other objects would collide with a hull, not the shape.
  That does not matter inside the twin, where parts do not collide.
- **Reversing it:** remove `JointSettings` and the filtered pairs. Prismatic joints would then
  need refusing again.

## Isaac Sim check
Not yet done. See `docs/setup/isaac-sim-check.md`, section 8.
