"""The exporter reads contract v0.2.0 (decision 0020): joint modes, adjustable stops and links
become drives, limits and couplings, with decision 0018's stand-in numbers."""

import json
import math

import pytest
from pxr import UsdPhysics

from moonwalkers.contracts import PipelineResult
from moonwalkers.usd import exporter
from moonwalkers.usd.exporter import DriveSettings, ExportError, JointSettings, build_stage
from moonwalkers.usd.physx_schemas import mimic_axes

JOINTS = "/test_slider/joints"
CITE = [{"source_id": "src-synthetic"}]
RATIO = 50.0  # rad per m: a made-up gearing for the tests


def with_fields(slider, issues: list[dict] | None = None, **joints: dict):
    """The slider twin with contract v0.2.0 fields set on some joints."""
    twin, result = slider
    data = result.model_dump(mode="json")
    for joint in data["joints"]:
        joint.update(joints.get(joint["joint_id"], {}))
    data["issues"] = issues or []
    return twin, PipelineResult.model_validate(data)


def stage_of(slider, **kwargs):
    twin, result = slider
    return build_stage(twin, [result], **kwargs)


def mode(kind: str, position: float | None = None) -> dict:
    return {"mode": {"kind": kind, "position": position, "citations": CITE}}


def follows(leader: str = "slide_travel", ratio: float = RATIO, **fields) -> dict:
    return {"follows": {"leader": leader, "ratio": ratio, "citations": CITE, **fields}}


def stop(position: float, side: str = "upper") -> dict:
    return {"adjustable_stop": {"position": position, "side": side, "citations": CITE}}


def limits(prim) -> tuple[float, float]:
    joint = UsdPhysics.PrismaticJoint(prim) if prim.IsA(UsdPhysics.PrismaticJoint) else None
    joint = joint or UsdPhysics.RevoluteJoint(prim)
    return joint.GetLowerLimitAttr().Get(), joint.GetUpperLimitAttr().Get()


# ------------------------------------------------------------------------------------- modes
@pytest.mark.parametrize(
    ("position", "target"),
    [(0.0, -0.03), (0.08, 0.11), (0.04, 0.04), (None, -0.03)],
    ids=["at-the-lower-limit", "at-the-upper-limit", "between", "modelled-pose"],
)
def test_a_spring_return_is_a_drive_preloaded_past_a_limit(slider, position, target) -> None:
    """Decision 0018: stiffness 600, damping 49, aimed 0.03 m past a rest position at a limit."""
    stage = stage_of(with_fields(slider, slide_travel=mode("spring_return", position)))
    prim = stage.GetPrimAtPath(f"{JOINTS}/slide_travel")
    drive = UsdPhysics.DriveAPI(prim, "linear")
    assert math.isclose(drive.GetTargetPositionAttr().Get(), target, abs_tol=1e-6)
    assert (drive.GetStiffnessAttr().Get(), drive.GetDampingAttr().Get()) == (600.0, 49.0)
    assert drive.GetTypeAttr().Get() == "acceleration"
    assert limits(prim) == pytest.approx((0.0, 0.08))
    assert not prim.GetAttribute("state:linear:physics:position").IsValid()


def test_the_spring_beats_gravity_with_its_preload() -> None:
    """An acceleration drive pushes with stiffness x distance; at the limit that must exceed g."""
    assert exporter.SPRING_STIFFNESS * exporter.SPRING_PRELOAD > 9.81


def test_a_locked_joint_has_equal_limits_and_no_drive_and_starts_there(slider) -> None:
    stage = stage_of(with_fields(slider, wheel_turn=mode("locked", math.radians(30))))
    prim = stage.GetPrimAtPath(f"{JOINTS}/wheel_turn")
    assert limits(prim) == pytest.approx((30.0, 30.0))  # degrees
    assert not UsdPhysics.DriveAPI(prim, "angular")
    start = prim.GetAttribute("state:angular:physics:position").Get()
    assert math.isclose(start, 30.0, abs_tol=1e-4)
    settings = prim.GetCustomDataByKey("moonwalkers:export_settings")
    assert "locked" in settings["note"] and settings["drive"] == "none"


def test_a_locked_joint_without_a_position_is_held_at_the_modelled_pose(slider) -> None:
    stage = stage_of(with_fields(slider, slide_travel=mode("locked")))
    assert limits(stage.GetPrimAtPath(f"{JOINTS}/slide_travel")) == (0.0, 0.0)


def test_a_free_joint_has_damping_only(slider) -> None:
    stage = stage_of(with_fields(slider, wheel_turn=mode("free")))
    drive = UsdPhysics.DriveAPI(stage.GetPrimAtPath(f"{JOINTS}/wheel_turn"), "angular")
    assert (drive.GetStiffnessAttr().Get(), drive.GetDampingAttr().Get()) == (0.0, 2.0)
    assert drive.GetTargetVelocityAttr().Get() == 0.0


def test_a_driven_joint_gets_the_default_drive_as_before(slider) -> None:
    def drives(stage):
        prim = stage.GetPrimAtPath(f"{JOINTS}/wheel_turn")
        drive = UsdPhysics.DriveAPI(prim, "angular")
        return drive.GetTargetPositionAttr().Get(), drive.GetStiffnessAttr().Get()

    driven = with_fields(slider, wheel_turn=mode("driven"))
    assert drives(stage_of(driven)) == drives(stage_of(slider)) == (0.0, 100.0)
    stage = stage_of(driven, drive=DriveSettings.spin(1.0))  # keep the stage: it owns the prims
    prim = stage.GetPrimAtPath(f"{JOINTS}/wheel_turn")
    assert math.isclose(
        UsdPhysics.DriveAPI(prim, "angular").GetTargetVelocityAttr().Get(),
        math.degrees(1.0),
        rel_tol=1e-6,  # a 32-bit float
    )


# --------------------------------------------------------------------------- adjustable stops
@pytest.mark.parametrize(("side", "expected"), [("upper", (0.0, 0.03)), ("lower", (0.03, 0.08))])
def test_an_adjustable_stop_replaces_the_limit_on_its_side(slider, side, expected) -> None:
    stage = stage_of(with_fields(slider, slide_travel=stop(0.03, side)))
    assert limits(stage.GetPrimAtPath(f"{JOINTS}/slide_travel")) == pytest.approx(expected)


def test_the_stop_stays_when_settings_replace_the_drive(slider) -> None:
    """A check that feeds the quill past its depth stop gives only a drive (Phase 1's depth_stop):
    the stop, a setting of the machine, still ends the travel."""
    machine = with_fields(slider, slide_travel={**mode("spring_return", 0.0), **stop(0.03)})
    feed = JointSettings(drive=DriveSettings.hold(0.08))
    stage = stage_of(machine, joint_settings={"slide_travel": feed})
    prim = stage.GetPrimAtPath(f"{JOINTS}/slide_travel")
    assert limits(prim) == pytest.approx((0.0, 0.03))
    assert UsdPhysics.DriveAPI(prim, "linear").GetTargetPositionAttr().Get() == pytest.approx(0.08)


# ------------------------------------------------------------------------------------- links
def test_a_link_is_a_mimic_in_degrees_per_metre(slider) -> None:
    stand_in = [{"severity": "warning", "ref": "wheel_turn", "message": "Stand-in ratio"}]
    linked = with_fields(slider, stand_in, wheel_turn=follows(stand_in=True))
    stage = stage_of(linked)
    prim = stage.GetPrimAtPath(f"{JOINTS}/wheel_turn")
    assert mimic_axes(prim) == ["rotX"]
    gearing = prim.GetAttribute("physxMimicJoint:rotX:gearing").Get()
    assert math.isclose(gearing, -math.degrees(RATIO), rel_tol=1e-6)
    assert not UsdPhysics.DriveAPI(prim, "angular")
    assert "stand-in" in prim.GetCustomDataByKey("moonwalkers:export_settings")["note"]
    link = json.loads(prim.GetCustomDataByKey("moonwalkers")["follows_json"])
    assert link["stand_in"] is True and link["leader"] == "slide_travel"


def test_the_coupling_method_picks_the_rack_and_pinion(slider) -> None:
    stage = stage_of(with_fields(slider, wheel_turn=follows()), coupling_method="rack_and_pinion")
    rack = stage.GetPrimAtPath(f"{JOINTS}/wheel_turn_rack_and_pinion")
    assert rack.GetTypeName() == "PhysxPhysicsRackAndPinionJoint"
    assert not mimic_axes(stage.GetPrimAtPath(f"{JOINTS}/wheel_turn"))


def test_a_follower_starts_where_its_leader_puts_it(slider) -> None:
    machine = with_fields(slider, slide_travel=mode("spring_return", 0.0), wheel_turn=follows())
    stage = stage_of(machine, starts={"slide_travel": 0.08})
    wheel = stage.GetPrimAtPath(f"{JOINTS}/wheel_turn")
    start = wheel.GetAttribute("state:angular:physics:position").Get()
    assert math.isclose(start, math.degrees(RATIO * 0.08), rel_tol=1e-5)


def test_a_turning_follower_without_limits_is_refused_for_the_mimic(slider) -> None:
    """PhysxMimicJointAPI supports "PhysicsRevoluteJoint (with a limit set)"; the contract does not
    require limits, so the exporter says what is missing."""
    with pytest.raises(ExportError, match="needs limits"):
        stage_of(with_fields(slider, arm_turn=follows()))


# ------------------------------------------------------------------- settings and starts on top
def test_settings_replace_what_the_contract_asks_for(slider) -> None:
    """A check can lock a joint by a stiff drive instead of the contract's equal limits."""
    locked = with_fields(slider, wheel_turn=mode("locked", 1.0))
    stiff = JointSettings(drive=DriveSettings(target=1.0, stiffness=10_000.0, damping=200.0))
    stage = stage_of(locked, joint_settings={"wheel_turn": stiff})
    prim = stage.GetPrimAtPath(f"{JOINTS}/wheel_turn")
    assert limits(prim) == pytest.approx((math.degrees(-0.5), math.degrees(5.0)))
    assert UsdPhysics.DriveAPI(prim, "angular").GetStiffnessAttr().Get() == 10_000.0


def test_starts_keep_the_contract_drive(slider) -> None:
    machine = with_fields(slider, slide_travel=mode("spring_return", 0.0))
    stage = stage_of(machine, starts={"slide_travel": 0.05})
    prim = stage.GetPrimAtPath(f"{JOINTS}/slide_travel")
    assert prim.GetAttribute("state:linear:physics:position").Get() == pytest.approx(0.05)
    target = UsdPhysics.DriveAPI(prim, "linear").GetTargetPositionAttr().Get()
    assert target == pytest.approx(-0.03)


def test_a_start_on_a_joint_without_settings_keeps_the_default_drive(slider) -> None:
    stage = stage_of(slider, starts={"arm_turn": 0.5})
    prim = stage.GetPrimAtPath(f"{JOINTS}/arm_turn")
    assert prim.GetAttribute("state:angular:physics:position").Get() == pytest.approx(
        math.degrees(0.5), abs=1e-4
    )
    assert UsdPhysics.DriveAPI(prim, "angular").GetStiffnessAttr().Get() == 100.0


def test_starts_must_name_a_joint(slider) -> None:
    with pytest.raises(ExportError, match="does not have"):
        stage_of(slider, starts={"missing": 0.1})


# ---------------------------------------------------------------------------------- provenance
def test_the_contract_fields_are_written_with_their_citations(slider) -> None:
    machine = with_fields(slider, slide_travel={**mode("spring_return", 0.0), **stop(0.03)})
    stage = stage_of(machine)
    data = stage.GetPrimAtPath(f"{JOINTS}/slide_travel").GetCustomDataByKey("moonwalkers")
    assert json.loads(data["mode_json"])["kind"] == "spring_return"
    assert json.loads(data["adjustable_stop_json"])["citations"] == [
        {"source_id": "src-synthetic", "locator": None, "quote": None}
    ]
    assert "follows_json" not in data
