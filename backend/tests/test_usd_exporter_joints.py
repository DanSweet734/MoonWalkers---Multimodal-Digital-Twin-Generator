"""USD exporter with several joints (decisions 0017-0019): prismatic joints, chains, settings per
joint, locks, starting positions, couplings, and collisions between parts that are not joined."""

import math
from datetime import datetime
from pathlib import Path

import pytest
from pxr import Gf, Sdf, UsdPhysics

from moonwalkers.usd.exporter import (
    DriveSettings,
    ExportError,
    JointCoupling,
    JointSettings,
    build_stage,
)
from moonwalkers.usd.frames import quat_between
from moonwalkers.usd.physx_schemas import applied_schemas, mimic_axes
from moonwalkers.usd.primitive_twin import DRIVES, build_test_twin

FIXTURES = Path(__file__).parent / "fixtures" / "test_twin"
ROOT = "/test_slider"
JOINTS = f"{ROOT}/joints"
RATIO = 50.0  # rad per m: a made-up gearing for the tests


def stage_with(slider, **settings: JointSettings):
    twin, result = slider
    return build_stage(twin, [result], joint_settings=settings)


# ------------------------------------------------------------------- unchanged output (Phase 2)
@pytest.mark.parametrize("name", sorted(DRIVES))
def test_the_phase_2_test_twin_is_unchanged(fixed_time: datetime, name: str) -> None:
    """Built at the tests' fixed time, the box-and-cylinder test twin is byte for byte what the
    exporter wrote before several joints were added (fixtures saved on 2026-10-22)."""
    twin, result = build_test_twin(fixed_time)
    stage = build_stage(twin, [result], DRIVES[name])
    expected = (FIXTURES / name).read_text(encoding="utf-8")  # text mode: any line endings
    assert stage.GetRootLayer().ExportToString() == expected


# -------------------------------------------------------------------------- prismatic joints
def test_prismatic_joint_slides_along_the_contract_axis_in_metres(slider) -> None:
    stage = stage_with(slider)
    prim = stage.GetPrimAtPath(f"{JOINTS}/slide_travel")
    slide = UsdPhysics.PrismaticJoint(prim)
    assert prim.IsA(UsdPhysics.PrismaticJoint)
    assert slide.GetAxisAttr().Get() == UsdPhysics.Tokens.x
    assert slide.GetBody0Rel().GetTargets() == [Sdf.Path(f"{ROOT}/base")]
    assert slide.GetBody1Rel().GetTargets() == [Sdf.Path(f"{ROOT}/slide")]
    rotation = slide.GetLocalRot0Attr().Get()
    q = (rotation.GetReal(), *rotation.GetImaginary())
    for got, want in zip(q, quat_between((1, 0, 0), (0, 0, -1)), strict=True):
        assert math.isclose(got, want, abs_tol=1e-6)
    assert math.isclose(slide.GetLowerLimitAttr().Get(), 0.0)
    assert math.isclose(slide.GetUpperLimitAttr().Get(), 0.08, rel_tol=1e-6)
    data = prim.GetCustomDataByKey("moonwalkers")
    assert math.isclose(data["upper_limit_m"], 0.08)
    assert "upper_limit_rad" not in data


def test_prismatic_joint_without_settings_holds_at_zero_with_a_linear_drive(slider) -> None:
    stage = stage_with(slider)
    prim = stage.GetPrimAtPath(f"{JOINTS}/slide_travel")
    assert not UsdPhysics.DriveAPI(prim, "angular")
    drive = UsdPhysics.DriveAPI(prim, "linear")
    assert drive.GetTargetPositionAttr().Get() == 0.0
    assert (drive.GetStiffnessAttr().Get(), drive.GetDampingAttr().Get()) == (100.0, 20.0)


def test_a_chain_is_one_articulation_from_the_root(slider) -> None:
    stage = stage_with(slider)
    parsed = UsdPhysics.UsdPhysicsLoadStageFromPrimRange(stage, [Sdf.Path.absoluteRootPath])
    _, articulations = parsed[UsdPhysics.ObjectType.Articulation]
    assert len(articulations) == 1
    # The world, the other side of the fixed joint, is listed as an empty path.
    bodies = {str(p) for p in articulations[0].articulatedBodies if not p.isEmpty}
    assert bodies == {f"{ROOT}/{p}" for p in ("base", "slide", "arm", "wheel")}


# ------------------------------------------------------------------- collisions between parts
def test_parts_not_joined_directly_do_not_collide(slider) -> None:
    stage = stage_with(slider)

    def filtered(part: str) -> set[str]:
        api = UsdPhysics.FilteredPairsAPI(stage.GetPrimAtPath(f"{ROOT}/{part}"))
        return {str(p) for p in api.GetFilteredPairsRel().GetTargets()} if api else set()

    # Joined: base-slide, slide-arm, base-wheel. Not joined: base-arm, slide-wheel, arm-wheel.
    pairs = {frozenset((part, Sdf.Path(other).name)) for part in ("base", "slide", "arm", "wheel")
             for other in filtered(part)}  # fmt: skip
    assert pairs == {
        frozenset(("base", "arm")),
        frozenset(("slide", "wheel")),
        frozenset(("arm", "wheel")),
    }


def test_a_twin_of_two_joined_parts_gets_no_filtered_pairs(fixed_time: datetime) -> None:
    twin, result = build_test_twin(fixed_time)
    stage = build_stage(twin, [result])
    for part in ("body", "spindle"):
        assert not stage.GetPrimAtPath(f"/moonwalkers_testindexer/{part}").HasAPI(
            UsdPhysics.FilteredPairsAPI
        )


# ---------------------------------------------------------------------------- joint settings
def test_settings_give_one_joint_its_own_drive(slider) -> None:
    stage = stage_with(
        slider,
        arm_turn=JointSettings(drive=DriveSettings.spin(math.radians(45))),
        slide_travel=JointSettings(drive=DriveSettings.free(damping=2.0)),
    )
    arm = UsdPhysics.DriveAPI(stage.GetPrimAtPath(f"{JOINTS}/arm_turn"), "angular")
    assert math.isclose(arm.GetTargetVelocityAttr().Get(), 45.0, abs_tol=1e-4)
    slide = UsdPhysics.DriveAPI(stage.GetPrimAtPath(f"{JOINTS}/slide_travel"), "linear")
    assert slide.GetTargetVelocityAttr().Get() == 0.0
    assert (slide.GetStiffnessAttr().Get(), slide.GetDampingAttr().Get()) == (0.0, 2.0)
    # The other revolute joint keeps the exporter's default drive.
    wheel = UsdPhysics.DriveAPI(stage.GetPrimAtPath(f"{JOINTS}/wheel_turn"), "angular")
    assert wheel.GetTargetPositionAttr().Get() == 0.0


def test_settings_can_leave_a_joint_without_a_drive(slider) -> None:
    stage = stage_with(slider, arm_turn=JointSettings(drive=None))
    prim = stage.GetPrimAtPath(f"{JOINTS}/arm_turn")
    assert not prim.HasAPI(UsdPhysics.DriveAPI, "angular")
    assert prim.GetCustomDataByKey("moonwalkers:export_settings")["drive"] == "none"


def test_equal_limits_lock_a_joint_where_it_is_set(slider) -> None:
    lock = math.radians(30)
    stage = stage_with(
        slider,
        arm_turn=JointSettings(drive=None, limits=(lock, lock), start=lock, note="locked"),
    )
    arm = UsdPhysics.RevoluteJoint(stage.GetPrimAtPath(f"{JOINTS}/arm_turn"))
    assert math.isclose(arm.GetLowerLimitAttr().Get(), 30.0, abs_tol=1e-4)
    assert math.isclose(arm.GetUpperLimitAttr().Get(), 30.0, abs_tol=1e-4)
    settings = arm.GetPrim().GetCustomDataByKey("moonwalkers:export_settings")
    assert settings["note"] == "locked"
    # The contract's own limits (none) stay in the provenance.
    assert "lower_limit_rad" not in arm.GetPrim().GetCustomDataByKey("moonwalkers")


def test_a_start_position_is_a_physx_joint_state(slider) -> None:
    stage = stage_with(
        slider,
        slide_travel=JointSettings(drive=DriveSettings.hold(0.0), start=0.05),
        arm_turn=JointSettings(drive=DriveSettings.hold(0.0), start=math.radians(90)),
    )
    slide = stage.GetPrimAtPath(f"{JOINTS}/slide_travel")
    assert "PhysicsJointStateAPI:linear" in applied_schemas(slide)
    position = slide.GetAttribute("state:linear:physics:position").Get()  # a 32-bit float
    assert math.isclose(position, 0.05, rel_tol=1e-6)
    assert slide.GetAttribute("state:linear:physics:velocity").Get() == 0.0
    arm = stage.GetPrimAtPath(f"{JOINTS}/arm_turn")
    assert "PhysicsJointStateAPI:angular" in applied_schemas(arm)
    assert math.isclose(
        arm.GetAttribute("state:angular:physics:position").Get(), 90.0, abs_tol=1e-4
    )


# -------------------------------------------------------------------------------- couplings
def test_a_mimic_coupling_writes_physx_gearing_in_degrees_per_metre(slider) -> None:
    stage = stage_with(
        slider,
        slide_travel=JointSettings(drive=DriveSettings.hold(0.0), start=0.04),
        wheel_turn=JointSettings(drive=None, coupling=JointCoupling("slide_travel", RATIO)),
    )
    wheel = stage.GetPrimAtPath(f"{JOINTS}/wheel_turn")
    assert mimic_axes(wheel) == ["rotX"]
    targets = wheel.GetRelationship("physxMimicJoint:rotX:referenceJoint").GetTargets()
    assert targets == [Sdf.Path(f"{JOINTS}/slide_travel")]
    # PhysX: jointPosition + gearing * referenceJointPosition + offset = 0, in degrees and metres.
    gearing = wheel.GetAttribute("physxMimicJoint:rotX:gearing").Get()
    assert math.isclose(gearing, -math.degrees(RATIO), rel_tol=1e-6)
    assert wheel.GetAttribute("physxMimicJoint:rotX:offset").Get() == 0.0
    assert not wheel.HasAPI(UsdPhysics.DriveAPI, "angular")
    # Without its own start, the follower starts where the coupling puts it.
    start = wheel.GetAttribute("state:angular:physics:position").Get()
    assert math.isclose(start, math.degrees(RATIO * 0.04), rel_tol=1e-6)


def test_a_rack_and_pinion_coupling_is_kept_out_of_the_articulation(slider) -> None:
    coupling = JointCoupling("slide_travel", -RATIO, method="rack_and_pinion")
    stage = stage_with(slider, wheel_turn=JointSettings(drive=None, coupling=coupling))
    prim = stage.GetPrimAtPath(f"{JOINTS}/wheel_turn_rack_and_pinion")
    assert prim.GetTypeName() == "PhysxPhysicsRackAndPinionJoint"
    rel = prim.GetRelationship
    assert rel("physics:body0").GetTargets() == [Sdf.Path(f"{ROOT}/wheel")]  # the pinion
    assert rel("physics:body1").GetTargets() == [Sdf.Path(f"{ROOT}/slide")]  # the rack
    assert rel("physics:hinge").GetTargets() == [Sdf.Path(f"{JOINTS}/wheel_turn")]
    assert rel("physics:prismatic").GetTargets() == [Sdf.Path(f"{JOINTS}/slide_travel")]
    # "abs(omega) = abs(V) * R", R in degrees per distance.
    assert math.isclose(prim.GetAttribute("physics:ratio").Get(), math.degrees(RATIO), rel_tol=1e-6)
    assert prim.GetAttribute("physics:excludeFromArticulation").Get() is True
    assert not mimic_axes(stage.GetPrimAtPath(f"{JOINTS}/wheel_turn"))


# --------------------------------------------------------------------------------- refusals
@pytest.mark.parametrize(
    ("settings", "message"),
    [
        ({"nope": JointSettings(drive=None)}, "does not have"),
        (
            {"wheel_turn": JointSettings(drive=None, coupling=JointCoupling("nope", 1.0))},
            "not another joint",
        ),
        (
            {"wheel_turn": JointSettings(drive=None, coupling=JointCoupling("wheel_turn", 1.0))},
            "not another joint",
        ),
        (  # PhysX needs "PhysicsRevoluteJoint (with a limit set)" for a mimic follower
            {"arm_turn": JointSettings(drive=None, coupling=JointCoupling("slide_travel", 1.0))},
            "needs limits",
        ),
        (
            {
                "slide_travel": JointSettings(
                    drive=None, coupling=JointCoupling("wheel_turn", 1.0, method="rack_and_pinion")
                )
            },
            "revolute follower",
        ),
    ],
)
def test_unusable_settings_are_refused(slider, settings, message) -> None:
    twin, result = slider
    with pytest.raises(ExportError, match=message):
        build_stage(twin, [result], joint_settings=settings)


def test_a_follower_cannot_have_its_own_drive() -> None:
    with pytest.raises(ValueError, match="own drive"):
        JointSettings(drive=DriveSettings.hold(), coupling=JointCoupling("slide_travel", 1.0))


def test_inverted_setting_limits_are_refused() -> None:
    with pytest.raises(ValueError, match="above upper limit"):
        JointSettings(drive=None, limits=(1.0, 0.0))


def test_settings_do_not_change_the_joint_frames(slider) -> None:
    plain = stage_with(slider)
    locked = stage_with(slider, arm_turn=JointSettings(drive=None, limits=(0.1, 0.1)))
    for stage in (plain, locked):
        arm = UsdPhysics.RevoluteJoint(stage.GetPrimAtPath(f"{JOINTS}/arm_turn"))
        assert arm.GetLocalPos0Attr().Get() == Gf.Vec3f(0, 0, 0.3)


@pytest.mark.parametrize("awake", [False, True])
def test_keep_awake_is_written_only_when_asked(slider, awake: bool) -> None:
    """PhysX puts a slow articulation to sleep (the drill press's spindle at 30 degrees a second,
    2026-10-23). ``keep_awake`` turns that off; without it nothing is written, so older twins'
    files do not change."""
    twin, result = slider
    stage = build_stage(twin, [result], keep_awake=awake)  # keep it: it owns its prims
    root = stage.GetPrimAtPath(ROOT)
    assert ("PhysxArticulationAPI" in applied_schemas(root)) is awake
    threshold = root.GetAttribute("physxArticulation:sleepThreshold")
    assert (threshold.Get() == 0.0) if awake else not threshold
