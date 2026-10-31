"""The box-and-cylinder drill press (drill-press plan, Phase 1), stated in contract v0.2.0 (Phase
2, decision 0020), and its command."""

import math
from datetime import datetime
from pathlib import Path

import pytest
from pxr import Usd, UsdPhysics

from moonwalkers.kb import machine_key
from moonwalkers.usd import primitive_drill_press as dp
from moonwalkers.usd.exporter import contract_settings
from moonwalkers.usd.physx_schemas import mimic_axes
from moonwalkers.usd.validate import validate_stage

INCH = 0.0254
ROOT = "/moonwalkers_testdrillpress"
JOINTS = f"{ROOT}/joints"
TABLE = ("table_height", "table_around_column", "table_tilt", "table_around_center")


@pytest.fixture
def drill_press(fixed_time: datetime):
    return dp.build_test_drill_press(fixed_time)


def joints_of(result) -> dict:
    return {j.joint_id: j for j in result.joints}


def test_the_test_model_is_labelled_and_kept_apart_from_the_real_machine(drill_press) -> None:
    twin, result = drill_press
    assert twin.machine_key == "moonwalkers/testdrillpress"  # not grizzly/t33901
    assert machine_key(result.identity.manufacturer, result.identity.model) == twin.machine_key
    assert any("Synthetic test model" in i.message for i in result.issues)
    assert result.needs_human_review is True
    manual = next(s for s in result.sources if s.source_id == dp.MANUAL)
    assert manual.sha256 == "cf117e5eccad47730cd3a04120863f4e25cfa5fc59cd0a9765d864e2c8817df5"


def test_every_part_and_joint_cites_the_manual_or_says_it_is_made_up(drill_press) -> None:
    _, result = drill_press
    behaviours = [
        item
        for j in result.joints
        for item in (j.mode, j.adjustable_stop, j.follows)
        if item is not None
    ]
    for item in [*result.parts, *result.joints, *behaviours]:
        assert item.citations, item
        for citation in item.citations:
            if citation.source_id == dp.MANUAL:
                assert citation.locator and citation.locator.startswith("PDF p. ")
                assert citation.quote
            else:
                assert citation.source_id == dp.SYNTHETIC


def test_the_joints_state_their_behaviour_in_contract_v0_2_0(drill_press) -> None:
    _, result = drill_press
    assert result.schema_version == "0.2.0"
    joints = joints_of(result)
    quill = joints["quill_travel"]
    assert (quill.mode.kind, quill.mode.position) == ("spring_return", 0.0)
    assert (quill.adjustable_stop.side, quill.adjustable_stop.position) == (
        "upper",
        dp.SPINDLE_TRAVEL,
    )
    handles = joints["downfeed_handles"].follows
    assert (handles.leader, handles.ratio, handles.stand_in) == (
        "quill_travel",
        dp.HANDLE_RATIO,
        True,
    )
    assert joints["spindle_rotation"].mode.kind == "driven"
    for joint_id in TABLE:  # locked by its handle or bolt, at the modelled pose
        assert (joints[joint_id].mode.kind, joints[joint_id].mode.position) == ("locked", None)


def test_the_stand_ins_and_the_assumption_are_logged_as_issues(drill_press) -> None:
    _, result = drill_press
    refs = {i.ref for i in result.issues if i.message.startswith("Stand-in")}
    assert refs == {"downfeed_handles", "quill_travel"}
    assumption = next(i for i in result.issues if i.message.startswith("Assumption"))
    assert assumption.ref == "table_height" and "Craftsman 103.23140" in assumption.message
    assert any("do not collide" in i.message for i in result.issues)


def test_the_sizes_derived_from_the_manual_agree_with_it() -> None:
    """The base's thickness and the spindle's height come from three cited sizes; the table's
    cited floor heights (9-5/8 to 24 in) must then match its cited travel (14-3/8 in)."""
    assert math.isclose(dp.BASE_TOP, 2.125 * INCH)
    assert math.isclose(dp.SPINDLE_NOSE, 25.5 * INCH)
    assert math.isclose(dp.TABLE_LOW_TOP + dp.TABLE_TRAVEL, 24 * INCH)
    assert math.isclose(dp.SPINDLE_NOSE - dp.TABLE_LOW_TOP, dp.SPINDLE_TO_TABLE)
    assert math.isclose(-dp.COLUMN_X - dp.COLUMN_RADIUS, 7 * INCH)


def test_seven_joints_in_the_chains_the_manual_shows(drill_press) -> None:
    _, result = drill_press
    parent = {j.child_part: j.parent_part for j in result.joints}
    assert len(result.joints) == 7 and len(result.parts) == 8

    def chain(part: str) -> list[str]:
        return [part] + (chain(parent[part]) if part in parent else [])

    assert chain("table") == ["table", "table_arm", "table_bracket", "column_rack", "frame"]
    assert chain("spindle") == ["spindle", "quill", "frame"]
    assert chain("handle_hub") == ["handle_hub", "frame"]
    joints = joints_of(result)
    assert joints["quill_travel"].joint_type == "prismatic"
    assert math.isclose(joints["quill_travel"].upper_limit, 3.25 * INCH)
    assert math.isclose(joints["table_height"].upper_limit, 14.375 * INCH)
    assert math.isclose(joints["table_tilt"].upper_limit, math.radians(45))


def test_the_spring_holds_the_quill_up_against_gravity(drill_press) -> None:
    """With an acceleration drive the preload is stiffness times the distance to the target; it
    must beat gravity, or the quill sags."""
    _, result = drill_press
    spring = contract_settings(joints_of(result)["quill_travel"]).drive
    assert spring.target < 0 and spring.stiffness * -spring.target > 9.81


def test_the_stand_in_ratio_turns_the_handles_270_degrees_over_the_stroke() -> None:
    assert math.isclose(dp.HANDLE_RATIO * dp.SPINDLE_TRAVEL, math.radians(270))


@pytest.mark.parametrize("name", sorted(dp.CHECKS))
def test_the_quills_spring_is_on_the_handles_unless_the_check_feeds_the_quill(
    drill_press, name: str
) -> None:
    """Decision 0025, update of 2026-10-31: where the handles follow the quill by mimic, they carry
    its spring, aimed 0.03 rad past the top, and the quill has no drive. The depth stop check feeds
    the quill with its own drive, and the rack and pinion leaves the spring on the quill."""
    stage = dp.check_stage(*drill_press, dp.CHECKS[name])
    quill = stage.GetPrimAtPath(f"{JOINTS}/quill_travel")
    handles = stage.GetPrimAtPath(f"{JOINTS}/downfeed_handles")
    if name == "depth_stop.usdc":
        drive = UsdPhysics.DriveAPI(quill, "linear")
        assert math.isclose(drive.GetTargetPositionAttr().Get(), dp.SPINDLE_TRAVEL, rel_tol=1e-6)
        assert not handles.HasAPI(UsdPhysics.DriveAPI, "angular")
    elif name == "handles_follow_rack_pinion.usdc":
        drive = UsdPhysics.DriveAPI(quill, "linear")
        assert math.isclose(drive.GetTargetPositionAttr().Get(), -0.03, rel_tol=1e-6)
    else:
        assert not quill.HasAPI(UsdPhysics.DriveAPI, "linear")
        drive = UsdPhysics.DriveAPI(handles, "angular")
        assert math.isclose(drive.GetTargetPositionAttr().Get(), math.degrees(-0.03), rel_tol=1e-6)
        assert drive.GetStiffnessAttr().Get() == 600.0


@pytest.mark.parametrize("name", sorted(dp.CHECKS))
def test_every_check_file_validates(drill_press, name: str) -> None:
    stage = dp.check_stage(*drill_press, dp.CHECKS[name])
    errors = [i for i in validate_stage(stage) if i.severity == "error"]
    assert errors == []


def test_a_check_changes_the_contract_only_for_its_machine_settings(drill_press) -> None:
    _, result = drill_press
    assert dp.check_result(result, dp.CHECKS["spindle_spin.usdc"]) is result
    stopped = dp.check_result(result, dp.CHECKS["depth_stop.usdc"])
    assert joints_of(stopped)["quill_travel"].adjustable_stop.position == dp.DEPTH_STOP
    assert joints_of(result)["quill_travel"].adjustable_stop.position == dp.SPINDLE_TRAVEL


def test_the_depth_stop_ends_the_feed(drill_press) -> None:
    stage = dp.check_stage(*drill_press, dp.CHECKS["depth_stop.usdc"])
    quill = UsdPhysics.PrismaticJoint(stage.GetPrimAtPath(f"{JOINTS}/quill_travel"))
    assert quill.GetUpperLimitAttr().Get() == pytest.approx(dp.DEPTH_STOP)


def test_the_coupling_files_use_the_two_methods(drill_press) -> None:
    mimic = dp.check_stage(*drill_press, dp.CHECKS["handles_follow_mimic.usdc"])
    assert mimic_axes(mimic.GetPrimAtPath(f"{JOINTS}/downfeed_handles")) == ["rotX"]
    rack = dp.check_stage(*drill_press, dp.CHECKS["handles_follow_rack_pinion.usdc"])
    prim = rack.GetPrimAtPath(f"{JOINTS}/downfeed_handles_rack_and_pinion")
    assert prim.GetTypeName() == "PhysxPhysicsRackAndPinionJoint"
    # Same sign as the mimic's gearing: the opposite sign jammed the handles (2026-10-23).
    ratio = prim.GetAttribute("physics:ratio").Get()
    assert math.isclose(ratio, -math.degrees(dp.HANDLE_RATIO), rel_tol=1e-6)


def test_the_loosened_table_is_free_and_its_height_drops(drill_press) -> None:
    """Daniel, 2026-10-23: a similar drill press's table fell once its lock was loosened, so the
    height is free too, and starts raised so the drop shows (decision 0018)."""
    loosened = joints_of(dp.check_result(drill_press[1], dp.CHECKS["table_free.usdc"]))
    assert all(loosened[j].mode.kind == "free" for j in TABLE)
    stage = dp.check_stage(*drill_press, dp.CHECKS["table_free.usdc"])
    height = stage.GetPrimAtPath(f"{JOINTS}/table_height")
    drive = UsdPhysics.DriveAPI(height, "linear")
    assert (drive.GetStiffnessAttr().Get(), drive.GetDampingAttr().Get()) == (0.0, 2.0)
    slide = UsdPhysics.PrismaticJoint(height)
    assert (slide.GetLowerLimitAttr().Get(), slide.GetUpperLimitAttr().Get()) == pytest.approx(
        (0.0, dp.TABLE_TRAVEL)
    )
    start = height.GetAttribute("state:linear:physics:position").Get()
    assert start == pytest.approx(dp.TABLE_SETTING["table_height"])


def test_command_writes_every_check_and_run_notes(tmp_path: Path, capsys) -> None:
    assert dp.main([str(tmp_path)]) == 0
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted(
        [*dp.CHECKS, "RUN.md", "record_joints.py"]
    )
    assert capsys.readouterr().out.count("0 error(s)") == len(dp.CHECKS)

    stage = Usd.Stage.Open(str(tmp_path / "spindle_spin.usdc"))
    drive = UsdPhysics.DriveAPI(stage.GetPrimAtPath(f"{JOINTS}/spindle_rotation"), "angular")
    assert math.isclose(drive.GetTargetVelocityAttr().Get(), 340 * 6.0, rel_tol=1e-6)  # deg/s

    notes = (tmp_path / "RUN.md").read_text(encoding="utf-8")
    assert "## Known inaccuracies and stand-ins" in notes
    assert notes.count("- Look for:") == notes.count("- Scenario:") == len(dp.CHECKS)
    assert "Shift" in notes and "## Isaac Sim check (fill in)" in notes


def test_the_check_files_keep_the_articulation_awake(tmp_path: Path) -> None:
    assert dp.main([str(tmp_path)]) == 0
    stage = Usd.Stage.Open(str(tmp_path / "spindle_spin_slow.usdc"))
    threshold = stage.GetPrimAtPath(ROOT).GetAttribute("physxArticulation:sleepThreshold")
    assert threshold.Get() == 0.0
