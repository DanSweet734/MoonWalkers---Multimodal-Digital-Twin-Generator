"""The MCP workspace: run folders, requests, reading notes and the geometry spec in parts."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from moonwalkers.contracts.pipeline_result import Citation, Fact, InputType, Source
from moonwalkers.mcp.workspace import SPEC_PARTS_FILE, Workspace, WorkspaceError
from moonwalkers.pipelines.b.pipeline import SPEC_FILE, RunFolderConflict

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


def day(clock) -> str:
    return clock().astimezone().date().isoformat()


def test_runs_are_numbered_per_machine_and_day(ws: Workspace, clock) -> None:
    first = ws.start_run("MoonWalkers", "Test Indexer")
    second = ws.start_run("MoonWalkers", "Test Indexer", new_version=True)
    assert ws.relative(first) == f"machines/moonwalkers-testindexer/runs/{day(clock)}_run-001"
    assert second.name == f"{day(clock)}_run-002"
    request = ws.request(second)
    assert request.job_id == f"moonwalkers-testindexer-{day(clock)}-run-002"
    assert request.machine is not None and request.machine.model == "Test Indexer"
    assert request.new_version and request.sources == []


@pytest.mark.parametrize(
    "run", ["runs/x", "machines/a/runs", "machines/a/other/b", "machines/../runs/b", "../x/runs/y"]
)
def test_run_ids_must_name_a_run_folder(ws: Workspace, run: str) -> None:
    with pytest.raises(WorkspaceError, match="is not a run"):
        ws.run_dir(run)


def test_unknown_runs_and_outside_files_are_refused(ws: Workspace, tmp_path: Path) -> None:
    with pytest.raises(WorkspaceError, match="no run"):
        ws.run_dir("machines/moonwalkers-testindexer/runs/2026-01-01_run-009")
    (tmp_path / "outside.png").write_bytes(b"x")
    with pytest.raises(WorkspaceError, match="not inside the data folder"):
        ws.data_file(str(tmp_path / "outside.png"))
    with pytest.raises(WorkspaceError, match="no file"):
        ws.data_file("machines/missing.png")


def test_inputs_are_added_once_and_fixed_after_generation(ws: Workspace, photo_run) -> None:
    run_dir = ws.start_run("MoonWalkers", "Test Indexer")
    request = ws.add_input(run_dir, photo_run.photo)
    assert [s.source_id for s in request.sources] == ["src-photo"]
    with pytest.raises(WorkspaceError, match="already has a source"):
        ws.add_input(run_dir, photo_run.photo)
    (run_dir / "generator").mkdir()
    (run_dir / "generator" / "run.json").write_text("{}", encoding="utf-8")
    other = photo_run.photo.model_copy(update={"source_id": "src-photo-2"})
    with pytest.raises(RunFolderConflict, match="already generated"):
        ws.add_input(run_dir, other)


def test_reference_changes_are_validated_before_saving(ws: Workspace, fixed_time) -> None:
    run_dir = ws.start_run("MoonWalkers", "Test Indexer")
    sheet = Source(
        source_id="src-sheet", kind="user_input", uri="user", title="Sheet", retrieved_at=fixed_time
    )
    ws.update_reference(run_dir, lambda d: d["sources"].append(sheet.model_dump(mode="json")))
    stray = Fact(key="x", value=1, confidence=1.0, citations=[Citation(source_id="src-none")])
    with pytest.raises(ValidationError, match="unknown sources"):
        ws.update_reference(run_dir, lambda d: d["facts"].append(stray.model_dump(mode="json")))
    reference = ws.reference(run_dir)
    assert reference is not None and reference.facts == []  # the bad change was not saved


def test_spec_is_written_once_both_parts_are_set(ws: Workspace) -> None:
    run_dir = ws.start_run("MoonWalkers", "Test Indexer")
    state = ws.set_spec_part(run_dir, "joint", JOINT)
    assert state.parts == ("joint",) and state.spec is None
    assert not (run_dir / SPEC_FILE).exists()
    state = ws.set_spec_part(run_dir, "scale", SCALE)
    assert state.spec is not None and state.spec.center_height_m == 0.1016
    assert state.spec.method == "Synthetic geometry. Scale: the cited centre height."
    saved = json.loads((run_dir / SPEC_FILE).read_text(encoding="utf-8"))
    assert saved["spindle_start_x"] == 1.0 and ws.spec_state(run_dir).spec == state.spec


def test_a_bad_part_leaves_the_spec_unchanged(ws: Workspace) -> None:
    run_dir = ws.start_run("MoonWalkers", "Test Indexer")
    ws.set_spec_part(run_dir, "joint", JOINT)
    ws.set_spec_part(run_dir, "scale", SCALE)
    with pytest.raises(ValidationError):
        ws.set_spec_part(run_dir, "joint", JOINT | {"up": "upward"})
    assert ws.spec_state(run_dir).spec.up == "+y"  # type: ignore[union-attr]
    assert json.loads((run_dir / SPEC_PARTS_FILE).read_text("utf-8"))["joint"]["up"] == "+y"


def test_nothing_changes_once_assembled_or_built(ws: Workspace, photo_run, fixed_time) -> None:
    run_dir = ws.start_run("MoonWalkers", "Test Indexer")
    (run_dir / "meshes").mkdir()
    (run_dir / "meshes" / "assembly.json").write_text("{}", encoding="utf-8")
    with pytest.raises(RunFolderConflict, match="already assembled"):
        ws.set_spec_part(run_dir, "joint", JOINT)
    (run_dir / "twin.usdc").write_bytes(b"")
    with pytest.raises(RunFolderConflict, match="already built"):
        ws.update_reference(run_dir, lambda d: None)
    photo = Source(
        source_id="src-new",
        kind="file",
        input_type=InputType.MACHINE_PHOTO,
        uri=photo_run.photo.uri,
        retrieved_at=fixed_time,
    )
    with pytest.raises(RunFolderConflict, match="already built"):
        ws.add_input(run_dir, photo)
