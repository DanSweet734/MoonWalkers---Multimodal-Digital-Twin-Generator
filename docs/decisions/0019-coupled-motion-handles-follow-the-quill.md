# 0019 - Coupled motion: the downfeed handles follow the quill

- **Status:** proposed (Claude Code, drill-press plan Phase 1). Checked in Isaac Sim by Daniel on
  2026-10-23: the mimic is kept. The rack and pinion, with its sign reversed, works as a fallback.
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
**1, the mimic, after the check.** 1 and 3 were both written for the check, and 2 and 4 were not.
Only the mimic worked. The rack and pinion stays in the exporter as a fallback for the risk below.
Its ratio's sign was reversed after it failed, and then it worked too. Kept for each:
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
- The rack and pinion ties only speeds, so its direction depends on the joint frames. It came out
  reversed in the first check (below).
- The ratio is a stand-in until a measurement or Grizzly gives it. Every twin carries it as an
  issue.
- Contract v0.2.0 (decision 0020) will describe linked joints, so pipelines can state couplings.

## Isaac Sim check (Daniel, 2026-10-23)
Run `2026-10-22_run-001`; its `RUN.md` holds the full record.
- **Mimic (file 5): works.**
  - The quill started down and rose, and the handles turned with it, about 270°, counter-clockwise
    from where Daniel watched.
  - Pushing a handle moved the quill too; pushing the quill alone did not, as decision 0018
    explains.
  - The follower's limits are -0.05 to 4.76 rad, so a 270° turn fits only in the positive sense.
    [INFERENCE] So the coupling's sign is as designed: pulling the front handle down lowers the
    quill.
- **Rack and pinion (file 6): did not work as written.** "the handles move a little and can be
  moved but not easily, and the quill doesn't seem to move at all."
  - [INFERENCE] The ratio's sign is reversed: as the quill tries to rise, the handles are driven
    the wrong way, into their limit about 3° away, and that holds the quill down.
  - PhysX allows a negative ratio ("Range: (-inf, inf)").
  - The exporter now writes the ratio with the mimic gearing's sign, and run `2026-10-23_run-002`
    retries it. If it then works, it is a ready fallback for the deprecation risk.
- **All motions (file 10):** the quill moved only through the handles, as in file 5.

## Re-check (Daniel, 2026-10-23, run `2026-10-23_run-002`)
- `handles_follow_rack_pinion`: the handles now turn back with the rising quill, as in the mimic
  file. Daniel confirmed "now" when asked, since his note read "not".
- So the reversed sign was the cause. The rack and pinion's ratio takes the mimic gearing's sign,
  and it is a working fallback if `PhysxMimicJointAPI` is ever dropped. It ties only the speeds,
  and stays out of the articulation.
- Measured with the joint recorder in `all_motions`: the mimic held the handles at 57.03-57.68 rad/m
  of quill travel while it moved, against the 57.085 set, so within 1%.
