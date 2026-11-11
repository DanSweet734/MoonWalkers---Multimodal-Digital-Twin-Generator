"""The box-and-cylinder ReBeL arm (the lab's machines plan, Phase 2) and its command."""

import math
from datetime import datetime
from pathlib import Path

import pytest
from pxr import Usd, UsdPhysics

from moonwalkers.kb import machine_key
from moonwalkers.usd import primitive_arm as arm
from moonwalkers.usd.validate import validate_stage

ROOT = "/moonwalkers_testarm"
JOINTS = f"{ROOT}/joints"
REVOLUTE = ("joint1", "joint2", "joint3", "joint4", "joint5", "joint6")


@pytest.fixture
def test_arm(fixed_time: datetime):
    return arm.build_test_arm(fixed_time)


def joints_of(result) -> dict:
    return {j.joint_id: j for j in result.joints}


def test_the_test_model_is_labelled_and_kept_apart_from_the_real_arm(test_arm) -> None:
    twin, result = test_arm
    assert twin.machine_key == "moonwalkers/testarm"  # not igus/rebel6dof02
    assert machine_key(result.identity.manufacturer, result.identity.model) == twin.machine_key
    assert any("Synthetic test model" in i.message for i in result.issues)
    assert result.needs_human_review is True


def test_every_part_and_joint_cites_a_source_or_says_it_is_made_up(test_arm) -> None:
    _, result = test_arm
    modes = [j.mode for j in result.joints if j.mode is not None]
    for item in [*result.parts, *result.joints, *modes]:
        assert item.citations, item
        for citation in item.citations:
            if citation.source_id == arm.DOC:
                assert citation.locator and citation.locator.startswith("PDF p. ")
                assert citation.quote
            elif citation.source_id == arm.URDF:
                assert citation.quote
            else:
                assert citation.source_id == arm.SYNTHETIC


def test_six_revolute_joints_in_series_and_the_hand_fixed_to_the_flange(test_arm) -> None:
    _, result = test_arm
    joints = joints_of(result)
    chain = [(joints[j].parent_part, joints[j].child_part) for j in REVOLUTE]
    assert chain == list(zip(arm.CHAIN, arm.CHAIN[1:], strict=False))
    hand = joints["hand_on_flange"]
    assert (hand.joint_type, hand.parent_part, hand.child_part) == ("fixed", "flange", "hand")
    assert {j.joint_type for j in result.joints if j.joint_id in REVOLUTE} == {"revolute"}


def test_the_heights_are_igus_sizes_and_the_ranges_igus_ranges(test_arm) -> None:
    joints = joints_of(test_arm[1])
    z = {j: joints[j].origin_m[2] for j in REVOLUTE}
    assert z["joint2"] == pytest.approx(0.252)  # X1
    assert z["joint3"] - z["joint2"] == pytest.approx(0.237)  # X2
    assert z["joint5"] - z["joint3"] == pytest.approx(0.297)  # X3
    assert arm.FLANGE_Z - z["joint5"] == pytest.approx(0.126)  # X4
    assert arm.FLANGE_Z - z["joint2"] == pytest.approx(0.660)  # L1
    for joint_id, (lower, upper, _) in arm.RANGES.items():
        joint = joints[joint_id]
        assert (joint.lower_limit, joint.upper_limit) == pytest.approx(
            (math.radians(lower), math.radians(upper))
        )
        assert joint.max_velocity == pytest.approx(math.radians(45))
        assert joint.mode.kind == "driven"
    assert [joints[j].axis for j in REVOLUTE] == [
        (0, 0, -1), (0, 1, 0), (0, 1, 0), (0, 0, 1), (0, 1, 0), (0, 0, 1),
    ]  # fmt: skip


def test_the_check_pose_is_within_every_range() -> None:
    for joint_id, angle in arm.POSE.items():
        lower, upper, _ = arm.RANGES[joint_id]
        assert math.radians(lower) < angle < math.radians(upper)


@pytest.mark.parametrize("name", sorted(arm.CHECKS))
def test_every_check_file_validates(test_arm, name: str) -> None:
    stage = arm.check_stage(*test_arm, arm.CHECKS[name])
    errors = [i for i in validate_stage(stage) if i.severity == "error"]
    assert errors == []


def test_the_usd_limits_and_speed_are_igus_in_degrees(test_arm) -> None:
    stage = arm.check_stage(*test_arm, arm.CHECKS["zero_pose.usdc"])
    for joint_id, (lower, upper, _) in arm.RANGES.items():
        prim = stage.GetPrimAtPath(f"{JOINTS}/{joint_id}")
        joint = UsdPhysics.RevoluteJoint(prim)
        assert joint.GetLowerLimitAttr().Get() == pytest.approx(lower)
        assert joint.GetUpperLimitAttr().Get() == pytest.approx(upper)
        assert prim.GetAttribute("physxJoint:maxJointVelocity").Get() == pytest.approx(45.0)


def test_the_hold_checks_differ_only_in_stiffness(test_arm) -> None:
    gains = {}
    for name in ("pose_hold_default.usdc", "pose_hold_stiff.usdc"):
        stage = arm.check_stage(*test_arm, arm.CHECKS[name])
        prim = stage.GetPrimAtPath(f"{JOINTS}/joint2")
        drive = UsdPhysics.DriveAPI(prim, "angular")
        assert drive.GetTargetPositionAttr().Get() == pytest.approx(45.0)
        assert prim.GetAttribute("state:angular:physics:position").Get() == pytest.approx(45.0)
        gains[name] = (drive.GetStiffnessAttr().Get(), drive.GetDampingAttr().Get())
    assert gains == {
        "pose_hold_default.usdc": (100.0, 20.0),
        "pose_hold_stiff.usdc": arm.STIFF,
    }


def test_a_sweep_starts_at_the_lower_limit_and_turns_at_45_degrees_a_second(test_arm) -> None:
    stage = arm.check_stage(*test_arm, arm.CHECKS["sweep_joint5.usdc"])
    prim = stage.GetPrimAtPath(f"{JOINTS}/joint5")
    drive = UsdPhysics.DriveAPI(prim, "angular")
    assert drive.GetTargetVelocityAttr().Get() == pytest.approx(45.0)  # deg/s
    assert drive.GetStiffnessAttr().Get() == 0.0
    assert prim.GetAttribute("state:angular:physics:position").Get() == pytest.approx(-95.0)
    other = UsdPhysics.DriveAPI(stage.GetPrimAtPath(f"{JOINTS}/joint2"), "angular")
    assert other.GetStiffnessAttr().Get() == arm.STIFF[0]


def test_command_writes_every_check_and_run_notes(tmp_path: Path, capsys) -> None:
    assert arm.main([str(tmp_path)]) == 0
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted(
        [*arm.CHECKS, "RUN.md", "record_joints.py"]
    )
    assert capsys.readouterr().out.count("0 error(s)") == len(arm.CHECKS)
    stage = Usd.Stage.Open(str(tmp_path / "zero_pose.usdc"))
    threshold = stage.GetPrimAtPath(ROOT).GetAttribute("physxArticulation:sleepThreshold")
    assert threshold.Get() == 0.0  # decision 0017
    notes = (tmp_path / "RUN.md").read_text(encoding="utf-8")
    assert notes.count("- Look for:") == len(arm.CHECKS)
    assert "## Known inaccuracies and stand-ins" in notes and "Shift" in notes
