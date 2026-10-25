"""Hunyuan3D-2 shape generation, run in its own environment (decisions 0006 and 0011).

The environment and weights live outside the repository (``docs/setup/generators.md``)::

    <root>/hunyuan3d-2/.venv      Python 3.12, torch 2.8.0+cu126, hy3dgen 2.0.2 (shape only)
    <root>/models/tencent/Hunyuan3D-2/hunyuan3d-dit-v2-0/   config.yaml + model.fp16.safetensors
    <root>/models/u2net/           rembg's background-removal model

The loader looks in ``HY3DGEN_MODELS`` before downloading anything (hy3dgen/shapegen/utils.py,
``smart_load_model``), so only the weights already placed there are used.
"""

from __future__ import annotations

import copy
import os
from collections.abc import Collection
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from moonwalkers.contracts.pipeline_result import Generator

from .base import SINGLE_VIEW, GeneratorRequest, GeneratorRun, ImageTo3DGenerator
from .subprocess_job import run_job

GEN_ROOT_ENV = "MOONWALKERS_GEN_ROOT"  # the folder Hunyuan3DConfig.under expects
DEFAULT_SCRIPT = Path(__file__).with_name("scripts") / "hunyuan3d_shape_job.py"
MULTIVIEW_KEYS = frozenset({"front", "left", "back", "right"})  # hy3dgen MVImageProcessorV2


@dataclass(frozen=True)
class Hunyuan3DSettings:
    """Generation settings, recorded with every run. Defaults follow the repository's examples
    (examples/shape_gen_multiview.py: 50 steps, octree 380, 20000 chunks, seed 12345) and the
    pipeline's own default guidance scale (5.0); 40000 faces is FaceReducer's default."""

    model_repo: str = "tencent/Hunyuan3D-2"
    subfolder: str = "hunyuan3d-dit-v2-0"  # single image; multi-view: tencent/Hunyuan3D-2mv, -mv
    steps: int = 50
    guidance_scale: float = 5.0
    octree_resolution: int = 380
    num_chunks: int = 20000
    max_faces: int = 40000
    seed: int = 12345

    @property
    def multiview(self) -> bool:
        return "-mv" in self.subfolder


# The multi-view model installed on 2026-10-22 (docs/setup/generators.md), with the same settings.
MULTIVIEW_SETTINGS = Hunyuan3DSettings(
    model_repo="tencent/Hunyuan3D-2mv", subfolder="hunyuan3d-dit-v2-mv"
)


@dataclass(frozen=True)
class Hunyuan3DConfig:
    """Where the generator environment and its weights are, and both models' settings: one photo
    runs ``settings``, several run ``multiview_settings`` (decision 0022)."""

    python: Path
    models_dir: Path
    u2net_home: Path
    settings: Hunyuan3DSettings = Hunyuan3DSettings()
    timeout_s: float = 1800.0
    multiview_settings: Hunyuan3DSettings = MULTIVIEW_SETTINGS

    @classmethod
    def under(cls, root: Path, settings: Hunyuan3DSettings | None = None) -> Hunyuan3DConfig:
        """The standard layout under one folder (``C:\\mw-gen`` on Daniel's machine)."""
        root = Path(root)
        venv = root / "hunyuan3d-2" / ".venv"
        python = venv / "Scripts" / "python.exe" if os.name == "nt" else venv / "bin" / "python"
        return cls(
            python=python,
            models_dir=root / "models",
            u2net_home=root / "models" / "u2net",
            settings=settings or Hunyuan3DSettings(),
        )


class Hunyuan3DGenerator(ImageTo3DGenerator):
    name = "hunyuan3d-2"

    def __init__(self, config: Hunyuan3DConfig, script: Path = DEFAULT_SCRIPT) -> None:
        self.config = config
        self.script = Path(script)
        self.settings = config.settings  # the model this generator runs (see for_views)

    def fingerprint(self) -> dict[str, Any]:
        return {"name": self.name, **asdict(self.settings)}

    def for_views(self, views: Collection[str]) -> Hunyuan3DGenerator:
        """This generator with the single-image model for ``single``, else the multi-view one."""
        wanted = (
            self.config.settings if set(views) == {SINGLE_VIEW} else self.config.multiview_settings
        )
        if wanted == self.settings:
            return self
        chosen = copy.copy(self)  # keeps a subclass, such as the MCP server's unconfigured one
        chosen.settings = wanted
        return chosen

    def generate(self, request: GeneratorRequest) -> GeneratorRun:
        settings = self.settings
        views = sorted(request.images)
        if settings.multiview:
            if not set(views) <= MULTIVIEW_KEYS:
                raise ValueError(f"multi-view input must use views {sorted(MULTIVIEW_KEYS)}")
        elif views != [SINGLE_VIEW]:
            raise ValueError(
                f"model {settings.subfolder} takes one image named '{SINGLE_VIEW}'; "
                "use a multi-view model for several views"
            )
        job: dict[str, Any] = {
            "images": {view: str(Path(path).resolve()) for view, path in request.images.items()},
            "out_dir": str(Path(request.out_dir).resolve()),
            **asdict(settings),
        }
        result = run_job(
            self.config.python,
            self.script,
            job,
            request.out_dir,
            self.config.timeout_s,
            env={
                "HY3DGEN_MODELS": str(self.config.models_dir),
                "U2NET_HOME": str(self.config.u2net_home),
            },
        )
        versions = result.get("versions", {})
        return GeneratorRun(
            mesh_path=Path(result["mesh_path"]),
            generator=Generator(
                name=self.name,
                version=versions.get("hy3dgen"),
                params={**asdict(settings), "versions": versions},
            ),
            seconds=float(result.get("seconds", 0.0)),
            peak_vram_gb=result.get("peak_vram_allocated_gb"),
            log_path=Path(result["log_path"]),
            details=result,
        )
