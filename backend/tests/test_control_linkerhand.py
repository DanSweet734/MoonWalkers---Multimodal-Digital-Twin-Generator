"""LinkerBot SDK calls on the L20 hand's twin (decision 0038): the slots' angles, the reader's
refusals, the binding to the twin's joints, the plan, the program folder and compare."""

import csv
import importlib.util
import json
import math
from pathlib import Path

import pytest
from pxr import Usd

from moonwalkers.contracts.pipeline_result import Citation, Fact, Joint, JointLink
from moonwalkers.control.cli import main as control_cli
from moonwalkers.control.compare import compare, read_recording
from moonwalkers.control.export import write_program_folder
from moonwalkers.control.linkerhand import (
    L20_RIGHT_MAX,
    L20_RIGHT_MIN,
    L20_RIGHT_SLOTS,
    HandProgram,
    HandSettings,
    bind_hand,
    pose_radians,
    run_hand_program,
    slot_radians,
    slot_value,
)
from moonwalkers.control.program import ProgramError, ProgramFile, packaged_programs
from moonwalkers.kb import JsonKnowledgeBase
from moonwalkers.usd import primitive_arm as arm
from moonwalkers.usd.primitive_drill_press import box, part
from moonwalkers.usd.validate import validate_file

REFERENCE = (
    Path(__file__).parents[1]
    / "src"
    / "moonwalkers"
    / "pipelines"
    / "b"
    / "igus_rebel6dof02.reference.json"
)
# the GUI's L20 presets (constants.py): open and fist
OPEN = [255, 255, 255, 255, 255, 255, 10, 100, 180, 240, 245, 255, 255, 255, 255]
OPEN += [255, 255, 255, 255, 255]
FIST = [40, 0, 0, 0, 0, 131, 10, 100, 180, 240, 19, 255, 255, 255, 255, 135, 0, 0, 0, 0]
POSE = {"thumb_joint0": -0.297, "thumb_joint1": 0.35}  # the photographed pose's SDK angles
FOLLOW_RATIO = 1.15 / 1.08


def cited_range(joint_id: str) -> tuple[float, float]:
    """The model's limits (rad) of a hand joint: its slot's, or a follower's (URDF)."""
    for slot, name in L20_RIGHT_SLOTS.items():
        if name == joint_id:
            return L20_RIGHT_MIN[slot], L20_RIGHT_MAX[slot]
    return (0.0, 1.29) if joint_id == "thumb_joint4" else (0.0, 1.15)


@pytest.fixture
def box_hand(fixed_time) -> tuple:
    """The box arm with a box L20 on its hand: 21 revolute joints named as LinkerBot's model,
    five following, posed as the ReBeL twin is (decision 0031), with the model's limits as
    cited facts."""
    twin, result = arm.build_test_arm(fixed_time)
    made_up = Citation(source_id=arm.SYNTHETIC)
    top = arm.FLANGE_Z + arm.HAND_SIZE[2]
    parts, joints, facts = list(result.parts), list(result.joints), list(result.facts)
    facts.append(
        Fact(key="hand_joint_speed", value=1.0, unit="rad/s", confidence=0.5, citations=[made_up])
    )
    for f, finger in enumerate(("thumb", "index", "middle", "ring", "little")):
        y = -0.04 + 0.02 * f
        parent = "hand"
        for k in range(5 if finger == "thumb" else 4):
            joint_id = f"{finger}_joint{k}"
            child = f"{finger}_link{k}"
            z = top + 0.012 * k
            parts.append(part(child, child, box((0.008, 0.008, 0.01), (0, y, z + 0.006)), made_up))
            low, high = cited_range(joint_id)
            pose = POSE.get(joint_id, 0.0)
            leader = {"thumb_joint4": "thumb_joint3"}.get(joint_id)
            if finger != "thumb" and k == 3:
                leader = f"{finger}_joint2"
            ratio = 1.0 if finger == "thumb" else FOLLOW_RATIO
            joints.append(
                Joint(
                    joint_id=joint_id,
                    joint_type="revolute",
                    parent_part=parent,
                    child_part=child,
                    axis=(0.0, 1.0, 0.0) if k else (1.0, 0.0, 0.0),
                    origin_m=(0.0, y, z),
                    lower_limit=low - pose,
                    upper_limit=high - pose,
                    max_velocity=1.0,
                    confidence=0.5,
                    citations=[made_up],
                    follows=None
                    if leader is None
                    else JointLink(leader=leader, ratio=ratio, citations=[made_up]),
                )
            )
            for end, value in (("lower", low), ("upper", high)):
                facts.append(
                    Fact(
                        key=f"{joint_id}_{end}",
                        value=value,
                        unit="rad",
                        confidence=0.9,
                        citations=[made_up],
                    )
                )
            parent = child
    result = result.model_copy(update={"parts": parts, "joints": joints, "facts": facts})
    return twin, result


def program_file(calls: list[dict], **program: object) -> ProgramFile:
    spec = {
        "format": "linkerhand_sdk",
        "hand_joint": "L20",
        "hand_type": "right",
        "slots": {str(k): v for k, v in L20_RIGHT_SLOTS.items()},
        "calls": calls,
        **program,
    }
    return ProgramFile.model_validate(
        {
            "name": "test-hand-program",
            "sources": [
                {
                    "source_id": "src-test",
                    "kind": "user_input",
                    "uri": "user",
                    "title": "a test",
                    "retrieved_at": "2026-11-17T00:00:00Z",
                }
            ],
            "behavior": {
                "behavior_id": "test_hand_program",
                "name": "a test hand program",
                "kind": "program_interpreter",
                "description": "test",
                "drives_joints": list(L20_RIGHT_SLOTS.values()),
                "spec": {"program": spec},
                "confidence": 0.5,
                "citations": [{"source_id": "src-test", "locator": "here", "quote": "test"}],
            },
        }
    )


def plan(calls: list[dict], result, settings: HandSettings | None = None):
    program = program_file(calls)
    settings = settings or HandSettings()
    binding = bind_hand(program.behavior, [result], settings)
    return run_hand_program(HandProgram.from_behavior(program.behavior), binding, settings)


def move(pose: list[float]) -> dict:
    return {"call": "finger_move", "pose": pose}


# --------------------------------------------------------------------------- the slots
def test_a_value_is_an_angle_by_the_slots_range_and_direction() -> None:
    assert slot_radians(1, 255) == 0.0 and slot_radians(1, 0) == pytest.approx(1.4)  # -1
    assert slot_radians(6, 0) == pytest.approx(-0.26) and slot_radians(6, 255) == 0.26  # 0
    assert slot_radians(5, 255) == pytest.approx(-0.297)  # the thumb's abduction, at its minimum
    assert slot_radians(1, 400) == 0.0  # clamped, as mapping.py clamps
    for slot in L20_RIGHT_SLOTS:
        for value in (0, 37, 128, 255):
            assert slot_value(slot, slot_radians(slot, value)) == pytest.approx(value)
    with pytest.raises(ProgramError, match="reserved"):
        slot_radians(12, 100)


def test_the_presets_fist_closes_every_finger_and_turns_the_thumb_in() -> None:
    fist = pose_radians(FIST)
    assert len(fist) == 16
    for finger in ("index", "middle", "ring", "little"):
        assert fist[f"{finger}_joint1"] == pytest.approx(1.4)
        assert fist[f"{finger}_joint2"] == pytest.approx(1.08)
    assert fist["thumb_joint1"] == pytest.approx(1.78 * (1 - 19 / 255))
    assert pose_radians(OPEN)["index_joint1"] == 0.0
    with pytest.raises(ProgramError, match="20 values"):
        pose_radians(FIST[:16])


def test_each_slots_range_is_its_joints_cited_limits_in_the_reference_file() -> None:
    """The slot-to-joint match (decision 0038) against the facts the twin carries."""
    facts = {f["key"]: f["value"] for f in json.loads(REFERENCE.read_text("utf-8"))["facts"]}
    for slot, joint_id in L20_RIGHT_SLOTS.items():
        assert facts[f"{joint_id}_lower"] == pytest.approx(L20_RIGHT_MIN[slot]), joint_id
        assert facts[f"{joint_id}_upper"] == pytest.approx(L20_RIGHT_MAX[slot]), joint_id


# --------------------------------------------------------------------------- the reader
@pytest.mark.parametrize(
    ("calls", "program", "reason"),
    [
        ([move(OPEN)], {"hand_type": "left"}, "L20 right"),
        ([move(OPEN[:19])], {}, "takes 20 values"),
        ([move([*OPEN[:19], 256])], {}, "0 to 255"),
        ([{"call": "set_speed", "speed": [100] * 4}, move(OPEN)], {}, "five values"),
        ([{"call": "sleep", "seconds": -1}, move(OPEN)], {}, "seconds, 0 or more"),
        ([{"call": "sleep", "seconds": 1}], {}, "no finger_move"),
        ([{"call": "wave"}], {}, "call 1"),
    ],
)
def test_what_the_reader_refuses(calls: list[dict], program: dict, reason: str) -> None:
    with pytest.raises(ValueError, match=reason):
        program_file(calls, **program)


def test_the_binding_refuses_slots_that_are_not_the_l20s_and_ranges_that_disagree(
    box_hand,
) -> None:
    _, result = box_hand
    swapped = {str(k): v for k, v in L20_RIGHT_SLOTS.items()}
    swapped["1"], swapped["16"] = swapped["16"], swapped["1"]
    program = program_file([move(OPEN)], slots=swapped)
    with pytest.raises(ProgramError, match="16 slots"):
        bind_hand(program.behavior, [result], HandSettings())
    facts = [
        f.model_copy(update={"value": 1.3}) if f.key == "index_joint1_upper" else f
        for f in result.facts
    ]
    wrong = result.model_copy(update={"facts": facts})
    with pytest.raises(ProgramError, match="not the joint it turns"):
        bind_hand(program_file([move(OPEN)]).behavior, [wrong], HandSettings())


def test_the_pose_and_the_followers_come_from_the_twin(box_hand) -> None:
    _, result = box_hand
    binding = bind_hand(program_file([move(OPEN)]).behavior, [result], HandSettings())
    assert len(binding.joints) == 21 and len(binding.driven()) == 16
    by_id = {j.joint_id: j for j in binding.joints}
    assert by_id["thumb_joint0"].pose_rad == pytest.approx(-0.297)
    assert by_id["thumb_joint1"].pose_rad == pytest.approx(0.35)
    assert by_id["index_joint3"].leader == "index_joint2" and by_id["index_joint3"].slot is None
    assert by_id["index_joint3"].top_speed_rad_s == pytest.approx(FOLLOW_RATIO)


# --------------------------------------------------------------------------- the plan
def test_each_joint_runs_alone_at_its_fingers_speed_and_the_followers_keep_ratio(
    box_hand,
) -> None:
    _, result = box_hand
    speeds = {"call": "set_speed", "speed": [255, 51, 255, 255, 255]}  # index at a fifth
    trajectory = plan([speeds, move(OPEN), {"call": "sleep", "seconds": 1}, move(FIST)], result)
    fist = trajectory.events[3]
    assert fist.command == "finger_move" and fist.start_s == pytest.approx(1.0)
    # the index's base: 1.4 rad at 1 rad/s * 51/255 takes 7 s; the middle's 1.4 s
    assert fist.end_s == pytest.approx(1.0 + 1.4 / 0.2)
    ids = trajectory.joint_ids
    index1 = trajectory.sdk_deg[ids.index("index_joint1")]
    middle1 = trajectory.sdk_deg[ids.index("middle_joint1")]
    k = trajectory.times.index(pytest.approx(2.4))
    assert middle1[k] == pytest.approx(math.degrees(1.4))
    assert index1[k] == pytest.approx(math.degrees(0.2 * 1.4))
    index3 = trajectory.sdk_deg[ids.index("index_joint3")]
    index2 = trajectory.sdk_deg[ids.index("index_joint2")]
    assert index3 == pytest.approx([FOLLOW_RATIO * v for v in index2])
    twin = trajectory.twin_deg()[ids.index("thumb_joint1")]
    assert twin[0] == 0.0  # the twin starts at its 0, the photographed pose
    # the open's slowest joint is the index's spread, at a fifth of the speed, so the fist at
    # 1 s takes over before it arrives
    spread = -0.26 + 0.52 * 10 / 255
    assert trajectory.events[1].end_s == pytest.approx(-spread / 0.2)
    assert trajectory.events[1].reached is False


def test_a_new_call_takes_over_from_where_each_joint_is(box_hand) -> None:
    _, result = box_hand
    calls = [move(OPEN), move(FIST), {"call": "sleep", "seconds": 0.5}, move(OPEN)]
    trajectory = plan(calls, result, HandSettings(start_speed=255))
    fist = trajectory.events[1]
    assert fist.reached is False
    assert trajectory.notes == [
        "call 2 at 0.000 s takes over before call 1 arrives",
        "call 4 at 0.500 s takes over before call 2 arrives",
    ]
    index1 = trajectory.sdk_deg[trajectory.joint_ids.index("index_joint1")]
    assert max(index1) == pytest.approx(math.degrees(0.5))  # halfway at 1 rad/s, then back
    assert index1[-1] == pytest.approx(0.0)
    # the thumb's roll, from 0.35 toward the fist's, is at 0.85 rad at 0.5 s; back to the
    # open's takes the longest
    roll_open = 1.78 * (1 - 245 / 255)
    assert trajectory.duration_s == pytest.approx(0.5 + (0.85 - roll_open))


def test_a_new_speed_takes_over_a_move_under_way(box_hand) -> None:
    _, result = box_hand
    calls = [
        {"call": "set_speed", "speed": [255] * 5},
        move(FIST),
        {"call": "sleep", "seconds": 0.4},
        {"call": "set_speed", "speed": [0, 0, 0, 0, 0]},
    ]
    trajectory = plan(calls, result)
    index1 = trajectory.sdk_deg[trajectory.joint_ids.index("index_joint1")]
    assert index1[-1] == pytest.approx(math.degrees(0.4))  # held where the speed went to 0
    assert any("speed 0 holds" in n for n in trajectory.notes)


# --------------------------------------------------------------------- the folder and compare
def test_a_program_folder_drives_the_16_and_leaves_the_followers_to_their_mimic(
    tmp_path: Path, box_hand
) -> None:
    twin, result = box_hand
    program = ProgramFile.load(packaged_programs()["linkerhand-l20-test-grasp"])
    output = write_program_folder(tmp_path / "p", program, twin, [result], tmp_path)
    folder = output.folder
    assert sorted(p.name for p in folder.iterdir()) == [
        "PROGRAM.md",
        "program.json",
        "program.usdc",
        "program_native.usdc",
        "record_joints.py",
        "run_program.py",
        "sdk_calls.py",
        "trajectory.json",
    ]
    for usd in ("program.usdc", "program_native.usdc"):
        assert [i for i in validate_file(folder / usd) if i.severity == "error"] == []
    stage = Usd.Stage.Open(str(folder / "program.usdc"))
    runner = _load_runner(folder)
    found = runner.find_programs(stage)
    assert len(found) == 16
    names = {p.joint_path.rsplit("/", 1)[-1] for p in found}
    assert "index_joint3" not in names and "thumb_joint4" not in names
    thumb1 = next(p for p in found if p.joint_path.endswith("thumb_joint1"))
    trajectory = output.trajectory
    k = trajectory.joint_ids.index("thumb_joint1")
    assert thumb1.angles == pytest.approx(trajectory.twin_deg()[k])
    plan_json = json.loads((folder / "trajectory.json").read_text(encoding="utf-8"))
    assert plan_json["kind"] == "linkerhand_sdk_program"
    assert len(plan_json["joints"]) == 21
    assert plan_json["joints"][0]["top_speed_deg_s"] == pytest.approx(57.2958, abs=1e-3)
    calls = (folder / "sdk_calls.py").read_text(encoding="utf-8")
    assert "hand.set_speed(speed=[100, 100, 100, 100, 100])" in calls
    compile(calls, "sdk_calls.py", "exec")  # a valid script, though nothing here runs it
    notes = (folder / "PROGRAM.md").read_text(encoding="utf-8")
    assert "| 10 | Thumb Roll | `thumb_joint1` |" in notes and "follows thumb_joint3" in notes


def test_the_command_line_and_compare_measure_a_recording(tmp_path: Path, box_hand, capsys) -> None:
    twin, result = box_hand
    kb = JsonKnowledgeBase(tmp_path / "kb")
    kb.save_result(result)
    kb.save_twin(twin)
    assert control_cli(["show", "linkerhand-l20-test-grasp"]) == 0
    assert "4  finger_move 40, 0, 0, 0, 0, 131" in capsys.readouterr().out
    args = ["run", "linkerhand-l20-test-grasp", "--twin", twin.machine_key]
    assert control_cli([*args, "--data", str(tmp_path), "--hand-top-speed", "2"]) == 0
    out = capsys.readouterr().out
    assert "the SDK's angle is thumb_joint0 -17.02, thumb_joint1 20.05 deg" in out
    (folder,) = (tmp_path / "machines" / "moonwalkers-testarm" / "programs").iterdir()
    plan_json = json.loads((folder / "trajectory.json").read_text(encoding="utf-8"))
    assert plan_json["settings"]["top_speed_rad_s"] == 2.0

    recording = tmp_path / "rec.csv"  # a perfect follower of the plan, sampled at 60 Hz
    ids = plan_json["joint_ids"]
    with recording.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["time_s", *(f"{j} (rad)" for j in ids)])
        k = 1
        while k / 60 < plan_json["duration_s"] + 1.0:
            t = k / 60
            row = [math.radians(_at(plan_json["times"], plan_json["twin_deg"][j], t)) for j in ids]
            writer.writerow([t, *row])
            k += 1
    measures = compare(read_recording(recording), plan_json)
    distance = [m for m in measures if m.what.endswith("largest distance from the plan")]
    assert len(distance) == 21 and all(m.recorded.startswith("0.00 deg") for m in distance)
    assert [m.what.split(":")[0] for m in measures if m.what.startswith("call")] == [
        "call 2",
        "call 4",
        "call 6",
    ]
    assert control_cli(["compare", str(recording), str(folder / "trajectory.json")]) == 0
    assert "call 4: all joints within 0.5 deg" in capsys.readouterr().out


def _at(times: list[float], values: list[float], t: float) -> float:
    if t >= times[-1]:
        return values[-1]
    for t0, v0, t1, v1 in zip(times, values, times[1:], values[1:], strict=False):
        if t0 <= t <= t1 and t1 > t0:
            return v0 + (v1 - v0) * (t - t0) / (t1 - t0)
    return values[0]


def _load_runner(folder: Path):
    spec = importlib.util.spec_from_file_location("run_program", folder / "run_program.py")
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module
