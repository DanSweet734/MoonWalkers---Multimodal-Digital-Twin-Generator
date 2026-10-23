"""The box-and-cylinder drill press (drill-press plan, Phase 1) and its command."""

import math
from datetime import datetime
from pathlib import Path

import pytest
from pxr import Usd, UsdPhysics

from moonwalkers.kb import machine_key
from moonwalkers.usd import primitive_drill_press as dp
from moonwalkers.usd.exporter import DriveSettings, JointSettings, build_stage
from moonwalkers.usd.physx_schemas import mimic_axes
from moonwalkers.usd.validate import validate_stage

INCH = 0.0254
ROOT = "/moonwalkers_testdrillpress"


@pytest.fixture
def drill_press(fixed_time: datetime):
    return dp.build_test_drill_press(fixed_time)


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
    for item in [*result.parts, *result.joints]:
        assert item.citations, item
        for citation in item.citations:
            if citation.source_id == dp.MANUAL:
                assert citation.locator and citation.locator.startswith("PDF p. ")
                assert citation.quote
            else:
                assert citation.source_id == dp.SYNTHETIC


def test_the_stand_ins_are_logged_as_issues(drill_press) -> None:
    _, result = drill_press
    refs = {i.ref for i in result.issues if i.message.startswith("Stand-in")}
    assert refs == {"downfeed_handles", "quill_travel"}
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
    joints = {j.joint_id: j for j in result.joints}
    assert joints["quill_travel"].joint_type == "prismatic"
    assert math.isclose(joints["quill_travel"].upper_limit, 3.25 * INCH)
    assert math.isclose(joints["table_height"].upper_limit, 14.375 * INCH)
    assert math.isclose(joints["table_tilt"].upper_limit, math.radians(45))


def test_the_spring_holds_the_quill_up_against_gravity() -> None:
    """With an acceleration drive the preload is stiffness times the distance to the target; it
    must beat gravity, or the quill sags."""
    assert dp.SPRING_STIFFNESS * -dp.SPRING_PRELOAD_TARGET > 9.81


def test_the_stand_in_ratio_turns_the_handles_270_degrees_over_the_stroke() -> None:
    assert math.isclose(dp.HANDLE_RATIO * dp.SPINDLE_TRAVEL, math.radians(270))


def test_every_check_gets_the_spring_unless_it_sets_the_quill() -> None:
    settings = dp.with_spring({})
    assert settings["quill_travel"].drive.target == dp.SPRING_PRELOAD_TARGET
    own = JointSettings(drive=DriveSettings.hold(0.01))
    assert dp.with_spring({"quill_travel": own})["quill_travel"] is own


@pytest.mark.parametrize("name", sorted(dp.CHECKS))
def test_every_check_file_validates(drill_press, name: str) -> None:
    twin, result = drill_press
    stage = build_stage(twin, [result], joint_settings=dp.with_spring(dp.CHECKS[name].settings))
    errors = [i for i in validate_stage(stage) if i.severity == "error"]
    assert errors == []


def test_the_coupling_files_use_the_two_methods(drill_press) -> None:
    twin, result = drill_press
    joints = f"{ROOT}/joints"
    mimic = build_stage(
        twin,
        [result],
        joint_settings=dp.with_spring(dp.CHECKS["handles_follow_mimic.usdc"].settings),
    )
    assert mimic_axes(mimic.GetPrimAtPath(f"{joints}/downfeed_handles")) == ["rotX"]
    rack = build_stage(
        twin,
        [result],
        joint_settings=dp.with_spring(dp.CHECKS["handles_follow_rack_pinion.usdc"].settings),
    )
    prim = rack.GetPrimAtPath(f"{joints}/downfeed_handles_rack_and_pinion")
    assert prim.GetTypeName() == "PhysxPhysicsRackAndPinionJoint"


def test_command_writes_every_check_and_run_notes(tmp_path: Path, capsys) -> None:
    assert dp.main([str(tmp_path)]) == 0
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted(
        [*dp.CHECKS, "RUN.md", "record_joints.py"]
    )
    assert capsys.readouterr().out.count("0 error(s)") == len(dp.CHECKS)

    stage = Usd.Stage.Open(str(tmp_path / "spindle_spin.usdc"))
    drive = UsdPhysics.DriveAPI(stage.GetPrimAtPath(f"{ROOT}/joints/spindle_rotation"), "angular")
    assert math.isclose(drive.GetTargetVelocityAttr().Get(), 340 * 6.0, rel_tol=1e-6)  # deg/s

    notes = (tmp_path / "RUN.md").read_text(encoding="utf-8")
    assert "## Known inaccuracies and stand-ins" in notes
    assert notes.count("- Look for:") == len(dp.CHECKS)
    assert "Shift" in notes and "## Isaac Sim check (fill in)" in notes
