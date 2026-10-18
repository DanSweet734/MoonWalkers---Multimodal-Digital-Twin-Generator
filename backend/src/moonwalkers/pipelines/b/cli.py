"""Command line for Pipeline B (decision 0012). Run from ``backend/``::

    uv run python -m moonwalkers.pipelines.b build RUN --reference FILE
    uv run python -m moonwalkers.pipelines.b inspect RUN [--up +y --front +z] [--preview]

``RUN`` is a run folder, ``data/machines/<machine>/runs/<run>``, holding ``request.json`` (a
``JobRequest`` with the photo as a source). ``build`` sends the request through the orchestrator:
the first time it generates the mesh and stops for the geometry spec; once
``geometry_spec.json`` exists, it stores the twin in ``data/kb``, exports ``twin.usda`` (plus
``checks/spin.usda`` and ``checks/quarter_turn.usda`` for the Isaac Sim check) and writes
``RUN.md``. ``inspect`` renders and measures the generated mesh, and ``--preview`` tries the spec
without storing anything. The generator environment is found through ``--gen-root`` or the
``MOONWALKERS_GEN_ROOT`` environment variable (docs/setup/generators.md).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import platform
import sys
from collections.abc import Sequence
from importlib.metadata import version as package_version
from pathlib import Path
from typing import Any

from moonwalkers.contracts.pipeline_result import (
    Issue,
    JobResult,
    PipelineId,
    PipelineResult,
    TwinRecord,
)
from moonwalkers.generators.base import GeneratorError
from moonwalkers.generators.hunyuan3d import Hunyuan3DConfig, Hunyuan3DGenerator
from moonwalkers.kb import JsonKnowledgeBase, KnowledgeBase
from moonwalkers.orchestrator import JobRequest, Orchestrator, OrchestratorError
from moonwalkers.pipelines import default_pipelines
from moonwalkers.usd.exporter import DriveSettings, ExportError, export_twin
from moonwalkers.usd.validate import validate_file

from .assemble import GeometrySpec
from .inspection import format_inspection, format_preview, inspect_mesh, preview_parts
from .pipeline import (
    GENERATOR_DIR,
    GENERATOR_RECORD,
    SPEC_FILE,
    GeometrySpecMissing,
    PipelineB,
    ReferenceFacts,
    RunFolderConflict,
    load_reference,
)

GEN_ROOT_ENV = "MOONWALKERS_GEN_ROOT"
REQUEST_FILE = "request.json"
TWIN_FILE = "twin.usda"
CHECKS_DIR = "checks"
# Drives for the hand check in Isaac Sim, as in Phase 2; chosen by us, not machine facts.
CHECK_DRIVES = {
    "spin.usda": DriveSettings.spin(math.radians(30.0)),
    "quarter_turn.usda": DriveSettings.hold(math.radians(90.0)),
}
AXES = ("+x", "-x", "+y", "-y", "+z", "-z")


class UsageError(Exception):
    """The command was given arguments it cannot use."""


EXPECTED_ERRORS = (
    UsageError,
    GeometrySpecMissing,
    RunFolderConflict,
    OrchestratorError,
    GeneratorError,
    ExportError,
    FileNotFoundError,
)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return args.command(args)
    except GeometrySpecMissing as exc:
        print(f"stopped: {exc}")
        return 2
    except EXPECTED_ERRORS as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m moonwalkers.pipelines.b", description=__doc__)
    commands = parser.add_subparsers(required=True)

    build = commands.add_parser("build", help="build (or reuse) the twin for a run's request")
    build.add_argument("run_dir", type=Path, help="data/machines/<machine>/runs/<run>")
    build.add_argument("--reference", type=Path, required=True, help="reference facts JSON")
    build.add_argument(
        "--request", type=Path, help=f"JobRequest JSON (default: RUN/{REQUEST_FILE})"
    )
    build.add_argument("--gen-root", type=Path, help=f"generator folder (default: ${GEN_ROOT_ENV})")
    build.add_argument("--data", type=Path, help="data folder (default: from the run folder)")
    build.add_argument("--kb", type=Path, help="knowledge base folder (default: DATA/kb)")
    build.set_defaults(command=_build)

    inspect = commands.add_parser("inspect", help="render and measure the generated mesh")
    inspect.add_argument("run_dir", type=Path)
    inspect.add_argument("--up", choices=AXES, help="the generator axis that points up")
    inspect.add_argument("--front", choices=AXES, help="the generator axis the spindle faces")
    inspect.add_argument("--window", type=float, help="profile radius limit (model units)")
    inspect.add_argument(
        "--preview", action="store_true", help=f"try RUN/{SPEC_FILE} without storing anything"
    )
    inspect.add_argument("--reference", type=Path, help="reference facts, for size checks")
    inspect.set_defaults(command=_inspect)
    return parser


# ------------------------------------------------------------------------------------ inspect
def _inspect(args: argparse.Namespace) -> int:
    run_dir = args.run_dir
    mesh = _generated_mesh(run_dir)
    if args.preview:
        spec_path = run_dir / SPEC_FILE
        if not spec_path.is_file():
            raise FileNotFoundError(f"--preview needs {spec_path}")
        spec = GeometrySpec.model_validate_json(spec_path.read_text(encoding="utf-8"))
        reference = load_reference(args.reference) if args.reference else None
        print(format_preview(preview_parts(mesh, spec, run_dir / "preview"), reference))
        return 0
    if (args.up is None) != (args.front is None):
        raise UsageError("give both --up and --front, or neither")
    out_dir = run_dir / ("inspect_oriented" if args.up else "inspect_raw")
    print(format_inspection(inspect_mesh(mesh, out_dir, args.up, args.front, args.window)))
    return 0


def _generated_mesh(run_dir: Path) -> Path:
    record = run_dir / GENERATOR_DIR / GENERATOR_RECORD
    if record.is_file():
        name = json.loads(record.read_text(encoding="utf-8"))["mesh_file"]
        return run_dir / GENERATOR_DIR / name
    mesh = run_dir / GENERATOR_DIR / "mesh.glb"
    if not mesh.is_file():
        raise FileNotFoundError(f"no generated mesh in {run_dir / GENERATOR_DIR}; run build first")
    return mesh


# -------------------------------------------------------------------------------------- build
def _build(args: argparse.Namespace) -> int:
    run_dir = args.run_dir.resolve()
    data_dir = (args.data or _data_dir_of(run_dir)).resolve()
    gen_root = args.gen_root or os.environ.get(GEN_ROOT_ENV)
    if gen_root is None:
        raise UsageError(f"the generator folder is needed: pass --gen-root or set {GEN_ROOT_ENV}")
    request_path = args.request or run_dir / REQUEST_FILE
    request = JobRequest.model_validate_json(request_path.read_text(encoding="utf-8"))
    reference = load_reference(args.reference)
    kb = JsonKnowledgeBase(args.kb or data_dir / "kb")

    generator = Hunyuan3DGenerator(Hunyuan3DConfig.under(Path(gen_root)))
    pipeline_b = PipelineB(generator, data_dir, run_dir, reference)
    findings: list[Issue] = []

    def export(twin: TwinRecord, results: Sequence[PipelineResult]) -> str:
        path = run_dir / TWIN_FILE
        if path.exists():
            raise RunFolderConflict(
                f"{path} exists: this run folder already holds an exported twin"
            )
        export_twin(twin, results, path, DriveSettings.hold(0.0), data_dir)
        findings.extend(validate_file(path))
        errors = [i for i in findings if i.severity == "error"]
        if errors:
            path.unlink()
            raise ExportError(f"the exported twin failed validation: {errors[0].message}")
        for name, drive in CHECK_DRIVES.items():
            export_twin(twin, results, run_dir / CHECKS_DIR / name, drive, data_dir)
        return path.relative_to(data_dir).as_posix()

    pipelines = {**default_pipelines(), PipelineId.B: pipeline_b}
    job = Orchestrator(kb, pipelines, exporter=export).run_job(request)
    print(job.message)
    _write_json(run_dir / f"{request_path.stem}.job_result.json", job.model_dump(mode="json"))
    if not job.reused_existing:
        _write_run_files(run_dir, kb, job, request_path, args.reference, reference, findings)
        for issue in findings:
            print(f"  validation {issue.severity}: {issue.message} ({issue.ref or '-'})")
    return 0


def _data_dir_of(run_dir: Path) -> Path:
    """``data/`` for a run folder ``data/machines/<machine>/runs/<run>`` (data/README.md)."""
    parts = run_dir.parts
    if len(parts) < 5 or parts[-2] != "runs" or parts[-4] != "machines":
        raise UsageError(f"{run_dir} is not data/machines/<machine>/runs/<run>; pass --data")
    return run_dir.parents[3]


def _write_run_files(
    run_dir: Path,
    kb: KnowledgeBase,
    job: JobResult,
    request_path: Path,
    reference_path: Path,
    reference: ReferenceFacts,
    findings: list[Issue],
) -> None:
    """Copies of the stored records, and ``RUN.md`` for the run's details and the review."""
    results = [kb.get_result(rid) for rid in job.twin.built_from]
    stored = [r for r in results if r is not None]
    _write_json(run_dir / "twin_record.json", job.twin.model_dump(mode="json"))
    for result in stored:
        name = f"pipeline_result_{result.pipeline.value.lower()}.json"
        _write_json(run_dir / name, result.model_dump(mode="json"))
    record_path = run_dir / GENERATOR_DIR / GENERATOR_RECORD
    generator = json.loads(record_path.read_text(encoding="utf-8"))
    lines = _run_notes(job, stored, generator, request_path, reference_path, reference, findings)
    (run_dir / "RUN.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def _run_notes(
    job: JobResult,
    results: list[PipelineResult],
    generator: dict[str, Any],
    request_path: Path,
    reference_path: Path,
    reference: ReferenceFacts,
    findings: list[Issue],
) -> list[str]:
    twin = job.twin
    details = generator["details"]
    versions = details.get("versions", {})
    backend = ", ".join(
        f"{name} {package_version(name)}"
        for name in ("moonwalkers", "usd-core", "trimesh", "numpy", "pydantic")
    )
    lines = [
        f"# Run: {twin.twin_id} (Pipeline B, one photo)",
        "",
        f"- Twin: {twin.twin_id}, status {twin.status}, USD `{twin.usd_path}`",
        f"- Created (UTC): {twin.created_at.isoformat(timespec='seconds')}",
        f"- Request: `{request_path.name}`, job `{job.job_id}`",
        f"- Reference facts: `{reference_path.as_posix()}` ({len(reference.facts)} facts)",
        f"- Backend: {backend}, Python {platform.python_version()}",
        f"- Generator: {generator['generator']['name']} {generator['generator'].get('version')}"
        f" on {details.get('device')}, Python {details.get('python')}; "
        + ", ".join(f"{k} {v}" for k, v in versions.items()),
        f"- Generator settings: {_settings(generator['generator']['params'])}",
        (
            f"- Generation: {generator['seconds']:.1f} s "
            f"({_timings(details.get('timings_s', {}))}); "
            f"peak VRAM {details.get('peak_vram_allocated_gb')} GB allocated, "
            f"{details.get('peak_vram_reserved_gb')} GB reserved"
        ),
    ]
    for result in results:
        if result.scale is not None and result.scale.scale_factor is not None:
            lines.append(
                f"- Scale: {result.scale.scale_factor:.6f} m per model unit "
                f"({result.scale.reference} {result.scale.known_value_m} m = "
                f"{result.scale.measured_model_units:.4f} model units)"
            )
        for part in result.parts:
            lines.append(
                f"- Part `{part.part_id}`: `{part.geometry_file}`, bounds (m) "
                f"{_triple(part.bbox_min_m)} to {_triple(part.bbox_max_m)}"
            )
        for joint in result.joints:
            lines.append(
                f"- Joint `{joint.joint_id}`: {joint.joint_type} about {list(joint.axis)} at "
                f"{list(joint.origin_m)} m, {joint.parent_part} -> {joint.child_part}"
            )
        lines += ["", f"## Issues in the Pipeline {result.pipeline.value} result", ""]
        lines += [f"- {i.severity}: {i.message}" for i in result.issues]
    lines += ["", "## Validation (moonwalkers.usd.validate)", ""]
    lines += [f"- {i.severity}: {i.message} ({i.ref or '-'})" for i in findings] or [
        "- no findings"
    ]
    lines += [
        "",
        "## Isaac Sim check (fill in)",
        "",
        "- Isaac Sim version/build:",
        f"- `{TWIN_FILE}` (spindle holds 0 deg):",
        "- `checks/spin.usda` (spindle turns at 30 deg/s):",
        "- `checks/quarter_turn.usda` (spindle turns to 90 deg and holds):",
        "- Success level reached (1-3):",
        "- Reviewer notes:",
    ]
    return lines


def _settings(params: dict[str, Any]) -> str:
    return ", ".join(f"{k} {v}" for k, v in params.items() if k != "versions")


def _timings(timings: dict[str, float]) -> str:
    return ", ".join(f"{k} {v:.1f} s" for k, v in timings.items())


def _triple(values: Sequence[float] | None) -> str:
    return "-" if values is None else "(" + ", ".join(f"{v:+.4f}" for v in values) + ")"


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    sys.exit(main())
