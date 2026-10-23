"""Validator checks for several joints: prismatic drives, locks, couplings, starting positions."""

import math

import pytest

from moonwalkers.usd.exporter import DriveSettings, JointCoupling, JointSettings, build_stage
from moonwalkers.usd.validate import validate_stage

JOINTS = "/test_slider/joints"
RATIO = 50.0  # rad per m, made up for the tests


def stage_with(slider, **settings: JointSettings):
    twin, result = slider
    return build_stage(twin, [result], joint_settings=settings)


def findings(stage, severity: str, ref: str | None = None) -> list[str]:
    return [
        i.message
        for i in validate_stage(stage)
        if i.severity == severity and (ref is None or i.ref == ref)
    ]


MIMIC = {
    "slide_travel": JointSettings(drive=DriveSettings.hold(0.0), start=0.04),
    "wheel_turn": JointSettings(drive=None, coupling=JointCoupling("slide_travel", RATIO)),
}


def test_a_twin_with_several_joints_validates(slider) -> None:
    assert findings(stage_with(slider), "error") == []


def test_a_prismatic_joint_without_a_drive_is_reported(slider) -> None:
    stage = stage_with(slider, slide_travel=JointSettings(drive=None))
    assert findings(stage, "warning", f"{JOINTS}/slide_travel") == ["prismatic joint has no drive"]


def test_equal_limits_are_a_lock_not_an_error(slider) -> None:
    lock = math.radians(20)
    stage = stage_with(slider, arm_turn=JointSettings(drive=None, limits=(lock, lock), start=lock))
    ref = f"{JOINTS}/arm_turn"
    assert findings(stage, "error") == []
    assert "joint is locked by equal limits" in findings(stage, "info", ref)


def test_a_mimic_follower_needs_no_drive_and_carries_the_migration_warning(slider) -> None:
    stage = stage_with(slider, **MIMIC)
    ref = f"{JOINTS}/wheel_turn"
    assert findings(stage, "error") == []
    assert findings(stage, "warning", ref) == []  # no "has no drive"
    assert any("do not accept the Newton migration" in m for m in findings(stage, "info", ref))


def test_a_turning_mimic_follower_without_limits_is_an_error(slider) -> None:
    stage = stage_with(slider, **MIMIC)
    wheel = stage.GetPrimAtPath(f"{JOINTS}/wheel_turn")
    for name in ("physics:lowerLimit", "physics:upperLimit"):
        wheel.RemoveProperty(name)  # back to the schema's fallbacks: not limited
    assert any("needs limits" in m for m in findings(stage, "error", f"{JOINTS}/wheel_turn"))


def test_a_mimic_joint_without_a_reference_is_an_error(slider) -> None:
    stage = stage_with(slider, **MIMIC)
    wheel = stage.GetPrimAtPath(f"{JOINTS}/wheel_turn")
    wheel.GetRelationship("physxMimicJoint:rotX:referenceJoint").SetTargets([])
    errors = findings(stage, "error", f"{JOINTS}/wheel_turn")
    assert errors == ["mimic joint must follow one other joint"]


def test_a_rack_and_pinion_must_stay_out_of_the_articulation(slider) -> None:
    coupling = JointCoupling("slide_travel", RATIO, method="rack_and_pinion")
    stage = stage_with(slider, wheel_turn=JointSettings(drive=None, coupling=coupling))
    ref = f"{JOINTS}/wheel_turn_rack_and_pinion"
    assert findings(stage, "error") == []
    assert findings(stage, "warning", f"{JOINTS}/wheel_turn") == []  # the hinge follows
    stage.GetPrimAtPath(ref).GetAttribute("physics:excludeFromArticulation").Set(False)
    assert any("excluded from the articulation" in m for m in findings(stage, "error", ref))


def test_a_rack_and_pinion_needs_a_hinge_and_a_slide(slider) -> None:
    coupling = JointCoupling("slide_travel", RATIO, method="rack_and_pinion")
    stage = stage_with(slider, wheel_turn=JointSettings(drive=None, coupling=coupling))
    ref = f"{JOINTS}/wheel_turn_rack_and_pinion"
    rack = stage.GetPrimAtPath(ref)
    rack.GetRelationship("physics:hinge").SetTargets([f"{JOINTS}/slide_travel"])
    rack.GetRelationship("physics:prismatic").SetTargets([f"{JOINTS}/arm_turn"])
    assert findings(stage, "error", ref) == [
        "rack and pinion needs one hinge",
        "rack and pinion needs one slide",
    ]


@pytest.mark.parametrize(("start", "warned"), [(0.05, False), (0.2, True)])
def test_a_start_outside_the_limits_is_reported(slider, start: float, warned: bool) -> None:
    stage = stage_with(slider, slide_travel=JointSettings(drive=None, start=start))
    warnings = findings(stage, "warning", f"{JOINTS}/slide_travel")
    assert any("outside the joint's limits" in m for m in warnings) is warned


def test_a_joint_state_must_suit_its_joint(slider) -> None:
    stage = stage_with(slider, slide_travel=JointSettings(drive=DriveSettings.hold(), start=0.01))
    slide = stage.GetPrimAtPath(f"{JOINTS}/slide_travel")
    slide.AddAppliedSchema("PhysicsJointStateAPI:angular")
    errors = findings(stage, "error", f"{JOINTS}/slide_travel")
    assert errors == ["joint state 'angular' does not suit this joint"]
