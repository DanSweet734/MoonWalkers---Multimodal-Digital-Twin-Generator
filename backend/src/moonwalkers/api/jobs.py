"""Jobs: run folders, read and started through the API (decision 0014).

Uploading photos starts a job the way the agent's ``start_run`` and ``add_input`` would: each
photo with where it came from and, when there are several, its view and use (decision 0022). If
the machine already has a reusable twin and no new version was asked for, the orchestrator reuses
it at once and the job says so. Otherwise the job waits for the agent, Claude Code, which finds it
with ``list_jobs`` and builds it through the MCP tools. The API never runs the generator.
"""

from __future__ import annotations

import hashlib
import re
from typing import Annotated, get_args

from fastapi import APIRouter, Form, HTTPException, UploadFile

from moonwalkers.contracts.pipeline_result import InputType, Source
from moonwalkers.kb import machine_key
from moonwalkers.orchestrator import InputPhoto, PhotoUse, PhotoView
from moonwalkers.pipelines.b.build import REQUEST_FILE, write_job_result
from moonwalkers.pipelines.b.photos import check_photos
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
# [INFERENCE] Enough for four views and the close-ups a manual adds (the T33901 run has 24).
MAX_PHOTOS = 32


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
    photo: list[UploadFile],
    origin: Annotated[
        list[str],
        Form(
            description="where each photo came from, in the photos' order: a URL, or who took "
            "it, where and when",
        ),
    ],
    view: Annotated[
        list[str] | None,
        Form(
            description="each photo's view, in the operator's words (decision 0022); needed when "
            f"there are several photos: {', '.join(get_args(PhotoView))}",
        ),
    ] = None,
    use: Annotated[
        list[str] | None,
        Form(description="each photo's use: generator or evidence (default from its view)"),
    ] = None,
    license_note: Annotated[
        list[str] | None,
        Form(description="one note for every photo, or one per photo; blank for none"),
    ] = None,
    new_version: Annotated[bool, Form()] = False,
) -> JobDetail:
    """Upload machine photos (JPEG or PNG) to start a job for the named machine. Several photos
    each need a view; all are checked before anything is saved."""
    if not 1 <= len(photo) <= MAX_PHOTOS:
        raise HTTPException(422, f"upload 1 to {MAX_PHOTOS} photos")
    count = len(photo)
    views, uses = view or [], use or []
    notes = license_note or []
    if len(origin) != count:
        raise HTTPException(422, f"give one origin per photo ({count}), not {len(origin)}")
    if views and len(views) != count or uses and len(uses) != count:
        raise HTTPException(422, f"give one view and one use per photo ({count}), or none")
    if len(notes) not in (0, 1, count):
        raise HTTPException(422, f"give one license note, or one per photo ({count})")
    if any(u.strip() and not (views[i].strip() if views else "") for i, u in enumerate(uses)):
        raise HTTPException(422, "give each photo's view along with its use")
    for text in origin:
        if not 1 <= len(text.strip()) <= 500:
            raise HTTPException(422, "each photo's origin must be 1 to 500 characters")
    if any(len(n) > 300 for n in notes):
        raise HTTPException(422, "a license note can be at most 300 characters")
    files = []
    for upload in photo:
        data = upload.file.read(ctx.max_upload_bytes + 1)
        if len(data) > ctx.max_upload_bytes:
            raise HTTPException(
                413, f"{upload.filename or 'a photo'} is larger than {ctx.max_upload_bytes} bytes"
            )
        files.append((upload.filename or "photo", data))
    shared = notes * count if len(notes) == 1 else notes or [""] * count
    note_for = [n.strip() or None for n in shared]
    with expected_errors(), ctx.lock:
        machine_key(manufacturer, model)  # an unusable name fails before anything is saved
        ids = [f"src-photo-{hashlib.sha256(data).hexdigest()[:12]}" for _, data in files]
        if len(set(ids)) != count:
            raise HTTPException(422, "the same photo was chosen twice")
        given = {
            ids[i]: InputPhoto.model_validate(
                {"view": _view(views[i]), "use": _use(uses[i]) if uses else None}
            )
            for i in range(count)
            if views and views[i].strip()
        }
        for _, data in files:
            photo_suffix(data)
        ws, now = ctx.workspace, ctx.clock()
        planned = [
            Source(
                source_id=ids[i],
                kind="file",
                input_type=InputType.MACHINE_PHOTO,
                uri=f"photo-{i}",
                retrieved_at=now,
            )
            for i in range(count)
        ]
        check_photos(planned, given)  # the views as a whole, before anything is saved
        machine_dir = ws.machine_dir(manufacturer, model)
        saved = [
            save_photo(machine_dir, data, name, origin[i], note_for[i], now)
            for i, (name, data) in enumerate(files)
        ]
        run_dir = ws.start_run(manufacturer, model, new_version)
        for i, item in enumerate(saved):
            ws.add_input(
                run_dir,
                Source(
                    source_id=ids[i],
                    kind="file",
                    input_type=InputType.MACHINE_PHOTO,
                    uri=ws.relative(item.path),
                    title=f"{' '.join(origin[i].split())} (uploaded through the dashboard)",
                    sha256=item.sha256,
                    retrieved_at=now,
                    license_note=note_for[i],
                ),
                given.get(ids[i]),
            )
        reused = ctx.orchestrator().reuse(ws.request(run_dir))
        if reused is not None:
            write_job_result(run_dir, run_dir / REQUEST_FILE, reused)
    return job_detail(ctx, run_dir.parent.parent.name, run_dir.name)


def _view(text: str) -> PhotoView:
    if text not in get_args(PhotoView):
        raise HTTPException(
            422, f"unknown view {text!r}: use one of {', '.join(get_args(PhotoView))}"
        )
    return text  # type: ignore[return-value]


def _use(text: str) -> PhotoUse | None:
    """A use from the form; blank means the default for the photo's view."""
    if not text.strip():
        return None
    if text not in get_args(PhotoUse):
        raise HTTPException(422, f"a photo's use is generator or evidence, not {text!r}")
    return text  # type: ignore[return-value]


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
