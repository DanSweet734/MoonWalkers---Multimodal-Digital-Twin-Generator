"""Hunyuan3D-2 shape generation for one job. Runs inside the generator's own environment.

Called by ``moonwalkers.generators.hunyuan3d`` as::

    <generator python> hunyuan3d_shape_job.py job.json result.json

This file must not import ``moonwalkers``: the generator environment does not have it.

Steps:
1. Remove photo backgrounds with rembg, unless an image already has transparency. (The repository's
   multi-view example converts to RGBA before its RGB check, so it never removes backgrounds; it
   relies on pre-cut images.)
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


def run(job: dict[str, Any]) -> dict[str, Any]:
    import torch
    from hy3dgen.rembg import BackgroundRemover
    from hy3dgen.shapegen import (
        DegenerateFaceRemover,
        FaceReducer,
        FloaterRemover,
        Hunyuan3DDiTFlowMatchingPipeline,
    )
    from PIL import Image

    out_dir = Path(job["out_dir"])
    prepared_dir = out_dir / "prepared"
    prepared_dir.mkdir(parents=True, exist_ok=True)
    timings: dict[str, float] = {}

    start = time.perf_counter()
    remover = None
    images = {}
    for view, path in job["images"].items():
        image = Image.open(path)
        if not _has_transparency(image):
            remover = remover or BackgroundRemover()
            image = remover(image.convert("RGB"))
        image = image.convert("RGBA")
        image.save(prepared_dir / f"{view}.png")
        images[view] = image
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
        "background_removed": remover is not None,
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
