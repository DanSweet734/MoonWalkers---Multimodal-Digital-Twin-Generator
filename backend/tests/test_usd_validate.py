"""USD validator: a clean twin passes, and each kind of breakage is reported."""

import logging
import math
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import pytest
from pxr import Gf, Usd, UsdGeom, UsdPhysics, Vt

from moonwalkers.usd.exporter import SCENE_PATH, DriveSettings, build_stage, export_twin
from moonwalkers.usd.primitive_twin import build_test_twin
from moonwalkers.usd.validate import main, validate_file, validate_stage

ROOT = "/moonwalkers_testindexer"
JOINT = f"{ROOT}/joints/spindle_rotation"
SPINDLE_MESH = f"{ROOT}/spindle/geometry"


@pytest.fixture
def stage(fixed_time: datetime) -> Usd.Stage:
    twin, result = build_test_twin(fixed_time)
    return build_stage(twin, [result], DriveSettings.spin(math.radians(30)))


def test_clean_twin_has_no_findings(stage: Usd.Stage) -> None:
    assert validate_stage(stage) == []


def joint(stage: Usd.Stage) -> UsdPhysics.RevoluteJoint:
    return UsdPhysics.RevoluteJoint(stage.GetPrimAtPath(JOINT))


def missing_body(stage):
    joint(stage).GetBody1Rel().SetTargets([f"{ROOT}/missing"])


def not_a_rigid_body(stage):
    stage.GetPrimAtPath(f"{ROOT}/spindle").RemoveAPI(UsdPhysics.RigidBodyAPI)


def no_bodies(stage):
    joint(stage).GetBody0Rel().ClearTargets(True)
    joint(stage).GetBody1Rel().ClearTargets(True)


def triangle_collider(stage):
    UsdPhysics.MeshCollisionAPI(stage.GetPrimAtPath(SPINDLE_MESH)).GetApproximationAttr().Set(
        "none"
    )


def frames_apart(stage):
    joint(stage).GetLocalPos1Attr().Set(Gf.Vec3f(0.11, 0.0, 0.1))


def frames_turned(stage):
    joint(stage).GetLocalRot1Attr().Set(
        Gf.Quatf(math.cos(math.pi / 4), 0, 0, math.sin(math.pi / 4))
    )


def inverted_limits(stage):
    joint(stage).CreateLowerLimitAttr(10.0)
    joint(stage).CreateUpperLimitAttr(-10.0)


def no_drive(stage):
    stage.GetPrimAtPath(JOINT).RemoveAPI(UsdPhysics.DriveAPI, "angular")


def centimetres(stage):
    UsdGeom.SetStageMetersPerUnit(stage, 0.01)


def y_up(stage):
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)


def no_kilograms(stage):
    stage.ClearMetadata("kilogramsPerUnit")


def no_scene(stage):
    stage.RemovePrim(SCENE_PATH)


def no_time_range(stage):
    stage.ClearMetadata("startTimeCode")
    stage.ClearMetadata("endTimeCode")


def empty_time_range(stage):
    stage.SetEndTimeCode(stage.GetStartTimeCode())


def stale_extent(stage):
    UsdGeom.Mesh(stage.GetPrimAtPath(SPINDLE_MESH)).GetExtentAttr().Set(
        Vt.Vec3fArray([Gf.Vec3f(0, 0, 0), Gf.Vec3f(1, 1, 1)])
    )


def broken_topology(stage):
    mesh = UsdGeom.Mesh(stage.GetPrimAtPath(SPINDLE_MESH))
    indices = list(mesh.GetFaceVertexIndicesAttr().Get())
    mesh.GetFaceVertexIndicesAttr().Set(Vt.IntArray([*indices[:-1], 999]))


def subdivided(stage):
    UsdGeom.Mesh(stage.GetPrimAtPath(SPINDLE_MESH)).GetSubdivisionSchemeAttr().Set("catmullClark")


def no_joint_provenance(stage):
    stage.GetPrimAtPath(JOINT).ClearCustomDataByKey("moonwalkers")


def no_joint_citations(stage):
    stage.GetPrimAtPath(JOINT).SetCustomDataByKey("moonwalkers:citations", Vt.StringArray())


def no_part_provenance(stage):
    stage.GetPrimAtPath(f"{ROOT}/body").ClearCustomDataByKey("moonwalkers")


def no_twin_provenance(stage):
    stage.GetDefaultPrim().ClearCustomDataByKey("moonwalkers")


@pytest.mark.parametrize(
    ("breakage", "severity", "message"),
    [
        (missing_body, "error", "points to a missing prim"),
        (not_a_rigid_body, "error", "is not a rigid body"),
        (no_bodies, "error", "connects no bodies"),
        (triangle_collider, "error", "use a convex one"),
        (frames_apart, "error", "apart in world space"),
        (frames_turned, "error", "differ by"),
        (inverted_limits, "error", "lower limit is not below"),
        (no_drive, "warning", "has no drive"),
        (centimetres, "error", "metersPerUnit is 0.01"),
        (y_up, "error", "upAxis must be Z"),
        (no_kilograms, "error", "kilogramsPerUnit is not authored"),
        (no_scene, "warning", "no PhysicsScene"),
        (no_time_range, "warning", "no usable time-code range"),
        (empty_time_range, "warning", "no usable time-code range"),
        (stale_extent, "warning", "extent is missing or stale"),
        (broken_topology, "error", "topology is inconsistent"),
        (subdivided, "warning", "subdivision surface"),
        (no_joint_provenance, "error", "joint has no provenance"),
        (no_joint_citations, "error", "joint cites no source"),
        (no_part_provenance, "error", "part has no provenance"),
        (no_twin_provenance, "error", "root has no twin provenance"),
    ],
    ids=lambda v: v.__name__ if callable(v) else None,
)
def test_breakage_is_reported(
    stage: Usd.Stage, breakage: Callable[[Usd.Stage], None], severity: str, message: str
) -> None:
    breakage(stage)
    found = [i.message for i in validate_stage(stage) if i.severity == severity]
    assert any(message in m for m in found), found


def test_stage_without_default_prim_is_reported(stage: Usd.Stage) -> None:
    stage.ClearDefaultPrim()
    assert [i.message for i in validate_stage(stage)] == ["the stage has no default prim"]


def test_unreadable_file_is_reported(tmp_path: Path) -> None:
    path = tmp_path / "broken.usda"
    path.write_text("#usda 1.0\n def Xform (", encoding="utf-8")
    issues = validate_file(path)
    assert [i.severity for i in issues] == ["error"]
    assert "cannot open stage" in issues[0].message


def test_command_line_exit_codes(fixed_time: datetime, tmp_path: Path, capsys) -> None:
    twin, result = build_test_twin(fixed_time)
    good = export_twin(twin, [result], tmp_path / "good.usda")
    assert main([str(good)]) == 0
    stage = Usd.Stage.Open(str(good))
    missing_body(stage)
    bad = tmp_path / "bad.usda"
    stage.Export(str(bad))
    assert main([str(bad)]) == 1
    assert "points to a missing prim" in capsys.readouterr().out


def test_nvidia_asset_validator_accepts_the_test_twin(fixed_time: datetime, tmp_path: Path) -> None:
    # The dev-only asset validator runs its default rules, including its Physics category.
    logging.getLogger("omni.asset_validator").setLevel(logging.WARNING)
    import omni.asset_validator as av

    twin, result = build_test_twin(fixed_time)
    path = export_twin(twin, [result], tmp_path / "twin.usda", DriveSettings.spin(0.5))
    issues = list(av.ValidationEngine(init_rules=True).validate(str(path)).issues())
    assert [f"{i.severity}: {i.message}" for i in issues] == []
