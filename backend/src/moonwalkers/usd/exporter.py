"""Write a twin as an OpenUSD stage that Isaac Sim can simulate (decision 0010).

An exported twin, for example machine key ``haas/ha5c``::

    /haas_ha5c                  Xform, defaultPrim, kind "component", PhysicsArticulationRootAPI
        /body                   Xform + PhysicsRigidBodyAPI (one per part)
            /geometry           Mesh + PhysicsCollisionAPI + PhysicsMeshCollisionAPI (convexHull)
        /spindle                ...
        /joints                 Scope
            /fixed_to_world     PhysicsFixedJoint, body1 = the root part (fixed base)
            /spindle_rotation   PhysicsRevoluteJoint + PhysicsDriveAPI:angular
    /PhysicsScene               outside the defaultPrim, so a stage that references the twin
                                does not inherit it

Rules followed (sources in decision 0010 and docs/research/2026-10-17-usd-physics-for-isaac-sim.md):

* Stage units are metres and kilograms with +Z up; angles are written in degrees.
* The timeline runs from 0 to 1,000,000 at 60 time codes per second, as in NVIDIA's own example
  stages (``isaacsim.examples.interactive/data/SurfaceGripper_gantry.usda`` in Isaac Sim 6.2.0).
  Without a range, Isaac Sim warns that playback "will loop over a single frame".
* Part transforms stay at identity: meshes are already in the twin's model frame, so each joint
  frame is the contract's ``origin_m`` in both bodies. UsdPhysics joint frames do not support scale,
  so any scale is baked into mesh points.
* A twin without joints is written as static colliders (no rigid bodies, nothing moves on Play).
* Parts are primitives (meshed by ``geometry``) or mesh files (GLB, OBJ) relative to ``data_dir``,
  already in the twin frame and in metres (Pipeline B writes them that way).
* Mass is not authored; physics engines infer it from the collision volume at 1000 kg/m^3. That is a
  placeholder, not the machine's real mass.
* Every part, joint and the root carry their citations in ``customData["moonwalkers"]``.
"""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from dataclasses import dataclass
from importlib.metadata import version as package_version
from pathlib import Path
from typing import Any, Literal

from pxr import Gf, Sdf, Tf, Usd, UsdGeom, UsdPhysics, Vt

from moonwalkers.contracts.pipeline_result import (
    SCHEMA_VERSION,
    Citation,
    Joint,
    Part,
    PipelineResult,
    TwinRecord,
)

from .frames import quat_between
from .geometry import MeshData, primitive_mesh
from .mesh_files import MESH_FILE_FORMATS, mesh_data_from_file
from .units import KILOGRAMS_PER_UNIT, METERS_PER_UNIT, usd_angle, usd_length

WORLD_JOINT = "fixed_to_world"
JOINTS_SCOPE = "joints"
GEOMETRY_PRIM = "geometry"
SCENE_PATH = "/PhysicsScene"

START_TIME_CODE = 0.0
END_TIME_CODE = 1_000_000.0
TIME_CODES_PER_SECOND = 60.0

ROOT_PART_COLOR = (0.55, 0.57, 0.60)  # grey: the fixed base
MOVING_PART_COLOR = (0.90, 0.45, 0.10)  # orange: parts that move


class ExportError(ValueError):
    """The twin cannot be written as a simulatable stage."""


@dataclass(frozen=True)
class DriveSettings:
    """The angular drive written on every revolute joint.

    These are simulation tuning values chosen by us, not facts about a machine [INFERENCE]. The
    drive type "acceleration" makes the spring act on acceleration rather than force (UsdPhysics
    DriveAPI docs), so the response does not depend on the placeholder masses. Position mode holds
    ``target`` (rad) with a critically damped spring: stiffness = w^2 and damping = 2w for w = 10
    rad/s. Velocity mode turns at ``target`` (rad/s) with zero stiffness, as Isaac Sim's GUI
    tutorial recommends for velocity control ("a high damping and zero stiffness").
    """

    mode: Literal["position", "velocity"] = "position"
    target: float = 0.0  # rad (position) or rad/s (velocity), contract units
    stiffness: float = 100.0
    damping: float = 20.0
    drive_type: Literal["force", "acceleration"] = "acceleration"

    def __post_init__(self) -> None:
        if self.stiffness < 0 or self.damping < 0:
            raise ValueError("drive stiffness and damping must be non-negative")
        if self.mode == "velocity" and self.stiffness != 0:
            raise ValueError("a velocity drive needs zero stiffness")

    @classmethod
    def hold(cls, angle_rad: float = 0.0) -> DriveSettings:
        """Hold (or move to) a joint angle."""
        return cls(mode="position", target=angle_rad)

    @classmethod
    def spin(cls, speed_rad_s: float) -> DriveSettings:
        """Turn continuously at a joint speed."""
        return cls(mode="velocity", target=speed_rad_s, stiffness=0.0, damping=20.0)


def export_twin(
    twin: TwinRecord,
    results: Sequence[PipelineResult],
    path: Path,
    drive: DriveSettings | None = None,
    data_dir: Path | None = None,
) -> Path:
    """Write the twin to ``path``; returns the path.

    ``.usda`` gives text with LF line endings, readable for small twins. ``.usdc`` gives a binary
    crate file, which NVIDIA's asset validator asks for once arrays pass 64 elements, as a
    generated mesh's do (decision 0012). ``data_dir`` is the project ``data/`` folder; mesh-file
    parts are relative to it (contract).
    """
    path = Path(path)
    if path.suffix not in (".usda", ".usdc"):
        raise ExportError(f"export writes .usda (text) or .usdc (binary) files, not {path.name}")
    stage = build_stage(twin, results, drive, data_dir)  # the stage owns its root layer: keep it
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.stem}.tmp{path.suffix}")  # the suffix picks the file format
    try:
        if path.suffix == ".usda":
            tmp.write_text(stage.GetRootLayer().ExportToString(), encoding="utf-8", newline="\n")
        elif not stage.GetRootLayer().Export(str(tmp)):
            raise ExportError(f"could not write {path}")
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)
    return path


def build_stage(
    twin: TwinRecord,
    results: Sequence[PipelineResult],
    drive: DriveSettings | None = None,
    data_dir: Path | None = None,
) -> Usd.Stage:
    """Build the twin's stage in memory (see the module docstring for its layout)."""
    drive = drive or DriveSettings()
    _check_results_match(twin, results)
    parts = _collect(results, "parts", "part_id")
    joints = _collect(results, "joints", "joint_id")
    if not parts:
        raise ExportError(f"twin {twin.twin_id} has no parts to export")
    _check_prim_names(list(parts), reserved={JOINTS_SCOPE}, what="part")
    _check_prim_names(list(joints), reserved={WORLD_JOINT}, what="joint")
    root_part = _root_part(parts, joints)

    stage = Usd.Stage.CreateInMemory()
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(stage, METERS_PER_UNIT)
    UsdPhysics.SetStageKilogramsPerUnit(stage, KILOGRAMS_PER_UNIT)
    stage.SetStartTimeCode(START_TIME_CODE)
    stage.SetEndTimeCode(END_TIME_CODE)
    stage.SetTimeCodesPerSecond(TIME_CODES_PER_SECOND)
    stage.GetRootLayer().documentation = (
        f"MoonWalkers digital twin {twin.twin_id} ({twin.status.replace('_', ' ')}). "
        f"Written by moonwalkers {package_version('moonwalkers')}; units: m, kg, degrees."
    )

    root_path = Sdf.Path.absoluteRootPath.AppendChild(_identifier(twin.machine_key))
    root = UsdGeom.Xform.Define(stage, root_path).GetPrim()
    stage.SetDefaultPrim(root)
    Usd.ModelAPI(root).SetKind("component")
    # assetInfo "identifier" is an asset (file) path, so the twin id lives in customData instead.
    Usd.ModelAPI(root).SetAssetName(twin.machine_key)
    Usd.ModelAPI(root).SetAssetVersion(str(twin.version))
    root.SetCustomDataByKey("moonwalkers", _twin_provenance(twin, results))

    articulated = bool(joints)
    body_paths: dict[str, Sdf.Path] = {}
    for part_id, (part, result_id) in parts.items():
        color = ROOT_PART_COLOR if part_id == root_part else MOVING_PART_COLOR
        body_paths[part_id] = _write_part(
            stage, root_path, part, result_id, articulated, color, data_dir
        )

    if articulated:
        UsdPhysics.ArticulationRootAPI.Apply(root)
        scope = UsdGeom.Scope.Define(stage, root_path.AppendChild(JOINTS_SCOPE)).GetPath()
        anchor = UsdPhysics.FixedJoint.Define(stage, scope.AppendChild(WORLD_JOINT))
        anchor.CreateBody1Rel().SetTargets([body_paths[root_part]])
        anchor.GetPrim().SetDocumentation(
            f"Fixes the root part '{root_part}' to the world, making a fixed-base articulation."
        )
        for joint, result_id in joints.values():
            _write_joint(stage, scope, joint, result_id, body_paths, drive)

    UsdPhysics.Scene.Define(stage, SCENE_PATH)  # default gravity: earth, opposite the up axis
    return stage


# --------------------------------------------------------------------------- structure checks
def _check_results_match(twin: TwinRecord, results: Sequence[PipelineResult]) -> None:
    given = [r.result_id for r in results]
    if sorted(given) != sorted(twin.built_from):
        raise ExportError(
            f"twin {twin.twin_id} was built from {twin.built_from}, but results {given} were given"
        )


def _collect(results: Sequence[PipelineResult], field: str, id_field: str) -> dict[str, Any]:
    """``{id: (item, result_id)}`` across results; the same id in two results is ambiguous."""
    items: dict[str, Any] = {}
    for result in results:
        for item in getattr(result, field):
            item_id = getattr(item, id_field)
            if item_id in items:
                raise ExportError(f"{id_field} '{item_id}' appears in more than one result")
            items[item_id] = (item, result.result_id)
    return items


def _check_prim_names(ids: list[str], reserved: set[str], what: str) -> None:
    """Ids become prim names; two ids must not map to one name or take a reserved name."""
    names: dict[str, str] = {}
    for item_id in ids:
        name = _identifier(item_id)
        if name in reserved:
            raise ExportError(f"{what} id '{item_id}' uses the reserved name '{name}'")
        if name in names:
            raise ExportError(
                f"{what} ids '{names[name]}' and '{item_id}' both become the prim name '{name}'"
            )
        names[name] = item_id


def _root_part(parts: dict[str, tuple[Part, str]], joints: dict[str, tuple[Joint, str]]) -> str:
    """The one part that is not a joint's child; every other part must hang from it."""
    if not joints:
        return next(iter(parts))
    children: dict[str, str] = {}
    for joint_id, (joint, _) in joints.items():
        if joint.joint_type == "prismatic":
            raise ExportError(f"joint '{joint_id}': prismatic joints are not exported yet")
        if joint.child_part in children:
            raise ExportError(
                f"part '{joint.child_part}' is the child of two joints "
                f"('{children[joint.child_part]}' and '{joint_id}')"
            )
        children[joint.child_part] = joint_id
    roots = [p for p in parts if p not in children]
    if len(roots) != 1:
        raise ExportError(f"expected one root part (not any joint's child), found {roots}")
    parent_of = {joint.child_part: joint.parent_part for joint, _ in joints.values()}
    for part in parts:  # walk up to the root; a loop or a detached part never gets there
        seen = {part}
        while part in parent_of:
            part = parent_of[part]
            if part in seen:
                raise ExportError(f"joints form a loop through part '{part}'")
            seen.add(part)
        if part != roots[0]:
            raise ExportError(f"part '{part}' is not connected to the root part '{roots[0]}'")
    return roots[0]


# ------------------------------------------------------------------------------------ writing
def _write_part(
    stage: Usd.Stage,
    root_path: Sdf.Path,
    part: Part,
    result_id: str,
    articulated: bool,
    color: tuple[float, float, float],
    data_dir: Path | None,
) -> Sdf.Path:
    mesh = _part_mesh(part, data_dir)

    body = UsdGeom.Xform.Define(stage, root_path.AppendChild(_identifier(part.part_id))).GetPrim()
    body.SetDocumentation(part.name)
    body.SetCustomDataByKey(
        "moonwalkers",
        _clean(
            {
                "part_id": part.part_id,
                "name": part.name,
                "result_id": result_id,
                "geometry_format": part.geometry_format,
                "primitive_json": json.dumps(part.primitive, sort_keys=True),
                "citations": _citations(part.citations),
            }
        ),
    )
    geometry = _write_mesh(stage, body.GetPath().AppendChild(GEOMETRY_PRIM), mesh, color)
    UsdPhysics.CollisionAPI.Apply(geometry)
    approximation = UsdPhysics.MeshCollisionAPI.Apply(geometry).CreateApproximationAttr()
    if articulated:
        # Moving bodies need convex colliders: NVIDIA's Omni Physics docs describe triangle meshes
        # as suited to "objects that are either static or kinematic".
        UsdPhysics.RigidBodyAPI.Apply(body)
        approximation.Set(UsdPhysics.Tokens.convexHull)
    else:
        approximation.Set(UsdPhysics.Tokens.none)
    return body.GetPath()


def _part_mesh(part: Part, data_dir: Path | None) -> MeshData:
    """A primitive's generated mesh, or a mesh file read from ``data_dir``."""
    try:
        if part.geometry_format == "primitive" and part.primitive is not None:
            return primitive_mesh(part.primitive)
        if part.geometry_format in MESH_FILE_FORMATS and part.geometry_file:
            if data_dir is None:
                raise ExportError(f"part '{part.part_id}' is a mesh file; pass data_dir")
            path = Path(data_dir) / part.geometry_file
            if not path.is_file():
                raise ExportError(f"part '{part.part_id}': mesh file not found: {path}")
            return mesh_data_from_file(path)
    except ExportError:
        raise
    except ValueError as exc:  # invalid primitive or unreadable mesh
        raise ExportError(f"part '{part.part_id}': {exc}") from exc
    raise ExportError(
        f"part '{part.part_id}': geometry format '{part.geometry_format}' is not exported "
        f"(supported: primitive, {', '.join(sorted(MESH_FILE_FORMATS))})"
    )


def _write_mesh(
    stage: Usd.Stage, path: Sdf.Path, mesh: MeshData, color: tuple[float, float, float]
) -> Usd.Prim:
    usd_mesh = UsdGeom.Mesh.Define(stage, path)
    points = [tuple(usd_length(c) for c in p) for p in mesh.points]
    usd_mesh.CreatePointsAttr(Vt.Vec3fArray([Gf.Vec3f(*p) for p in points]))
    usd_mesh.CreateFaceVertexCountsAttr(Vt.IntArray(list(mesh.face_vertex_counts)))
    usd_mesh.CreateFaceVertexIndicesAttr(Vt.IntArray(list(mesh.face_vertex_indices)))
    lo, hi = mesh.extent()
    usd_mesh.CreateExtentAttr(
        Vt.Vec3fArray([Gf.Vec3f(*map(usd_length, lo)), Gf.Vec3f(*map(usd_length, hi))])
    )
    # Polygons rather than a subdivision surface, with one normal per face corner so each face
    # renders flat (the asset validator requires normals when subdivision is off).
    usd_mesh.CreateSubdivisionSchemeAttr(UsdGeom.Tokens.none)
    corner_normals = [
        Gf.Vec3f(*normal)
        for normal, count in zip(mesh.face_normals(), mesh.face_vertex_counts, strict=True)
        for _ in range(count)
    ]
    usd_mesh.CreateNormalsAttr(Vt.Vec3fArray(corner_normals))
    usd_mesh.SetNormalsInterpolation(UsdGeom.Tokens.faceVarying)
    usd_mesh.CreateDisplayColorAttr(Vt.Vec3fArray([Gf.Vec3f(*color)]))
    return usd_mesh.GetPrim()


def _write_joint(
    stage: Usd.Stage,
    scope: Sdf.Path,
    joint: Joint,
    result_id: str,
    body_paths: dict[str, Sdf.Path],
    drive: DriveSettings,
) -> None:
    path = scope.AppendChild(_identifier(joint.joint_id))
    if joint.joint_type == "revolute":
        usd_joint: UsdPhysics.Joint = UsdPhysics.RevoluteJoint.Define(stage, path)
    else:
        usd_joint = UsdPhysics.FixedJoint.Define(stage, path)
    usd_joint.CreateBody0Rel().SetTargets([body_paths[joint.parent_part]])
    usd_joint.CreateBody1Rel().SetTargets([body_paths[joint.child_part]])

    # Parts sit at identity, so the joint frame is the same point in both bodies. The frame's X
    # axis is turned onto the contract's joint axis, and the joint rotates about X.
    origin = Gf.Vec3f(*(usd_length(c) for c in joint.origin_m))
    w, x, y, z = quat_between((1.0, 0.0, 0.0), joint.axis)
    rotation = Gf.Quatf(w, Gf.Vec3f(x, y, z))
    usd_joint.CreateLocalPos0Attr(origin)
    usd_joint.CreateLocalPos1Attr(origin)
    usd_joint.CreateLocalRot0Attr(rotation)
    usd_joint.CreateLocalRot1Attr(rotation)

    if joint.joint_type == "revolute":
        revolute = UsdPhysics.RevoluteJoint(usd_joint.GetPrim())
        revolute.CreateAxisAttr(UsdPhysics.Tokens.x)
        if joint.lower_limit is not None:  # unlimited joints wrap on a 360 degree boundary
            revolute.CreateLowerLimitAttr(usd_angle(joint.lower_limit))
        if joint.upper_limit is not None:
            revolute.CreateUpperLimitAttr(usd_angle(joint.upper_limit))
        _write_drive(usd_joint.GetPrim(), drive)

    prim = usd_joint.GetPrim()
    prim.SetDocumentation(
        f"{joint.joint_type.capitalize()} joint '{joint.joint_id}': "
        f"{joint.parent_part} (body0) -> {joint.child_part} (body1)."
    )
    prim.SetCustomDataByKey(
        "moonwalkers",
        _clean(
            {
                "joint_id": joint.joint_id,
                "joint_type": joint.joint_type,
                "result_id": result_id,
                "axis": json.dumps(list(joint.axis)),
                "origin_m": json.dumps(list(joint.origin_m)),
                "lower_limit_rad": joint.lower_limit,
                "upper_limit_rad": joint.upper_limit,
                "max_velocity_rad_s": joint.max_velocity,
                "confidence": joint.confidence,
                "citations": _citations(joint.citations),
            }
        ),
    )


def _write_drive(prim: Usd.Prim, drive: DriveSettings) -> None:
    api = UsdPhysics.DriveAPI.Apply(prim, "angular")
    api.CreateTypeAttr(drive.drive_type)
    api.CreateStiffnessAttr(drive.stiffness)
    api.CreateDampingAttr(drive.damping)
    if drive.mode == "position":
        api.CreateTargetPositionAttr(usd_angle(drive.target))
    else:
        api.CreateTargetVelocityAttr(usd_angle(drive.target))


# --------------------------------------------------------------------------------- provenance
def _twin_provenance(twin: TwinRecord, results: Sequence[PipelineResult]) -> dict[str, Any]:
    return {
        "twin": _clean(
            {
                "twin_id": twin.twin_id,
                "machine_key": twin.machine_key,
                "version": twin.version,
                "status": twin.status,
                "created_at": twin.created_at.isoformat(),
                "built_from": list(twin.built_from),
                "notes": twin.notes,
                "contract_schema_version": SCHEMA_VERSION,
            }
        ),
        "results": {r.result_id: _result_provenance(r) for r in results},
    }


def _result_provenance(result: PipelineResult) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "pipeline": result.pipeline.value,
        "produced_by": result.produced_by,
        "produced_at": result.produced_at.isoformat(),
        "needs_human_review": result.needs_human_review,
        "sources": {
            s.source_id: _clean(
                {
                    "kind": s.kind,
                    "input_type": s.input_type.value if s.input_type else None,
                    "uri": s.uri,
                    "title": s.title,
                    "retrieved_at": s.retrieved_at.isoformat(),
                    "license_note": s.license_note,
                }
            )
            for s in result.sources
        },
        "facts": {
            f.key: _clean(
                {
                    "value": f.value,
                    "unit": f.unit,
                    "original": f.original,
                    "confidence": f.confidence,
                    "citations": _citations(f.citations),
                }
            )
            for f in result.facts
        },
        "control": {
            b.behavior_id: _clean(
                {
                    "name": b.name,
                    "kind": b.kind,
                    "description": b.description,
                    "drives_joints": list(b.drives_joints),
                    "spec_json": json.dumps(b.spec, sort_keys=True),
                    "confidence": b.confidence,
                    "citations": _citations(b.citations),
                }
            )
            for b in result.control
        },
        "issues": Vt.StringArray(
            [f"{i.severity}: {i.message}" + (f" ({i.ref})" if i.ref else "") for i in result.issues]
        ),
    }
    if result.identity is not None:
        entry["identity"] = _clean(
            {
                "manufacturer": result.identity.manufacturer,
                "model": result.identity.model,
                "category": result.identity.category,
                "confidence": result.identity.confidence,
                "citations": _citations(result.identity.citations),
            }
        )
    if result.scale is not None:
        entry["scale"] = _clean(
            {
                "method": result.scale.method,
                "reference": result.scale.reference,
                "known_value_m": result.scale.known_value_m,
                "scale_factor": result.scale.scale_factor,
                "citations": _citations(result.scale.citations),
            }
        )
    return entry


def _citations(citations: Sequence[Citation]) -> list[str]:
    """Each citation as one line: ``source_id | locator | "quote"`` (empty parts left out)."""
    lines = []
    for c in citations:
        line = c.source_id
        if c.locator:
            line += f" | {c.locator}"
        if c.quote:
            line += f' | "{c.quote}"'
        lines.append(line)
    return lines


def _clean(values: dict[str, Any]) -> dict[str, Any]:
    """Drop ``None`` (USD dictionaries cannot hold it) and store string lists as ``string[]``."""
    cleaned: dict[str, Any] = {}
    for key, value in values.items():
        if value is None:
            continue
        cleaned[key] = Vt.StringArray(value) if isinstance(value, list) else value
    return cleaned


def _identifier(text: str) -> str:
    """A valid USD prim name for an id or machine key ("haas/ha5c" becomes "haas_ha5c")."""
    return Tf.MakeValidIdentifier(text)
