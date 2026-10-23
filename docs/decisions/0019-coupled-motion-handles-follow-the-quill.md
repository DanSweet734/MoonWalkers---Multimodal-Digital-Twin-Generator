# 0019 - Coupled motion: the downfeed handles follow the quill

- **Status:** proposed (Claude Code, drill-press plan Phase 1). Which coupling to keep waits for
  Daniel's Isaac Sim check.
- **Date:** 2026-10-22
- **Decided by:** team (Daniel)

## Context
"Downfeed Handle (1 of 3): Moves spindle down when pulled down" (T33901 manual, p. 7), through
the quill's rack and pinion (p. 35). The handles must turn as the quill slides: a turning joint
tied to a sliding one. The manual gives no ratio, and nothing public we could reach does either
(`docs/research/2026-10-22-t33901-handle-ratio-and-figures.md`). Daniel accepted a labelled
stand-in, logged as an inaccuracy (2026-10-22). Sources:
`docs/research/2026-10-22-sliding-joints-locks-and-coupling.md`, section 4.

## Options considered
1. **`PhysxMimicJointAPI`.**
   - It is "DEPRECATED: use NewtonMimicAPI ... instead", but still read by Isaac Sim 6.2.
   - It supports "linear to angular" gearing in "degrees / distance", inside the articulation, as a
     two-way hard constraint.
   - A turning follower needs "a limit set".
   - NVIDIA's own `MimicJointDemo.py` in Isaac Sim 6.2 drives a revolute joint from a prismatic
     one.
2. **`NewtonMimicAPI`.** "The leader and follower must be the same joint type ... an angular
   follower tracking a linear leader ... is not supported." It cannot do this.
3. **`PhysxPhysicsRackAndPinionJoint`.**
   - It "connects an existing revolute/hinge joint to an existing prismatic joint".
   - It ties their speeds, "abs(omega) = abs(V) * R", not their positions, and its direction
     depends on the joint frames.
   - Between articulation joints it must be excluded from the articulation.
4. **A script or time samples** that set the handles' target from the quill's position. Then a push
   on the quill would not turn the handles [INFERENCE].

usd-core defines none of these PhysX schemas, so 1 and 3 are written by name, with the names and
types of Isaac Sim 6.2's schema file (`usd/physx_schemas.py`).

## Decision
1 and 3 are both written for the check, and 2 and 4 are not. Kept for each:
- **`JointCoupling(leader, ratio, offset, method)` in `JointSettings`.**
  - The follower's position is `ratio` × the leader's + `offset`, in contract units (rad per m
    here).
  - The exporter converts to PhysX's "jointPosition + gearing * referenceJointPosition + offset =
    0": gearing = -ratio × 180/π, in degrees per metre.
  - A follower has no drive of its own. Without its own start, it starts where the coupling puts
    it.
- **The stand-in ratio:** the handles turn 270° over the 3-1/4 in stroke (57.1 rad/m). It is signed
  so that pulling the front handle down lowers the quill, as p. 7 says.
- **Validation:** our validator checks a mimic's reference joint and limits. It reports, as info,
  that the Newton migration must not be accepted for this joint. Isaac Sim's own
  `NewtonMimicMigrationChecker` would offer that migration, because it checks only that both
  joints have one degree of freedom.

## Consequences
- **The deprecation is a risk.** If a later Isaac Sim drops `PhysxMimicJointAPI` and Newton still
  refuses cross-type mimics, 3 or 4 is what remains. Then a push on the handles would turn the
  quill only with 3.
- The rack and pinion ties only speeds, so its direction may come out reversed. Daniel's check of
  file 6 says which way it turns.
- The ratio is a stand-in until a measurement or Grizzly gives it. Every twin carries it as an
  issue.
- Contract v0.2.0 (decision 0020) will describe linked joints, so pipelines can state couplings.

## Isaac Sim check
Not yet done. See `docs/setup/isaac-sim-check.md`, section 8, files 5, 6 and 10.
