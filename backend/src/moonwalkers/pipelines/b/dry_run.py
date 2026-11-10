"""Build a run in a scratch copy of the data folder and run both validators, storing nothing for
real (the lab's machines plan, tool gap 7).

A real build stores a twin version for good (v2's lesson, CLAUDE.md), so the T33901's builds were
first tried by hand in a scratch copy: three dry runs for the agent's v9, one each for v10 and
v11 (drill-press report, section 7.3, item 7; ``docs/agent-procedure.md``, step 5b.10). This does
the same in one step:

- copies into ``<data>/scratch/<date>_dry-run-<NNN>/data/`` what the build reads: the run folder
  (without its previews), the knowledge base, each file the request and the reading notes cite,
  and each mask a photo's cut-out names (decision 0029);
- gives the copied request its own job id, as the knowledge base refuses a job it already holds;
- builds the copy through the orchestrator, as ``submit_twin`` would;
- runs our validator and NVIDIA's asset validator on every USD file the build wrote. NVIDIA's is a
  development dependency (``pyproject.toml``); without it, its findings are reported as not run.

The scratch folder is kept, so its files can be opened; ``data/scratch/`` is gitignored with the
rest of ``data/``.
"""

from __future__ import annotations

import shutil
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from moonwalkers.clock import Clock, utc_now
from moonwalkers.contracts.pipeline_result import Issue, PipelineId
from moonwalkers.generators.base import GeneratorError, ImageTo3DGenerator
from moonwalkers.kb import JsonKnowledgeBase
from moonwalkers.orchestrator import JobRequest, OrchestratorError
from moonwalkers.pipelines.base import Pipeline
from moonwalkers.usd.exporter import ExportError
from moonwalkers.usd.validate import validate_file

from .build import REQUEST_FILE, build_run
from .pipeline import GeometrySpecMissing, ReferenceFacts, RunFolderConflict

REFERENCE_FILE = "reference_facts.json"  # the agent's reading notes (workspace.runs)
# Folders in a run that only previews write: nothing a build reads.
PREVIEW_DIRS = frozenset(
    {"preview", "preview_parts", "inspect_raw", "inspect_oriented", "cutouts", "views"}
)
DRY_RUN_SUFFIX = "-dry-run"
BUILD_ERRORS = (
    OrchestratorError,
    ExportError,
    RunFolderConflict,
    GeometrySpecMissing,
    GeneratorError,
    ValueError,
    FileNotFoundError,
)


@dataclass(frozen=True)
class FileFindings:
    file: Path
    ours: list[Issue]
    nvidia: list[Issue] | None  # None: NVIDIA's validator is not installed


@dataclass(frozen=True)
class DryRun:
    data_dir: Path  # the scratch data folder
    run_dir: Path  # the copied run
    message: str  # the build's message, or why it stopped
    built: bool
    twin_file: Path | None = None
    files: list[FileFindings] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        """Built, and neither validator found an error or a warning."""
        return self.built and not any(
            i.severity in ("error", "warning")
            for f in self.files
            for i in [*f.ours, *(f.nvidia or [])]
        )


def scratch_copy(data_dir: Path, run_dir: Path, clock: Clock = utc_now) -> tuple[Path, Path]:
    """A new scratch data folder holding what building ``run_dir`` reads; returns it and the
    copied run folder."""
    data_dir, run_dir = Path(data_dir).resolve(), Path(run_dir).resolve()
    if not run_dir.is_relative_to(data_dir):
        raise ValueError(f"run folder {run_dir} is not inside data folder {data_dir}")
    if sorted(run_dir.glob("twin.usd*")) or (run_dir / "twin_record.json").is_file():
        raise RunFolderConflict(f"{run_dir} has already built its twin: nothing to try")
    day = clock().astimezone().date().isoformat()
    root = data_dir / "scratch"
    root.mkdir(parents=True, exist_ok=True)
    number = 1
    while True:  # mkdir refuses an existing folder, so two dry runs never share one
        folder = root / f"{day}_dry-run-{number:03d}"
        try:
            folder.mkdir()
            break
        except FileExistsError:
            number += 1
    scratch = folder / "data"
    copied_run = scratch / run_dir.relative_to(data_dir)
    shutil.copytree(
        run_dir, copied_run, ignore=lambda d, names: [n for n in names if n in PREVIEW_DIRS]
    )
    if (data_dir / "kb").is_dir():
        shutil.copytree(data_dir / "kb", scratch / "kb")
    for relative in _cited_files(data_dir, copied_run):
        source = data_dir / relative
        target = scratch / relative
        if source.is_file() and not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    request_path = copied_run / REQUEST_FILE
    request = JobRequest.model_validate_json(request_path.read_text(encoding="utf-8"))
    if not request.job_id.endswith(DRY_RUN_SUFFIX):
        request = request.model_copy(update={"job_id": request.job_id + DRY_RUN_SUFFIX})
    request_path.write_text(request.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return scratch, copied_run


def _cited_files(data_dir: Path, run_dir: Path) -> list[Path]:
    """The data folder's files the run's request and reading notes name, relative to it."""
    request = JobRequest.model_validate_json((run_dir / REQUEST_FILE).read_text(encoding="utf-8"))
    uris = [s.uri for s in request.sources if s.kind == "file"]
    uris += [p.cutout.mask for p in request.photos.values() if p.cutout and p.cutout.mask]
    notes = run_dir / REFERENCE_FILE
    if notes.is_file():
        reference = ReferenceFacts.model_validate_json(notes.read_text(encoding="utf-8"))
        uris += [s.uri for s in reference.sources if s.kind == "file"]
    files = []
    for uri in uris:
        path = (data_dir / uri).resolve()
        if path.is_relative_to(data_dir) and path.is_file():
            files.append(path.relative_to(data_dir))
    return files


def dry_run(
    run_dir: Path,
    data_dir: Path,
    reference: ReferenceFacts | None,
    generator: ImageTo3DGenerator,
    pipelines: Mapping[PipelineId, Pipeline] | None = None,
    clock: Clock = utc_now,
    reference_path: Path | None = None,
) -> DryRun:
    """Build ``run_dir`` in a scratch copy and validate every file it wrote. ``reference`` is
    the reference facts the real build would use; ``reference_path``, their file, is copied
    beside the run when it is outside it (the HA5C's and the T33901's live in the package)."""
    scratch, copied = scratch_copy(data_dir, run_dir, clock)
    if reference_path is not None and not (copied / REFERENCE_FILE).is_file():
        shutil.copy2(reference_path, copied / REFERENCE_FILE)
    try:
        outcome = build_run(
            copied,
            scratch,
            copied / REQUEST_FILE,
            reference,
            copied / REFERENCE_FILE if (copied / REFERENCE_FILE).is_file() else None,
            generator,
            JsonKnowledgeBase(scratch / "kb"),
            pipelines=pipelines,
        )
        message, built, twin_file = outcome.job.message, True, outcome.twin_file
    except BUILD_ERRORS as exc:
        message, built, twin_file = f"the build stopped: {exc}", False, None
    files = [
        FileFindings(path, validate_file(path), nvidia_findings(path)) for path in usd_files(copied)
    ]
    return DryRun(scratch, copied, message, built, twin_file, files)


def usd_files(run_dir: Path) -> list[Path]:
    """Every USD file a build writes in a run: the twin, its check files, and controls."""
    return sorted(
        p for p in Path(run_dir).rglob("*.usd*") if p.suffix in (".usd", ".usda", ".usdc")
    )


def nvidia_findings(path: Path) -> list[Issue] | None:
    """NVIDIA's asset validator on one file, as ``omni_asset_validate`` runs it; None when it is
    not installed. Its failures are errors here, and its warnings warnings."""
    try:
        from omni.asset_validator import ValidationEngine
    except ImportError:
        return None
    results = ValidationEngine(init_rules=True).validate(str(path))
    issues = []
    for found in results.issues():
        severity = found.severity.name.lower()
        rule = type(found.rule).__name__ if found.rule is not None else "rule"
        where = str(found.at.path) if getattr(found.at, "path", None) is not None else None
        issues.append(
            Issue(
                severity="error"
                if severity in ("error", "failure")
                else "warning"
                if severity == "warning"
                else "info",
                message=f"{rule}: {found.message}",
                ref=where,
            )
        )
    return issues
