# 0037 - The hand's fingers and joints: stand-ins on the maker's frames, parts that pass through each other, and mimic followers that clear their reach

- **Status:** accepted by Daniel on 2026-11-17 ("decision 0037 and 0038 seem good, let's accept
  them"), after his Isaac Sim checks of v4 and v5 (the lab's machines plan, Phase 7; PR #34)
- **Date:** 2026-11-17
- **Decided by:** team (Daniel), proposed by Claude Code
- **Applies:** decisions 0020 (`follows`), 0023 and 0024 (cut lists and stand-ins), 0031 (the
  photographed pose as 0), 0032 (`hold_drive`, `self_collision`)

## Context
Phase 7 gives the arm's hand, one fused part in `igus/rebel6dof02@v3`, its 21 joints (5
following). Three questions came up:

1. **Its geometry.** The generated hand contradicts the photos: no shell, four tubes from the
   wrist to the tips, two thumbs, 155 mm long where LinkerBot's model is 260 mm (worklog
   2026-11-17). Daniel's answer on the plan's review (question 4): "If they can't be modeled from
   the input photos then stand ins will have to do"; the maker's meshes are not imported.
   Which model the stand-ins follow: `docs/research/2026-11-17-l20-hand-sdk-and-models.md`.
2. **Collisions inside the hand.** With `self_collision` "on" (decision 0032), every part
   collides as one convex hull. A box the size of a link's bounds is larger than the link, so
   neighbouring fingers and the thumb would stop each other short of the poses the SDK commands.
3. **The followers blew up** in Daniel's check of v4: joint positions to about 1e36, then NaN,
   when a leader reached the end of its range, when the thumb was dragged, and in `spin.usdc`.
   Headless trials in Isaac Sim 6.2 reproduced it and tried variants (worklog 2026-11-17).

## Options considered
**Geometry**
1. Cut the fingers from the generated mesh: matches nothing in the photos; the generator's
   hand is wrong in count and size.
2. Import the maker's meshes: closest in shape, but the checklist and Daniel's answer rule it
   out, and the twin would no longer come from the photos.
3. **Labelled stand-ins:** the palm and the 21 links as boxes sized from LinkerBot's link
   meshes' bounds (read, not imported), posed by its joint frames and placed on the generated
   adapter disc, the only generated part kept.

**Collisions inside the hand**
1. Leave them on: the box hulls jam before the SDK's poses.
2. Per-finger groups: fingers would still meet the thumb's oversized boxes.
3. **One group whose parts pass through each other** (`collide_apart` in the spec, new), still
   colliding with the arm and everything else.

**Followers**
1. A soft mimic (NVIDIA's Inspire hand uses `naturalFrequency` 25, `dampingRatio` 0.005): in
   trials our light links' followers wandered to 82° from a planned 62°.
2. No speed cap on a follower: held for typed targets, but `spin` still blew up at 2.17 s.
3. **No speed cap and limits clear of the coupling's reach**, as the Inspire hand's followers
   are (-19.5 to 116.9° against a reach of 0 to 97.4): held everything, at 10° and at 2°.

## Decision
- **The hand is labelled stand-ins on LinkerBot's right L20's frames** (option 3): the palm and
  21 links, the model's joint names, axes, origins and limits (`thumb_joint0`... and the five
  mimic followers, ratios from the URDF), each limit shifted by the photographed pose (decision
  0031: `thumb_joint0` -0.297 rad, at its lower limit; `thumb_joint1` 0.35 rad, read from the
  photo overlays [INFERENCE]). Its hold is the twin's (decision 0032).
- **The spec's `collide_apart`**: a list of groups (`parts`, at least two, and a `why`), needing
  `self_collision` "on". The exporter filters each pair within a group; everything else still
  collides. v5 has one group: the palm and the 21 links.
- **Every mimic follower is written without a speed cap of its own and with limits at least
  2° (2 mm) beyond its leader's reach** (`ratio * the leader's limits + offset`), widened only
  where needed (`MIMIC_CLEARANCE`, `_with_mimic_clearance` in `usd/exporter.py`). The contract's
  limits stay in the joint's provenance; the widening is in its export note.

## Consequences
- `igus/rebel6dof02@v5` (run `2026-11-17_run-002`): 30 parts, 27 moving joints in one
  articulation (6 of the arm, 16 driven and 5 following of the hand). **Level 2 met** (Daniel,
  2026-11-17): every typed joint reached its cited ends within 0.15°, the followers within
  0.04°, no NaN; the hand's size, proportions and pose match the photos (his check of v4, the
  same geometry).
- **Logged inaccuracies:**
  - the fingers are boxes, larger than the real links, and pass through each other: Daniel saw
    the thumb pass through the fingers in the fist (2026-11-17). The maker's own meshes at the
    SDK's fist preset overlap too (the research note, section 4), so collisions between the
    thumb and the fingers would stop the twin short of the preset where the real hand stops on
    contact [INFERENCE];
  - right hand and LinkerBot's model, until the visit list's item 14;
  - the thumb's roll in the photographed pose (0.35 rad) is read from the photos, not measured;
  - masses are the placeholder density's (decision 0024).
- The drill press's followers already cleared their reach (2.7 to 2.9°), so its files are
  unchanged by the mimic rule; a test covers both cases. A future twin with mimic followers
  gets the rule without asking.
- **To reverse:** closer collisions need shapes nearer the links (a convex decomposition, an
  install to be asked for first, or several boxes per link); then the group can shrink to the
  pairs that truly touch. Isaac Sim's soft mimic could be revisited with heavier links.
