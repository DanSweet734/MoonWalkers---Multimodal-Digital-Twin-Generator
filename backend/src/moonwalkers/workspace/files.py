"""The images and output files in a run folder that a person may want to open (decision 0014).

Paths are relative to the data folder, the form the contract uses, so the API can serve them and
the dashboard can link to them. Only the rendered sheets are listed, not every single view.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from moonwalkers.pipelines.b.build import CHECKS_DIR
from moonwalkers.pipelines.b.pipeline import GENERATOR_DIR, INSPECT_DIR, MESHES_DIR

from .runs import Workspace

IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp"})
# Rendered sheets (six views each), in the order the steps make them.
SHEETS = (
    (f"{INSPECT_DIR}/views.png", "Generated mesh, generator axes"),
    ("inspect_oriented/views.png", "Generated mesh, twin axes"),
    ("preview/assembled/views.png", "Preview: assembled"),
    ("preview/body/views.png", "Preview: body"),
    ("preview/spindle/views.png", "Preview: spindle"),
)
ISAAC_SIM_DIR = "isaac-sim"  # screenshots from the hand check, when someone saved them

FileKind = Literal["image", "usd", "check", "notes", "record", "mesh", "log"]


class RunFile(BaseModel):
    label: str
    path: str = Field(description="relative to the data folder")
    kind: FileKind


def run_images(ws: Workspace, run_dir: Path) -> list[RunFile]:
    """The photo as the generator prepared it, the rendered sheets, and Isaac Sim screenshots."""
    run_dir = Path(run_dir)
    images = [
        RunFile(label=f"Generator input ({png.stem})", path=ws.relative(png), kind="image")
        for png in sorted((run_dir / GENERATOR_DIR / "prepared").glob("*.png"))
    ]
    images += [
        RunFile(label=label, path=ws.relative(run_dir / sheet), kind="image")
        for sheet, label in SHEETS
        if (run_dir / sheet).is_file()
    ]
    images += [
        RunFile(label=f"Isaac Sim check: {shot.name}", path=ws.relative(shot), kind="image")
        for shot in sorted((run_dir / ISAAC_SIM_DIR).glob("*"))
        if shot.suffix.lower() in IMAGE_SUFFIXES and shot.is_file()
    ]
    return images


def run_outputs(ws: Workspace, run_dir: Path) -> list[RunFile]:
    """The twin and its check files, the run notes, the JSON records, meshes and the log."""
    run_dir = Path(run_dir)

    def files(pattern: str, label: str, kind: FileKind) -> list[RunFile]:
        return [
            RunFile(label=label.format(name=p.name), path=ws.relative(p), kind=kind)
            for p in sorted(run_dir.glob(pattern))
            if p.is_file() and not p.name.startswith(".")
        ]

    return [
        *files("twin.usd*", "Twin ({name})", "usd"),
        *files(f"{CHECKS_DIR}/*.usd*", "Isaac Sim check file ({name})", "check"),
        *files("RUN.md", "Run notes (RUN.md)", "notes"),
        *files("*.json", "{name}", "record"),
        *files(f"{MESHES_DIR}/*.glb", "Part mesh ({name})", "mesh"),
        *files(f"{GENERATOR_DIR}/*.glb", "Generated mesh ({name})", "mesh"),
        *files(f"{GENERATOR_DIR}/*.log", "Generator log ({name})", "log"),
    ]
