# 0018 - Springs, stops and locks

- **Status:** accepted (proposed by Claude Code in the drill-press plan's Phase 1; Daniel reviewed PR #16 and approved it on 2026-10-23).
  Checked in Isaac Sim by Daniel on 2026-10-23: locks by equal limits are kept.
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
- **Locks: (b), equal limits, after the check.** Both (a) and (b) were written for the check,
  and only (b) held completely.
  - (a) has stiffness 10,000 and damping 200; (b) has equal limits. Daniel compared them in
    Isaac Sim (below).
  - (c) and (d) are kept in reserve.
  - A free table motion gets damping 2 and no spring (`DriveSettings.free`), a stand-in for
    friction, so a pushed table comes to rest.
  - The free table's height stays held, because the real crank's worm holds it [INFERENCE: worm
    drives are commonly self-locking; the manual does not say]. A hold drive was tried first and
    sagged, so it is now held by equal limits too.
- **Starting positions:** PhysX's `PhysicsJointStateAPI`, written by name (decision 0019). It
  starts the quill at full depth in the spring check, and the table at its locked pose.

## Consequences
- The spring's look in Isaac Sim depends on stand-in numbers. How fast the real quill returns is
  not known.
- Changing a lock or the depth stop during a simulation is not tested. The checks write each
  setting into its own file.
- The contract has no field for any of this yet. Decision 0020 adds joint modes: spring return to
  a rest position, locked at a setting, free, and an adjustable stop.
- **A hold drive sags on a vertical slide.** With stiffness 100 and an "acceleration" drive,
  gravity balances it 0.098 m below its target. The free table showed this on Play and could be
  pushed up and down. A lock or a hold against gravity needs equal limits, or a much stiffer
  drive.

## Isaac Sim check (Daniel, 2026-10-23)
Run `2026-10-22_run-001`; its `RUN.md` holds the full record.
- **Spring (file 3):** on Play the quill jumped to its stored start at full depth, then rose to the
  top and stayed there. Pushing the quill directly barely moved it. In the coupled files the handles
  did move it: through the coupling their lever is about 10 times stronger [INFERENCE: 178 mm × the
  stand-in 57.1 rad/m ≈ 10].
- **Depth stop (file 4):** the quill stopped short of its full travel. Daniel measured about 2.88 in
  out of the head, which is the made-up 1.38 in it sticks out at the top plus the 1.50 in stop.
- **Locks (files 8 and 9):** "the lmits [sic] (file 9) seemed to hold better" (Daniel). The stiff
  drive was stiff, but moved a little up and down when pushed. The equal limits did not move at all.
- **Free table (file 7):** it swung, tilted and turned under a push, as intended. Its height also
  sagged and could be pushed, which was not intended; run `2026-10-23_run-002` holds it by equal
  limits.

## Re-check (Daniel, 2026-10-23, run `2026-10-23_run-002`)
- `table_free`: "the table swings, tilts, and turns without the hight [sic] changing no matter how
  much I try". Equal limits hold the height, as the crank's worm does.
- Measured with the joint recorder in `all_motions` (`2026-10-23_run-002/recordings/all_motions_2026-10-23_141658.csv`):
  - the spring brought the quill from 82 mm down to within 1 mm of the top in 0.83 s;
  - the four table motions locked by equal limits stayed exactly at their settings for 35 s.

## Update (2026-10-23): what holds the table's height
Researched for decision 0020 (`docs/research/2026-10-23-table-height-lock-and-mimic-chains.md`,
section 1).
- **In use, the lock handle holds it.** "Table Height Lock Handle: Loosens to allow adjustment of
  table position on column; tightens to lock table position" (manual, p. 7). The height is changed
  by loosening that handle, turning the crank, then tightening it "to secure" (p. 32). So the
  locked table's height, held by equal limits, matches the manual.
- **With the lock loose, not confirmed.** The free table's height is still held by equal limits,
  on the inference that the crank's worm holds it. The manual gives no lead angle for the worm, so
  whether it self-locks cannot be checked. And under "shock and vibration, the friction
  coefficient between worm and gear may suddenly drop", after which "back-driving can occur"
  (A. V. Karvelis, *Machine Design*, 2000, quoted in the note). It stays an inference and a known
  inaccuracy of `table_free` until a real T33901 or Grizzly settles it.

**Daniel's direction, the same day.** He found that the Garage Journal thread is about a 1950s
Craftsman drill press, model 103.23140, with a similar table mechanism, whose table fell once a lock
was loosened. He found no T33901 page on Grizzly's site. "Other drill presses seem to show that
behavior so it might be a safe assumption to assume the T33901 does as well unless otherwise stated
somewhere." So, from contract v0.2.0's drill press on (decision 0020):
- once its lock is loosened, the table's height is **free**, like its other three motions, and the
  table drops to the bottom of its travel;
- the check file `table_free` shows this. The equal limits that held the free height in run-002
  are gone;
- it is an assumption from a similar machine, logged as an inaccuracy in the twin, until a real
  T33901 or a source settles it.

**Seen in Isaac Sim (Daniel, 2026-10-24, run `2026-10-23_run-003`):** in `table_free`, "upon hitting
play the table does indeed drop". The assumption itself, that the real T33901's table drops, is
still not confirmed.

## Update (2026-10-31): a slide's spring on its pinion
When a turning joint follows a sprung slide by mimic (the T33901's handles and quill), the spring
is simulated on the turning joint. The acceleration drive scales by its own joint's parts only,
so the handles' inertia, reflected through the link, made the quill swing and bounce (decision
0025, "Isaac Sim check" and "Update (2026-10-31)").
