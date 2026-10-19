"""Jobs: run folders, read and started through the API (decision 0014).

Uploading a photo starts a job the way the agent's ``start_run`` and ``add_input`` would. If the
machine already has a reusable twin and no new version was asked for, the orchestrator reuses it
at once and the job says so. Otherwise the job waits for the agent, Claude Code, which finds it
with ``list_jobs`` and builds it through the MCP tools. The API never runs the generator.
"""

from __future__ import annotations

import re
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, UploadFile

from moonwalkers.contracts.pipeline_result import InputType, Source
from moonwalkers.kb import machine_key
from moonwalkers.pipelines.b.build import REQUEST_FILE, write_job_result
from moonwalkers.workspace import (
    OPEN_STAGES,
    RunStatus,
    list_runs,
    photo_suffix,
    run_images,
    run_outputs,
    run_status,
    save_photo,
)

from .context import ApiContext, Context, expected_errors
from .models import JobDetail

router = APIRouter(prefix="/api/jobs", tags=["jobs"])
FOLDER = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
RUN_NAME = r"^[A-Za-z0-9][A-Za-z0-9._-]*$"


@router.get("")
def list_jobs(ctx: Context) -> list[RunStatus]:
    """Every job (run folder with a request), the most recently changed first."""
    return list_runs(ctx.workspace)


@router.get("/{machine}/{run}")
def get_job(machine: str, run: str, ctx: Context) -> JobDetail:
    """One job with its steps, reading notes so far, images and output files."""
    return job_detail(ctx, machine, run)


@router.post("", status_code=201)
def create_job(
    ctx: Context,
    manufacturer: Annotated[str, Form(min_length=1, max_length=100)],
    model: Annotated[str, Form(min_length=1, max_length=100)],
    photo: UploadFile,
    origin: Annotated[
        str,
        Form(
            min_length=1,
            max_length=500,
            description="where the photo came from: a URL, or who took it, where and when",
        ),
    ],
    license_note: Annotated[str | None, Form(max_length=300)] = None,
    new_version: Annotated[bool, Form()] = False,
) -> JobDetail:
    """Upload one machine photo (JPEG or PNG) to start a job for the named machine."""
    data = photo.file.read(ctx.max_upload_bytes + 1)
    if len(data) > ctx.max_upload_bytes:
        raise HTTPException(413, f"the photo is larger than {ctx.max_upload_bytes} bytes")
    with expected_errors(), ctx.lock:
        machine_key(manufacturer, model)  # an unusable name fails before anything is saved
        photo_suffix(data)
        ws, now = ctx.workspace, ctx.clock()
        saved = save_photo(
            ws.machine_dir(manufacturer, model),
            data,
            photo.filename or "photo",
            origin,
            license_note,
            now,
        )
        run_dir = ws.start_run(manufacturer, model, new_version)
        ws.add_input(
            run_dir,
            Source(
                source_id=f"src-photo-{saved.sha256[:12]}",
                kind="file",
                input_type=InputType.MACHINE_PHOTO,
                uri=ws.relative(saved.path),
                title=f"{' '.join(origin.split())} (uploaded through the dashboard)",
                sha256=saved.sha256,
                retrieved_at=now,
                license_note=license_note,
            ),
        )
        reused = ctx.orchestrator().reuse(ws.request(run_dir))
        if reused is not None:
            write_job_result(run_dir, run_dir / REQUEST_FILE, reused)
    return job_detail(ctx, run_dir.parent.parent.name, run_dir.name)


def job_detail(ctx: ApiContext, machine: str, run: str) -> JobDetail:
    if not re.fullmatch(FOLDER, machine) or not re.fullmatch(RUN_NAME, run):
        raise HTTPException(404, f"no job {machine}/{run}")
    run_dir = ctx.data_dir / "machines" / machine / "runs" / run
    status = run_status(ctx.workspace, run_dir) if run_dir.is_dir() else None
    if status is None:
        raise HTTPException(404, f"no job machines/{machine}/runs/{run}")
    notes = None
    if status.stage != "unreadable":
        with expected_errors():
            notes = ctx.workspace.reference(run_dir)
    prompt = (
        f"Build the twin for the dashboard job {status.run}, following docs/agent-procedure.md."
        if status.stage in OPEN_STAGES
        else None
    )
    return JobDetail(
        job=status,
        notes=notes,
        images=run_images(ctx.workspace, run_dir),
        outputs=run_outputs(ctx.workspace, run_dir),
        agent_prompt=prompt,
    )
