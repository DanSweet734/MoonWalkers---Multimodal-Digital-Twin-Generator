# 0012 - Pipeline B: from one photo to a scaled body and spindle

- **Status:** accepted for the PoC (proposed by Claude Code in Phase 3; Daniel chose the spindle split
  on 2026-10-17, then reviewed PR #6 and checked the twin in Isaac Sim on 2026-10-18)
- **Date:** 2026-10-17
- **Decided by:** team (Daniel)
- **Amends:** decision 0010 (twins with generated meshes are written as binary `.usdc`)

## Context
The generator (decision 0011) returns one closed mesh with no joints, no scale and its own axes
(+Y up, front facing +Z, about 2 units across). The twin needs a fixed body and a spindle on a
revolute joint, in metres with +Z up (decision 0010). Every number in it must trace to a source
(CLAUDE.md rule 1). `docs/poc-plan.md` allows a "manual or semi-automatic" split for the PoC if the
method is documented. That is this record. Sources and measurements are in
`docs/research/2026-10-17-ha5c-photo-to-twin.md`.

## Options considered
1. **Who decides how to orient, split and scale.** (a) Fully automatic: none of the articulation
   tools reviewed in project-context Topic 13 names industrial machinery as a test domain, and none
   is installed; (b) an inspection step, in which the agent or a
   person looks at rendered views and measurements and writes a small **geometry spec** that the
   twin cites; (c) editing meshes by hand in Blender, which leaves no machine-readable record.
2. **Finding the spindle axis.** (a) Pick it by eye; (b) the centre of the vertices in thin slabs
   behind the nose tip, checked by a radial profile along the axis; (c) fit circles to slices.
   (b) is simple and shows its own consistency: slabs of three depths should agree.
3. **Splitting.** (a) Cut with a plane and cap the hole; (b) take every face whose centre lies
   within a radius of the axis and in front of a cut plane (a cylinder); (c) learned part
   segmentation. (b) keeps the generator's faces as they are, but leaves open edges at the cut.
   Moving parts use convex-hull colliders (decision 0010), so open edges do not affect physics.
4. **What turns with the spindle.** The photo shows a black disc with six cap screws around the
   threaded nose. (a) Only the nose turns; (b) the disc and the nose turn. Evidence for (a), from the
   2006 manual: its parts list has six "SHCS 1/4-20 X 1" and six "WASHER 1/4 COPPER", plus a
   "SPINDLE COVER S5C" and a "BEARING END CAP" (PDF p. 53). Its maintenance figure labels a "Front
   Seal" and a separate "Front Spindle Seal" (PDF p. 50). Evidence for (b): a chuck "seats against
   the rear of the spindle" (PDF p. 18), and in the mesh the disc's face is the only shoulder behind
   the nose. That the nose turns is stated: "Chucks and face plates utilize the 2 3/16-10 threaded
   nose on the spindle" (PDF p. 18).
5. **Scale reference.** (a) The centre height, 4.000 ± .001 in. The drawing, the manual ("Height
   4.000 ± 0.001 from spindle center to base") and the Haas UK page all give it. (b) The overall
   width: the text says only where a dimension sits on the page, not what it spans. (c) A
   least-squares fit to several dimensions, all of which would need interpreting first.
6. **Where machine facts come from.** (a) Only from the photo: the photo gives none; (b) cited
   reference facts that the agent read in documents, carried in Pipeline B's result as in the
   team's illustrative fixture (`backend/tests/fixtures/ha5c_pipeline_b.example.json`).
7. **Re-runs.** (a) Overwrite a run folder's outputs; (b) reuse them when the inputs match and refuse
   when they differ.
8. **File format.** (a) Text `.usda` (decision 0010); (b) binary `.usdc`. NVIDIA's asset validator
   fails a text layer whose arrays pass 64 elements, saying they "should be stored in crate files
   for improved performance". Twin v1 (40,000 faces, 6.4 MB of text) hit this.

## Decision
- **Inspection step (1b).** `GeometrySpec` (`backend/src/moonwalkers/pipelines/b/assemble.py`)
  holds:
  - `up` and `front`: generator axes;
  - `spindle_axis_yz`, `spindle_radius` and `spindle_start_x`: model units, after orienting;
  - `base_z`: optional; the lowest point if omitted;
  - `center_height_m`, `decided_by` and `method`.

  It is saved as `geometry_spec.json` in the run folder and becomes a source of the twin, with its
  SHA-256. Until the spec exists, the pipeline renders views and stops (`GeometrySpecMissing`). The
  command `python -m moonwalkers.pipelines.b inspect` renders and measures the mesh, and
  `--preview` tries a draft spec without storing anything. In Phase 4 the agent writes the spec
  through an MCP tool.
- **Twin frame.**
  - Metres, +Z up, the machine's front (spindle nose) facing +X, so its width runs along Y.
  - The origin is on the base plane, directly under the spindle axis, at the cut plane. The spindle
    axis is therefore the line y = 0, z = centre height, and the joint origin is
    (0, 0, 0.1016) m about +X.
  - Meshes are written already in this frame (GLB). Part transforms stay at identity, as decision
    0010 requires.
- **Axis (2b):** `tip_slabs` takes the y-z bounding-box centre of the vertices within 0.01, 0.03 and
  0.06 units of the front-most point. The spec uses the middle slab. `radial_profile` then shows how
  far the surface reaches from that axis along +X.
- **Split (3b):** `split_by_cylinder` by face centre.
- **Spindle (4a):** the nose only. Daniel chose this on 2026-10-17 after seeing both previews. It is
  labelled `[INFERENCE]` in every result, as a warning.
- **Scale (5a):** scale = centre height / (axis z - base z). If the reference facts cite a
  `center_height`, the spec's value must equal it, so the scale always traces to a document.
- **Reference facts (6b):** `ReferenceFacts` JSON with sources, identity, facts, control and issues.
  Every citation must name one of its own sources. For the HA5C:
  `backend/src/moonwalkers/pipelines/b/haas_ha5c.reference.json`. Short quotes give the page or the
  drawing view. `±` and `°` are restored where pypdf could not decode them (research note).
- **Size checks:** the assembled model's overall depth (x), width (y) and height (z) are compared
  with any cited `overall_depth`, `overall_width` and `overall_height`. A difference above 10% is a
  warning, otherwise information. The 10% threshold is our choice [INFERENCE].
- **Joint confidence:** 0.6, our judgment of the measured axis and position [INFERENCE].
- **Run folders (7b).** One folder per build (`data/machines/<machine>/runs/<run>`):
  - `generator/run.json` keys the mesh to the photo's SHA-256 and the generator's fingerprint;
  - `meshes/assembly.json` keys the parts to the mesh's and the spec's SHA-256;
  - matching keys are reused, other keys are refused (`RunFolderConflict`);
  - a folder that already holds an exported twin is refused.

  A new version (`new_version: true`) is built in a new run folder.
- **Format (8b):** Pipeline B writes `twin.usdc`, plus `checks/spin.usdc` and
  `checks/quarter_turn.usdc` for the Isaac Sim check. `export_twin` still writes `.usda` for small
  twins such as the Phase 2 test twin.

### Values used for the HA5C (runs 2026-10-17_run-002 and run-003)
Model units after orienting (+Y up and +Z front become +Z up and +X front):

| Spec field | Value | From |
|---|---|---|
| `up`, `front` | `+y`, `+z` | Inspection views |
| `spindle_axis_yz` | (0.0757, 0.0030) | Tip slab 0.03; slabs 0.01 and 0.06 agree within 0.0004 |
| `spindle_start_x` | 0.42 | The disc's front face is at x = 0.4125 (area-weighted); the nose starts at 0.42 |
| `spindle_radius` | 0.22 | Between the nose (r 0.16-0.17) and the disc (r 0.28) |
| `base_z` | lowest point, -0.5338 | A flat area of 0.38 square units under the casting; the motor housing's bottom sits higher, at -0.48 |
| `center_height_m` | 0.1016 | The cited 4.000 in |

Result: 0.189268 m per model unit, with an axis height of 0.5368 units. The size checks give:
- width: -3.0% (cited 15.32 in, fact confidence 0.7);
- height with the handle: -3.0% (cited 8.3 in, fact confidence 0.8);
- depth: +7.9% (cited 7.93 in, fact confidence 0.4; which dimension it is was inferred from where
  its text sits on the drawing).

## Consequences
- Re-running a build costs nothing: the generator and the assembly are reused. A second request
  reaches the stored twin either by naming the machine or with the same photo.
- A person or the agent is in the loop for every new machine's spec, as the PoC's human review
  expects. The spec is short, cited and reviewable.
- The split method assumes one spindle along the machine's front axis, as on the HA5C. The backup
  drill press has several joints, some prismatic, so it would need a richer spec (more parts, more
  joint types).
- Both parts have open edges at the cut, and the hidden faces are the generator's guesses. Masses
  are placeholders (decision 0010).
- If the six-screw disc does turn on the real machine, the fix is a spec with radius 0.31 and start
  0.281 in a new run folder, built as a new twin version.
- Twins with generated meshes are binary, so reading their provenance needs a tool (`usdcat` or
  pxr) rather than a text editor. The run folder keeps `pipeline_result_b.json` and
  `twin_record.json` as plain JSON copies.

## Isaac Sim check (2026-10-18)
Daniel checked twin v2 in Isaac Sim 6.2.0 (worklog 2026-10-18; `RUN.md` of run-003):
- **Level 2 reached.**
  - Sizes measured by hand are close to the expected ones.
  - The spindle turns at the drive's speed and reverses when the target changes.
  - The quarter turn settles in under a second and holds.
- **Collisions.** None between the overlapping hulls: no shaking, drift or push.
- **Sizes by hand.** 14.89 in wide and 8.04 in tall, against 14.87 in and 8.05 in computed.
  Daniel reads the drawing's 15.32 in as the full width, motor end to lever tip, so the -3.0% width
  check compares like with like. The reference facts now cite his reading, and the next build
  carries it.
- **Seam gaps.** After the spindle turns, small black gaps show at the seam. The shared cut edge's
  outer ring lies 30.4-32.7 mm from the axis, because the generated nose is slightly out of round.
  After a 90 degree turn the spindle's edge is 1.1 mm (median) and up to 2.8 mm from the body's, and
  the hollow insides show through. This comes from option 3b's "leaves open edges at the cut" and is
  cosmetic.

  If the seam matters later, the candidates are:
  - cut with a true cylinder and plane and cap the cut faces (option 3a);
  - make the seam round.

  Either needs its own decision.
