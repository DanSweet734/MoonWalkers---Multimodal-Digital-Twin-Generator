"""Build, or reuse, the twin for one run folder through the orchestrator (decisions 0012, 0013).

The command line (``cli.py``) and the MCP server (``moonwalkers.mcp``) both use ``build_run``, so
a twin is built the same way whoever asks for it:

- Pipeline B runs on the run's request: it generates the mesh, or stops with
  ``GeometrySpecMissing`` until the spec exists, then assembles the parts.
- The orchestrator stores the result, or reuses a stored twin, following decision 0009.
- A new twin is exported first, as ``twin.usdc`` plus the two check files, and validated. The
  run folder then gets copies of the stored records and ``RUN.md``.
"""

from __future__ import annotations

import json
import math
import platform
import shutil
from collections.abc import Sequence
from dataclasses import dataclass, field
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
from moonwalkers.control.export import write_program_folder
from moonwalkers.control.program import ProgramFile, runnable_behaviors
from moonwalkers.generators.base import ImageTo3DGenerator
from moonwalkers.kb import KnowledgeBase
from moonwalkers.orchestrator import JobRequest, Orchestrator
from moonwalkers.pipelines import default_pipelines
from moonwalkers.usd.exporter import DriveSettings, ExportError, export_twin
from moonwalkers.usd.validate import validate_file

from .pipeline import GENERATOR_DIR, GENERATOR_RECORD, PipelineB, ReferenceFacts, RunFolderConflict

REQUEST_FILE = "request.json"
JOB_RESULT_SUFFIX = ".job_result.json"
TWIN_FILE = "twin.usdc"  # binary: a generated mesh is too big for text USD (decision 0012)
CHECKS_DIR = "checks"
PROGRAMS_DIR = "programs"  # one folder per control behaviour with a program (decision 0016)
# Drives for the hand check in Isaac Sim, as in Phase 2; chosen by us, not machine facts.
CHECK_DRIVES = {
    "spin.usdc": DriveSettings.spin(math.radians(30.0)),
    "quarter_turn.usdc": DriveSettings.hold(math.radians(90.0)),
}


@dataclass(frozen=True)
class BuildOutcome:
    job: JobResult
    validation: list[Issue] = field(default_factory=list)  # findings on the exported twin
    twin_file: Path | None = None  # None when the stored twin was reused
    check_files: list[Path] = field(default_factory=list)


def build_run(
    run_dir: Path,
    data_dir: Path,
    request_path: Path,
    reference: ReferenceFacts | None,
    reference_path: Path | None,
    generator: ImageTo3DGenerator,
    kb: KnowledgeBase,
) -> BuildOutcome:
    """Send the run's request through the orchestrator with Pipeline B.

    Raises what the pipeline and the orchestrator raise, for example ``GeometrySpecMissing``
    before the spec exists, or ``RunFolderConflict`` when the run folder already holds a twin.
    """
    run_dir, data_dir = Path(run_dir).resolve(), Path(data_dir).resolve()
    request = JobRequest.model_validate_json(Path(request_path).read_text(encoding="utf-8"))
    pipeline_b = PipelineB(generator, data_dir, run_dir, reference)
    findings: list[Issue] = []
    exported: list[Path] = []

    def export(twin: TwinRecord, results: Sequence[PipelineResult]) -> str:
        path = run_dir / TWIN_FILE
        earlier = sorted(p.name for p in run_dir.glob("twin.usd*"))
        if earlier:
            raise RunFolderConflict(
                f"{run_dir} already holds an exported twin ({', '.join(earlier)}); "
                "build a new version in a new run folder"
            )
        programs = program_files(results)  # a program that cannot run fails before any file
        export_twin(twin, results, path, DriveSettings.hold(0.0), data_dir)
        written = [path]
        try:
            findings.extend(validate_file(path))
            errors = [i for i in findings if i.severity == "error"]
            if errors:
                raise ExportError(f"the exported twin failed validation: {errors[0].message}")
            for name, drive in CHECK_DRIVES.items():
                check = run_dir / CHECKS_DIR / name
                written.append(check)
                export_twin(twin, results, check, drive, data_dir)
            for program in programs:  # level 3: the program drives the joint (decision 0016)
                folder = run_dir / PROGRAMS_DIR / program.name
                written.append(folder)
                write_program_folder(folder, program, twin, results, data_dir)
        except BaseException:  # nothing is stored, so leave no files that claim otherwise
            for item in written:
                shutil.rmtree(item) if item.is_dir() else item.unlink(missing_ok=True)
            raise
        exported.extend(p for p in written if p.is_file())
        return path.relative_to(data_dir).as_posix()

    pipelines = {**default_pipelines(), PipelineId.B: pipeline_b}
    job = Orchestrator(kb, pipelines, exporter=export).run_job(request)
    write_job_result(run_dir, Path(request_path), job)
    if job.reused_existing:
        return BuildOutcome(job)
    _write_run_files(run_dir, kb, job, Path(request_path), reference_path, reference, findings)
    return BuildOutcome(job, findings, exported[0], exported[1:])


def program_files(results: Sequence[PipelineResult]) -> list[ProgramFile]:
    """A program file for each control behaviour that carries a program to run, with the
    sources its citations name (decision 0016)."""
    programs = []
    for result in results:
        for behavior in runnable_behaviors(result.control):
            cited = {c.source_id for c in behavior.citations}
            programs.append(
                ProgramFile(
                    name=behavior.behavior_id.lower().replace("_", "-"),
                    sources=[s for s in result.sources if s.source_id in cited],
                    behavior=behavior,
                )
            )
    return programs


def job_result_file(request_path: Path) -> str:
    """The file name for what a request returned: ``request.json`` gives
    ``request.job_result.json``, written next to it in the run folder."""
    return f"{Path(request_path).stem}{JOB_RESULT_SUFFIX}"


def write_job_result(run_dir: Path, request_path: Path, job: JobResult) -> Path:
    path = Path(run_dir) / job_result_file(request_path)
    _write_json(path, job.model_dump(mode="json"))
    return path


def _write_run_files(
    run_dir: Path,
    kb: KnowledgeBase,
    job: JobResult,
    request_path: Path,
    reference_path: Path | None,
    reference: ReferenceFacts | None,
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
    reference_path: Path | None,
    reference: ReferenceFacts | None,
    findings: list[Issue],
) -> list[str]:
    twin = job.twin
    details = generator["details"]
    versions = details.get("versions", {})
    backend = ", ".join(
        f"{name} {package_version(name)}"
        for name in ("moonwalkers", "usd-core", "trimesh", "numpy", "pydantic")
    )
    facts = (
        f"`{reference_path.as_posix()}` ({len(reference.facts)} facts)"
        if reference is not None and reference_path is not None
        else "none"
    )
    lines = [
        f"# Run: {twin.twin_id} (Pipeline B, one photo)",
        "",
        f"- Twin: {twin.twin_id}, status {twin.status}, USD `{twin.usd_path}`",
        f"- Created (UTC): {twin.created_at.isoformat(timespec='seconds')}",
        f"- Request: `{request_path.name}`, job `{job.job_id}`",
        f"- Reference facts: {facts}",
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
    programs = program_files(results)
    if programs:
        lines += ["", "## Programs (decision 0016)", ""]
        lines += [
            f"- `{PROGRAMS_DIR}/{p.name}/`: {p.behavior.name}; see its PROGRAM.md" for p in programs
        ]
    lines += [
        "",
        "## Isaac Sim check (fill in)",
        "",
        "- Isaac Sim version/build:",
        f"- `{TWIN_FILE}` (spindle holds 0 deg):",
        "- `checks/spin.usdc` (spindle turns at 30 deg/s):",
        "- `checks/quarter_turn.usdc` (spindle turns to 90 deg and holds):",
        *(
            f"- `{PROGRAMS_DIR}/{p.name}/program.usdc` with run_program.py (the program "
            "drives the spindle):"
            for p in programs
        ),
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
