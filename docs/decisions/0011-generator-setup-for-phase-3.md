# 0011 - Generator setup for Phase 3: single-image Hunyuan3D-2 in its own environment

- **Status:** accepted (proposed by Claude Code; Daniel chose each option on 2026-10-17)
- **Date:** 2026-10-17
- **Decided by:** team (Daniel)
- **Changes:** decision 0006's fallback (Stable Fast 3D is replaced by Hunyuan3D-2's single-image model)
- **Amended by:** decision 0022 (two to four photos with their views run the multi-view model;
  one photo still runs the single-image model)

## Context
Decision 0006 picked Hunyuan3D-2mv (multi-view) as Pipeline B's generator, with Stable Fast 3D as
the fallback. Phase 3 has to run one of them on Daniel's machine (Windows 11, RTX 4090 24 GB) as a
subprocess in its own environment. The findings that shaped the setup are below. Each is quoted, with
its source and access date, in `docs/research/2026-10-17-ha5c-photo-to-twin.md`.

- **Photos.** Only one clean public photo of the standard HA5C could be reached: the Haas UK studio
  shot, a three-quarter view on white. The Haas US product page answered HTTP 403 to automated
  access. A used-machine listing had 14 images of one unit, but that unit has a pneumatic closer,
  brackets and hoses, on a cluttered bench (seen in its photos).
- **Hunyuan3D-2.** The README says: "It takes 6 GB VRAM for shape generation and 16 GB for shape and
  texture generation in total". Shape generation needs no compiled extensions; texture generation
  does. One repository and one environment hold both the single-image model
  (`tencent/Hunyuan3D-2`, subfolder `hunyuan3d-dit-v2-0`) and the multi-view model
  (`tencent/Hunyuan3D-2mv`). Neither weight set is gated on Hugging Face.
- **License.** "TENCENT HUNYUAN 3D 2.0 COMMUNITY LICENSE AGREEMENT": "THIS LICENSE AGREEMENT DOES
  NOT APPLY IN THE EUROPEAN UNION, UNITED KINGDOM AND SOUTH KOREA". Services with more than 1 million
  monthly active users must request a separate license. "Tencent claims no rights in Outputs You
  generate."
- **Stable Fast 3D.** Its README lists "For Windows **(experimental)**: Visual Studio 2022" and says
  "Our model is gated at Hugging Face".
- **Versions.** The Hunyuan3D-2 code was last changed on 2025-10-28. Today's packages postdate it
  (for example transformers 5.x). The README links a community Windows bundle (YanWenKun's
  Hunyuan3D-2-WinPortable). Its build pins `torch==2.8.0` and `torchvision==0.23.0` and uses Python
  3.12, and it was last updated on 2025-11-19.

## Options considered
1. **Input for the first run.** (a) The Haas UK studio photo with the single-image model; (b) the
   used-listing photos with the multi-view model; (c) wait for Dr. Li's lab photos. (a) is clean and
   shows the standard machine, but the model must guess the hidden sides. (b) shows a modified unit.
   (c) has no date.
2. **Fallback generator.** (a) Keep Stable Fast 3D, which needs Visual Studio 2022, a compiled
   extension and gated weights; (b) Hunyuan3D-2's single-image model, which uses the same
   environment and has no compiling and no gate.
3. **Where the environment lives.** (a) Inside the repo (rejected: large files must stay out of
   git); (b) `C:\mw-gen` on the C: SSD; (c) `G:\mw-gen` on the G: SSD.
4. **Package versions.** (a) Today's latest; (b) resolve as of the community bundle's last update
   (`uv pip install --exclude-newer 2025-11-19`), with torch 2.8.0 as in the bundle.
5. **Scope.** (a) Shape and texture; (b) shape only. The PoC needs geometry for the joint and scale.
   Texture needs compiled CUDA extensions and 16 GB of VRAM.

## Decision
- **Input:** (1a) the Haas UK studio photo, so the single-image model runs first. The multi-view
  model stays the primary choice from decision 0006 for when a proper multi-view photo set exists
  (Dr. Li's lab photos).
- **Fallback:** (2b) Hunyuan3D-2's single-image model replaces Stable Fast 3D. Stable Fast 3D stays a
  later option.
- **Environment:** (3b) `C:\mw-gen`, shape generation only (5b), with packages resolved as of
  2025-11-19 (4b). Setup steps, versions and disk use: `docs/setup/generators.md`.
- **Adapter:** `backend/src/moonwalkers/generators/` runs `scripts/hunyuan3d_shape_job.py` with the
  environment's Python. Communication is a JSON job file in and a JSON result file out. The adapter
  takes either model through `Hunyuan3DSettings.subfolder`. The multi-view weights (another 4.93 GB)
  are downloaded only when multi-view photos exist.
- **Settings:** the repository's examples: 50 steps, octree resolution 380, 20,000 chunks and seed
  12345 (`examples/shape_gen_multiview.py`). Guidance scale 5.0 is the pipeline's default, and
  40,000 faces is `FaceReducer`'s default.

## Consequences
- Generation runs on Windows with no compiler. Four runs on 2026-10-17 each took about 50 s per
  photo on the RTX 4090 (14 s of it loading the model), peaking at 6.08 GB of VRAM allocated
  (6.94 GB reserved). The same photo and seed gave identical geometry every time.
- The model guesses every surface the photo does not show. Each twin says so in an issue.
- The license excludes the EU, UK and South Korea. A US student PoC is inside its territory, but a
  release or a deployment abroad needs a new review.
- pymeshlab (GPL-3.0) is in the generator environment only. Our backend never imports it; the
  generator runs as a separate process.
- About 12 GB on C: (environment 7.1 GB, weights 4.6 GB, background model 168 MB, code 161 MB).
- Switching to the multi-view model is a settings change plus a weight download, then a new run
  folder. Switching to another generator means a new adapter that implements `ImageTo3DGenerator`.
