# HA5C from one photo: sources, generator findings and measurements (Phase 3)

**Question.** What public material, generator setup and method let Pipeline B turn the Haas HA5C
into a scaled, cited, jointed twin? How well does the result match the machine's documents?

**Dates.** Everything was read or measured on 2026-10-17, local time (PDT). Some times are given in
UTC, where they are already Oct 18. Decisions that use this note: 0011 (generator setup) and 0012
(Pipeline B method). Run details: `docs/worklog/2026-10-17.md`.

## 1. Inputs

### Photos
| Source | What happened | Used? |
|---|---|---|
| Haas US HA5C page, https://www.haascnc.com/machines/rotaries-indexers/indexers/models/ha5c.html | WebFetch got "HTTP 403 Forbidden". A plain request got a 5,574-byte page with no product images (a bot check). Not bypassed. (00:30 UTC) | No |
| Haas UK HA5C page, https://haas.co.uk/?p=2253 | One studio photo, `HA5C_2011.original.jpg`: 1600 x 1200, CMYK JPEG, a three-quarter view on white | **Yes** |
| Used-machine listing, machinehub.com 435029 | 14 images of one unit with a pneumatic collet closer, brackets and hoses, on a cluttered bench (seen in its photos) | No |
| Listings machinehub.com 440099, equipt.com 967276, surplusrecord.com | 1 image, 0 images, HTTP 403 | No |

### Documents
| File (in `data/machines/haas-ha5c/inputs/`) | Source URL | Identity |
|---|---|---|
| `documents/HA5C_Dimensions.pdf` | https://www.haas.co.uk/wp-content/uploads/2019/10/HA5C_Dimensions.pdf | "HA5C Layout Drawing, Revision B, September 17, 2013"; PDF title "HA5C Rev B.cdr"; 1 page |
| `documents/ha5c-operators-manual-2006.pdf` | https://www.haascnc.com/content/dam/haascnc/en/service/manual/operator/english---ha5c-indexer-operator's-manual---2006.pdf | "96-4039 rev N June 2006"; 53 pages |
| `photos/haas-uk_HA5C_2011.original.jpg` | https://www.haas.co.uk/wp-content/uploads/2019/10/HA5C_2011.original.jpg (image on the Haas UK page) | SHA-256 `5ba3c704...cbf1` |

`inputs/SOURCES.md` (local, gitignored) holds full hashes and retrieval times. The files were saved
between 00:32 and 00:35 UTC. They are copyrighted and kept for internal research only.

The Haas UK product page itself was read with WebFetch on 2026-10-17 at 01:58:41 UTC (earlier, in
Phase 1). WebFetch summarizes pages, so its quotes below were not checked against the raw HTML.

## 2. Facts read in the documents
All of them are in `backend/src/moonwalkers/pipelines/b/haas_ha5c.reference.json`, with the same
quotes and locators.

| Fact | Value used | Source, locator: quote |
|---|---|---|
| Identity | Haas Automation HA5C | Product page: "5C Collet Servo Rotary Head with Manual Collet Closer." Manual PDF p. 2: "The Haas HA5C digital indexing head is a fully automatic, programmable, rotary positioning device." |
| Centre height | 0.1016 m | Drawing, front view: `4.000±.001" (101.60±0.03 mm)`. Manual PDF p. 4: "Height 4.000 ± 0.001 from spindle center to base". Product page: "4.000 ± 0.001" |
| Maximum speed | 7.1558 rad/s (410 °/s) | Product page, Max Speed: "0.001 to 410 °/sec" (see the disagreement below) |
| Gear ratio | 60:1 | Manual PDF p. 4: "Gear Ratio 60:1 self locking worm gear (33:1 HA5CSB)". Product page: "60:1" |
| Spindle nose thread | 2 3/16-10 NS-2A | Drawing, side view: `SPINDLE NOSE 2 3/16-10 NS-2A`. Manual PDF p. 4: "Nose Thread 2 3/16 - 10" |
| Collets | 5C | Manual PDF p. 4: "Collets Standard 5C" |
| Overall width | 0.3891 m (15.32 in) | Drawing: `15.32" (389.1 mm)`. Which dimension it is: [INFERENCE], section 3 |
| Overall height | 0.2108 m (8.3 in) | Drawing: `8.3" (211 mm) INCLUDES REMOVABLE HANDLE` |
| Overall depth | 0.2014 m (7.93 in) | Drawing: `7.93" (201.4 mm)`. [INFERENCE], section 3 |
| Indexing program | G90/G91 steps, loops | Manual PDF p. 2: "The control can be programmed to rotate the spindle in a clockwise or counter-clockwise direction with step sizes from .001 to 999.999°. There can be 99 different steps stored in memory." and "You may store seven separate programs (Prog 0 - Prog 6)." PDF p. 34: "G90 and G91 are used to select absolute (G90) or incremental (G91) motion." and "The loop count display is three digits between 1 and 999 preceded by an L." PDF p. 4: "Resolution 0.001°" |

**The sources disagree on maximum speed.** The product page gives 410 °/s. The 2006 manual gives:
- "Speed Feed rate selectable from .001°/sec to 330°/sec" (PDF p. 4, specifications);
- "Variable from .001°/sec to 270°/sec (brush) to 320°/sec (Brushless), 725°/sec (HA5CSB)" (PDF
  p. 3, features);
- "a feed rate of .001°/sec up to 270°/sec (for rapid positioning)" (PDF p. 2);
- "The feed rate display ranges between 00.001 and 270.000" (PDF p. 34).

The twin uses 410 °/s, because the product page describes the HA5C sold today and is where the photo
comes from; the manual may describe older units [INFERENCE]. Found but not used yet: "Torque 60 ft-lb
brushless, 20 ft-lb HA5CSB (45 ft-lb, brush)" (PDF p. 4), for drive tuning in Phase 6.

**How the PDFs were read.**
- Text was extracted with pypdf 6.21.1 (`extract_text`); the drawing could not be viewed as an
  image, because no PDF renderer is installed.
- pypdf could not decode some glyphs (`±`, `°`, `©`, curly quotes), which come out as one unreadable
  character. The quotes restore them: `±` from the metric equivalents ("101.60±0.03 mm") and the
  product page's "4.000 ± 0.001", and `°` from the units.
- The drawing's stacked fraction comes out as `2 -10 NS-2A`, `3`, `16`; it reads 2 3/16-10 NS-2A,
  as the manual's "2 3/16 - 10" confirms.
- Manual page numbers: PDF page n is printed page n - 1. For example, PDF p. 4 begins
  `396-4039 rev N June 2006`: printed page 3, then the document number. The locators give both.

## 3. Which drawing dimension is which [INFERENCE]
All text on the drawing is horizontal, so its direction says nothing. pypdf's text positions do
show which view each number sits in. Positions are in points on a 792 x 1224 page, with the origin
at the bottom left:

| Text | Position | Nearest view label |
|---|---|---|
| `7.93" (201.4 mm)` | (454, 922) | "Top View" at (308, 854), the only label nearby |
| `15.32" (389.1 mm)` | (284, 560) | "Front View" at (304, 535), just below it; the widest dimension under that view |
| `8.3" (211 mm) INCLUDES REMOVABLE HANDLE` | (21-41, 699-739) | Front view, left side |
| `4.000±.001" (101.60±0.03 mm)` | (109, 650-660) | Front view, left side |
| `7.38" (187.5 mm)` | (72, 674-684) | Front view, left side (probably the body height) |
| `SPINDLE NOSE 2 3/16-10 NS-2A` | (459-477, 733-745) | "Side View" at (622, 548) |
| `7.80"(198.1 mm)` | (714, 694) | Side view; not identified |

In third-angle projection the front view's horizontal dimensions are widths and the top view's
vertical dimensions are depths. So 15.32 in is read as the overall width and 7.93 in as the overall
depth. Whether 7.93 in includes the spindle nose is not known. The manual's own dimension figure
(PDF p. 5) lists the same values (15.32, 7.931, 7.80, 7.375, 4.000) and could not be viewed either.

Supporting evidence: the generated mesh's width-to-height ratio is 1.9950 / 1.0803 = 1.847, and the
drawing's 15.32 / 8.3 = 1.846. Daniel supplied an image of this drawing on Oct 5 (project-context
Topic 13), so he can confirm the reading.

## 4. What turns with the spindle
- **Stated in the manual:** "Chucks and face plates utilize the 2 3/16-10 threaded nose on the
  spindle." and "Screw the chuck on gently until it seats against the rear of the spindle." (PDF
  p. 18).
- **Parts list (PDF p. 53):** "20-4001A SPINDLE 5CV", "20-4002A SPINDLE LOCK", "20-2072 SPINDLE
  COVER S5C", "20-4008 BEARING END CAP", six "40-1610 SHCS 1/4-20 X 1" and six "49-4101 WASHER 1/4
  COPPER". The assembly drawing itself is an image and was not read.
- **Maintenance figure (PDF p. 50):** labels "Front Seal", "Rear Seal", "Front Spindle Seal" and
  "Rear Gear Seal".
- **Photo:** a black disc with six socket-head cap screws sits in a recess of the casting. The
  threaded nose, with a knurled band and a ground face ring around the bore, sticks out of it.
- **Reading [INFERENCE]:** six cap screws with copper sealing washers and a separate front spindle
  seal fit a fixed, oil-sealing cover with the spindle turning inside it. The "seats against the rear
  of the spindle" sentence fits a turning flange. Neither is confirmed.
- **Decision:** Daniel chose "nose only" on 2026-10-17 (decision 0012) after seeing both previews.

## 5. Generator findings (Hunyuan3D-2)
Read 2026-10-17 between 00:24 and 00:44 UTC. Code pages are from the `main` branch at that time; the
clone is at commit `f8db63096c8282cb27354314d896feba5ba6ff8a` (2025-10-28, "Update LICENSE").

**Requirements.** README (https://github.com/Tencent-Hunyuan/Hunyuan3D-2):
- "It takes 6 GB VRAM for shape generation and 16 GB for shape and texture generation in total."
- "Hunyuan3D 2.0 supports Macos, Windows, Linux."
- Texture needs `custom_rasterizer` and `differentiable_renderer` built with `python3 setup.py
  install`; shape generation does not.

**License.** `LICENSE`:
- "TENCENT HUNYUAN 3D 2.0 COMMUNITY LICENSE AGREEMENT";
- "THIS LICENSE AGREEMENT DOES NOT APPLY IN THE EUROPEAN UNION, UNITED KINGDOM AND SOUTH KOREA";
- a separate license is required above "1 million monthly active users";
- "Tencent claims no rights in Outputs You generate."

**Weights.** The Hugging Face API, read on 2026-10-17:
- `tencent/Hunyuan3D-2`: `gated=False`, `license_name=tencent-hunyuan-community`, last modified
  2025-10-17. `hunyuan3d-dit-v2-0/model.fp16.safetensors` is 4.93 GB (4,928,151,562 bytes on disk).
- `tencent/Hunyuan3D-2mv`: `gated=False`. `hunyuan3d-dit-v2-mv/model.fp16.safetensors` is 4.93 GB.

**Loader and settings.** `hy3dgen` source:
- `smart_load_model` tries a local path first: `base_dir = os.environ.get('HY3DGEN_MODELS',
  '~/.cache/hy3dgen')` (`hy3dgen/shapegen/utils.py`, line 97).
- `Hunyuan3DDiTFlowMatchingPipeline.__call__` defaults: `num_inference_steps: int = 50`,
  `guidance_scale: float = 5.0`, `octree_resolution=384`, `num_chunks=8000`. We use the example
  values instead: `examples/shape_gen_multiview.py` uses 50 steps, `octree_resolution=380`,
  `num_chunks=20000` and `torch.manual_seed(12345)`.
- `FaceReducer.__call__(..., max_facenum: int = 40000)`.
- `MVImageProcessorV2`: "view order: front, front clockwise 90, back, front clockwise 270", with
  `view2idx` `front 0, left 1, back 2, right 3` (`hy3dgen/shapegen/preprocessors.py`).
- The post-processors write temporary files with `tempfile.NamedTemporaryFile(suffix='.ply',
  delete=False)` (`hy3dgen/shapegen/postprocessors.py`, lines 63, 77, 151 and 191-192 at the pinned
  commit). They are never deleted; see section 7.

**Versions.**
- Community Windows bundle (https://github.com/YanWenKun/Hunyuan3D-2-WinPortable, linked from the
  README as a "Windows installation tool"):
  - `builder/pak2.txt` pins `torch==2.8.0` and `torchvision==0.23.0`;
  - `builder/stage1.sh` downloads `cpython-3.12.11`;
  - the repository was last pushed on 2025-11-19.
- PyTorch wheels: `torch-2.8.0+cu126-cp312-cp312-win_amd64.whl` is 2.92 GB.
- `pip install` without a numba floor failed: "Failed to build `llvmlite==0.36.0`" ... "Cannot
  install on Python version 3.12.15; only versions >=3.6,<3.10 are supported." `"numba>=0.61"` fixed
  it (numba 0.62.1, llvmlite 0.45.1).

**Background removal.** rembg (https://github.com/danielgatis/rembg):
- `LICENSE` begins "MIT License".
- `sessions/u2net.py` downloads
  `https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net.onnx` (176.0 MB).
- `sessions/base.py` stores it in `U2NET_HOME`.

**pymeshlab.** PyPI lists its license as "GPL3" (2025.7.post1).

**Stable Fast 3D.** README (https://github.com/Stability-AI/stable-fast-3d), read 00:29 UTC:
- "For Windows **(experimental)**: Visual Studio 2022";
- "Our model is gated at [Hugging Face]".

## 6. Measurements on the generated mesh
Runs 2026-10-17_run-001, run-002 and run-003 and the GPU test made identical geometry (section 7).
Units are model units after orienting the mesh (generator +Y up and +Z front become +Z up and +X
front).

- **Bounds:** min (-0.5801, -1.0002, -0.5338), max (+0.5686, +0.9948, +0.5465); extents 1.1487
  (depth), 1.9950 (width), 1.0803 (height).
- **Tip slabs** behind the front-most point (x = 0.5686):

  | Depth | Vertices | Centre (y, z) | Radius |
  |---|---|---|---|
  | 0.01 | 402 | (0.0755, 0.0026) | 0.1613 |
  | 0.03 | 574 | (0.0757, 0.0030) | 0.1647 |
  | 0.06 | 694 | (0.0754, 0.0028) | 0.1647 |

- **Radial profile along +X** about (y, z) = (0.0757, 0.0030), 600,000 surface samples:
  - the body fills a 0.36-unit window up to x = 0.28;
  - a disc of radius 0.28 (0.30 at its chamfered back edge) runs from x 0.28 to 0.41;
  - the nose, of radius 0.160-0.171, runs from x 0.42 to 0.57.
- **Front-facing faces** (area-weighted x): body front 0.2465; disc front 0.4125; nose front
  0.5651.
- **Base:**
  - down-facing area 0.38 square units at z -0.5338 to -0.5298 (x -0.47 to 0.24, y -0.23 to 0.36),
    under the casting;
  - a second flat area of 0.35 square units at z -0.486 to -0.482 (y -0.99 to -0.25), the bottom
    of the motor housing;
  - nothing hangs below the casting's base. The drawing's locating pins ("MOUNTED PIN EXTENSION
    .35"") are not in the mesh.
- **Scale:** axis height 0.0030 - (-0.5338) = 0.5368 units, so 0.1016 / 0.5368 = 0.189268 m per unit.
- **Twin sizes (v2):**
  - overall 0.2174 x 0.3776 x 0.2045 m;
  - body: 37,106 faces, bounds (-0.1893, -0.2036, 0) to (0.0051, 0.1740, 0.2045);
  - spindle: 2,894 faces, bounds (-0.0056, -0.0321, 0.0700) to (0.0281, 0.0324, 0.1330), so about
    0.0645 m across the nose. The thread's nominal major diameter is 2 3/16 in, 0.0556 m.
- **Size checks:** width -3.0%, height -3.0% and depth +7.9% against the cited values. Width and
  height being off by the same amount suggests the scale is uniformly about 3% small. That could
  come from the generator's proportions or from the axis-height measurement [INFERENCE].

## 7. Reproducibility
- **Same photo, same settings, seed 12345.** Four generations on 2026-10-17 (run-001 by hand,
  run-002, run-003 and the GPU test) gave identical vertex and face arrays: `numpy.array_equal`.
  The prepared, background-removed image was byte-identical in run-001, run-002 and run-003
  (SHA-256 `ceacaf32...`). The GPU test's copy was not kept.
- **The GLB files differ anyway.** Only the JSON chunk differs, which holds the mesh name. That name
  is a temporary file name (`tmpv7o8wdvc.ply`, `tmpwe7stqeh.ply`, ...) left by hy3dgen's clean-up.
  The binary geometry chunk (719,976 bytes) is identical. Pipeline B now names its parts, so its
  part files depend only on the geometry. v2's part files were made before this fix and still carry
  the name.
- **Leftover files.** Each run left seven `tmp*.ply` files (about 77 MB) in `%TEMP%`: 22 files
  after three runs and one test. They were deleted. The adapter now gives the generator its own
  temporary folder and removes it.
- **Generation times** (seconds; VRAM peak 6.077 GB allocated and 6.937 GB reserved every time):

  | Run | Total | Prepare | Load model | Generate | Clean up |
  |---|---|---|---|---|---|
  | run-001 | 52.1 | 4.0 | 13.7 | 27.8 | 6.6 |
  | run-002 | 49.4 | 0.9 | 13.4 | 28.3 | 6.7 |
  | run-003 | 49.0 | 0.8 | 13.6 | 27.8 | 6.8 |
  | GPU test | 50.9 | 1.0 | 14.4 | 28.2 | 7.3 |

## 8. Export findings
- **NVIDIA's ASCII rule.** omniverse-asset-validator 1.18.0's `UsdAsciiPerformanceChecker` flags
  arrays longer than `_ARRAY_LENGTH_LIMIT = 64` in `.usda` layers. Its message on twin v1: "8
  attribute(s) in '...twin.usda' have large array lengths and should be stored in crate files for
  improved performance." v1 is 6,430,567 bytes of text. v2, the same twin as binary `.usdc`, is
  1,872,255 bytes; NVIDIA's validator reported "No issues found" and ours 0 errors, 0 warnings.
- **Joint collisions.** usd-core 26.8's schema gives `physics:collisionEnabled` the fallback `False`,
  documented as "Determines if the jointed subtrees should collide or not."
- **Time range.** Since `a37f5e7` every export carries a time range (decision 0010, Phase 3 update).

## 9. Isaac Sim check (2026-10-18)
Daniel checked twin v2 in Isaac Sim 6.2.0 (`docs/worklog/2026-10-18.md`):
- sizes close to expected (measured by hand);
- the spindle turns at 30 degrees per second, reverses at -90 and holds a quarter turn;
- no collisions, no errors, and no time-code warning;
- success level 2.

The seam shows small black gaps once the spindle turns. Measured: the shared cut edge's outer ring
is 30.4-32.7 mm from the axis. After 90 degrees the spindle's edge is 1.09 mm (median) and up to
2.83 mm from the body's, against 0 mm at rest. The out-of-round nose no longer meets its cut, and
the open shells show through [INFERENCE].

## Open questions
1. Does the six-screw disc turn on a real HA5C? Lab photos or a person at a machine could settle it.
2. Is 15.32 in the overall width and 7.93 in the overall depth, with or without the nose? What is
   7.80 in? Daniel can check the drawing.
3. Which side of the object is the multi-view model's `left` image (before the first multi-view run)?
4. What is the license of the `u2net.onnx` model (rembg's code is MIT)?
5. Is the uniform -3% size difference the generator's or ours? A second photo or a multi-view run
   would tell.
