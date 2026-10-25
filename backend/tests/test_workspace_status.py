"""Job status read from a run folder's files, step by step, as the dashboard and agent see it."""

import json
import os
from pathlib import Path

import pytest

from moonwalkers.contracts.pipeline_result import JobResult, Source, TwinRecord
from moonwalkers.orchestrator import InputPhoto
from moonwalkers.workspace import Workspace, list_runs, run_status

JOINT = {
    "up": "+y",
    "front": "+z",
    "spindle_axis_yz": [0.0, 0.2],
    "spindle_radius": 0.45,
    "spindle_start_x": 1.0,
    "decided_by": "test",
    "method": "Synthetic geometry.",
}
SCALE = {"center_height_m": 0.1016, "base_z": None, "note": "the cited centre height."}


@pytest.fixture
def ws(photo_run, clock) -> Workspace:
    return Workspace(photo_run.data_dir, clock)


def steps(status) -> dict[str, bool]:
    return {s.step: s.done for s in status.steps}


def twin_record(fixed_time, version: int = 1) -> TwinRecord:
    return TwinRecord(
        twin_id=f"moonwalkers/testindexer@v{version}",
        machine_key="moonwalkers/testindexer",
        version=version,
        status="needs_review",
        created_at=fixed_time,
    )


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_a_job_moves_through_its_steps(ws: Workspace, photo_run, fixed_time) -> None:
    run_dir = ws.start_run("MoonWalkers", "Test Indexer")
    status = run_status(ws, run_dir)
    assert status is not None and status.stage == "no_photo"
    assert status.run == ws.relative(run_dir) and status.machine == "moonwalkers-testindexer"
    assert status.machine_key == "moonwalkers/testindexer" and not any(steps(status).values())

    ws.add_input(run_dir, photo_run.photo)
    status = run_status(ws, run_dir)
    assert (status.stage, status.stage_label) == ("waiting_for_agent", "Waiting for the agent")
    assert status.photo == photo_run.photo and status.steps[0].detail == photo_run.photo.uri

    sheet = Source(source_id="src-sheet", kind="user_input", uri="user", retrieved_at=fixed_time)
    ws.update_reference(run_dir, lambda d: d["sources"].append(sheet.model_dump(mode="json")))
    status = run_status(ws, run_dir)
    assert status.stage == "in_progress"
    assert status.stage_label == "In progress: reading notes recorded"
    assert status.steps[1].detail.startswith("1 source(s), 0 fact(s)")

    record = {"generator": {"name": "fake-generator", "version": "0"}, "seconds": 0.1}
    write(run_dir / "generator" / "run.json", json.dumps(record))
    assert run_status(ws, run_dir).steps[2].detail == "fake-generator 0 in 0.1 s"

    ws.set_spec_part(run_dir, "joint", JOINT)
    spec = run_status(ws, run_dir).steps[3]
    assert not spec.done and spec.detail == "joint set; still to set: scale"
    ws.set_spec_part(run_dir, "scale", SCALE)
    write(run_dir / "preview" / "assembled" / "views.png", "png")
    status = run_status(ws, run_dir)
    assert steps(status) == {
        "photo": True,
        "notes": True,
        "mesh": True,
        "spec": True,
        "preview": True,
        "twin": False,
    }
    assert status.steps[3].detail == "decided by test"

    built = twin_record(fixed_time)
    write(run_dir / "twin_record.json", built.model_dump_json())
    job = JobResult(job_id=status.job_id, twin=built, reused_existing=False, message="Built.")
    write(run_dir / "request.job_result.json", job.model_dump_json())
    status = run_status(ws, run_dir)
    assert (status.stage, status.twin_id) == ("built", built.twin_id)
    assert status.requests[0].result == job and status.steps[5].detail == built.twin_id


def test_a_job_lists_its_photos_with_their_views(ws: Workspace, photo_run) -> None:
    run_dir = ws.start_run("MoonWalkers", "Test Indexer")
    table = photo_run.photo.model_copy(update={"source_id": "src-table"})
    ws.add_input(run_dir, table, InputPhoto(view="detail"))  # type: ignore[call-arg]
    status = run_status(ws, run_dir)
    assert status is not None and status.photo is not None  # evidence only: still a photo
    assert status.steps[0].label == "Photo added"
    ws.add_input(run_dir, photo_run.photo, InputPhoto(view="front_operator_left"))  # type: ignore[call-arg]

    status = run_status(ws, run_dir)
    assert status is not None
    assert [(p.source.source_id, p.view, p.use) for p in status.photos] == [
        ("src-table", "detail", "evidence"),
        ("src-photo", "front_operator_left", "generator"),
    ]
    assert status.photo is not None and status.photo.source_id == "src-photo"  # the fed one
    step = status.steps[0]
    assert (step.label, step.detail) == (
        "2 photos added",
        "generator: front_operator_left; evidence: 1",
    )


def test_a_reused_job_and_extra_request_files(ws: Workspace, photo_run, fixed_time) -> None:
    run_dir = ws.start_run("MoonWalkers", "Test Indexer")
    ws.add_input(run_dir, photo_run.photo)
    stored = twin_record(fixed_time)
    reused = JobResult(job_id="j", twin=stored, reused_existing=True, message="Found ...")
    write(run_dir / "request.job_result.json", reused.model_dump_json())
    extra = ws.request(run_dir).model_copy(update={"job_id": "reuse-check"})
    write(run_dir / "request-reuse.json", extra.model_dump_json())

    status = run_status(ws, run_dir)
    assert (status.stage, status.stage_label) == ("reused", f"Reused {stored.twin_id}")
    assert status.steps[5].detail == f"reused {stored.twin_id}"
    assert [(r.file, r.job_id, r.result is not None) for r in status.requests] == [
        ("request.json", status.job_id, True),
        ("request-reuse.json", "reuse-check", False),
    ]


def test_command_line_builds_count_their_notes_as_done(ws: Workspace, fixed_time) -> None:
    run_dir = ws.start_run("MoonWalkers", "Test Indexer")
    write(run_dir / "twin_record.json", twin_record(fixed_time).model_dump_json())
    notes = run_status(ws, run_dir).steps[1]
    assert notes.done and "command-line build" in (notes.detail or "")


def test_folders_without_a_request_are_not_jobs_and_bad_files_are_reported(
    ws: Workspace, photo_run
) -> None:
    runs = photo_run.data_dir / "machines" / "moonwalkers-testindexer" / "runs"
    (runs / "exploration").mkdir(parents=True)
    assert run_status(ws, runs / "exploration") is None
    write(runs / "broken" / "request.json", "{not json")
    broken = run_status(ws, runs / "broken")
    assert broken is not None and broken.stage == "unreadable"
    assert broken.stage_label.startswith("Cannot read this run's files:")
    assert [s.name for s in list_runs(ws)] == ["broken"]


def test_jobs_are_listed_newest_first_and_by_machine(ws: Workspace) -> None:
    older = ws.start_run("MoonWalkers", "Test Indexer")
    newer = ws.start_run("Haas", "HA5C")
    os.utime(older / "request.json", (1_000_000_000, 1_000_000_000))
    os.utime(older, (1_000_000_000, 1_000_000_000))
    assert [s.run for s in list_runs(ws)] == [ws.relative(newer), ws.relative(older)]
    assert [s.run for s in list_runs(ws, "haas-ha5c")] == [ws.relative(newer)]
    with pytest.raises(ValueError, match="not a machine folder"):
        list_runs(ws, "../haas-ha5c")
