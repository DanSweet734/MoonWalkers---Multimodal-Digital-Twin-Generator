"""Program folders for Isaac Sim: the twin with its program, the runner, and the notes."""

import importlib.util
import json
import math
from pathlib import Path

import pytest
from pxr import Usd, UsdPhysics

from moonwalkers.control import ProgramError, ProgramFile, packaged_programs, write_program_folder
from moonwalkers.control.cli import main as control_cli
from moonwalkers.kb import JsonKnowledgeBase
from moonwalkers.usd.exporter import ExportError
from moonwalkers.usd.primitive_twin import build_test_twin
from moonwalkers.usd.validate import validate_file

JOINT = "/moonwalkers_testindexer/joints/spindle_rotation"


@pytest.fixture
def twin_and_result(fixed_time):
    return build_test_twin(fixed_time)


def program(name: str = "example-5-subroutine") -> ProgramFile:
    return ProgramFile.load(packaged_programs()[f"ha5c-manual-{name}"])


def load_runner(folder: Path):
    spec = importlib.util.spec_from_file_location("run_program", folder / "run_program.py")
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def test_a_program_folder_holds_the_twin_its_program_and_the_runner(
    tmp_path: Path, twin_and_result
) -> None:
    twin, result = twin_and_result
    output = write_program_folder(tmp_path / "p", program(), twin, [result], tmp_path)
    folder = output.folder
    assert sorted(p.name for p in folder.iterdir()) == [
        "PROGRAM.md",
        "program.json",
        "program.usdc",
        "program_native.usdc",
        "run_program.py",
        "trajectory.json",
    ]
    for usd in ("program.usdc", "program_native.usdc"):
        assert [i for i in validate_file(folder / usd) if i.severity == "error"] == []

    stage = Usd.Stage.Open(str(folder / "program.usdc"))
    joint = stage.GetPrimAtPath(JOINT)
    times = list(joint.GetAttribute("moonwalkers:program:times").Get())
    degrees = list(joint.GetAttribute("moonwalkers:program:anglesDeg").Get())
    assert times == [w.t for w in output.trajectory.waypoints]
    assert degrees == [w.deg for w in output.trajectory.waypoints]
    planned = joint.GetAttribute("moonwalkers:program:plannedAngleDeg")
    assert planned.Get(Usd.TimeCode(1.125 * 60)) == pytest.approx(90.0)  # after the first index
    drive = UsdPhysics.DriveAPI(joint, "angular")
    assert drive.GetTargetPositionAttr().Get() == 0.0 and drive.GetTargetVelocityAttr().Get() == 0.0
    provenance = joint.GetCustomDataByKey("moonwalkers:program")
    assert provenance["name"] == "ha5c-manual-example-5-subroutine"
    assert json.loads(provenance["steps"])[0] == [1, 0.0, 4, 3, 96]

    native = Usd.Stage.Open(str(folder / "program_native.usdc"))  # keep the stage alive
    target = UsdPhysics.DriveAPI(native.GetPrimAtPath(JOINT), "angular").GetTargetPositionAttr()
    assert len(target.GetTimeSamples()) == len(times)

    notes = (folder / "PROGRAM.md").read_text(encoding="utf-8")
    assert "| 01 | 0 | Step# 4 | 3 | 96 |" in notes
    assert "## Check in Isaac Sim (fill in)" in notes
    assert json.loads((folder / "trajectory.json").read_text())["duration_s"] == pytest.approx(
        output.trajectory.duration_s
    )


def test_the_runner_follows_the_program_it_finds_on_the_stage(
    tmp_path: Path, twin_and_result
) -> None:
    twin, result = twin_and_result
    folder = write_program_folder(tmp_path / "p", program(), twin, [result], tmp_path).folder
    runner = load_runner(folder)  # outside Isaac Sim, so it does not start itself
    (found,) = runner.find_programs(Usd.Stage.Open(str(folder / "program.usdc")))
    assert found.joint_path == JOINT and found.name == "ha5c-manual-example-5-subroutine"
    assert found.target_at(0.5) == pytest.approx((40.0, 80.0))
    assert found.target_at(1.5) == pytest.approx((90.0, 0.0))
    assert found.target_at(1e6) == pytest.approx((0.0, 0.0))
    with pytest.raises(ValueError, match="must not go backwards"):
        runner.Program("/j", "p", [0.0, 2.0, 1.0], [0.0, 1.0, 2.0])


def test_the_runner_prints_its_lines_again_after_stop_then_play(
    tmp_path: Path, twin_and_result
) -> None:
    twin, result = twin_and_result
    folder = write_program_folder(tmp_path / "p", program(), twin, [result], tmp_path).folder
    runner = load_runner(folder)
    progress = runner.Progress(runner.find_programs(Usd.Stage.Open(str(folder / "program.usdc"))))
    finished = "'ha5c-manual-example-5-subroutine' finished at 16.112 s, target 0.000 deg"
    # Daniel's check on 2026-10-19: Play, the program to its end, Stop, then Play again
    assert progress.lines(1 / 60) == ["MoonWalkers runner: first physics step at t = 0.017 s"]
    assert progress.lines(8.0) == []
    assert progress.lines(16.2) == [f"MoonWalkers runner: {finished}"]
    assert progress.lines(30.0) == []
    assert progress.lines(1 / 60) == [
        "MoonWalkers runner: first physics step at t = 0.017 s (run 2)"
    ]
    assert progress.lines(16.2) == [f"MoonWalkers runner: {finished}"]


def test_the_joints_cited_top_speed_caps_the_feeds(tmp_path: Path, twin_and_result) -> None:
    twin, result = twin_and_result
    slow = result.model_copy(
        update={"joints": [result.joints[0].model_copy(update={"max_velocity": math.radians(100)})]}
    )
    output = write_program_folder(tmp_path / "p", program("example-3"), twin, [slow], tmp_path)
    assert output.settings.joint_max_deg_s == pytest.approx(100.0)
    assert output.trajectory.notes and "runs at 100" in output.trajectory.notes[0]


def test_folders_are_never_overwritten_and_the_joint_must_exist(
    tmp_path: Path, twin_and_result
) -> None:
    twin, result = twin_and_result
    write_program_folder(tmp_path / "p", program(), twin, [result], tmp_path)
    with pytest.raises(ExportError, match="never overwritten"):
        write_program_folder(tmp_path / "p", program(), twin, [result], tmp_path)
    other = program().model_copy(deep=True)
    other.behavior.drives_joints = ["table_tilt"]
    with pytest.raises(ProgramError, match="drives \\['table_tilt'\\]"):
        write_program_folder(tmp_path / "q", other, twin, [result], tmp_path)
    assert not (tmp_path / "q").exists()


def test_the_command_line_runs_a_program_on_a_stored_twin(
    tmp_path: Path, twin_and_result, capsys
) -> None:
    twin, result = twin_and_result
    kb = JsonKnowledgeBase(tmp_path / "kb")
    kb.save_result(result)
    kb.save_twin(twin)
    assert control_cli(["show", "ha5c-manual-example-3", "--dwell", "0"]) == 0
    assert "duration 2.667 s, final target 720.000 deg" in capsys.readouterr().out
    args = ["run", "ha5c-manual-example-3", "--twin", twin.machine_key, "--data", str(tmp_path)]
    assert control_cli(args) == 0
    out = capsys.readouterr().out
    assert f"for {twin.twin_id}, joint spindle_rotation" in out
    (folder,) = (tmp_path / "machines" / "moonwalkers-testindexer" / "programs").iterdir()
    assert folder.name.endswith("_ha5c-manual-example-3_v1")
    assert control_cli(args) == 0  # a second run gets its own folder
    assert len(list(folder.parent.iterdir())) == 2
    assert control_cli(["run", "nothing", "--twin", twin.machine_key]) == 1
    assert "neither a packaged program" in capsys.readouterr().err
