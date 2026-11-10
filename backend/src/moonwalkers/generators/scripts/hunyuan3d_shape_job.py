"""Hunyuan3D-2 shape generation for one job. Runs inside the generator's own environment.

Called by ``moonwalkers.generators.hunyuan3d`` as::

    <generator python> hunyuan3d_shape_job.py job.json result.json

This file must not import ``moonwalkers``: the generator environment does not have it.

Steps:
1. Turn each photo upright by its EXIF orientation, then cut the machine out of it: as the job's
   ``cutouts`` say for that view (SAM with a box and points, a crop box, or a mask drawn by hand;
   decision 0029), else with rembg's automatic background removal, unless the photo already has
   transparency. (The repository's multi-view example converts to RGBA before its RGB check, so
   it never removes backgrounds; it relies on pre-cut images.) With ``cutout_only``, stop here
   and draw ``sheet.png``, each cut-out on grey with its box and points.
2. Generate the shape with Hunyuan3D-DiT.
3. Clean up with the repository's own post-processors (floaters, degenerate faces, face count).
4. Write ``mesh.glb`` and a JSON result with timings, peak VRAM and package versions.
"""

from __future__ import annotations

import json
import platform
import sys
import time
import traceback
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

PACKAGES = ("hy3dgen", "torch", "diffusers", "transformers", "rembg", "onnxruntime", "pymeshlab")


def _version(dist: str) -> str | None:
    try:
        return version(dist)
    except PackageNotFoundError:
        return None


def _has_transparency(image: Any) -> bool:
    return image.mode in ("RGBA", "LA") and image.getextrema()[-1][0] < 255


def _open_upright(path: str | Path) -> Any:
    """The photo turned as its EXIF orientation says. Phone JPEGs often store a portrait photo
    sideways with "rotate 90°" in EXIF: 19 of the lab's 29 photos (orientation 6, 2026-11-09).
    Without this the generator saw them sideways."""
    from PIL import Image, ImageOps

    with Image.open(path) as image:
        return ImageOps.exif_transpose(image)


# rembg's SAM fits each image into 1024 x 684 with cv2.warpAffine and INTER_LINEAR
# (rembg/sessions/sam.py, ``input_size = (684, 1024)``), which does not antialias: a 4000-pixel
# photo reaches the encoder aliased, and the mask kept the wall behind the TM-1 (2026-11-09). So
# the photo is shrunk to that size with Pillow's LANCZOS first, and the mask scaled back up.
SAM_INPUT = (1024, 684)


def sam_size(size: tuple[int, int]) -> tuple[int, int]:
    """The size an image of ``size`` (w, h) is shrunk to for SAM: fitted into ``SAM_INPUT``."""
    scale = min(SAM_INPUT[0] / size[0], SAM_INPUT[1] / size[1], 1.0)
    return max(round(size[0] * scale), 1), max(round(size[1] * scale), 1)


def box_pixels(box: list[float], size: tuple[int, int]) -> tuple[int, int, int, int]:
    """A box of fractions (x0, y0, x1, y1) as whole pixels of an image of ``size`` (w, h)."""
    w, h = size
    x0, y0, x1, y1 = box
    return round(x0 * w), round(y0 * h), max(round(x1 * w), 1), max(round(y1 * h), 1)


def sam_prompt(cutout: dict[str, Any], size: tuple[int, int]) -> list[dict[str, Any]]:
    """rembg's SAM prompt (``rembg/sessions/sam.py``): the box, then each point, label 1 to keep
    and 0 to leave out, in pixels of the upright photo."""
    w, h = size
    prompt: list[dict[str, Any]] = [
        {"type": "rectangle", "label": 1, "data": list(box_pixels(cutout["box"], size))}
    ]
    for point in cutout.get("points", []):
        prompt.append(
            {
                "type": "point",
                "label": 1 if point["keep"] else 0,
                "data": [point["x"] * w, point["y"] * h],
            }
        )
    return prompt


def keep_large_pieces(alpha: Any, min_piece: float) -> tuple[Any, int]:
    """``alpha`` (uint8, H x W) with every separate piece smaller than ``min_piece`` times the
    largest one cleared, and how many pieces were cleared. Pieces are 8-connected pixels above
    127."""
    import numpy as np
    from scipy import ndimage

    if min_piece <= 0:
        return alpha, 0
    labels, count = ndimage.label(alpha > 127, structure=np.ones((3, 3), dtype=bool))
    if count <= 1:
        return alpha, 0
    sizes = np.bincount(labels.ravel())[1:]
    small = np.flatnonzero(sizes < min_piece * sizes.max()) + 1
    out = alpha.copy()
    out[np.isin(labels, small)] = 0
    return out, int(small.size)


def mask_from_file(path: str, size: tuple[int, int]) -> Any:
    """A mask drawn by hand, as uint8 alpha: its transparency if it has any, else its brightness.
    A mask drawn on a smaller copy of the photo is scaled up when its shape matches."""
    import numpy as np
    from PIL import Image

    with Image.open(path) as drawn:
        drawn.load()
    if drawn.size != size:
        if abs(drawn.size[0] / drawn.size[1] - size[0] / size[1]) > 0.01 * size[0] / size[1]:
            raise ValueError(
                f"the mask {path} is {drawn.size[0]} x {drawn.size[1]}, not the shape of the "
                f"upright photo ({size[0]} x {size[1]})"
            )
        drawn = drawn.resize(size, Image.Resampling.NEAREST)
    band = drawn.getchannel("A") if _has_transparency(drawn) else drawn.convert("L")
    return np.asarray(band, dtype=np.uint8)


class Cutter:
    """Cuts the machine out of upright photos, loading each rembg model once, when first needed.
    The automatic removal is hy3dgen's own ``BackgroundRemover`` (rembg's u2net)."""

    def __init__(self) -> None:
        self._sessions: dict[str, Any] = {}
        self._remover: Any = None

    def _session(self, name: str) -> Any:
        from rembg import new_session

        if name not in self._sessions:
            self._sessions[name] = (
                new_session("sam", sam_quant=True) if name == "sam" else new_session(name)
            )
        return self._sessions[name]

    def __call__(self, image: Any, cutout: dict[str, Any] | None) -> tuple[Any, dict[str, Any]]:
        """The RGBA cut-out of an upright photo, and what was done."""
        import numpy as np
        from PIL import Image
        from rembg import remove

        if cutout is None:
            if _has_transparency(image):
                cut = image.convert("RGBA")
                info: dict[str, Any] = {"method": "own transparency"}
            else:
                if self._remover is None:
                    from hy3dgen.rembg import BackgroundRemover

                    self._remover = BackgroundRemover()
                cut = self._remover(image.convert("RGB")).convert("RGBA")
                info = {"method": "auto"}
            alpha = np.asarray(cut.getchannel("A"))
            return cut, {**info, "kept_share": round(float((alpha > 127).mean()), 4)}

        rgb = image.convert("RGB")
        method = cutout["method"]
        if method == "sam":
            small = rgb.resize(sam_size(rgb.size), Image.Resampling.LANCZOS)
            prompt = sam_prompt(cutout, small.size)
            mask = remove(small, session=self._session("sam"), only_mask=True, sam_prompt=prompt)
            mask = mask.convert("L").resize(rgb.size, Image.Resampling.BILINEAR)
            # SAM's mask is binary: keep it so, with edges smoothed by the upscale only
            alpha = np.where(np.asarray(mask) > 127, 255, 0).astype(np.uint8)
        elif method == "crop":
            x0, y0, x1, y1 = box_pixels(cutout["box"], rgb.size)
            inside = remove(
                rgb.crop((x0, y0, x1, y1)), session=self._session("u2net"), only_mask=True
            )
            alpha = np.zeros((rgb.height, rgb.width), dtype=np.uint8)
            alpha[y0:y1, x0:x1] = np.asarray(inside.convert("L"), dtype=np.uint8)
        elif method == "mask":
            alpha = mask_from_file(cutout["mask"], rgb.size)
        else:
            raise ValueError(f"unknown cut-out method {method!r}")
        alpha, dropped = keep_large_pieces(alpha, float(cutout.get("min_piece", 0.0)))
        cut = rgb.convert("RGBA")
        cut.putalpha(Image.fromarray(alpha))
        return cut, {
            "method": method,
            "kept_share": round(float((alpha > 127).mean()), 4),
            "pieces_dropped": dropped,
        }


def prepare_images(
    job: dict[str, Any], prepared_dir: Path
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Each photo turned upright and cut out, saved as ``<view>.png``; and what was done to it."""
    cutouts = job.get("cutouts", {})
    cutter = Cutter()
    images, done = {}, {}
    for view, path in job["images"].items():
        image, done[view] = cutter(_open_upright(path), cutouts.get(view))
        image.save(prepared_dir / f"{view}.png")
        images[view] = image
    return images, done


def draw_sheet(
    job: dict[str, Any], images: dict[str, Any], done: dict[str, Any], path: Path
) -> None:
    """Each cut-out on grey, its box in blue and its points green (keep) or red (leave out)."""
    from PIL import Image, ImageDraw

    tile_size, label = 640, 24
    tiles = []
    for view, cut in images.items():
        shown = Image.new("RGBA", cut.size, (128, 128, 128, 255))
        shown.alpha_composite(cut)
        draw = ImageDraw.Draw(shown)
        cutout = job.get("cutouts", {}).get(view) or {}
        line = max(cut.width // 400, 2)
        if cutout.get("box"):
            draw.rectangle(box_pixels(cutout["box"], cut.size), outline=(0, 120, 255), width=line)
        r = 4 * line
        for p in cutout.get("points", []):
            x, y = p["x"] * cut.width, p["y"] * cut.height
            colour = (0, 200, 0) if p["keep"] else (220, 0, 0)
            draw.ellipse([x - r, y - r, x + r, y + r], fill=colour)
        shown = shown.convert("RGB")
        shown.thumbnail((tile_size, tile_size))
        tile = Image.new("RGB", (tile_size, tile_size + label), "white")
        tile.paste(shown, ((tile_size - shown.width) // 2, label))
        info = done[view]
        text = f"{view}: {info['method']}, {info['kept_share']:.1%} kept"
        if info.get("pieces_dropped"):
            text += f", {info['pieces_dropped']} specks dropped"
        ImageDraw.Draw(tile).text((6, 5), text, fill="black")
        tiles.append(tile)
    cols = min(len(tiles), 4)
    rows = -(-len(tiles) // cols)
    sheet = Image.new("RGB", (cols * tile_size, rows * (tile_size + label)), "white")
    for i, tile in enumerate(tiles):
        sheet.paste(tile, ((i % cols) * tile_size, (i // cols) * (tile_size + label)))
    sheet.save(path)


def cut_out_only(job: dict[str, Any]) -> dict[str, Any]:
    """Step 1 alone, for checking cut-outs before generating: no 3D model is loaded."""
    out_dir = Path(job["out_dir"])
    prepared_dir = out_dir / "prepared"
    prepared_dir.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    images, done = prepare_images(job, prepared_dir)
    sheet = out_dir / "sheet.png"
    draw_sheet(job, images, done, sheet)
    return {
        "status": "ok",
        "prepared": {view: str(prepared_dir / f"{view}.png") for view in images},
        "sheet": str(sheet),
        "cutouts": done,
        "seconds": round(time.perf_counter() - start, 3),
        "versions": {name: _version(name) for name in ("rembg", "onnxruntime", "pillow")},
    }


def run(job: dict[str, Any]) -> dict[str, Any]:
    if job.get("cutout_only"):
        return cut_out_only(job)
    import torch
    from hy3dgen.shapegen import (
        DegenerateFaceRemover,
        FaceReducer,
        FloaterRemover,
        Hunyuan3DDiTFlowMatchingPipeline,
    )

    out_dir = Path(job["out_dir"])
    prepared_dir = out_dir / "prepared"
    prepared_dir.mkdir(parents=True, exist_ok=True)
    timings: dict[str, float] = {}

    start = time.perf_counter()
    images, done = prepare_images(job, prepared_dir)
    timings["prepare_images"] = time.perf_counter() - start

    start = time.perf_counter()
    pipeline = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained(
        job["model_repo"], subfolder=job["subfolder"], variant="fp16"
    )
    timings["load_model"] = time.perf_counter() - start

    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()
    start = time.perf_counter()
    image_input = images["single"] if list(images) == ["single"] else images
    mesh = pipeline(
        image=image_input,
        num_inference_steps=job["steps"],
        guidance_scale=job["guidance_scale"],
        octree_resolution=job["octree_resolution"],
        num_chunks=job["num_chunks"],
        generator=torch.manual_seed(job["seed"]),
        output_type="trimesh",
    )[0]
    timings["generate"] = time.perf_counter() - start
    raw = {"vertices": len(mesh.vertices), "faces": len(mesh.faces)}

    start = time.perf_counter()
    mesh = FloaterRemover()(mesh)
    mesh = DegenerateFaceRemover()(mesh)
    mesh = FaceReducer()(mesh, max_facenum=job["max_faces"])
    timings["clean_up"] = time.perf_counter() - start

    mesh_path = out_dir / "mesh.glb"
    mesh.export(mesh_path)
    cuda = torch.cuda.is_available()
    return {
        "status": "ok",
        "mesh_path": str(mesh_path),
        "raw_mesh": raw,
        "final_mesh": {"vertices": len(mesh.vertices), "faces": len(mesh.faces)},
        "timings_s": {k: round(v, 3) for k, v in timings.items()},
        "seconds": round(sum(timings.values()), 3),
        "peak_vram_allocated_gb": round(torch.cuda.max_memory_allocated() / 1e9, 3)
        if cuda
        else None,
        "peak_vram_reserved_gb": round(torch.cuda.max_memory_reserved() / 1e9, 3) if cuda else None,
        "device": torch.cuda.get_device_name(0) if cuda else "cpu",
        "versions": {name: _version(name) for name in PACKAGES} | {"cuda": torch.version.cuda},
        "python": platform.python_version(),
        "background_removed": any(d["method"] != "own transparency" for d in done.values()),
        "cutouts": done,
    }


def main(argv: list[str]) -> int:
    job_path, result_path = Path(argv[1]), Path(argv[2])
    try:
        result = run(json.loads(job_path.read_text(encoding="utf-8")))
    except Exception as exc:  # noqa: BLE001 - every failure must reach the result file
        traceback.print_exc()
        result = {"status": "error", "error": f"{type(exc).__name__}: {exc}"}
    result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
