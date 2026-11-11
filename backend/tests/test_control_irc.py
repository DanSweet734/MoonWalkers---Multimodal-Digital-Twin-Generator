"""An arm's program in igus Robot Control's XML (decision 0033): reading, planning, the program
folder, the command line and the measures against a recording."""

import csv
import importlib.util
import json
import math
from pathlib import Path

import pytest
from pxr import Usd, UsdPhysics

from moonwalkers.contracts.pipeline_result import Citation, Fact, PipelineResult
from moonwalkers.control import (
    ArmSettings,
    IrcProgram,
    ProgramError,
    ProgramFile,
    bind_arm,
    packaged_programs,
    run_irc_program,
    write_program_folder,
)
from moonwalkers.control.cli import main as control_cli
from moonwalkers.control.compare import compare, read_recording
from moonwalkers.control.irc import ACCELERATION_STAND_IN_DEG_S2
from moonwalkers.kb import JsonKnowledgeBase
from moonwalkers.usd import primitive_arm as arm
from moonwalkers.usd.exporter import DriveSettings
from moonwalkers.usd.validate import validate_file

POSE = {"joint2": -21.81, "joint3": 118.82, "joint5": 10.46}  # decision 0031, iRC degrees
IGUS = {1: (-179, 179), 2: (-80, 140), 3: (-80, 140), 4: (-179, 179), 5: (-95, 95), 6: (-179, 179)}
ZERO = {f"joint{i}": 0.0 for i in range(1, 7)}  # the box arm stands straight up: igus's 0
NO_ACC = ArmSettings(acceleration_deg_s2=None, pose_deg=ZERO)


def joint(nr: int, *angles: float, vel: float = 100, acc: float = 40, **extra: str) -> str:
    values = " ".join(f'a{i}="{v:g}"' for i, v in enumerate(angles, start=1))
    more = " ".join(f'{k}="{v}"' for k, v in extra.items())
    return (
        f'<Joint AbortCondition="False" Nr="{nr}" Source="Numerical" velPercent="{vel:g}" '
        f'acc="{acc:g}" smooth="0" {values} e1="0" e2="0" e3="0" Descr="" {more} />'
    )


def xml(*lines: str) -> str:
    return '<?xml version="1.0" encoding="utf-8"?>\n<Program>\n' + "\n".join(lines) + "\n</Program>"


def program_file(text: str) -> ProgramFile:
    return ProgramFile.model_validate(
        {
            "name": "test-arm-program",
            "sources": [
                {
                    "source_id": "src-test",
                    "kind": "user_input",
                    "uri": "user",
                    "title": "a test",
                    "retrieved_at": "2026-11-10T00:00:00Z",
                }
            ],
            "behavior": {
                "behavior_id": "test_program",
                "name": "a test program",
                "kind": "program_interpreter",
                "description": "test",
                "drives_joints": [f"joint{i}" for i in range(1, 7)],
                "spec": {
                    "program": {
                        "format": "irc_xml",
                        "axes": {f"A{i}": f"joint{i}" for i in range(1, 7)},
                        "xml": text,
                    }
                },
                "confidence": 0.5,
                "citations": [{"source_id": "src-test", "locator": "here", "quote": "test"}],
            },
        }
    )


@pytest.fixture
def box_arm(fixed_time):
    """The box-and-cylinder arm: igus's ranges about the arm straight up, so a pose of 0."""
    return arm.build_test_arm(fixed_time)


@pytest.fixture
def posed_arm(box_arm) -> tuple:
    """The box arm as decision 0031 builds the ReBeL: its 0 is the photographed pose, so its
    limits are igus's minus the pose, and its facts carry igus's ranges."""
    twin, result = box_arm
    cite = Citation(source_id=arm.DOC, locator="PDF p. 2, Joint Movement", quote="J1")
    joints, facts = [], list(result.facts)
    for j in result.joints:
        if j.joint_type != "revolute":
            joints.append(j)
            continue
        n = int(j.joint_id[-1])
        pose = POSE.get(j.joint_id, 0.0)
        low, high = IGUS[n]
        joints.append(
            j.model_copy(
                update={
                    "lower_limit": math.radians(low - pose),
                    "upper_limit": math.radians(high - pose),
                }
            )
        )
        for end, value in (("lower", low), ("upper", high)):
            facts.append(
                Fact(
                    key=f"{j.joint_id}_{end}",
                    value=math.radians(value),
                    unit="rad",
                    confidence=0.9,
                    citations=[cite],
                )
            )
    return twin, result.model_copy(update={"joints": joints, "facts": facts})


def plan(text: str, results: list[PipelineResult], settings: ArmSettings | None = None):
    program = program_file(text)
    settings = settings or ArmSettings()
    binding = bind_arm(program.behavior, results, settings)
    return run_irc_program(IrcProgram.from_behavior(program.behavior), binding, settings)


# ------------------------------------------------------------------------------- reading
def test_the_wikis_example_program_is_read() -> None:
    """The CPR wiki's example (decision 0033), as printed, with its Header and endless loop."""
    text = xml(
        '<Header RobotName="igus Gantry" RobotType="DLE-RG-0001" GripperType="" '
        'Software="iRC V902-13-022-DEV" VelocitySetting="0" />',
        '<Loop Nr="1" Mode="DIn" Condition="False" Descr="" />',
        joint(2, 10, 0, 0, 0, 0, 0),
        joint(3, 210, 0, 0, 0, 0, 0),
        '<EndLoop Nr="4" Descr="" />',
    )
    program = IrcProgram.from_xml(text)
    assert program.header["RobotType"] == "DLE-RG-0001"
    (loop,) = program.commands
    assert [c.nr for c in loop.body] == [2, 3]
    assert loop.body[1].target_deg == (210, 0, 0, 0, 0, 0)
    assert loop.body[0].vel_percent == 100 and loop.body[0].acc_percent == 40


@pytest.mark.parametrize(
    ("line", "reason"),
    [
        ('<Linear Nr="1" x="1" />', "inverse kinematics"),
        ('<RelativeJoint Nr="1" />', "not confirmed"),
        ('<If Nr="1" />', "conditions are not simulated"),
        ('<Gripper Nr="1" />', "not read"),
        (joint(1, 0, 0, 0, 0, 0, 0, vel=0), "velPercent 0"),
        (joint(1, 0, 0, 0, 0, 0, 0, vel=150), "velPercent 150"),
        (joint(1, 0, 0, 0, 0, 0, 0, acc=0), "acc 0"),
        (joint(1, 0, 0, 0, 0, 0, 0).replace('"Numerical"', '"Variable"'), "variables"),
        (joint(1, 0, 0, 0, 0, 0, 0).replace('Condition="False"', 'Condition="DIn1"'), "abort"),
        (joint(1, 0, 0, 0, 0, 0, 0).replace('e1="0"', 'e1="5"'), "no external axes"),
        (joint(1, 0, 0, 0, 0, 0, 0).replace('a6="0"', 'a6="x"'), "a6='x' is not a number"),
        (joint(1, 0, 0, 0, 0, 0, 0).replace('a6="0" ', ""), "a6 is missing"),
        ('<Loop Nr="1" Mode="DIn" Condition="DIn4" />', "only the endless loop"),
        ('<EndLoop Nr="1" />', "without its Loop"),
        ('<Loop Nr="1" Condition="False" />', "has no EndLoop"),
        ('<Wait Nr="1" Seconds="-1" />', "negative"),
    ],
)
def test_what_the_reader_refuses_and_why(line: str, reason: str) -> None:
    with pytest.raises(ProgramError, match=reason):
        IrcProgram.from_xml(xml(line, joint(9, 0, 0, 0, 0, 0, 0)))


def test_a_program_must_be_xml_with_a_joint_move() -> None:
    with pytest.raises(ProgramError, match="not well-formed"):
        IrcProgram.from_xml("<Program><Joint></Program>")
    with pytest.raises(ProgramError, match="root element"):
        IrcProgram.from_xml("<Programme />")
    with pytest.raises(ProgramError, match="no Joint move"):
        IrcProgram.from_xml(xml('<Wait Nr="1" Seconds="1" />'))


def test_the_axis_map_must_name_six_joints() -> None:
    program = program_file(xml(joint(1, 0, 0, 0, 0, 0, 0)))
    data = program.model_dump(mode="json")
    data["behavior"]["spec"]["program"]["axes"].pop("A6")
    with pytest.raises(ValueError, match="must map each of A1"):
        ProgramFile.model_validate(data)
    data["behavior"]["spec"]["program"]["axes"]["A6"] = "joint5"
    with pytest.raises(ValueError, match="same joint"):
        ProgramFile.model_validate(data)


# ------------------------------------------------------------------------------- planning
def test_a_joint_move_runs_its_farthest_joint_at_vel_percent_and_the_rest_keep_pace(
    box_arm,
) -> None:
    _, result = box_arm
    text = xml(joint(1, 90, 45, 0, 0, 0, 0))
    no_acc = plan(text, [result], NO_ACC)
    assert no_acc.duration_s == pytest.approx(2.0)  # 90 deg at 45 deg/s, the cited top speed
    assert no_acc.irc_deg[0] == pytest.approx([0, 90]) and no_acc.irc_deg[1] == [0, 45]

    accelerated = plan(text, [result], ArmSettings(pose_deg=ZERO))
    acc = ACCELERATION_STAND_IN_DEG_S2 * 0.40  # Acc 40 % of the stand-in
    assert accelerated.duration_s == pytest.approx(90 / 45 + 45 / acc)  # a trapezoid
    for k, _t in enumerate(accelerated.times):  # all joints together: joint 2 is half of joint 1
        assert accelerated.irc_deg[1][k] == pytest.approx(accelerated.irc_deg[0][k] / 2)
    speeds = [
        (b - a) / (t1 - t0)
        for a, b, t0, t1 in zip(
            accelerated.irc_deg[0],
            accelerated.irc_deg[0][1:],
            accelerated.times,
            accelerated.times[1:],
            strict=False,
        )
    ]
    assert max(speeds) == pytest.approx(45.0)

    half = plan(xml(joint(1, 90, 0, 0, 0, 0, 0, vel=50)), [result], NO_ACC)
    slow = plan(text, [result], NO_ACC.model_copy(update={"override_percent": 50}))
    assert half.duration_s == pytest.approx(4.0) and slow.duration_s == pytest.approx(4.0)


def test_waits_outputs_and_an_endless_loop(box_arm) -> None:
    _, result = box_arm
    text = xml(
        '<Loop Nr="1" Mode="DIn" Condition="False" Descr="" />',
        joint(2, 45, 0, 0, 0, 0, 0),
        '<Wait Nr="3" Seconds="0.5" Descr="" />',
        '<Output Nr="4" Local="True" DIO="DOut21" State="True" Descr="" />',
        joint(5, 0, 0, 0, 0, 0, 0),
        '<EndLoop Nr="6" Descr="" />',
    )
    trajectory = plan(text, [result], NO_ACC.model_copy(update={"loop_passes": 2}))
    assert trajectory.duration_s == pytest.approx(2 * (1 + 0.5 + 1))
    assert [e.command for e in trajectory.events].count("Output") == 2
    assert any("runs 2 pass(es)" in n for n in trajectory.notes)


def test_a_target_outside_the_twins_range_is_refused_in_both_terms(posed_arm) -> None:
    _, result = posed_arm
    with pytest.raises(ProgramError, match=r"A3 to 150 deg \(iRC\) is the twin's 31.18 deg"):
        plan(xml(joint(1, 0, -21.81, 150, 0, 10.46, 0)), [result])


# ------------------------------------------------------------------------------- binding
def test_the_pose_comes_from_igus_ranges_against_the_twins_limits(posed_arm, box_arm) -> None:
    _, posed = posed_arm
    program = program_file(xml(joint(1, 0, 0, 0, 0, 0, 0)))
    binding = bind_arm(program.behavior, [posed], ArmSettings())
    assert binding.pose == pytest.approx((0, -21.81, 118.82, 0, 10.46, 0))
    assert binding.top_speed_deg_s == pytest.approx(45.0)

    _, plain = box_arm  # no ranges among its facts
    with pytest.raises(ProgramError, match="give no joint1_lower"):
        bind_arm(program.behavior, [plain], ArmSettings())
    given = ArmSettings(pose_deg=ZERO)
    assert bind_arm(program.behavior, [plain], given).pose == (0,) * 6

    skewed = posed.model_copy(deep=True)
    skewed.joints[1].upper_limit += math.radians(1)
    with pytest.raises(ProgramError, match="not the twin's range moved by one pose angle"):
        bind_arm(program.behavior, [skewed], ArmSettings())


def test_the_packaged_test_program_fits_the_photographed_twin(posed_arm) -> None:
    program = ProgramFile.load(packaged_programs()["rebel-test-joint-moves"])
    assert program.is_irc and all(c.quote for c in program.behavior.citations)
    _, result = posed_arm
    settings = ArmSettings()
    binding = bind_arm(program.behavior, [result], settings)
    trajectory = run_irc_program(IrcProgram.from_behavior(program.behavior), binding, settings)
    assert trajectory.events[0].end_s == 0.0  # Nr 1 is the photographed pose: no motion
    assert trajectory.final_irc() == pytest.approx(list(binding.pose))
    assert [round(v, 9) for v in (s[-1] for s in trajectory.twin_deg())] == [0.0] * 6
    for series in trajectory.irc_deg:
        for (t0, a), (t1, b) in zip(
            zip(trajectory.times, series, strict=True),
            zip(trajectory.times[1:], series[1:], strict=True),
            strict=False,
        ):
            assert t1 == t0 or abs(b - a) / (t1 - t0) <= 45.0 + 1e-6  # the cited top speed
    assert 20 < trajectory.duration_s < 40


# ------------------------------------------------------------------------------- the folder
def test_a_program_folder_drives_every_joint_with_the_twins_hold(tmp_path: Path, posed_arm) -> None:
    twin, result = posed_arm
    program = ProgramFile.load(packaged_programs()["rebel-test-joint-moves"])
    stiff = DriveSettings(stiffness=10_000.0, damping=200.0)
    output = write_program_folder(
        tmp_path / "p", program, twin, [result], tmp_path, hold=stiff, collide_unjoined=True
    )
    folder = output.folder
    assert sorted(p.name for p in folder.iterdir()) == [
        "PROGRAM.md",
        "program.json",
        "program.usdc",
        "program.xml",
        "program_native.usdc",
        "record_joints.py",
        "run_program.py",
        "trajectory.json",
    ]
    for usd in ("program.usdc", "program_native.usdc"):
        assert [i for i in validate_file(folder / usd) if i.severity == "error"] == []
    stage = Usd.Stage.Open(str(folder / "program.usdc"))
    runner = _load_runner(folder)
    found = runner.find_programs(stage)
    assert len(found) == 6
    trajectory = output.trajectory
    joint3 = next(p for p in found if p.joint_path.endswith("joint3"))
    assert joint3.angles == pytest.approx(trajectory.twin_deg()[2])
    prim = stage.GetPrimAtPath(joint3.joint_path)
    drive = UsdPhysics.DriveAPI(prim, "angular")
    assert drive.GetStiffnessAttr().Get() == pytest.approx(10_000.0)
    assert drive.GetDampingAttr().Get() == pytest.approx(200.0)
    assert drive.GetTargetPositionAttr().Get() == 0.0  # the twin's 0, the photographed pose
    assert not [p for p in stage.Traverse() if p.HasAPI(UsdPhysics.FilteredPairsAPI)]
    native = Usd.Stage.Open(str(folder / "program_native.usdc"))
    target = UsdPhysics.DriveAPI(native.GetPrimAtPath(joint3.joint_path), "angular")
    assert len(target.GetTargetPositionAttr().GetTimeSamples()) == len(set(trajectory.times))

    plan_json = json.loads((folder / "trajectory.json").read_text(encoding="utf-8"))
    assert plan_json["kind"] == "irc_joint_program" and plan_json["hold"]["stiffness"] == 10_000
    notes = (folder / "PROGRAM.md").read_text(encoding="utf-8")
    assert "iRC A1 0, A2 -21.81, A3 118.82" in notes and "300.2 deg/s^2" in notes
    assert (folder / "program.xml").read_text(encoding="utf-8").startswith("<?xml")


def test_the_command_line_and_compare_measure_a_recording(
    tmp_path: Path, posed_arm, capsys
) -> None:
    twin, result = posed_arm
    kb = JsonKnowledgeBase(tmp_path / "kb")
    kb.save_result(result)
    kb.save_twin(twin)
    assert control_cli(["show", "rebel-test-joint-moves"]) == 0
    assert "Nr   2  Joint to [45, -21.81" in capsys.readouterr().out
    args = ["run", "rebel-test-joint-moves", "--twin", twin.machine_key, "--data", str(tmp_path)]
    assert control_cli([*args, "--acceleration", "0"]) == 0
    out = capsys.readouterr().out
    assert "the twin's 0 is iRC A1 0, A2 -21.81" in out
    (folder,) = (tmp_path / "machines" / "moonwalkers-testarm" / "programs").iterdir()
    plan_json = json.loads((folder / "trajectory.json").read_text(encoding="utf-8"))
    assert plan_json["settings"]["acceleration_deg_s2"] is None

    recording = tmp_path / "rec.csv"  # a perfect follower of the plan, sampled at 60 Hz
    ids = plan_json["joint_ids"]
    end = plan_json["duration_s"] + 1.0
    with recording.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["time_s", *(f"{j} (rad)" for j in ids)])
        k = 1
        while k / 60 < end:
            t = k / 60
            row = [math.radians(_at(plan_json["times"], plan_json["twin_deg"][j], t)) for j in ids]
            writer.writerow([t, *row])
            k += 1
    measures = compare(read_recording(recording), plan_json)
    distance = [m for m in measures if m.what.endswith("largest distance from the plan")]
    assert len(distance) == 6 and all(m.recorded.startswith("0.00 deg") for m in distance)
    arrivals = [m for m in measures if m.what.startswith("move Nr")]
    assert len(arrivals) == 15  # every move but Nr 1, which does not move
    assert control_cli(["compare", str(recording), str(folder / "trajectory.json")]) == 0
    assert "move Nr 2: all joints within 0.5 deg" in capsys.readouterr().out


def _at(times: list[float], values: list[float], t: float) -> float:
    if t >= times[-1]:
        return values[-1]
    for (t0, v0), (t1, v1) in zip(
        zip(times, values, strict=True), zip(times[1:], values[1:], strict=True), strict=False
    ):
        if t0 <= t <= t1 and t1 > t0:
            return v0 + (v1 - v0) * (t - t0) / (t1 - t0)
    return values[0]


def _load_runner(folder: Path):
    spec = importlib.util.spec_from_file_location("run_program", folder / "run_program.py")
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module
