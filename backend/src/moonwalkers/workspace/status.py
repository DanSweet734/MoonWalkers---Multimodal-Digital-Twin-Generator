"""How far each job has got, read from the files its steps leave in the run folder (decision 0014).

The dashboard (through the API) and the agent's ``list_jobs`` tool both read jobs this way, so they
agree on a job's stage. A run folder is a job when it holds ``request.json``. The steps, and the
file each one leaves (data/README.md):

- photo: a machine photo in ``request.json`` (``add_input``, or an upload in the dashboard);
- notes: ``reference_facts.json`` (``add_reference_source`` and the other note tools);
- mesh: ``generator/run.json`` (``generate_geometry``);
- spec: ``geometry_spec.json``, written once ``add_joint`` and ``set_scale`` are both done;
- preview: ``preview/assembled/views.png`` (``preview_twin``; optional);
- twin: ``twin_record.json`` (``submit_twin``), or a reuse recorded in ``request.job_result.json``.

Command-line builds (decision 0012) read their notes from a file outside the run folder, so their
notes step counts as done once the twin is built.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from moonwalkers.contracts.pipeline_result import InputType, JobResult, Source, TwinRecord
from moonwalkers.kb import machine_key
from moonwalkers.orchestrator import JobRequest
from moonwalkers.pipelines.b.build import JOB_RESULT_SUFFIX, REQUEST_FILE, job_result_file
from moonwalkers.pipelines.b.pipeline import GENERATOR_DIR, GENERATOR_RECORD, ReferenceFacts

from .runs import SpecState, Workspace

TWIN_RECORD = "twin_record.json"
PREVIEW_SHEET = "preview/assembled/views.png"
MACHINE_FOLDER = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")

Stage = Literal["no_photo", "waiting_for_agent", "in_progress", "built", "reused", "unreadable"]
StepName = Literal["photo", "notes", "mesh", "spec", "preview", "twin"]
OPEN_STAGES: tuple[Stage, ...] = ("no_photo", "waiting_for_agent", "in_progress")


class JobStep(BaseModel):
    step: StepName
    label: str
    done: bool
    detail: str | None = None


class RequestRecord(BaseModel):
    """One request file in the run folder and, once it has run, what it returned."""

    file: str
    job_id: str
    machine_key: str | None
    new_version: bool
    result: JobResult | None


class RunStatus(BaseModel):
    """One job: a run folder and how far its steps have got."""

    run: str = Field(description="machines/<machine>/runs/<run>, relative to the data folder")
    machine: str = Field(description="the machine folder, for example haas-ha5c")
    name: str = Field(description="the run folder, for example 2026-10-18_run-001")
    job_id: str | None
    machine_key: str | None
    new_version: bool
    photo: Source | None
    stage: Stage
    stage_label: str
    twin_id: str | None = Field(description="the twin this job built or reused")
    updated_at: datetime = Field(description="when a file in the run folder last changed")
    steps: list[JobStep]
    requests: list[RequestRecord] = Field(description="request.json first, then any others")


def run_status(ws: Workspace, run_dir: Path) -> RunStatus | None:
    """The job in ``run_dir``, or None when the folder holds no ``request.json``."""
    run_dir = Path(run_dir)
    if not (run_dir / REQUEST_FILE).is_file():
        return None
    where: dict[str, Any] = {
        "run": ws.relative(run_dir),
        "machine": run_dir.parent.parent.name,
        "name": run_dir.name,
        "updated_at": _updated_at(run_dir),
    }
    try:
        return _status(ws, run_dir, where)
    except (OSError, ValueError) as exc:  # pydantic's ValidationError is a ValueError
        first_line = str(exc).splitlines()[0] if str(exc) else type(exc).__name__
        return RunStatus(
            **where,
            job_id=None,
            machine_key=None,
            new_version=False,
            photo=None,
            stage="unreadable",
            stage_label=f"Cannot read this run's files: {first_line}",
            twin_id=None,
            steps=[],
            requests=[],
        )


def list_runs(ws: Workspace, machine: str | None = None) -> list[RunStatus]:
    """Every job in the data folder (or one machine folder's), the most recently changed first."""
    if machine is not None and not MACHINE_FOLDER.fullmatch(machine):
        raise ValueError(f"{machine!r} is not a machine folder name, for example 'haas-ha5c'")
    pattern = f"{machine or '*'}/runs/*"
    statuses = [run_status(ws, d) for d in (ws.data_dir / "machines").glob(pattern) if d.is_dir()]
    found = [s for s in statuses if s is not None]
    return sorted(found, key=lambda s: (s.updated_at, s.run), reverse=True)


# ------------------------------------------------------------------------------------- helpers
def _status(ws: Workspace, run_dir: Path, where: dict[str, Any]) -> RunStatus:
    requests = [_request_record(run_dir, p) for p in _request_files(run_dir)]
    main, request = requests[0], ws.request(run_dir)
    photo = next((s for s in request.sources if s.input_type == InputType.MACHINE_PHOTO), None)
    twin = _twin(run_dir / TWIN_RECORD)
    reused = main.result if main.result is not None and main.result.reused_existing else None
    spec = ws.spec_state(run_dir)
    steps = [
        JobStep(
            step="photo",
            label="Photo added",
            done=photo is not None,
            detail=photo.uri if photo else None,
        ),
        _notes_step(ws.reference(run_dir), built=twin is not None),
        _mesh_step(_read_json(run_dir / GENERATOR_DIR / GENERATOR_RECORD)),
        _spec_step(spec),
        JobStep(step="preview", label="Preview rendered", done=(run_dir / PREVIEW_SHEET).is_file()),
        _twin_step(twin, reused),
    ]

    twin_id: str | None = None
    if reused is not None:
        stage, twin_id = "reused", reused.twin.twin_id
        label = f"Reused {twin_id}"
    elif twin is not None:
        stage, twin_id = "built", twin.twin_id
        label = f"Built {twin_id}"
    elif photo is None:
        stage, label = "no_photo", "No photo yet"
    elif not any(s.done for s in steps[1:]) and not spec.parts:
        stage, label = "waiting_for_agent", "Waiting for the agent"
    else:
        stage = "in_progress"
        label = f"In progress: {[s for s in steps if s.done][-1].label.lower()}"
    return RunStatus(
        **where,
        job_id=main.job_id,
        machine_key=main.machine_key,
        new_version=main.new_version,
        photo=photo,
        stage=stage,
        stage_label=label,
        twin_id=twin_id,
        steps=steps,
        requests=requests,
    )


def _request_files(run_dir: Path) -> list[Path]:
    """``request.json`` first, then other ``request*.json`` files (for example reuse checks)."""
    others = sorted(
        p
        for p in run_dir.glob("request*.json")
        if p.name != REQUEST_FILE and not p.name.endswith(JOB_RESULT_SUFFIX)
    )
    return [run_dir / REQUEST_FILE, *others]


def _request_record(run_dir: Path, path: Path) -> RequestRecord:
    request = JobRequest.model_validate_json(path.read_text(encoding="utf-8"))
    result_path = run_dir / job_result_file(path)
    result = (
        JobResult.model_validate_json(result_path.read_text(encoding="utf-8"))
        if result_path.is_file()
        else None
    )
    machine = request.machine
    return RequestRecord(
        file=path.name,
        job_id=request.job_id,
        machine_key=machine_key(machine.manufacturer, machine.model) if machine else None,
        new_version=request.new_version,
        result=result,
    )


def _notes_step(reference: ReferenceFacts | None, built: bool) -> JobStep:
    if reference is None:
        detail = "from a file given to the command-line build (RUN.md)" if built else None
        return JobStep(step="notes", label="Reading notes recorded", done=built, detail=detail)
    detail = (
        f"{len(reference.sources)} source(s), {len(reference.facts)} fact(s), "
        f"{len(reference.control)} control behaviour(s), {len(reference.issues)} issue(s)"
    )
    if reference.identity is not None:
        detail += f"; identified as {reference.identity.manufacturer} {reference.identity.model}"
    return JobStep(step="notes", label="Reading notes recorded", done=True, detail=detail)


def _mesh_step(record: dict[str, Any] | None) -> JobStep:
    if record is None:
        return JobStep(step="mesh", label="Mesh generated", done=False)
    generator = record.get("generator", {})
    detail = f"{generator.get('name')} {generator.get('version')}"
    if isinstance(record.get("seconds"), int | float):
        detail += f" in {record['seconds']:.1f} s"
    return JobStep(step="mesh", label="Mesh generated", done=True, detail=detail)


def _spec_step(state: SpecState) -> JobStep:
    if state.spec is not None:
        detail = f"decided by {state.spec.decided_by}"
    elif state.parts:
        missing = [p for p in ("joint", "scale") if p not in state.parts]
        detail = f"{', '.join(state.parts)} set; still to set: {', '.join(missing)}"
    else:
        detail = None
    return JobStep(
        step="spec", label="Joint and scale set", done=state.spec is not None, detail=detail
    )


def _twin_step(twin: TwinRecord | None, reused: JobResult | None) -> JobStep:
    if reused is not None:
        detail = f"reused {reused.twin.twin_id}"
    elif twin is not None:
        detail = twin.twin_id
    else:
        detail = None
    return JobStep(step="twin", label="Twin built", done=detail is not None, detail=detail)


def _twin(path: Path) -> TwinRecord | None:
    if not path.is_file():
        return None
    return TwinRecord.model_validate_json(path.read_text(encoding="utf-8"))


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _updated_at(run_dir: Path) -> datetime:
    times = [run_dir.stat().st_mtime]
    for path in run_dir.rglob("*"):
        try:
            if path.is_file():
                times.append(path.stat().st_mtime)
        except OSError:  # removed while we looked
            continue
    return datetime.fromtimestamp(max(times), UTC)
