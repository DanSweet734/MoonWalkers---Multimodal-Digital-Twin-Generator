"""Run folders as the shared workspace of the agent and the dashboard (decisions 0013, 0014).

Every MCP tool and every API job works on one run folder,
``data/machines/<machine>/runs/<run>`` (data/README.md), and keeps its state in files there, so a
person can read each step and the command line works on the same folders:

- ``request.json``: the ``JobRequest``, with the job id, the machine the agent named,
  ``new_version``, and the input photos once added, each with its view and use (decision 0022).
- ``reference_facts.json``: the ``ReferenceFacts`` the agent recorded from documents. The first
  reference source creates it.
- ``geometry_spec.parts.json``: the geometry spec as the agent sets it, piece by piece, in one of
  two kinds (decision 0028):
  - decision 0012's single spindle: ``joint`` and ``scale``;
  - several parts (decision 0027): ``frame``, ``scale_length``, ``cuts``, ``parts`` and ``joints``
    (by id), and ``size_checks``. Each piece is checked as it is set, the whole spec once the
    required pieces are there.

  ``geometry_spec.json`` is there only while the pieces make a valid spec, so a spec that a later
  change broke cannot be built.

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

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from moonwalkers.clock import Clock, utc_now
from moonwalkers.contracts.pipeline_result import Source
from moonwalkers.kb import machine_key
from moonwalkers.orchestrator import InputPhoto, JobRequest, MachineHint
from moonwalkers.pipelines.b.assemble import AxisName, GeometrySpec
from moonwalkers.pipelines.b.build import REQUEST_FILE
from moonwalkers.pipelines.b.part_cuts import PartCut
from moonwalkers.pipelines.b.parts_spec import (
    PartsSpec,
    ScaleReference,
    SizeCheck,
    SpecJoint,
    SpecPart,
)
from moonwalkers.pipelines.b.photos import check_photos
from moonwalkers.pipelines.b.pipeline import (
    ASSEMBLY_RECORD,
    GENERATOR_DIR,
    GENERATOR_RECORD,
    MESHES_DIR,
    SPEC_FILE,
    ReferenceFacts,
    RunFolderConflict,
    read_spec,
)

REFERENCE_FILE = "reference_facts.json"
SPEC_PARTS_FILE = "geometry_spec.parts.json"
SPEC_PARTS = ("joint", "scale")
# A several-part spec's pieces: the required ones, then the ones it may leave out.
PARTS_REQUIRED = ("frame", "scale_length", "cuts", "parts")
PARTS_PIECES = (*PARTS_REQUIRED, "joints", "size_checks")
PARTS_ENTRIES = {"parts": "part_id", "joints": "joint_id"}  # pieces kept by id


class WorkspaceError(ValueError):
    """The request cannot be applied to the run folder as asked."""


class PartsFrame(BaseModel):
    """A several-part spec's frame: how the mesh is turned into the twin's axes, where the twin's
    origin is, which part stays fixed, and who decided it how (``PartsSpec``'s own fields)."""

    model_config = ConfigDict(extra="forbid")

    up: AxisName
    front: AxisName
    yaw_deg: float = Field(default=0.0, ge=-180.0, le=180.0)
    origin_xy: tuple[float, float]
    base_z: float | None = None
    fixed_part: str
    decided_by: str
    method: str


@dataclass(frozen=True)
class SpecState:
    parts: tuple[str, ...]  # the pieces set, of either kind
    spec: GeometrySpec | PartsSpec | None  # the complete spec, while the pieces make one
    kind: str | None = None  # "spindle" (decision 0012) or "parts" (decision 0027)
    problem: str | None = None  # why the pieces do not make a spec yet


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

    def add_input(
        self, run_dir: Path, source: Source, photo: InputPhoto | None = None
    ) -> JobRequest:
        """Add an input source to the run's request, with a machine photo's view and use.

        The run's photos are checked as a whole (decision 0022), so a second photo of a view the
        generator already gets, or a photo without a view next to others, is refused before
        anything is written.
        """
        _require_unbuilt(run_dir)
        if (run_dir / GENERATOR_DIR / GENERATOR_RECORD).is_file():
            raise RunFolderConflict(
                "this run already generated its mesh from its inputs; start a new run to use others"
            )
        request = self.request(run_dir)
        if any(s.source_id == source.source_id for s in request.sources):
            raise WorkspaceError(f"the request already has a source {source.source_id!r}")
        photos = dict(request.photos)
        if photo is not None:
            photos[source.source_id] = photo
        updated = JobRequest.model_validate(
            {**request.model_dump(), "sources": [*request.sources, source], "photos": photos}
        )
        check_photos(updated.sources, updated.photos)
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
        """The pieces set, and the spec they make, of either kind. A spec written by hand (the
        command line) counts too."""
        pieces = (
            _read_json(run_dir / SPEC_PARTS_FILE) if (run_dir / SPEC_PARTS_FILE).is_file() else {}
        )
        spec_path = run_dir / SPEC_FILE
        spec = read_spec(spec_path) if spec_path.is_file() else None
        if any(p in pieces for p in PARTS_PIECES) or isinstance(spec, PartsSpec):
            kind = "parts"
            problem = None if spec is not None else _parts_problem(pieces)
            return SpecState(tuple(p for p in PARTS_PIECES if p in pieces), spec, kind, problem)
        kind = "spindle" if pieces or spec is not None else None
        return SpecState(tuple(p for p in SPEC_PARTS if p in pieces), spec, kind)

    def set_spec_part(self, run_dir: Path, part: str, values: dict[str, Any]) -> SpecState:
        """Save one part of the spec; with both parts set, write ``geometry_spec.json``.

        The joint part holds the orientation and split, plus ``decided_by`` and ``method``. The
        scale part holds ``center_height_m``, ``base_z`` and a note for the method.
        """
        if part not in SPEC_PARTS:
            raise WorkspaceError(f"unknown spec part {part!r}")
        path = _changeable_spec(run_dir)
        parts = _read_json(path) if path.is_file() else {}
        if any(p in parts for p in PARTS_PIECES):
            raise WorkspaceError(
                "this run's spec has several parts (set_spec_frame and the others); a single "
                "spindle's joint and scale cannot be added to it"
            )
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
        return SpecState(tuple(p for p in SPEC_PARTS if p in parts), spec, "spindle")

    # ----------------------------------------------------------------- a several-part spec
    def set_parts_piece(self, run_dir: Path, piece: str, value: Any) -> SpecState:
        """Set one piece of a several-part spec (decisions 0027, 0028): ``frame``,
        ``scale_length``, ``cuts`` or ``size_checks`` replaced whole; a part or a joint added,
        or replaced by its id. The piece is checked first, so a bad one is refused."""
        checked = _check_piece(piece, value)
        path = _changeable_spec(run_dir)
        pieces = _parts_pieces(path)
        if piece in PARTS_ENTRIES:
            pieces.setdefault(piece, {})[checked[PARTS_ENTRIES[piece]]] = checked
        else:
            pieces[piece] = checked
        return _save_parts_pieces(run_dir, path, pieces)

    def parts_pieces(self, run_dir: Path) -> dict[str, Any]:
        """A several-part spec's pieces as set so far (JSON values; parts and joints by id)."""
        return _parts_pieces(run_dir / SPEC_PARTS_FILE)

    def remove_parts_entry(self, run_dir: Path, piece: str, entry_id: str) -> SpecState:
        """Take a part or a joint out of a several-part spec, by its id."""
        if piece not in PARTS_ENTRIES:
            raise WorkspaceError(f"only {' and '.join(PARTS_ENTRIES)} are removed by id")
        path = _changeable_spec(run_dir)
        pieces = _parts_pieces(path)
        if entry_id not in pieces.get(piece, {}):
            raise WorkspaceError(f"the spec has no {piece[:-1]} {entry_id!r}")
        del pieces[piece][entry_id]
        return _save_parts_pieces(run_dir, path, pieces)


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


_PIECE_MODELS: dict[str, TypeAdapter[Any]] = {
    "frame": TypeAdapter(PartsFrame),
    "scale_length": TypeAdapter(ScaleReference),
    "cuts": TypeAdapter(list[PartCut]),
    "parts": TypeAdapter(SpecPart),
    "joints": TypeAdapter(SpecJoint),
    "size_checks": TypeAdapter(list[SizeCheck]),
}


def _check_piece(piece: str, value: Any) -> Any:
    """The piece as JSON values, once its own model accepts it."""
    if piece not in _PIECE_MODELS:
        raise WorkspaceError(f"unknown piece {piece!r} of a several-part spec")
    adapter = _PIECE_MODELS[piece]
    return adapter.dump_python(adapter.validate_python(value), mode="json")


def _changeable_spec(run_dir: Path) -> Path:
    """The draft's path, once the run may still change its spec."""
    _require_unbuilt(run_dir)
    if (run_dir / MESHES_DIR / ASSEMBLY_RECORD).is_file():
        raise RunFolderConflict(
            "this run's parts are already assembled from its spec; start a new run to change it"
        )
    return run_dir / SPEC_PARTS_FILE


def _parts_pieces(path: Path) -> dict[str, Any]:
    pieces = _read_json(path) if path.is_file() else {}
    if any(p in pieces for p in SPEC_PARTS):
        raise WorkspaceError(
            "this run's spec is a single spindle's (add_joint and set_scale); start a new run for "
            "a spec of several parts"
        )
    return pieces


def _parts_spec(pieces: dict[str, Any]) -> PartsSpec:
    """The spec the pieces make; ``ValidationError`` if they do not make one."""
    return PartsSpec.model_validate(
        {
            **pieces["frame"],
            "scale": pieces["scale_length"],
            "cuts": pieces["cuts"],
            "parts": list(pieces["parts"].values()),
            "joints": list(pieces.get("joints", {}).values()),
            "size_checks": pieces.get("size_checks", []),
        }
    )


def _parts_problem(pieces: dict[str, Any]) -> str | None:
    missing = [p for p in PARTS_REQUIRED if p not in pieces]
    if missing:
        return f"still to set: {', '.join(missing)}"
    try:
        _parts_spec(pieces)
    except ValidationError as error:
        return "; ".join(e["msg"] for e in error.errors())
    return None


def _save_parts_pieces(run_dir: Path, path: Path, pieces: dict[str, Any]) -> SpecState:
    """Save the pieces; write ``geometry_spec.json`` while they make a valid spec, and remove it
    while they do not, so only a valid spec is ever built."""
    _write_json(path, pieces)
    spec_path = run_dir / SPEC_FILE
    problem = _parts_problem(pieces)
    spec = None if problem else _parts_spec(pieces)
    if spec is None:
        spec_path.unlink(missing_ok=True)
    else:
        _write_json(spec_path, spec.model_dump(mode="json"))
    return SpecState(tuple(p for p in PARTS_PIECES if p in pieces), spec, "parts", problem)


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
