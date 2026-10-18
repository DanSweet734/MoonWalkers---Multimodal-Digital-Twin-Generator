"""USD exporter: stage layout, physics schemas, units, provenance, and refusals."""

import math
from datetime import datetime
from pathlib import Path

import pytest
from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics

from moonwalkers.contracts.pipeline_result import PipelineResult, TwinRecord
from moonwalkers.usd.exporter import (
    SCENE_PATH,
    WORLD_JOINT,
    DriveSettings,
    ExportError,
    build_stage,
    export_twin,
)
from moonwalkers.usd.frames import quat_between, rotate
from moonwalkers.usd.geometry import primitive_mesh
from moonwalkers.usd.primitive_twin import build_test_twin
from moonwalkers.usd.validate import validate_stage

ROOT = "/moonwalkers_testindexer"
JOINT = f"{ROOT}/joints/spindle_rotation"


@pytest.fixture
def twin_and_result(fixed_time: datetime) -> tuple[TwinRecord, PipelineResult]:
    return build_test_twin(fixed_time)


def variant(result: PipelineResult, **changes) -> PipelineResult:
    """A copy of ``result`` with some fields replaced, validated against the contract again."""
    data = result.model_dump()
    data.update(changes)
    return PipelineResult.model_validate(data)


def with_joint(result: PipelineResult, **changes) -> PipelineResult:
    joint = result.joints[0].model_dump()
    joint.update(changes)
    return variant(result, joints=[joint])


def stage_of(twin: TwinRecord, result: PipelineResult, drive: DriveSettings | None = None):
    return build_stage(twin, [result], drive)


# ------------------------------------------------------------------------------------ layout
def test_stage_units_and_default_prim(twin_and_result) -> None:
    stage = stage_of(*twin_and_result)
    assert UsdGeom.GetStageUpAxis(stage) == UsdGeom.Tokens.z
    assert UsdGeom.StageHasAuthoredMetersPerUnit(stage)
    assert UsdGeom.GetStageMetersPerUnit(stage) == 1.0
    assert UsdPhysics.StageHasAuthoredKilogramsPerUnit(stage)
    assert UsdPhysics.GetStageKilogramsPerUnit(stage) == 1.0
    # Same timeline as NVIDIA's example stages, so Isaac Sim does not loop over a single frame.
    assert stage.HasAuthoredTimeCodeRange()
    assert (stage.GetStartTimeCode(), stage.GetEndTimeCode()) == (0.0, 1_000_000.0)
    assert stage.GetTimeCodesPerSecond() == 60.0
    root = stage.GetDefaultPrim()
    assert root.GetPath() == Sdf.Path(ROOT)
    assert Usd.ModelAPI(root).GetKind() == "component"
    assert Usd.ModelAPI(root).GetAssetName() == "moonwalkers/testindexer"
    assert Usd.ModelAPI(root).GetAssetVersion() == "1"


def test_parts_are_rigid_bodies_with_convex_mesh_colliders(twin_and_result) -> None:
    twin, result = twin_and_result
    stage = stage_of(twin, result)
    for part in result.parts:
        body = stage.GetPrimAtPath(f"{ROOT}/{part.part_id}")
        assert body.HasAPI(UsdPhysics.RigidBodyAPI)
        assert UsdGeom.Xformable(body).GetOrderedXformOps() == []  # identity: model frame
        geometry = stage.GetPrimAtPath(f"{ROOT}/{part.part_id}/geometry")
        mesh = UsdGeom.Mesh(geometry)
        assert geometry.HasAPI(UsdPhysics.CollisionAPI)
        approximation = UsdPhysics.MeshCollisionAPI(geometry).GetApproximationAttr().Get()
        assert approximation == UsdPhysics.Tokens.convexHull
        assert mesh.GetSubdivisionSchemeAttr().Get() == UsdGeom.Tokens.none
        assert mesh.GetNormalsInterpolation() == UsdGeom.Tokens.faceVarying
        assert len(mesh.GetNormalsAttr().Get()) == len(mesh.GetFaceVertexIndicesAttr().Get())
        expected = primitive_mesh(part.primitive)
        points = mesh.GetPointsAttr().Get()
        assert len(points) == len(expected.points)
        for got, want in zip(points, expected.points, strict=True):
            assert Gf.IsClose(Gf.Vec3d(got), Gf.Vec3d(*want), 1e-6)


def test_root_part_is_fixed_to_the_world(twin_and_result) -> None:
    stage = stage_of(*twin_and_result)
    assert stage.GetDefaultPrim().HasAPI(UsdPhysics.ArticulationRootAPI)
    anchor = UsdPhysics.FixedJoint(stage.GetPrimAtPath(f"{ROOT}/joints/{WORLD_JOINT}"))
    assert anchor.GetBody0Rel().GetTargets() == []  # the world
    assert anchor.GetBody1Rel().GetTargets() == [Sdf.Path(f"{ROOT}/body")]
    parsed = UsdPhysics.UsdPhysicsLoadStageFromPrimRange(stage, [Sdf.Path.absoluteRootPath])
    _, articulations = parsed[UsdPhysics.ObjectType.Articulation]
    assert len(articulations) == 1
    assert list(articulations[0].rootPrims) == [Sdf.Path(f"{ROOT}/joints/{WORLD_JOINT}")]


@pytest.mark.parametrize("axis", [(1, 0, 0), (0, 1, 0), (0, 0, -1), (0.6, 0.8, 0.0)])
def test_revolute_joint_frame_turns_x_onto_the_contract_axis(twin_and_result, axis) -> None:
    twin, result = twin_and_result
    stage = stage_of(twin, with_joint(result, axis=axis))
    joint = UsdPhysics.RevoluteJoint(stage.GetPrimAtPath(JOINT))
    assert joint.GetAxisAttr().Get() == UsdPhysics.Tokens.x
    assert joint.GetBody0Rel().GetTargets() == [Sdf.Path(f"{ROOT}/body")]  # parent
    assert joint.GetBody1Rel().GetTargets() == [Sdf.Path(f"{ROOT}/spindle")]  # child
    assert joint.GetLocalPos0Attr().Get() == joint.GetLocalPos1Attr().Get() == Gf.Vec3f(0.1, 0, 0.1)
    rot0, rot1 = joint.GetLocalRot0Attr().Get(), joint.GetLocalRot1Attr().Get()
    assert rot0 == rot1
    q = (rot0.GetReal(), *rot0.GetImaginary())
    for got, want in zip(q, quat_between((1, 0, 0), axis), strict=True):
        assert math.isclose(got, want, abs_tol=1e-6)
    turned = rotate(q, (1.0, 0.0, 0.0))
    length = math.hypot(*axis)
    for got, want in zip(turned, axis, strict=True):
        assert math.isclose(got, want / length, abs_tol=1e-6)


def test_limits_are_written_in_degrees(twin_and_result) -> None:
    twin, result = twin_and_result
    stage = stage_of(twin, with_joint(result, lower_limit=-math.pi / 2, upper_limit=math.pi))
    joint = UsdPhysics.RevoluteJoint(stage.GetPrimAtPath(JOINT))
    assert math.isclose(joint.GetLowerLimitAttr().Get(), -90.0)
    assert math.isclose(joint.GetUpperLimitAttr().Get(), 180.0)


def test_joint_without_limits_is_left_unlimited(twin_and_result) -> None:
    stage = stage_of(*twin_and_result)  # keep the stage alive while its prims are used
    joint = UsdPhysics.RevoluteJoint(stage.GetPrimAtPath(JOINT))
    assert not joint.GetLowerLimitAttr().HasAuthoredValue()
    assert joint.GetLowerLimitAttr().Get() == -math.inf  # UsdPhysics fallback: not limited
    assert joint.GetUpperLimitAttr().Get() == math.inf


def test_position_drive_targets_degrees(twin_and_result) -> None:
    stage = stage_of(*twin_and_result, DriveSettings.hold(math.radians(90)))
    drive = UsdPhysics.DriveAPI(stage.GetPrimAtPath(JOINT), "angular")
    assert math.isclose(drive.GetTargetPositionAttr().Get(), 90.0, abs_tol=1e-4)
    assert not drive.GetTargetVelocityAttr().HasAuthoredValue()
    assert drive.GetTypeAttr().Get() == "acceleration"
    assert (drive.GetStiffnessAttr().Get(), drive.GetDampingAttr().Get()) == (100.0, 20.0)


def test_velocity_drive_targets_degrees_per_second(twin_and_result) -> None:
    stage = stage_of(*twin_and_result, DriveSettings.spin(math.radians(30)))
    drive = UsdPhysics.DriveAPI(stage.GetPrimAtPath(JOINT), "angular")
    assert math.isclose(drive.GetTargetVelocityAttr().Get(), 30.0, abs_tol=1e-4)
    assert drive.GetStiffnessAttr().Get() == 0.0
    assert not drive.GetTargetPositionAttr().HasAuthoredValue()


@pytest.mark.parametrize(
    "settings",
    [
        {"mode": "velocity", "stiffness": 5.0},
        {"damping": -1.0},
        {"stiffness": -1.0},
    ],
)
def test_bad_drive_settings_are_refused(settings) -> None:
    with pytest.raises(ValueError):
        DriveSettings(**settings)


def test_physics_scene_is_outside_the_twin(twin_and_result, tmp_path: Path) -> None:
    path = export_twin(*twin_and_result[:1], [twin_and_result[1]], tmp_path / "twin.usda")
    stage = Usd.Stage.Open(str(path))
    assert stage.GetPrimAtPath(SCENE_PATH).IsA(UsdPhysics.Scene)
    assert not stage.GetPrimAtPath(SCENE_PATH).GetPath().HasPrefix(Sdf.Path(ROOT))

    # A stage that references the twin gets the machine but not the physics scene.
    world = Usd.Stage.CreateInMemory()
    world.DefinePrim("/World/indexer").GetReferences().AddReference(str(path))
    assert world.GetPrimAtPath("/World/indexer/spindle").HasAPI(UsdPhysics.RigidBodyAPI)
    assert not any(p.IsA(UsdPhysics.Scene) for p in world.Traverse())


# -------------------------------------------------------------------------------- provenance
def test_provenance_is_carried_in_the_file(twin_and_result) -> None:
    twin, result = twin_and_result
    fact = {
        "key": "center_height",
        "value": 0.1,
        "unit": "m",
        "original": "100 mm",
        "confidence": 0.9,
        "citations": [{"source_id": "src-synthetic", "locator": "page 2", "quote": "100 mm"}],
    }
    stage = stage_of(twin, variant(result, facts=[fact]))
    root = stage.GetDefaultPrim()
    assert root.GetCustomDataByKey("moonwalkers:twin:twin_id") == twin.twin_id
    assert list(root.GetCustomDataByKey("moonwalkers:twin:built_from")) == twin.built_from
    entry = root.GetCustomDataByKey(f"moonwalkers:results:{result.result_id}")
    assert entry["pipeline"] == "C"
    assert entry["sources"]["src-synthetic"]["uri"] == "user"
    assert entry["facts"]["center_height"]["value"] == 0.1
    assert list(entry["facts"]["center_height"]["citations"]) == [
        'src-synthetic | page 2 | "100 mm"'
    ]
    part = stage.GetPrimAtPath(f"{ROOT}/spindle").GetCustomDataByKey("moonwalkers")
    assert part["part_id"] == "spindle" and list(part["citations"]) == ["src-synthetic"]
    joint = stage.GetPrimAtPath(JOINT).GetCustomDataByKey("moonwalkers")
    assert joint["joint_id"] == "spindle_rotation" and list(joint["citations"]) == ["src-synthetic"]


# ----------------------------------------------------------------------------- static twins
def test_twin_without_joints_is_static(twin_and_result) -> None:
    twin, result = twin_and_result
    stage = stage_of(twin, variant(result, joints=[]))
    assert not stage.GetDefaultPrim().HasAPI(UsdPhysics.ArticulationRootAPI)
    assert not stage.GetPrimAtPath(f"{ROOT}/joints")
    for part_id in ("body", "spindle"):
        assert not stage.GetPrimAtPath(f"{ROOT}/{part_id}").HasAPI(UsdPhysics.RigidBodyAPI)
        geometry = stage.GetPrimAtPath(f"{ROOT}/{part_id}/geometry")
        assert geometry.HasAPI(UsdPhysics.CollisionAPI)
        assert UsdPhysics.MeshCollisionAPI(geometry).GetApproximationAttr().Get() == "none"
    assert [i for i in validate_stage(stage) if i.severity == "error"] == []


# ---------------------------------------------------------------------------------- writing
def test_export_is_deterministic_lf_text(twin_and_result, tmp_path: Path) -> None:
    twin, result = twin_and_result
    first = export_twin(twin, [result], tmp_path / "a" / "twin.usda").read_bytes()
    second = export_twin(twin, [result], tmp_path / "b" / "twin.usda").read_bytes()
    assert first == second
    assert first.startswith(b"#usda 1.0")
    assert b"\r\n" not in first
    assert sorted(p.name for p in tmp_path.rglob("*") if p.is_file()) == ["twin.usda", "twin.usda"]


def test_export_writes_binary_crate_files(twin_and_result, tmp_path: Path) -> None:
    twin, result = twin_and_result
    text = Usd.Stage.Open(str(export_twin(twin, [result], tmp_path / "twin.usda")))
    path = export_twin(twin, [result], tmp_path / "twin.usdc")
    assert path.read_bytes().startswith(b"PXR-USDC")
    crate = Usd.Stage.Open(str(path))
    assert [p.GetPath() for p in crate.Traverse()] == [p.GetPath() for p in text.Traverse()]
    assert [i for i in validate_stage(crate) if i.severity == "error"] == []
    assert sorted(p.name for p in tmp_path.iterdir()) == ["twin.usda", "twin.usdc"]


@pytest.mark.parametrize("name", ["twin.usd", "twin.obj"])
def test_export_needs_an_explicit_usd_format(twin_and_result, tmp_path: Path, name: str) -> None:
    twin, result = twin_and_result
    with pytest.raises(ExportError, match=r"\.usda \(text\) or \.usdc \(binary\)"):
        export_twin(twin, [result], tmp_path / name)


# --------------------------------------------------------------------------------- refusals
def example_twin(example_result: PipelineResult, fixed_time) -> TwinRecord:
    return TwinRecord(
        twin_id="haas/ha5c@v1",
        machine_key="haas/ha5c",
        version=1,
        status="needs_review",
        built_from=[example_result.result_id],
        created_at=fixed_time,
    )


def test_mesh_file_parts_need_the_data_folder(example_result: PipelineResult, fixed_time) -> None:
    with pytest.raises(ExportError, match="pass data_dir"):
        build_stage(example_twin(example_result, fixed_time), [example_result])


def test_missing_mesh_file_is_reported(
    example_result: PipelineResult, fixed_time, tmp_path: Path
) -> None:
    with pytest.raises(ExportError, match="mesh file not found"):
        build_stage(example_twin(example_result, fixed_time), [example_result], data_dir=tmp_path)


def test_mesh_file_parts_are_exported(
    example_result: PipelineResult, fixed_time, tmp_path: Path, indexer
) -> None:
    # The example's parts point at twins/haas-ha5c/v1/{body,spindle}.glb under the data folder.
    from moonwalkers.pipelines.b.mesh_tools import split_by_cylinder

    body, spindle = split_by_cylinder(indexer(), (1.0, 0, 0.2), (1, 0, 0), 0.45, 0.0)
    folder = tmp_path / "twins" / "haas-ha5c" / "v1"
    folder.mkdir(parents=True)
    body.export(folder / "body.glb")
    spindle.export(folder / "spindle.glb")

    stage = build_stage(
        example_twin(example_result, fixed_time), [example_result], data_dir=tmp_path
    )
    mesh = UsdGeom.Mesh(stage.GetPrimAtPath("/haas_ha5c/spindle/geometry"))
    assert len(mesh.GetFaceVertexCountsAttr().Get()) == len(spindle.faces)
    lo, hi = mesh.GetExtentAttr().Get()
    assert math.isclose(lo[0], 1.0, abs_tol=1e-6) and math.isclose(hi[0], 1.6, abs_tol=1e-6)
    assert [i.message for i in validate_stage(stage) if i.severity == "error"] == []


def test_results_must_match_the_twin(twin_and_result) -> None:
    twin, result = twin_and_result
    with pytest.raises(ExportError, match="built from"):
        build_stage(twin.model_copy(update={"built_from": ["res-other"]}), [result])


def test_twin_without_parts_is_refused(twin_and_result) -> None:
    twin, result = twin_and_result
    with pytest.raises(ExportError, match="no parts"):
        build_stage(twin, [variant(result, parts=[], joints=[])])


def test_same_part_in_two_results_is_refused(twin_and_result) -> None:
    twin, result = twin_and_result
    copy = variant(result, result_id="res-copy")
    twin = twin.model_copy(update={"built_from": [result.result_id, "res-copy"]})
    with pytest.raises(ExportError, match="more than one result"):
        build_stage(twin, [result, copy])


def extra_part(part_id: str) -> dict:
    return {
        "part_id": part_id,
        "name": part_id,
        "geometry_format": "primitive",
        "primitive": {"shape": "box", "size_m": [0.01, 0.01, 0.01]},
    }


def joint(joint_id: str, parent: str, child: str, joint_type: str = "revolute") -> dict:
    return {
        "joint_id": joint_id,
        "joint_type": joint_type,
        "parent_part": parent,
        "child_part": child,
        "axis": (1, 0, 0),
        "origin_m": (0, 0, 0),
        "confidence": 1.0,
        "citations": [{"source_id": "src-synthetic"}],
    }


@pytest.mark.parametrize(
    ("extra_parts", "joints", "message"),
    [
        ([], [joint("slide", "body", "spindle", "prismatic")], "prismatic"),
        (
            ["arm"],
            [joint("a", "body", "spindle"), joint("b", "arm", "spindle")],
            "child of two joints",
        ),
        ([], [joint("a", "body", "spindle"), joint("b", "spindle", "body")], "one root part"),
        (["loose"], [joint("a", "body", "spindle")], "one root part"),
        (["joints"], [joint("a", "body", "spindle")], "reserved name"),
        ([], [joint(WORLD_JOINT, "body", "spindle")], "reserved name"),
        (["a-b", "a_b"], [], "both become the prim name"),
    ],
)
def test_unexportable_structures_are_refused(twin_and_result, extra_parts, joints, message) -> None:
    twin, result = twin_and_result
    parts = [p.model_dump() for p in result.parts] + [extra_part(p) for p in extra_parts]
    with pytest.raises(ExportError, match=message):
        build_stage(twin, [variant(result, parts=parts, joints=joints)])
