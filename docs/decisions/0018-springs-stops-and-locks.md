# 0018 - Springs, stops and locks

- **Status:** proposed (Claude Code, drill-press plan Phase 1). Which lock to keep waits for
  Daniel's Isaac Sim check.
- **Date:** 2026-10-22
- **Decided by:** team (Daniel)

## Context
The T33901's quill is returned by a spring, and stopped by an adjustable depth stop. Its table's
four motions are held by locks:
- "Spindle Return Spring: Automatically returns quill into headstock" (manual, p. 7);
- "Depth Stop: Stops spindle travel at predetermined drilling depth" (p. 7), "a threaded rod
  attached to the quill with a depth stop nut that can be lowered or raised against a stop
  bracket" (p. 31);
- the lock handles and the tilt bolt (p. 32), and the crank, whose worm drive holds the height
  (exploded view, p. 48).

No source gives the spring's force. The spring is a wound "FLAT COIL SPRING" (p. 49) whose tension
is set by notches (p. 40). No schema names a "lock". The sources are in
`docs/research/2026-10-22-sliding-joints-locks-and-coupling.md`, section 5.

## Options considered
1. **The spring.**
   - (a) A position drive towards the top of travel. With gravity, it sags a little.
   - (b) A position drive towards a point above the top of travel, so the quill rests on its top
     limit with a preload, as a wound spring does.
   - (c) A force applied by a script.
2. **The depth stop.**
   - (a) The joint's limit at the bottom of travel, set to the depth. It is always written: NVIDIA,
     "Articulation joints without limits cannot be configured with limits after attaching the
     stage".
   - (b) A collider for the stop nut, which would need parts to collide (decision 0017 turns that
     off).
3. **A lock.**
   - (a) A stiff position drive at the setting. A push stronger than the drive moves it.
   - (b) Equal limits at the setting. This is a hard stop.
   - (c) PhysX joint friction (`physxJoint:jointFriction`). Its units are not stated where it was
     read.
   - (d) A fixed joint beside the moving one, switched on with `physics:jointEnabled`. It closes a
     loop, so it would need to be kept out of the articulation.

## Decision
- **Spring: 1b.** A position drive with stiffness 600 and damping 49 (about critically damped),
  targeting 0.03 m above the top of travel.
  - The preload, 600 × 0.03 = 18 m/s², is more than gravity's 9.81, so the quill holds at the top.
  - At full depth the spring gives 600 × 0.113 = 68 m/s².
  - All three numbers are **stand-ins**, chosen for the simulation, and logged as an inaccuracy.
- **Depth stop: 2a.** The stop is the quill's limit at the bottom of its travel, set within the
  3-1/4 in. The check sets it at 1-1/2 in.
- **Locks: (a) and (b) are both written for the check.**
  - (a) has stiffness 10,000 and damping 200; (b) has equal limits. Daniel compares them in
    Isaac Sim.
  - (c) and (d) are kept in reserve.
  - A free table motion gets damping 2 and no spring (`DriveSettings.free`), a stand-in for
    friction, so a pushed table comes to rest.
  - The free table's height stays held by a drive, because the real crank's worm holds it.
- **Starting positions:** PhysX's `PhysicsJointStateAPI`, written by name (decision 0019). It
  starts the quill at full depth in the spring check, and the table at its locked pose.

## Consequences
- The spring's look in Isaac Sim depends on stand-in numbers. How fast the real quill returns is
  not known.
- Changing a lock or the depth stop during a simulation is not tested. The checks write each
  setting into its own file.
- The contract has no field for any of this yet. Decision 0020 adds joint modes: spring return to
  a rest position, locked at a setting, free, and an adjustable stop.
- **To fill in after the check:** which lock held, and whether the spring behaved as above.

## Isaac Sim check
Not yet done. See `docs/setup/isaac-sim-check.md`, section 8, files 3, 4 and 7 to 9.
