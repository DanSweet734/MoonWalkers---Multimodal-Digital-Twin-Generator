# Background removal on the lab's photos: a spike

**Question:** does the generator's background removal cut the lab's machines out of their photos
well enough to feed the multi-view model? The lab's machines plan, Phase 1, "A background spike".

**Answer: no, not as it is.** It fails on the TM-1, and is partial on the VF-3 and the arm. A
second fault turned up on the way: the generator did not turn phone photos upright. That one is
fixed.

## Method
- The 21 outside photos of the three machines (the arm's sides and corners, the mills' outsides;
  not the tops, insides or nameplates), from `data/machines/*/inputs/photos/` (their
  `SOURCES.md`).
- The generator job's own steps (`generators/scripts/hunyuan3d_shape_job.py`): `_open_upright`,
  then hy3dgen's `BackgroundRemover`, which is rembg 2.0.68 with its default `u2net` model, from
  `C:\mw-gen\models\u2net` as the generator sets it (`U2NET_HOME`).
- Each photo scaled to 1600 px on its long side first (rembg works at 320 px, so this changes
  little and saves time [INFERENCE from rembg's u2net session]).
- Script and outputs: `data/scratch/2026-11-09_background-spike/` (`spike.py`, `out/<machine>.jpg`
  with each cut-out on grey, `out/masks.csv` with the share of each photo kept). Run with the
  generator environment's Python; nothing installed.

## The orientation fault, fixed
19 of the 29 photos are stored sideways with EXIF orientation 6 ("rotate 90°"), which a phone writes
for a portrait photo. The job opened them with `Image.open` alone, so the generator would have
seen them on their sides. The drill press's photos were PNGs with no EXIF orientation, which is
why this never showed. The job now opens each photo with `ImageOps.exif_transpose`
(`_open_upright`), and everything downstream reads the job's upright `prepared/` PNGs. In the
spike, every orientation-6 photo came out portrait (1200 x 1600).

## Results
| Machine | Photo, view | Kept | What the cut-out holds |
|---|---|---|---|
| Arm | `133252`, operator_left | 7.5% | The arm, the hand faded; the e-stop and base plate kept |
| Arm | `133306`, front | 12.5% | The arm and hand; the e-stop and a box in front kept |
| Arm | `133317`, operator_right | 12.2% | The arm, the hand lost |
| Arm | `133326`, back | 13.5% | The arm and base plate; the e-stop and cables kept |
| Arm | `133342`, front_operator_right | 9.2% | **Fails:** the foam box in front kept, the arm mostly lost |
| Arm | `133352`, front_operator_left | 7.8% | The arm and the e-stop, the hand lost |
| Arm | `133402`, back_operator_right | 16.7% | The arm, the e-stop and a box |
| Arm | `133414`, back_operator_left | 18.2% | The arm and base plate, the hand lost |
| TM-1 | `134300`, front_operator_left | 12.0% | The head; the table and guards ghosted |
| TM-1 | `134314`, front | 0.1% | **Fails:** almost nothing |
| TM-1 | `134322`, back | 22.1% | **Fails:** the sign in front, not the machine |
| TM-1 | `134329`, back | 24.0% | **Fails:** the sign and one guard |
| TM-1 | `134337`, front_operator_right | 0.3% | **Fails:** almost nothing |
| TM-1 | `134346`, operator_left (to check) | 23.9% | **Fails:** one side guard only |
| TM-1 | `134355`, back_operator_left (to check) | 23.5% | **Fails:** the electrical cabinet only |
| VF-3 | `133735`, front | 13.6% | The doors only |
| VF-3 | `133749`, front_operator_left | 31.8% | **Good:** the enclosure, its shelf and tray |
| VF-3 | `133812`, operator_right | 30.6% | The side, with the monitor in front of it |
| VF-3 | `133826`, back_operator_right | 24.2% | The side and cables, faded at the back |
| VF-3 | `133831`, back_operator_right | 29.4% | The corner, with cables |
| VF-3 | `133846`, back_operator_left | 10.9% | The side faded, the back lost |

Why [INFERENCE]: u2net keeps the most salient object. In the lab that is often something in front
of the machine (a sign, a box, a monitor), or one large flat panel of the machine. The drill
press's photos were catalogue and manual pictures on plain backgrounds.

## Options
The job already skips background removal for a photo that has transparency, so any of these can
feed a cut-out without changing the generator.

| Option | What it takes | Install | Licence |
|---|---|---|---|
| A. Crop boxes per photo in `request.json` | A box per photo, then u2net inside it. Cannot remove what stands in front of the machine (the TM-1's sign, the arm's e-stop) | None | |
| B. Box-prompted SAM, already in rembg 2.0.68 (`sam` session, `sam_vit_b_01ec64`) | A box around the machine per photo, plus points to add or drop a region. rembg takes `"rectangle"` and `"point"` prompts (`rembg/sessions/sam.py`) | Weights only, downloaded by rembg into `C:\mw-gen\models\u2net`: encoder 359,217,310 bytes and decoder 16,500,570 bytes, or the quantised pair 108,836,115 and 8,755,366 bytes (GitHub release `danielgatis/rembg` v0.0.0, sizes from HTTP HEAD, 2026-11-09) | SAM: Apache-2.0 (`facebookresearch/segment-anything`); rembg: MIT |
| C. BiRefNet in rembg (`birefnet-general`) | A stronger salient-object model; still keeps whatever is most salient, so it may fail where u2net fails on the TM-1 [INFERENCE] | Weights only: 972,666,916 bytes, or the lite one 224,005,088 bytes | MIT (`ZhengPeng7/BiRefNet`); rembg: MIT |
| D. Masks drawn by a person | Daniel cuts each fed photo out in an image editor, saved as a processed PNG under the run (`data/README.md`: "save processed versions under `runs/`") | None | |

**Recommended: B, the quantised pair (about 118 MB).** It is the only option that follows a box
and points, so it can leave out the sign, the e-stop and the monitor. It needs no new package, and
the box and points can live in `request.json` beside each photo's view, so a run stays repeatable
(an amendment to decision 0022). Option A is a subset of it. D is the fallback if SAM's masks are
poor.

## Sources
Accessed 2026-11-09.
- rembg 2.0.68 as installed in `C:\mw-gen\hunyuan3d-2\.venv` (`rembg/sessions/sam.py`,
  `birefnet_general.py`, `birefnet_general_lite.py`), and https://github.com/danielgatis/rembg
  (MIT)
- https://github.com/facebookresearch/segment-anything (Apache-2.0)
- https://github.com/ZhengPeng7/BiRefNet (MIT)
- The weights' sizes: HTTP HEAD on
  `https://github.com/danielgatis/rembg/releases/download/v0.0.0/<file>`
