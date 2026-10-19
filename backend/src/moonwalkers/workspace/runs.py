"""Run folders as the shared workspace of the agent and the dashboard (decisions 0013, 0014).

Every MCP tool and every API job works on one run folder,
``data/machines/<machine>/runs/<run>`` (data/README.md), and keeps its state in files there, so a
person can read each step and the command line works on the same folders:

- ``request.json``: the ``JobRequest``, with the job id, the machine the agent named,
  ``new_version``, and the input photo once added.
- ``reference_facts.json``: the ``ReferenceFacts`` the agent recorded from documents. The first
  reference source creates it.
- ``geometry_spec.parts.json``: the joint and scale parts of the geometry spec, as the agent sets
  them. ``geometry_spec.json`` is written once both are there.

A run folder never changes what it has produced (decision 0012). Inputs are fixed once the mesh is
generated, the spec once the parts are assembled, and everything once the twin is built.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from moonwalkers.clock import Clock, utc_now
from moonwalkers.contracts.pipeline_result import Source
from moonwalkers.kb import machine_key
from moonwalkers.orchestrator import JobRequest, MachineHint
from moonwalkers.pipelines.b.assemble import GeometrySpec
from moonwalkers.pipelines.b.build import REQUEST_FILE
from moonwalkers.pipelines.b.pipeline import (
    ASSEMBLY_RECORD,
    GENERATOR_DIR,
    GENERATOR_RECORD,
    MESHES_DIR,
    SPEC_FILE,
    ReferenceFacts,
    RunFolderConflict,
)

REFERENCE_FILE = "reference_facts.json"
SPEC_PARTS_FILE = "geometry_spec.parts.json"
SPEC_PARTS = ("joint", "scale")


class WorkspaceError(ValueError):
    """The request cannot be applied to the run folder as asked."""


@dataclass(frozen=True)
class SpecState:
    parts: tuple[str, ...]  # which of SPEC_PARTS are set
    spec: GeometrySpec | None  # the complete spec, once both parts are set


@dataclass(frozen=True)
class Workspace:
    data_dir: Path
    clock: Clock = utc_now

    # --------------------------------------------------------------------------------- folders
    def machine_dir(self, manufacturer: str, model: str) -> Path:
        """``machines/<machine>``: the machine key with "/" replaced by "-" (decision 0009)."""
        return self.data_dir / "machines" / machine_key(manufacturer, model).replace("/", "-")

    def start_run(self, manufacturer: str, model: str, new_version: bool = False) -> Path:
        """A new run folder for the machine, named after the local date, with its request."""
        machine = self.machine_dir(manufacturer, model)
        folder, runs = machine.name, machine / "runs"
        day = self.clock().astimezone().date().isoformat()
        runs.mkdir(parents=True, exist_ok=True)
        number = 1
        while True:  # mkdir refuses an existing folder, so two processes never share a run
            run_dir = runs / f"{day}_run-{number:03d}"
            try:
                run_dir.mkdir()
                break
            except FileExistsError:
                number += 1
        request = JobRequest(
            job_id=f"{folder}-{day}-run-{number:03d}",
            machine=MachineHint(manufacturer=manufacturer, model=model),
            new_version=new_version,
        )
        _write_json(run_dir / REQUEST_FILE, request.model_dump(mode="json"))
        return run_dir

    def run_dir(self, run: str) -> Path:
        """The folder for ``machines/<machine>/runs/<run>``, which must exist."""
        parts = PurePosixPath(run.replace("\\", "/")).parts
        if (
            len(parts) != 4
            or parts[0] != "machines"
            or parts[2] != "runs"
            or any(p in {".", ".."} for p in parts)
        ):
            raise WorkspaceError(
                f"{run!r} is not a run; expected machines/<machine>/runs/<run> "
                "(start_run returns it)"
            )
        path = self.data_dir.joinpath(*parts)
        if not path.is_dir():
            raise WorkspaceError(f"no run {run!r} in {self.data_dir}; start one with start_run")
        return path

    def relative(self, path: Path) -> str:
        """``path`` relative to the data folder, the form the contract uses."""
        return Path(path).resolve().relative_to(self.data_dir.resolve()).as_posix()

    def data_file(self, path: str) -> Path:
        """An existing file inside the data folder, given relative to it (or absolute)."""
        given = Path(path)
        full = (given if given.is_absolute() else self.data_dir / given).resolve()
        if not full.is_relative_to(self.data_dir.resolve()):
            raise WorkspaceError(f"{path!r} is not inside the data folder {self.data_dir}")
        if not full.is_file():
            raise WorkspaceError(f"no file {path!r} in the data folder {self.data_dir}")
        return full

    # --------------------------------------------------------------------------------- request
    def request(self, run_dir: Path) -> JobRequest:
        return JobRequest.model_validate_json((run_dir / REQUEST_FILE).read_text(encoding="utf-8"))

    def add_input(self, run_dir: Path, source: Source) -> JobRequest:
        """Add an input source to the run's request."""
        _require_unbuilt(run_dir)
        if (run_dir / GENERATOR_DIR / GENERATOR_RECORD).is_file():
            raise RunFolderConflict(
                "this run already generated its mesh from its inputs; start a new run to use others"
            )
        request = self.request(run_dir)
        if any(s.source_id == source.source_id for s in request.sources):
            raise WorkspaceError(f"the request already has a source {source.source_id!r}")
        updated = JobRequest.model_validate(
            {**request.model_dump(), "sources": [*request.sources, source]}
        )
        _write_json(run_dir / REQUEST_FILE, updated.model_dump(mode="json"))
        return updated

    # ------------------------------------------------------------------------- reference facts
    def reference(self, run_dir: Path) -> ReferenceFacts | None:
        path = run_dir / REFERENCE_FILE
        if not path.is_file():
            return None
        return ReferenceFacts.model_validate_json(path.read_text(encoding="utf-8"))

    def update_reference(
        self, run_dir: Path, change: Callable[[dict[str, Any]], None]
    ) -> ReferenceFacts:
        """Apply ``change`` to the reference facts (as JSON values), validate, and save.

        ``ReferenceFacts`` checks every citation against its sources and refuses duplicate fact
        keys, so a bad change is refused and nothing is written.
        """
        _require_unbuilt(run_dir)
        current = self.reference(run_dir)
        data = current.model_dump(mode="json") if current else {"sources": []}
        change(data)
        updated = ReferenceFacts.model_validate(data)
        _write_json(run_dir / REFERENCE_FILE, updated.model_dump(mode="json"))
        return updated

    # ---------------------------------------------------------------------------- spec parts
    def spec_state(self, run_dir: Path) -> SpecState:
        parts = (
            _read_json(run_dir / SPEC_PARTS_FILE) if (run_dir / SPEC_PARTS_FILE).is_file() else {}
        )
        spec_path = run_dir / SPEC_FILE
        spec = (
            GeometrySpec.model_validate_json(spec_path.read_text(encoding="utf-8"))
            if spec_path.is_file()
            else None
        )
        return SpecState(tuple(p for p in SPEC_PARTS if p in parts), spec)

    def set_spec_part(self, run_dir: Path, part: str, values: dict[str, Any]) -> SpecState:
        """Save one part of the spec; with both parts set, write ``geometry_spec.json``.

        The joint part holds the orientation and split, plus ``decided_by`` and ``method``. The
        scale part holds ``center_height_m``, ``base_z`` and a note for the method.
        """
        if part not in SPEC_PARTS:
            raise WorkspaceError(f"unknown spec part {part!r}")
        _require_unbuilt(run_dir)
        if (run_dir / MESHES_DIR / ASSEMBLY_RECORD).is_file():
            raise RunFolderConflict(
                "this run's parts are already assembled from its spec; start a new run to change it"
            )
        path = run_dir / SPEC_PARTS_FILE
        parts = _read_json(path) if path.is_file() else {}
        parts[part] = values
        spec = None
        if all(p in parts for p in SPEC_PARTS):
            joint, scale = dict(parts["joint"]), dict(parts["scale"])
            method = f"{joint.pop('method')} Scale: {scale.pop('note')}"
            spec = GeometrySpec(
                **joint, **scale, method=method
            )  # validates before anything is saved
        _write_json(path, parts)
        if spec is not None:
            _write_json(run_dir / SPEC_FILE, spec.model_dump(mode="json"))
        return SpecState(tuple(p for p in SPEC_PARTS if p in parts), spec)


def default_data_dir() -> Path:
    """``MOONWALKERS_DATA_DIR``; else ``data/`` in Claude Code's project folder
    (``CLAUDE_PROJECT_DIR``); else the repository's ``data/`` next to ``backend/``."""
    if os.environ.get("MOONWALKERS_DATA_DIR"):
        return Path(os.environ["MOONWALKERS_DATA_DIR"]).resolve()
    if os.environ.get("CLAUDE_PROJECT_DIR"):
        return (Path(os.environ["CLAUDE_PROJECT_DIR"]) / "data").resolve()
    return Path(__file__).resolve().parents[4] / "data"


def sha256_of(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _require_unbuilt(run_dir: Path) -> None:
    built = sorted(p.name for p in run_dir.glob("twin.usd*"))
    if built or (run_dir / "twin_record.json").is_file():
        raise RunFolderConflict(
            f"this run already built its twin ({', '.join(built) or 'twin_record.json'}); "
            "start a new run (new_version) to change anything"
        )


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict[str, Any]) -> None:
    Path(path).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n")
