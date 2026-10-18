"""The interface every image-to-3D generator adapter implements."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from moonwalkers.contracts.pipeline_result import Generator

SINGLE_VIEW = "single"


@dataclass(frozen=True)
class GeneratorRequest:
    """Images to turn into one mesh.

    ``images`` maps a view name to an image file: ``{"single": path}`` for single-image models, or
    some of ``front``, ``left``, ``back``, ``right`` for multi-view models (``left`` is the
    object's own left side).
    """

    images: Mapping[str, Path]
    out_dir: Path

    def __post_init__(self) -> None:
        if not self.images:
            raise ValueError("a generator request needs at least one image")
        missing = [str(p) for p in self.images.values() if not Path(p).is_file()]
        if missing:
            raise FileNotFoundError(f"input image(s) not found: {missing}")


@dataclass(frozen=True)
class GeneratorRun:
    """What one generation produced, with the details a run record needs."""

    mesh_path: Path
    generator: Generator  # name, version and parameters, for the PipelineResult's provenance
    seconds: float
    peak_vram_gb: float | None
    log_path: Path
    details: dict[str, Any] = field(default_factory=dict)


class GeneratorError(RuntimeError):
    """A generator run failed; the message points to its log."""


class ImageTo3DGenerator(ABC):
    """Turns one or more photos of an object into a mesh file."""

    name: str

    @abstractmethod
    def generate(self, request: GeneratorRequest) -> GeneratorRun:
        """Run the generator; raises ``GeneratorError`` on failure."""
