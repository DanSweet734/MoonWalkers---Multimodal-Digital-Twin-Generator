# 0034 - A mill's axes from its photos: the fed views, stand-in carriages, the pose and the slide check

- **Status:** proposed by Claude Code in the lab's machines plan, Phase 4 (2026-11-11), for
  Daniel's review with his Isaac Sim check of `haas/tm1@v2`.
- **Date:** 2026-11-11
- **Decided by:** team (Daniel), proposed by Claude Code
- **Applies:** decisions 0012 (the twin frame), 0022 (views and the corner grid), 0023, 0027 and
  0028 (cut lists, stand-ins, the spec), 0029 (cut-outs), 0031 (position 0 is the photographed
  pose), 0032 (`hold_drive`, `loose_pieces`, `self_collision`)

## Context
Phase 4 builds the lab's Haas TM-1 (made 11/06) from its photos: the frame, the axes' carriages,
the head, the spindle and the tool carousel, each axis through its cited travel (plan, Phase 4;
sources in [the research note](../research/2026-11-11-haas-tm1-sources.md); the build in the
[worklog of 2026-11-11](../worklog/2026-11-11.md)). A mill raised five questions the drill press
and the arm did not:

1. **Which photos to feed.** The plan says the four corners. The back right one (`134329`) is
   hidden below about 60% by a sign and a stool and shows the pendant's back close up. In a trial
   with all four, the generator put the pendant at the back right and grew stray columns; with
   the other three it put the guards, the carousel, the head and the pendant where the photos
   have them (`data/machines/haas-tm1/part_cutting/2026-11-11_spec/trials_from_corners.png`).
2. **The carriages.** The generator made the table, the saddle and the chip guard as one piece,
   its table 1.016 m long against the cited 47.75 in (1.213 m), -16%. No round spindle can be told
   in the head, and the carousel is a plain disc.
3. **The pose.** Decision 0031 makes position 0 the photographed pose. On a mill the photos give
   it only in part: the front photo `134314` puts the spindle nose about 10 in over the table and
   the table near its operator-left end of X, but nothing shows where the saddle stands in Y.
4. **The hold.** The default drive (stiffness 100) would let the head sag g / 100 = 98 mm on Z.
5. **The check.** The build's check files spin driven turning joints; nothing ran a driven
   sliding joint through its travel, so a mill's ranges could not be recorded, and the scorer
   read only turning joints.

## Options considered
1. **Feed the four corners, as planned.** Follows the plan; the mesh contradicts the photos (the
   pendant at the back), and the masks cannot recover what the sign and the stool hide.
2. **Feed the three corners whose machine is visible** (front left, front right, back left).
   The mesh follows the photos; the back right is the generator's guess. Chosen.
3. **Cut the carriages from the generated piece.** Shows the generator's work; the table would be
   16% short and the saddle has no edge in the mesh to cut along.
4. **Stand-ins for the saddle, the table with its chip guard, the spindle nose and the carousel**,
   placed and sized from the cited facts and the photos, each labelled, with its uncited sizes
   logged (decision 0027 and Daniel's rule for visible parts). The head is cut from the mesh: it is
   a clear slab before the column. Chosen.
5. **The pose:** where the photos give an axis's place, use it (Z from the front photo; X so
   that the table's left end sits just inside the generated left guard, near where the photo puts
   it); where they do not, the middle of the travel (Y), logged as not measured. Chosen.
6. **The hold:** decision 0032's arm hold (10000, 200) leaves about 1 mm of sag on Z, at the
   scorecard's limit; 100000 and 632.5 (w = 316 rad/s, critically damped) leave about 0.1 mm.
   The stiffer one is chosen, untried on a mill: Daniel's check decides.
7. **A slide check in the build**, the twin of the spin check: `checks/slide.usdc` runs each
   driven sliding joint from its lower limit to its upper one at its cited top speed (else
   25 mm/s), with a velocity drive whose damping (10000) carries a slide's weight (speed error
   g / damping, about 1 mm/s). The scorer reads a sliding joint's recording in millimetres
   against the scorecard's 1 mm. Chosen; the alternative, setting each axis's target by hand in
   the Property panel, is not recorded end to end.

## Decision
A mill's twin is generated from the photos in which the machine is visible, every one of the
plan's views it leaves out logged with why. Its axes' carriages, its spindle nose and its tool
carousel are labelled stand-ins where the mesh gets them wrong or does not show them, and its
head is cut from the mesh. Position 0 is the photographed pose where the photos give it, else the
middle of the travel. Driven joints hold with stiffness 100000 and damping 632.5. Every build
with driven sliding joints writes `checks/slide.usdc`, and the scorer measures sliding joints'
ranges in millimetres.

## Consequences
- **`haas/tm1@v2`** (run `2026-11-11_run-002`) applies it; v1 (run `2026-11-11_run-001`) is the
  same build without the slide check, stored before the build learned it.
- **Logged inaccuracies** (in the twin and `RUN.md`):
  - the back is the generator's guess;
  - the generated guards stand about 4 in closer in than in the front photo, so at X's left end
    the table passes about 2 in into the left guard (parts do not collide, `self_collision`
    "off");
  - Y's photographed place is not measured;
  - which way Haas's +X and +Y move is not confirmed;
  - the overall height is 24% under the cited 109 in, which the front photo agrees with
    [INFERENCE].
- **The VF-3 (Phase 6)** reuses all of it: its photos are busier, and its trunnion sits on the
  table, so the table stand-in is where the trunnion goes.
- **Phase 5's programs** drive these joints: the hold's lag on a moving target is about
  damping / stiffness x speed = 0.0063 s x 84.7 mm/s = 0.5 mm at a rapid [INFERENCE from decision
  0033's arm], inside the scorecard's 1 mm.
- **The build's change is general:** any twin with a driven sliding joint now gets
  `checks/slide.usdc`; the drill press's quill is spring-return and its table locked, so its
  checks are unchanged (tests).
- **To reverse:** feed the four corners and cut the carriages from the mesh in a new run; drop
  `slide.usdc` from `pipelines/b/build.py`.
