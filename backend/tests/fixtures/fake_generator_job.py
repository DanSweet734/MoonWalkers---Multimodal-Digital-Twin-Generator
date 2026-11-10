"""Stand-in for a generator job script in tests: writes a small box mesh and a result file.

Runs with the backend's own Python (trimesh is available there), so the subprocess protocol can be
tested without a GPU or model weights. ``seed == 666`` simulates a failed generation. A
``cutout_only`` job (decision 0029) writes placeholder files where the real job writes its
cut-outs and sheet.
"""

import json
import os
import sys
import tempfile
from pathlib import Path

import trimesh


def main(argv: list[str]) -> int:
    job = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    result_path = Path(argv[2])
    print("fake generator ran")
    if job.get("cutout_only"):
        prepared = Path(job["out_dir"]) / "prepared"
        prepared.mkdir(parents=True, exist_ok=True)
        for view in job["images"]:
            (prepared / f"{view}.png").write_bytes(b"cut out")
        sheet = Path(job["out_dir"]) / "sheet.png"
        sheet.write_bytes(b"sheet")
        done = {
            v: {"method": (job["cutouts"].get(v) or {}).get("method", "auto"), "kept_share": 0.5}
            for v in job["images"]
        }
        result = {
            "status": "ok",
            "prepared": {v: str(prepared / f"{v}.png") for v in job["images"]},
            "sheet": str(sheet),
            "cutouts": done,
            "seconds": 0.1,
            "cutouts_seen": job["cutouts"],
        }
        result_path.write_text(json.dumps(result), encoding="utf-8")
        return 0
    if job.get("seed") == 666:
        result_path.write_text(json.dumps({"status": "error", "error": "simulated failure"}))
        return 1
    mesh_path = Path(job["out_dir"]) / "mesh.glb"
    trimesh.creation.box(extents=(1.0, 0.5, 0.25)).export(mesh_path)
    with tempfile.NamedTemporaryFile(suffix=".ply", delete=False) as leftover:  # as hy3dgen does
        leftover.write(b"temporary")
    result = {
        "status": "ok",
        "mesh_path": str(mesh_path),
        "seconds": 0.1,
        "peak_vram_allocated_gb": None,
        "versions": {"hy3dgen": "fake"},
        "images_seen": job["images"],
        "cutouts_seen": job.get("cutouts"),
        "env_seen": {k: os.environ.get(k) for k in ("HY3DGEN_MODELS", "U2NET_HOME")},
        "leftover_seen": leftover.name,
    }
    result_path.write_text(json.dumps(result), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
