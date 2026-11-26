# 0041 - Drawing and correcting a cut-out

- **Status:** accepted by Daniel on 2026-11-25, as it stands ("I accept decision 0041 as it
  stands"), after his check (below, "Daniel's check"). Drafted by Claude Code in the video plan's
  Phase 1 (2026-11-25); its shape was shown to Daniel before any code, and he chose the
  recommended option on its four open choices the same day: one ordered list of edits; the whole
  cut-out in the dashboard (method, box, points and edits); the API runs the cut-out preview
  only; the warnings listed without changing `clean` (options 2(a), 4(a), 5(a) and the warnings'
  last paragraph). He also confirmed that the agent offers to skip a cut-out the person does not
  want to draw (the procedure, step 2).
- **Date:** 2026-11-25
- **Decided by:** team (Daniel)
- **Amends:** decision 0029 (a cut-out gains drawn edits and an `auto` method) and decision 0014
  (the API may run the cut-out preview, never the 3D generator)

## Context
- **The advisors' ask** (meeting of 2026-11-19, [video plan](../video-plan.md), "What the advisors
  decided"): a cut-out drawing tool, then a second agent run. It closes gap 1 of the
  [lab report, section 8.3](../lab-machines-report.md): "No way to draw or correct a cut-out. SAM
  breaks into pieces with many points and keeps the neighbours with few; a drawn mask must be made
  outside the tools."
- **What v3 needed** (`haas/tm1@v3`, approved 2026-11-17): its masks were made by a script,
  `data/machines/haas-tm1/part_cutting/2026-11-11_spec/make_masks.py`. It starts from SAM's
  cut-out (the preview's prepared PNG, alpha at 128 and above), then draws, in fractions of the
  upright photo and in this order:
  - `FILL` polygons, where SAM lost the machine (its shiny guards, the table, the pendant):
    19 polygons over the four photos;
  - `TUBE` lines with a width (`draw.line(..., width=int(width * w), joint="curve")`): the cable
    conduit from the cabinet to the head, one per photo, 0.014 to 0.025 of the photo's width;
  - `ERASE` polygons, where SAM kept the room: two ceiling rafters on `photo-134355`.

  The run then fed each mask with `method: "mask"` and `min_piece` 0.1 (`tm1_request.py`).
- **What v4 lacked** (`haas/tm1@v4`, rejected by Daniel 2026-11-18): the agent had SAM alone,
  its masks matched the photos less (IoU 0.61-0.77 against v3's 0.75-0.84, the report's
  Phase 8 section), and the twin kept a pedestal, shards and holes.
- **Where the code stands** (the plan's Phase 1 hand-off): the mask is made in the generator's job
  script (`generators/scripts/hunyuan3d_shape_job.py`, `Cutter.__call__`), in `C:\mw-gen`'s
  environment, the only one with Pillow. The backend validates (`orchestrator/photos.py`,
  `Cutout`) and keys the run on the settings (`pipelines/b/pipeline.py`, `_cutouts`). The API
  "never runs the generator" (`api/jobs.py`'s docstring; decision 0014, option 1(c) not taken),
  and nothing in it writes a photo's `cutout`.

## Options considered
1. **What a person or the agent draws.**
   - (a) **Edits on top of any cut-out**: polygons that add or remove, and lines with a width
     that add or remove, applied to the mask SAM, the crop, the automatic removal or a drawn PNG
     made. What make_masks.py did, inside the tools.
   - (b) Polygons only: v3's conduits would have to be traced as thin polygons (both edges of a
     curved tube), and its masks are not reproduced exactly.
   - (c) A brush that paints a PNG mask (`method: "mask"`). Nothing new in the request, but the
     agent cannot paint, the PNG is a second file to keep beside the request, and a mask from
     SAM is not easily touched up after the box moves.
2. **How the edits combine.**
   - (a) **One ordered list, the later edit wins** where two overlap. A person who cuts out a
     region and then adds back a piece of it gets what they drew, as in a paint program; v3's
     order (fills, tubes, erases) is one such list.
   - (b) Two lists, `add` then `remove`, so a removal always wins. Simpler to read, but an added
     piece inside a removed region cannot be drawn; the removal must be reshaped round it.
3. **A base for the edits when no method suits.**
   - (a) **A new `auto` method**: the automatic removal (u2net) that a photo with no cut-out gets,
     named so edits can go on it. An `auto` cut-out with no edits is refused: leave `cutout` out.
   - (b) Edits only on `sam`, `crop` and `mask`. A dashboard job's photos start with no cut-out,
     so a person would first have to choose and place a SAM box.
4. **Where a person draws.**
   - (a) **The dashboard's job page** (the plan's proposal): each fed photo with its cut-out
     tinted over it; a person places the box and SAM's points, draws edits, saves, and runs the
     preview to see the real mask.
   - (b) Edits only in the dashboard, with the box and points still set by the agent or by hand
     in `request.json`. Less to build; a person cannot start a cut-out alone.
5. **Who runs the cut-out to show the real mask.**
   - (a) **The API runs the preview** (`cutout_only`, the job script's step 1: SAM or u2net on
     the fed photos, seconds, no 3D model loaded) when `MOONWALKERS_GEN_ROOT` is set; without it,
     the dashboard shows the last preview and says how to run one. The GPU-heavy 3D generator
     stays with the agent (decision 0014, 1(a)).
   - (b) The API never runs it: the dashboard draws the edits over the last preview made by the
     agent or the command line, and a person asks for a new one there.

## Decision (proposed)
1(a), 2(a), 3(a), 4(a) and 5(a):
- **The setting.** A cut-out (`orchestrator.photos.Cutout`) gains `edits`, an ordered list of:
  ```json
  {"op": "add" | "remove", "points": [[x, y], ...], "width": null, "note": "the pendant"}
  ```
  - without `width`: a polygon, 3 points or more;
  - with `width`: a line through 2 points or more, `width` a fraction of the photo's width
    (make_masks.py's unit), above 0 and at most 0.2 [INFERENCE: wider is a polygon];
  - `note`, optional: what the edit covers, for the record (make_masks.py's comments);
  - points in fractions of the upright photo, as boxes and points are (decision 0029, 3(a));
  - at most 200 edits and 500 points per edit [INFERENCE: v3's busiest photo has 10].

  `method` gains `auto`, which takes no box, points or mask and needs at least one edit.
  `mask` takes edits too.
- **The mask.** In the job script, after the method's mask (SAM's, the crop's, u2net's or the
  file's) and before `min_piece`: each edit is drawn in order with Pillow's `ImageDraw` (a polygon
  filled, a line with `joint="curve"`), 255 to add and 0 to remove, as make_masks.py drew them.
  The job also writes each final mask as `masks/<photo>.png` beside `prepared/`, small enough for
  the dashboard to load.
- **The record.** Edits are part of the cut-out's settings, so they enter the reuse key and the
  generator record as they are (decision 0029): another edit is another mesh, and a run that has
  generated refuses it. A cut-out without edits is keyed exactly as before.
- **The preview.** `preview_cutouts` and `... pipelines.b cutouts <run>` draw each edit's outline
  on the sheet (green to add, red to remove), and say how many edits each photo has. With
  `--compare <folder>`, the command line also prints each mask's IoU against `<folder>/<photo>.png`
  (Phase 1's check against v3's masks); the job computes it, where Pillow is.
- **The agent.** `set_photo` takes the same `cutout` with `edits`. The procedure (step 2): where
  SAM still keeps a neighbour or loses a part after a few boxes and points, ask the user to draw
  the cut-out in the dashboard, with the option to skip (Dr. Li's rule, 2026-11-05); the agent
  may draw a large, plain edit itself [INFERENCE: it places polygons poorly by eye on a busy
  photo, the plan's Phase 1].
- **The API.**
  - `PUT /api/jobs/{machine}/{run}/photos/{source_id}/cutout` (a `Cutout`, or null to clear):
    through `Workspace.set_photo`, the photo's view and use kept, with its checks (a run that has
    generated or been built refuses).
  - `POST /api/jobs/{machine}/{run}/cutouts`: runs the preview into `<run>/cutouts/`, as
    `preview_cutouts` does; 503 with the command to run when `MOONWALKERS_GEN_ROOT` is not set.
  - The job's photos show their cut-out and, when previewed, their mask's path and whether the
    preview is `current` or `stale` (the cut-out changed since); the job says whether its
    cut-outs can still change (`cutouts_editable`).
- **The dashboard.** On a job's page, while the run has not generated, each fed photo has
  "Edit the cut-out": the upright photo with the cut-away dimmed under the last preview's mask
  (the dashboard is black and white by rule: adds are solid outlines, removals dashed), and
  tools to choose the method, drag the box, click SAM's points (keep or leave out), draw add
  and remove polygons and lines, undo, save and preview. The drawing's pure geometry (fractions,
  hit tests, a polygon's closing, a line's outline) is in `dashboard/src/lib/cutout.ts` with
  tests. Between previews the edits are drawn over the mask in the browser, which is close to
  the job's mask but not it [INFERENCE: two rasterisers]; the saved and previewed mask is the
  record.

### With it: warnings for v4's faults (the plan's question 3, gaps 2, 3 and 9)
`preview_twin` (its `issues`) and `dry_run_twin` (a new `spec_warnings`) warn, from the spec and the
oriented mesh, when:
- **gap 2, a base on a small slab** (`ref` `base_z`): seen from above, the box round the kept
  faces that reach into the bottom 5% of the twin's height (from `base_z`, or the mesh's lowest
  point) is under 15% of the widest such box over the 20 bands of 5%. A face counts in every
  band it crosses, so a coarse mesh's tall walls count low down too. The figures are set from
  the built twins (2026-11-25, worklog), the bottom band as a share of the widest:

  | Twin | Bottom band | Warns |
  |---|---|---|
  | `haas/tm1@v4` (rejected, its 10 in pedestal) | 0.050 | yes |
  | the tests' box-and-cylinder drill press (its 18 x 10.5 in base, the handles wider) | 0.24 | no |
  | `igus/rebel6dof02@v3`, `@v5` | 0.663, 0.933 | no |
  | `haas/vf3@v1` | 0.613 | no |
  | `haas/tm1@v3`, `grizzly/t33901@v11` | 1.000 | no |

  15% is drawn between v4 and the drill press [INFERENCE: a real base can be a quarter as wide
  as the machine above it; a generated pedestal under a large machine is far narrower]. Setting
  `base_z` at the floor is not enough when the pedestal is still kept: the band is measured from
  `base_z`, so the pedestal still shows;
- **gap 3, shards where a moving part passes** (`ref` the cut part): a cut part whose
  `loose_pieces` is `keep` has loose pieces (all but its largest connected piece) with faces
  inside a stand-in that `replaces` a removed part. The stand-in is placed where it is modelled
  and at 9 steps along each sliding joint up its chain (every combination); turning joints keep
  their modelled pose [INFERENCE: v4's shards were in sliding parts' way]. Inside is the
  stand-in's exact shape (boxes, cylinders, the slotted table), computed directly: trimesh's
  `contains` needs `rtree`, which is not installed. The message gives both readings: shards to
  remove, or the stand-in passing into the machine. The fix is `loose_pieces: "remove"` or a cut;
- **gap 9, no size checks** (`ref` `size_checks`): a spec of several parts with no
  `size_checks`.

On the built twins (2026-11-25): v4 gets five warnings (its slab; shards of its frame inside the
stand-in table along its travel, 18 faces, in the saddle, 100, and in the carousel, 1; no size
checks), v3, the VF-3 and both arms none. The T33901 v11 (and v8) gets one: its frame's loose
pieces inside the stand-in crank with `table_height` at its lowest, the crank passing into the
base, a fault already logged ([drill-press report](../drill-press-report.md), "passes up to 4 cm
into the base"). Small synthetic fixtures shaped like v3's and v4's specs
(`tests/test_spec_warnings.py`) are quiet and warn. They do not change `clean`, which stays the
validators' verdict; the procedure has the agent fix each or record why with `add_issue` before
`submit_twin`.

### Checked against v3's masks
v3's three fed photos' masks, rewritten as edits on SAM's cut-out from make_masks.py's and
`tm1_request.py`'s own values (a script beside them,
`data/machines/haas-tm1/part_cutting/2026-11-25_cutout-tool/v3_as_edits.py`), previewed with
`--compare` against run `2026-11-11_run-003`'s `masks/` (16 s): IoU 0.999 (`photo-134300`, 8
edits), 0.992 (`photo-134337`, 11) and 0.997 (`photo-134355`, 5). The small differences are
expected [INFERENCE: make_masks.py drew on SAM's prepared PNG thresholded at alpha 128, and
its mask was then cut at `min_piece` 0.1 when fed; the job draws on SAM's mask and applies
`min_piece` 0.1 after the edits, so the compared mask is the fed one].

### Daniel's check (2026-11-25)
Daniel drew the TM-1's three fed photos in the dashboard on a scratch job
(`data/scratch/2026-11-25_cutout-tool-check/`, `docs/setup/dashboard.md` section 3b), in
"roughly 3 or 4 minutes" for all three (his estimate). On each he kept the automatic removal
and drew one large polygon to add around the whole machine, with polygons to remove inside the
conduit's loop: 4, 2 and 2 edits, against v3's 8, 11 and 5 over SAM. Against v3's masks:

| Photo | Edits | Kept | IoU against v3's mask |
|---|---|---|---|
| `photo-134300` | 4 | 54.0% | 0.879 |
| `photo-134337` | 2 | 48.9% | 0.933 |
| `photo-134355` | 2 | 66.7% | 0.873 |

Most of the difference is his outline's straight edges, which keep a little floor and the
coolant hose where v3's masks follow SAM's edge [INFERENCE, from the sheet]. Whether that
matters for the mesh shows only in a build: Phase 2's agent run is the next measure. The
plan set no target for this phase.

### The T33901's crank (Daniel, 2026-11-25)
The warning that fires on `grizzly/t33901@v11` is the crank passing into the base, a fault
known but not yet an issue in the twin. Daniel: log it as an issue in the T33901's next
version. The drill-press report's table of inaccuracies says so.

## Consequences
- **Easier:**
  - a person corrects SAM's cut-out in the dashboard in place of a script, and the agent can ask
    for it;
  - every edit is in `request.json`, so a run stays repeatable from its request;
  - v3's masks can be remade from their polygons, so the tool is measured against them.
- **Harder:**
  - drawing many polygons by hand takes a person's time (measured in Daniel's check);
  - the API now starts the generator environment's Python for previews (seconds, SAM's 118 MB
    weights, no GPU model), so the API and an agent's preview can overwrite the same
    `cutouts/` folder; the last one wins, as for two agents' previews today;
  - the request and the reuse key grow by the edits.
- **Not changed:** the pipeline contract; the generator's settings and fingerprint; a cut-out
  without edits, keyed and run as before.
- **To reverse it:** drop `edits` and `auto`; runs without them never used them.
