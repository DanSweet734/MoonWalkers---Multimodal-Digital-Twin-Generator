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
- About 12 GB of free disk space (see "Disk use" below).

## Layout
One root folder, `C:\mw-gen` on Daniel's machine. Short paths avoid Windows path-length trouble.

```
C:\mw-gen\
  hunyuan3d-2\repo\     the Hunyuan3D-2 code (git clone, commit f8db630)
  hunyuan3d-2\.venv\    Python 3.12 environment
  models\tencent\Hunyuan3D-2\hunyuan3d-dit-v2-0\   config.yaml + model.fp16.safetensors
  models\u2net\         u2net.onnx, the background-removal model (downloaded on first use)
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
| `models\u2net` | 168 MB |
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
- The job removes the photo's background (unless the image already has transparency) and
  generates the shape. It then cleans the shape up (floaters, degenerate faces, at most 40,000
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

## Adding the multi-view model later
Download `tencent/Hunyuan3D-2mv` files `hunyuan3d-dit-v2-mv/config.yaml` and
`hunyuan3d-dit-v2-mv/model.fp16.safetensors` (4.93 GB) into `C:\mw-gen\models\tencent\Hunyuan3D-2mv`,
then use `Hunyuan3DSettings(model_repo="tencent/Hunyuan3D-2mv", subfolder="hunyuan3d-dit-v2-mv")`.
Images are named `front`, `left`, `back` and `right`. hy3dgen documents the order as "front, front
clockwise 90, back, front clockwise 270". Which side of the machine `left` must show is not
confirmed: check it with the repository's example images before the first real run.
