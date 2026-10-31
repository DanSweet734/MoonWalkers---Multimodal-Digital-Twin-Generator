"""Controls folders for Isaac Sim (decision 0025): the twin with its Controls prim, the runner,
the plans and the notes; the live controls the runner reads from the Property panel."""

import importlib.util
import json
import math
from pathlib import Path

import pytest
from pxr import Usd, UsdPhysics

from moonwalkers.control import ProgramError, controls_files, write_controls_folder
from moonwalkers.control.cli import main as control_cli
from moonwalkers.kb import JsonKnowledgeBase
from moonwalkers.usd.exporter import ExportError
from moonwalkers.usd.physx_schemas import applied_schemas
from moonwalkers.usd.validate import validate_file

ROOT = "/moonwalkers_testdrillpress"
CONTROLS = f"{ROOT}/Controls"
SPINDLE = f"{ROOT}/joints/spindle_rotation"


@pytest.fixture
def folder(tmp_path: Path, controlled_drill_press) -> Path:
    twin, result = controlled_drill_press
    (controls,) = controls_files([result])
    out = write_controls_folder(tmp_path / "operator-controls", controls, twin, [result], tmp_path)
    return out.folder


def load_runner(folder: Path):
    spec = importlib.util.spec_from_file_location("run_controls", folder / "run_controls.py")
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def test_a_controls_folder_holds_the_twin_the_runner_the_plans_and_the_notes(folder) -> None:
    assert sorted(p.name for p in folder.iterdir()) == [
        "PROGRAM.md",
        "controls.json",
        "controls.usdc",
        "record_joints.py",
        "run_controls.py",
        "trajectory_drilling-stroke.json",
        "trajectory_no-key-no-start.json",
    ]
    assert not [i for i in validate_file(folder / "controls.usdc") if i.severity == "error"]
    notes = (folder / "PROGRAM.md").read_text(encoding="utf-8")
    assert "DISCONNECT MACHINE FROM POWER!" in notes
    assert "## Scenario `drilling-stroke`" in notes and "## Scenario `no-key-no-start`" in notes
    assert "simulated on `downfeed_handles`, the pinion it turns" in notes
    plan = json.loads((folder / "trajectory_drilling-stroke.json").read_text(encoding="utf-8"))
    assert plan["followers"] == [
        {"joint_id": "downfeed_handles", "ratio": pytest.approx(57.085, abs=1e-3), "stand_in": True}
    ]
    assert plan["milestones"]["stop_m"] == 0.043


def test_the_controls_prim_offers_the_inputs_in_the_property_panel(folder) -> None:
    stage = Usd.Stage.Open(str(folder / "controls.usdc"))
    prim = stage.GetPrimAtPath(CONTROLS)
    speed = prim.GetAttribute("moonwalkers:controls:speedRpm")
    assert speed.Get() == "790"
    assert list(speed.GetMetadata("allowedTokens"))[:3] == ["340", "500", "530"]
    assert len(speed.GetMetadata("allowedTokens")) == 12
    key = prim.GetAttribute("moonwalkers:controls:keyInserted")
    assert key.Get() is False and key.GetDisplayName() == "Disabling key in"
    assert key.GetDisplayGroup() == "MoonWalkers controls"
    scenario = prim.GetAttribute("moonwalkers:controls:scenario")
    assert list(scenario.GetMetadata("allowedTokens")) == [
        "drilling-stroke",
        "no-key-no-start",
        "live",
    ]
    assert prim.GetAttribute("moonwalkers:controls:spec").IsHidden()
    assert (
        prim.GetAttribute("moonwalkers:controls:motorOn")
        .GetDisplayGroup()
        .endswith("set by run_controls.py")
    )


def test_the_spindle_has_a_velocity_drive_and_its_cited_top_speed(folder) -> None:
    stage = Usd.Stage.Open(str(folder / "controls.usdc"))
    joint = stage.GetPrimAtPath(SPINDLE)
    drive = UsdPhysics.DriveAPI(joint, "angular")
    assert drive.GetStiffnessAttr().Get() == 0.0
    assert drive.GetTargetVelocityAttr().Get() == 0.0
    assert "PhysxJointAPI" in applied_schemas(joint)
    assert joint.GetAttribute("physxJoint:maxJointVelocity").Get() == pytest.approx(17160)


def test_the_runner_reads_the_panel_and_puts_a_refused_speed_back(folder) -> None:
    run = load_runner(folder)
    stage = Usd.Stage.Open(str(folder / "controls.usdc"))
    prim = run.find_controls(stage)
    assert str(prim.GetPath()) == CONTROLS
    spec = json.loads(prim.GetAttribute(run.SPEC).Get())
    controller = run.Controller(spec)
    for name in ("powerConnected", "keyInserted", "paddleUp"):
        prim.GetAttribute(run.PREFIX + name).Set(True)
    prim.GetAttribute(run.SPEED).Set("340")  # changed while plugged in
    lines = run.apply_panel(prim, controller)
    assert "motor starts" in lines
    assert any(line.startswith("refused: disconnect the machine first") for line in lines)
    assert prim.GetAttribute(run.SPEED).Get() == "790" and controller.rpm == 790
    prim.GetAttribute(run.PULL).Set(True)
    assert run.apply_panel(prim, controller)[0].startswith("pull the handles down")
    prim.GetAttribute(run.PULL).Set(False)
    assert run.apply_panel(prim, controller)[0].startswith("release the handles")


def test_a_scenario_shows_its_inputs_in_the_panel(folder) -> None:
    run = load_runner(folder)
    stage = Usd.Stage.Open(str(folder / "controls.usdc"))
    prim = run.find_controls(stage)
    controller = run.Controller(json.loads(prim.GetAttribute(run.SPEC).Get()))
    steps = controller.spec["scenarios"]["no-key-no-start"]["steps"]
    run.ScenarioPlayer(controller, steps, strict=False).advance(0.0)
    run.show_inputs(prim, controller)
    assert prim.GetAttribute(run.PREFIX + "powerConnected").Get() is True
    assert prim.GetAttribute(run.PREFIX + "paddleUp").Get() is True
    assert prim.GetAttribute(run.PREFIX + "keyInserted").Get() is False


def test_importing_the_runner_outside_isaac_sim_starts_nothing(folder) -> None:
    import builtins

    load_runner(folder)
    assert getattr(builtins, "_moonwalkers_controls_runner", None) is None


def test_a_folder_is_never_overwritten_and_a_refused_scenario_writes_nothing(
    tmp_path: Path, controlled_drill_press, folder
) -> None:
    twin, result = controlled_drill_press
    (controls,) = controls_files([result])
    with pytest.raises(ExportError, match="never overwritten"):
        write_controls_folder(folder, controls, twin, [result], tmp_path)
    bad = []
    for b in controls.behaviors:
        if b.behavior_id == "operator_controls":
            spec = json.loads(json.dumps(b.spec))
            spec["scenarios"]["drilling-stroke"]["steps"].insert(2, {"do": "set_speed", "rpm": 340})
            b = b.model_copy(update={"spec": spec})
        bad.append(b)
    broken = controls.model_copy(update={"behaviors": bad})
    with pytest.raises(ProgramError, match="step 3"):
        write_controls_folder(tmp_path / "other", broken, twin, [result], tmp_path)
    assert not (tmp_path / "other").exists()
    assert not list(tmp_path.glob(".other*"))


def test_the_command_line_writes_controls_for_a_stored_twin(
    tmp_path: Path, controlled_drill_press, capsys
) -> None:
    twin, result = controlled_drill_press
    kb = JsonKnowledgeBase(tmp_path / "kb")
    kb.save_result(result)
    kb.save_twin(twin)
    args = ["controls", "--twin", twin.machine_key, "--data", str(tmp_path)]
    assert control_cli(args) == 0
    out = capsys.readouterr().out
    assert "drilling-stroke:" in out and f"for {twin.twin_id}" in out
    (written,) = (tmp_path / "machines" / "moonwalkers-testdrillpress" / "programs").iterdir()
    assert written.name.endswith("_operator-controls_v1")
    assert (written / "controls.usdc").is_file()


def test_the_runner_moves_the_handles_drive_in_degrees(folder) -> None:
    """The quill's spring is on the downfeed handles (decision 0025, update): the runner turns
    the hand's metres of quill travel into the handles' degrees."""
    run = load_runner(folder)
    stage = Usd.Stage.Open(str(folder / "controls.usdc"))
    spec = json.loads(run.find_controls(stage).GetAttribute(run.SPEC).Get())
    drive = spec["joints"]["quill"]["drive"]
    assert drive["path"] == f"{ROOT}/joints/downfeed_handles" and drive["kind"] == "angular"
    assert stage.GetPrimAtPath(drive["path"]).HasAPI(UsdPhysics.DriveAPI, "angular")
    assert not stage.GetPrimAtPath(f"{ROOT}/joints/quill_travel").HasAPI(
        UsdPhysics.DriveAPI, "linear"
    )
    stop = spec["joints"]["quill"]["stop_m"]
    assert run.to_drive(drive, stop) == pytest.approx(
        math.degrees(math.radians(270) * stop / 0.08255)
    )
