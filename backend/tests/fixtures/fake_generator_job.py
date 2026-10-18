"""Stand-in for a generator job script in tests: writes a small box mesh and a result file.

Runs with the backend's own Python (trimesh is available there), so the subprocess protocol can be
tested without a GPU or model weights. ``seed == 666`` simulates a failed generation.
"""

import json
import os
import sys
from pathlib import Path

import trimesh


def main(argv: list[str]) -> int:
    job = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    result_path = Path(argv[2])
    print("fake generator ran")
    if job.get("seed") == 666:
        result_path.write_text(json.dumps({"status": "error", "error": "simulated failure"}))
        return 1
    mesh_path = Path(job["out_dir"]) / "mesh.glb"
    trimesh.creation.box(extents=(1.0, 0.5, 0.25)).export(mesh_path)
    result = {
        "status": "ok",
        "mesh_path": str(mesh_path),
        "seconds": 0.1,
        "peak_vram_allocated_gb": None,
        "versions": {"hy3dgen": "fake"},
        "images_seen": job["images"],
        "env_seen": {k: os.environ.get(k) for k in ("HY3DGEN_MODELS", "U2NET_HOME")},
    }
    result_path.write_text(json.dumps(result), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
