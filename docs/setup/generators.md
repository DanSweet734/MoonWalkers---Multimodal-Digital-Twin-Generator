# Setting up the image-to-3D generator (Hunyuan3D-2, shape only)

Pipeline B turns a machine photo into a mesh with Hunyuan3D-2 (decisions 0006 and 0011). The
generator has its own Python environment outside the repository. The backend runs it as a separate
process through `backend/src/moonwalkers/generators/hunyuan3d.py`, so none of its packages mix with
ours. This guide repeats the setup used on Daniel's machine on 2026-10-17. Sources and quotes are in
`docs/research/2026-10-17-ha5c-photo-to-twin.md`.

Everything here is an install, so CLAUDE.md rule 3 applies: agree on it before running it. Daniel
approved this setup for his machine on 2026-10-17.

## What you need
- An NVIDIA GPU. The Hunyuan3D-2 README says: "It takes 6 GB VRAM for shape generation". The setup
  was tested on an RTX 4090 (24 GB), driver 617.42.
- `uv` and `git` (`docs/setup/windows-dev-setup.md`).
- About 12 GB of free disk space, and 4.6 GB more for the multi-view model (see "Disk use"
  below).

## Layout
One root folder, `C:\mw-gen` on Daniel's machine. Short paths avoid Windows path-length trouble.

```
C:\mw-gen\
  hunyuan3d-2\repo\     the Hunyuan3D-2 code (git clone, commit f8db630)
  hunyuan3d-2\.venv\    Python 3.12 environment
  models\tencent\Hunyuan3D-2\hunyuan3d-dit-v2-0\   config.yaml + model.fp16.safetensors
  models\tencent\Hunyuan3D-2mv\hunyuan3d-dit-v2-mv\   the multi-view model (added 2026-10-22)
  models\u2net\         u2net.onnx, the background-removal model (downloaded on first use);
                       sam_vit_b_01ec64.*.quant.onnx, SAM for box-prompted cut-outs (2026-11-09)
```

`Hunyuan3DConfig.under(root)` expects exactly this layout.

## Steps (PowerShell)
1. **Get the code** at the commit we tested (2025-10-28, "Update LICENSE"):
   ```powershell
   New-Item -ItemType Directory -Force -Path C:\mw-gen\hunyuan3d-2, C:\mw-gen\models | Out-Null
   git clone https://github.com/Tencent-Hunyuan/Hunyuan3D-2 C:\mw-gen\hunyuan3d-2\repo
   git -C C:\mw-gen\hunyuan3d-2\repo checkout f8db63096c8282cb27354314d896feba5ba6ff8a
   ```
2. **Create the environment and install PyTorch** (CUDA 12.6 build; the wheel is 2.92 GB):
   ```powershell
   uv venv --python 3.12 C:\mw-gen\hunyuan3d-2\.venv
   $py = "C:\mw-gen\hunyuan3d-2\.venv\Scripts\python.exe"
   uv pip install --python $py "torch==2.8.0" "torchvision==0.23.0" --index-url https://download.pytorch.org/whl/cu126
   & $py -c "import torch; print(torch.__version__, torch.cuda.is_available())"   # 2.8.0+cu126 True
   ```
   torch 2.8.0 is what the community Windows bundle linked from the Hunyuan3D-2 README pins
   (YanWenKun/Hunyuan3D-2-WinPortable, `builder/pak2.txt`).
3. **Install the shape-generation packages**, resolved as of the bundle's last update
   (2025-11-19). Today's releases postdate the generator code.
   ```powershell
   uv pip install --python $py --exclude-newer 2025-11-19 diffusers transformers accelerate einops safetensors huggingface-hub numpy trimesh opencv-python scikit-image pymeshlab pyyaml tqdm rembg onnxruntime omegaconf "numba>=0.61"
   ```
   Keep `"numba>=0.61"`. Without it the resolver picks `llvmlite==0.36.0`, which fails to build:
   "Cannot install on Python version 3.12.15; only versions >=3.6,<3.10 are supported."
4. **Install the generator code without its dependency list.** Its `setup.py` also asks for gradio,
   fastapi and uvicorn, which only its demo app needs.
   ```powershell
   uv pip install --python $py --no-deps -e C:\mw-gen\hunyuan3d-2\repo
   & $py -c "from hy3dgen.shapegen import Hunyuan3DDiTFlowMatchingPipeline; print('ok')"
   ```
5. **Download the single-image shape weights** (fp16 only, 4.93 GB). They are not gated, so no
   Hugging Face login is needed.
   ```powershell
   & C:\mw-gen\hunyuan3d-2\.venv\Scripts\hf.exe download tencent/Hunyuan3D-2 hunyuan3d-dit-v2-0/config.yaml hunyuan3d-dit-v2-0/model.fp16.safetensors --local-dir C:\mw-gen\models\tencent\Hunyuan3D-2
   ```
   The background-removal model (`u2net.onnx`, 176 MB) needs no step. rembg downloads it on first
   use into `models\u2net` (the adapter sets `U2NET_HOME`).
6. **Tell the backend where the generator is.** Either set the variable for your user (new
   terminals pick it up):
   ```powershell
   [Environment]::SetEnvironmentVariable("MOONWALKERS_GEN_ROOT", "C:\mw-gen", "User")
   ```
   or pass `--gen-root C:\mw-gen` to `python -m moonwalkers.pipelines.b build`.
7. **Check it** from `backend/`. This test generates a mesh from the HA5C photo: it took 72 s and
   passed on 2026-10-17.
   ```powershell
   $env:MOONWALKERS_GEN_ROOT = "C:\mw-gen"; uv run pytest -m gpu
   ```

## Installed versions (2026-10-17)
Python 3.12.15, torch 2.8.0+cu126, torchvision 0.23.0+cu126, diffusers 0.35.2, transformers
4.57.1, accelerate 1.11.0, huggingface-hub 0.36.0, rembg 2.0.68, onnxruntime 1.23.2, pymeshlab
2025.7, scikit-image 0.25.2, scipy 1.16.3, numba 0.62.1, llvmlite 0.45.1, numpy 2.3.5, trimesh
4.9.0, opencv-python 4.11.0.86, pillow 12.3.0, safetensors 0.7.0, einops 0.8.1, omegaconf 2.3.0,
hy3dgen 2.0.2 (commit f8db630). Every run also records its versions in `generator/result.json`.

## Disk use (2026-10-17)
| Folder | Size |
|---|---|
| `hunyuan3d-2\.venv` | 7.1 GB |
| `models\tencent` (`model.fp16.safetensors`, 4,928,151,562 bytes) | 4.6 GB |
| `models\tencent\Hunyuan3D-2mv` (added 2026-10-22; its weights are also 4,928,151,562 bytes) | 4.6 GB more |
| `models\u2net` (with SAM's 117,591,481 bytes from 2026-11-09) | 280 MB |
| `hunyuan3d-2\repo` | 161 MB |

## Licenses
- **Hunyuan3D-2 code and weights:** "TENCENT HUNYUAN 3D 2.0 COMMUNITY LICENSE AGREEMENT". It "DOES
  NOT APPLY IN THE EUROPEAN UNION, UNITED KINGDOM AND SOUTH KOREA". "Tencent claims no rights in
  Outputs You generate." Review it again before any release (decision 0011).
- **pymeshlab:** GPL-3.0. It lives only in this environment and runs in the generator's own
  process; the backend never imports it.
- **rembg:** MIT. The license of the `u2net.onnx` model it downloads is not confirmed. On
  2026-10-22, the U-2-Net project the model comes from [INFERENCE: rembg names it `u2net`] showed
  the Apache-2.0 license (https://github.com/xuebinqin/U-2-Net). Its page states no separate terms
  for the trained weights.
- **SAM (`sam_vit_b_01ec64`, quantised, through rembg):** Apache-2.0
  (https://github.com/facebookresearch/segment-anything). rembg downloaded it on Daniel's
  choice on 2026-11-09; the SHA-256 of both files is in
  `docs/research/2026-11-09-background-removal-spike.md`.
- **The rest:** not reviewed one by one. On 2026-10-17 the PyPI entries of the current releases of
  torch, torchvision, diffusers, transformers, accelerate, einops, omegaconf and opencv-python listed
  BSD, Apache-2.0 or MIT licenses; the older pinned versions were not checked.

## How the backend uses it
- `Hunyuan3DGenerator.generate` writes `job.json` into the output folder and runs
  `scripts/hunyuan3d_shape_job.py` with this environment's Python. It then reads `result.json`.
  Everything the script prints goes to `generator.log`.
- Environment variables it sets for the job:
  - `HY3DGEN_MODELS=<root>\models`: hy3dgen looks for weights there before downloading anything
    (`smart_load_model` in `hy3dgen/shapegen/utils.py`);
  - `U2NET_HOME=<root>\models\u2net`;
  - `TMP`, `TEMP` and `TMPDIR` set to `<output>\tmp`, a folder deleted when the job ends.
- The job turns each photo upright by its EXIF orientation (phone JPEGs often store a portrait
  photo sideways; added on 2026-11-09), then cuts the machine out of it. Without a cut-out in
  the request, rembg's u2net removes the background, unless the image already has transparency.
  On cluttered photos that fails or keeps the wrong object
  (`docs/research/2026-11-09-background-removal-spike.md`). So a photo may carry a cut-out
  (decision 0029):
  - SAM with a box and points (the quantised `sam_vit_b_01ec64`, given the photo shrunk to
    1024 x 684 with antialiasing);
  - u2net inside a crop box;
  - a mask drawn by hand.
  Small separate pieces are then dropped. The job writes each cut-out to `prepared/<view>.png`.
- With `"cutout_only": true` the job stops there and draws `sheet.png`, without loading the 3D
  model: `python -m moonwalkers.pipelines.b cutouts <run>` and the MCP tool `preview_cutouts`.
- Otherwise it generates the shape, cleans it up (floaters, degenerate faces, at most 40,000
  faces) and exports `mesh.glb`. In the HA5C runs the output had +Y up and the spindle nose facing
  +Z. Each run's geometry spec records the axes, and Pipeline B turns the mesh into the twin frame
  (decision 0012).

## Known issues
- **Temporary files.** hy3dgen's clean-up writes temporary `.ply` files with `delete=False`, seven
  files (about 77 MB) per run. The adapter keeps them in the run's `tmp` folder and deletes it.
  Runs made before that fix (2026-10-17) left 22 such files in `%TEMP%`; they were deleted.
- **File names in meshes.** The generator's GLB names its mesh after one of those temporary files,
  so two runs with identical geometry give files with different bytes. Pipeline B renames its parts
  (`body`, `spindle`).
- **Slow start.** Each run starts a fresh process, so about 14 s of every run goes to loading the
  model.

## The multi-view model (added 2026-10-22)
Daniel approved the download on 2026-10-22. It is the standard `hunyuan3d-dit-v2-mv`, not the
`-fast` or `-turbo` variants in the same repository.
- **Download** (not gated, so no login), pinned to the repository's commit of that day:
  ```powershell
  & C:\mw-gen\hunyuan3d-2\.venv\Scripts\hf.exe download tencent/Hunyuan3D-2mv hunyuan3d-dit-v2-mv/config.yaml hunyuan3d-dit-v2-mv/model.fp16.safetensors --revision 3a761b539b29fe4ff64714813aa9560fd66f5de0 --local-dir C:\mw-gen\models\tencent\Hunyuan3D-2mv
  ```
- **Checked:**
  - `model.fp16.safetensors` is 4,928,151,562 bytes;
  - its SHA-256, `d36f5881bcdc56726b73e517cd444c13c60732431622da7268145355c8d38e9c`, matches the
    one Hugging Face lists (https://huggingface.co/api/models/tencent/Hunyuan3D-2mv?blobs=true,
    read 2026-10-22);
  - `config.yaml` is 1,608 bytes.
- **License:** the same "TENCENT HUNYUAN 3D 2.0 COMMUNITY LICENSE AGREEMENT" as the single-image
  model, with the same "DOES NOT APPLY IN THE EUROPEAN UNION, UNITED KINGDOM AND SOUTH KOREA"
  (https://huggingface.co/tencent/Hunyuan3D-2mv/raw/main/LICENSE, read 2026-10-22). Its model card
  links to Hunyuan3D-2's license file.
- **Use:** `Hunyuan3DSettings(model_repo="tencent/Hunyuan3D-2mv", subfolder="hunyuan3d-dit-v2-mv")`,
  with images named `front`, `left`, `back` and `right`. Since decision 0022 (2026-10-24) the
  adapter carries both models (`Hunyuan3DConfig.multiview_settings`, the same settings as above)
  and Pipeline B picks one per run: one photo, the single-image model; two to four, each with its
  view, the multi-view model (`for_views`). People name views in the operator's words, and
  `pipelines/b/photos.py` alone translates them to these names.
- **First run (2026-10-22).** Our adapter, on example set 1 (`front`, `left`, `back`; scratch
  output, not a twin):
  - status "ok" in 58.5 s: loading the model took 13.1 s, generating 37.7 s, and clean-up 7.6 s;
  - peak VRAM 6.09 GB allocated, 7.29 GB reserved, on the RTX 4090;
  - 631,780 faces before clean-up, 40,000 after, and the mesh is watertight;
  - no background removal, since the example images are already cut out;
  - the same versions as above (hy3dgen 2.0.2, torch 2.8.0+cu126).

  By eye, the rendered views show the figure whole: head, pigtails, arms and legs.

### Which side each image shows (checked 2026-10-22)
hy3dgen documents the order as "front, front clockwise 90, back, front clockwise 270". The
repository's example sets (`repo\assets\example_mv_images\1` to `14`, at commit f8db630) settle
what that means:
- **`left` shows the object's own left side, with its front pointing to the image's left.**
  - In set 1 the figure faces the camera in `front.png`, with her right hand on her hip, on the
    image's left.
  - In `left.png` she faces the image's left, and the arm we see hangs straight: her left arm.
  - `back.png` shows the hand on the hip on the image's right.
  - Set 2 also faces the image's left in `left.png`.
- That is "front clockwise 90": turn the object 90° clockwise, seen from above, and the camera sees
  its left side. [INFERENCE] `right` is then the object's right side, with its front pointing to the
  image's right.
- **For a machine:** stand facing its front, then walk around to your right. The photo from there
  is `left`. On the T33901, that is the side with the downfeed handles (the manual's photos,
  pp. 6-7).
- **Watch the words.** Manuals name sides as the operator sees them, the opposite of the model's
  names. [INFERENCE] The T33901 manual's "spring housing is located on the left side" (p. 40) is
  the side opposite the handles, so its photo is the model's `right`.
- **Fewer views work:** the repository's own `examples/shape_gen_multiview.py` passes only `front`,
  `left` and `back`, and all 14 example sets have only those three. Our adapter accepts any subset
  of the four names (`generators/hunyuan3d.py`).
- **Corner views, tried on 2026-10-24** (`docs/research/2026-10-24-several-photos-and-corner-views.md`):
  given two corners 90° apart as a grid turned 45°, the multi-view model put the T33901's front
  within 3.5° and 7.7° of where the photos imply. The single-image model, given one corner, turned
  the machine square to an axis instead. Decision 0022 feeds corners as that grid.
