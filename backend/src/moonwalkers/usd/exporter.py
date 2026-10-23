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

Several joints (decision 0017):

* Revolute and prismatic joints both turn their frame's X axis onto the contract axis. Prismatic
  limits and linear drive targets are in metres, the stage unit.
* Joints form one tree from the root part, so a chain of any length is one articulation.
* Parts that are not joined directly do not collide with each other (``PhysicsFilteredPairsAPI``):
  a machine's own parts are held by its joints and limits, and a convex hull can enclose a part
  that sits inside another (the spindle inside the head). Joined parts already do not collide (the
  joint's ``collisionEnabled`` fallback is false). A twin of two parts gets no filtered pairs.
* ``JointSettings`` gives one joint its own drive, limits (a lock or a depth stop), starting
  position or coupling to another joint (decisions 0018 and 0019). Joints without settings get
  ``drive`` (revolute) or a hold at 0 (prismatic), as before.
* Twins stay awake (decision 0017, Daniel, 2026-10-23): the articulation root gets PhysX's
  ``PhysxArticulationAPI`` with ``physxArticulation:sleepThreshold = 0``. Otherwise PhysX puts a
  slowly moving twin to sleep, and its drives stop. ``keep_awake=False`` writes nothing.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
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
from .physx_schemas import apply_mimic, define_rack_and_pinion, set_joint_state
from .physx_schemas import keep_awake as keep_articulation_awake
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
    """A joint drive: angular on a revolute joint, linear on a prismatic one.

    These are simulation tuning values chosen by us, not facts about a machine [INFERENCE]. The
    drive type "acceleration" makes the spring act on acceleration rather than force (UsdPhysics
    DriveAPI docs), so the response does not depend on the placeholder masses. Position mode holds
    ``target`` (rad, or m on a prismatic joint) with a critically damped spring: stiffness = w^2
    and damping = 2w for w = 10 rad/s. Velocity mode moves at ``target`` (rad/s or m/s) with zero
    stiffness, as Isaac Sim's GUI tutorial recommends for velocity control ("a high damping and
    zero stiffness"). With the "acceleration" type, stiffness and damping have the same meaning
    for both kinds (per second squared and per second).
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
        """Hold (or move to) a joint position: an angle, or a distance on a prismatic joint."""
        return cls(mode="position", target=angle_rad)

    @classmethod
    def spin(cls, speed_rad_s: float) -> DriveSettings:
        """Turn continuously at a joint speed."""
        return cls(mode="velocity", target=speed_rad_s, stiffness=0.0, damping=20.0)

    @classmethod
    def free(cls, damping: float) -> DriveSettings:
        """No spring: the joint moves freely within its limits, slowed by ``damping`` (a stand-in
        for friction, so a pushed part comes to rest)."""
        return cls(mode="velocity", target=0.0, stiffness=0.0, damping=damping)


@dataclass(frozen=True)
class JointCoupling:
    """The joint follows ``leader``: position = ``ratio`` * leader position + ``offset``, in the
    contract's units (rad per m for a turning joint that follows a sliding one; decision 0019).

    ``method`` "mimic" writes PhysX's ``PhysxMimicJointAPI``, a two-way hard constraint inside the
    articulation; it worked in Isaac Sim 6.2.0 on 2026-10-23 and is the one to use.
    "rack_and_pinion" writes a ``PhysxPhysicsRackAndPinionJoint`` kept out of the articulation; it
    ties the joints' speeds, so ``offset`` comes from their starting positions. Its first check
    failed, and its sign is being retried.
    """

    leader: str
    ratio: float
    offset: float = 0.0
    method: Literal["mimic", "rack_and_pinion"] = "mimic"


@dataclass(frozen=True)
class JointSettings:
    """How one joint is written, beyond what the contract says (decisions 0017-0019).

    ``drive`` is the joint's own drive, or None for no drive (a follower must have none: the
    coupling moves it). ``limits`` replace the contract's, in its units: equal limits lock the
    joint, and a depth stop narrows a slide. ``start`` is the position the joint starts at.
    ``note`` says why, for example that a value is a stand-in; it is written into the joint's
    provenance.
    """

    drive: DriveSettings | None
    limits: tuple[float, float] | None = None
    start: float | None = None
    coupling: JointCoupling | None = None
    note: str | None = None

    def __post_init__(self) -> None:
        if self.limits is not None and self.limits[0] > self.limits[1]:
            raise ValueError(f"lower limit {self.limits[0]} is above upper limit {self.limits[1]}")
        if self.coupling is not None and self.drive is not None:
            raise ValueError("a joint that follows another cannot have its own drive")


def export_twin(
    twin: TwinRecord,
    results: Sequence[PipelineResult],
    path: Path,
    drive: DriveSettings | None = None,
    data_dir: Path | None = None,
    *,
    joint_settings: Mapping[str, JointSettings] | None = None,
    keep_awake: bool = True,
) -> Path:
    """Write the twin to ``path``; returns the path.

    ``.usda`` gives text with LF line endings, readable for small twins. ``.usdc`` gives a binary
    crate file, which NVIDIA's asset validator asks for once arrays pass 64 elements, as a
    generated mesh's do (decision 0012). ``data_dir`` is the project ``data/`` folder; mesh-file
    parts are relative to it (contract). ``joint_settings`` maps joint ids to their settings, and
    ``keep_awake`` (the default) stops PhysX from putting the articulation to sleep (decision
    0017).
    """
    path = Path(path)
    if path.suffix not in (".usda", ".usdc"):
        raise ExportError(f"export writes .usda (text) or .usdc (binary) files, not {path.name}")
    # The stage owns its root layer: keep it.
    stage = build_stage(
        twin, results, drive, data_dir, joint_settings=joint_settings, keep_awake=keep_awake
    )
    return write_stage(stage, path)


def write_stage(stage: Usd.Stage, path: Path) -> Path:
    """Write a stage built by ``build_stage`` (and perhaps added to) to ``path``, atomically:
    ``.usda`` as text with LF line endings, ``.usdc`` as a binary crate file."""
    path = Path(path)
    if path.suffix not in (".usda", ".usdc"):
        raise ExportError(f"export writes .usda (text) or .usdc (binary) files, not {path.name}")
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
    *,
    joint_settings: Mapping[str, JointSettings] | None = None,
    keep_awake: bool = True,
) -> Usd.Stage:
    """Build the twin's stage in memory (see the module docstring for its layout)."""
    drive = drive or DriveSettings()
    settings = dict(joint_settings or {})
    _check_results_match(twin, results)
    parts = _collect(results, "parts", "part_id")
    joints = _collect(results, "joints", "joint_id")
    if not parts:
        raise ExportError(f"twin {twin.twin_id} has no parts to export")
    _check_prim_names(list(parts), reserved={JOINTS_SCOPE}, what="part")
    _check_prim_names(list(joints), reserved={WORLD_JOINT}, what="joint")
    root_part = _root_part(parts, joints)
    _check_settings(settings, joints)
    settings = _with_follower_starts(settings, joints)

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
        if keep_awake:
            keep_articulation_awake(root)
        scope = UsdGeom.Scope.Define(stage, root_path.AppendChild(JOINTS_SCOPE)).GetPath()
        anchor = UsdPhysics.FixedJoint.Define(stage, scope.AppendChild(WORLD_JOINT))
        anchor.CreateBody1Rel().SetTargets([body_paths[root_part]])
        anchor.GetPrim().SetDocumentation(
            f"Fixes the root part '{root_part}' to the world, making a fixed-base articulation."
        )
        joint_paths = {joint_id: scope.AppendChild(_identifier(joint_id)) for joint_id in joints}
        for joint_id, (joint, result_id) in joints.items():
            _write_joint(stage, scope, joint, result_id, body_paths, drive, settings.get(joint_id))
        for joint_id, joint_setting in settings.items():
            if joint_setting.coupling is not None:
                _write_coupling(stage, joints, joint_paths, body_paths, joint_id, joint_setting)
        _filter_unjoined_pairs(stage, body_paths, joints)

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


def _check_settings(
    settings: Mapping[str, JointSettings], joints: dict[str, tuple[Joint, str]]
) -> None:
    """Settings must name real joints, and fit their type; couplings must be ones PhysX takes."""
    for joint_id, setting in settings.items():
        if joint_id not in joints:
            raise ExportError(f"settings name joint '{joint_id}', which the twin does not have")
        joint = joints[joint_id][0]
        if joint.joint_type == "fixed":
            raise ExportError(f"joint '{joint_id}' is fixed, so it takes no settings")
        coupling = setting.coupling
        if coupling is None:
            continue
        if coupling.leader == joint_id or coupling.leader not in joints:
            raise ExportError(f"joint '{joint_id}' follows '{coupling.leader}', not another joint")
        leader = joints[coupling.leader][0]
        if leader.joint_type == "fixed":
            raise ExportError(
                f"joint '{joint_id}' cannot follow the fixed joint '{leader.joint_id}'"
            )
        if coupling.method == "mimic" and joint.joint_type == "revolute":
            limits = setting.limits or (joint.lower_limit, joint.upper_limit)
            if None in limits:
                # PhysxMimicJointAPI supports "PhysicsRevoluteJoint (with a limit set)".
                raise ExportError(f"joint '{joint_id}' follows by mimic, so it needs limits")
        if coupling.method == "rack_and_pinion" and (
            joint.joint_type != "revolute" or leader.joint_type != "prismatic"
        ):
            raise ExportError(
                f"joint '{joint_id}': a rack and pinion couples a revolute follower to a "
                "prismatic leader"
            )


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
    setting: JointSettings | None,
) -> None:
    path = scope.AppendChild(_identifier(joint.joint_id))
    if joint.joint_type == "revolute":
        usd_joint: UsdPhysics.Joint = UsdPhysics.RevoluteJoint.Define(stage, path)
    elif joint.joint_type == "prismatic":
        usd_joint = UsdPhysics.PrismaticJoint.Define(stage, path)
    else:
        usd_joint = UsdPhysics.FixedJoint.Define(stage, path)
    usd_joint.CreateBody0Rel().SetTargets([body_paths[joint.parent_part]])
    usd_joint.CreateBody1Rel().SetTargets([body_paths[joint.child_part]])

    # Parts sit at identity, so the joint frame is the same point in both bodies. The frame's X
    # axis is turned onto the contract's joint axis, and the joint rotates about, or slides
    # along, X.
    origin = Gf.Vec3f(*(usd_length(c) for c in joint.origin_m))
    w, x, y, z = quat_between((1.0, 0.0, 0.0), joint.axis)
    rotation = Gf.Quatf(w, Gf.Vec3f(x, y, z))
    usd_joint.CreateLocalPos0Attr(origin)
    usd_joint.CreateLocalPos1Attr(origin)
    usd_joint.CreateLocalRot0Attr(rotation)
    usd_joint.CreateLocalRot1Attr(rotation)

    prim = usd_joint.GetPrim()
    lower, upper = (
        setting.limits if setting and setting.limits else (joint.lower_limit, joint.upper_limit)
    )
    if joint.joint_type == "revolute":
        revolute = UsdPhysics.RevoluteJoint(prim)
        revolute.CreateAxisAttr(UsdPhysics.Tokens.x)
        if lower is not None:  # unlimited joints wrap on a 360 degree boundary
            revolute.CreateLowerLimitAttr(usd_angle(lower))
        if upper is not None:
            revolute.CreateUpperLimitAttr(usd_angle(upper))
    elif joint.joint_type == "prismatic":
        prismatic = UsdPhysics.PrismaticJoint(prim)
        prismatic.CreateAxisAttr(UsdPhysics.Tokens.x)
        if lower is not None:
            prismatic.CreateLowerLimitAttr(usd_length(lower))
        if upper is not None:
            prismatic.CreateUpperLimitAttr(usd_length(upper))
    joint_drive = _joint_drive(joint, drive, setting)
    if joint_drive is not None:
        _write_drive(prim, joint_drive, _drive_kind(joint))

    prim.SetDocumentation(
        f"{joint.joint_type.capitalize()} joint '{joint.joint_id}': "
        f"{joint.parent_part} (body0) -> {joint.child_part} (body1)."
    )
    length, speed = ("m", "m_s") if joint.joint_type == "prismatic" else ("rad", "rad_s")
    prim.SetCustomDataByKey(
        "moonwalkers",
        _clean(
            {
                "joint_id": joint.joint_id,
                "joint_type": joint.joint_type,
                "result_id": result_id,
                "axis": json.dumps(list(joint.axis)),
                "origin_m": json.dumps(list(joint.origin_m)),
                f"lower_limit_{length}": joint.lower_limit,
                f"upper_limit_{length}": joint.upper_limit,
                f"max_velocity_{speed}": joint.max_velocity,
                "confidence": joint.confidence,
                "citations": _citations(joint.citations),
            }
        ),
    )
    if setting is not None:
        if setting.start is not None:
            set_joint_state(prim, _drive_kind(joint), _to_usd(joint, setting.start))
        prim.SetCustomDataByKey("moonwalkers:export_settings", _describe_settings(setting))


def _joint_drive(
    joint: Joint, drive: DriveSettings, setting: JointSettings | None
) -> DriveSettings | None:
    """The joint's own drive if it has settings; otherwise ``drive`` on a revolute joint and a
    hold at 0 on a prismatic one. Fixed joints have none."""
    if joint.joint_type == "fixed":
        return None
    if setting is not None:
        return setting.drive
    return drive if joint.joint_type == "revolute" else DriveSettings.hold(0.0)


def _drive_kind(joint: Joint) -> Literal["angular", "linear"]:
    return "linear" if joint.joint_type == "prismatic" else "angular"


def _to_usd(joint: Joint, value: float) -> float:
    """A position or speed in contract units (rad, m) as USD writes it (degrees, stage units)."""
    return usd_length(value) if joint.joint_type == "prismatic" else usd_angle(value)


def _write_drive(prim: Usd.Prim, drive: DriveSettings, kind: Literal["angular", "linear"]) -> None:
    api = UsdPhysics.DriveAPI.Apply(prim, kind)
    convert = usd_angle if kind == "angular" else usd_length
    api.CreateTypeAttr(drive.drive_type)
    api.CreateStiffnessAttr(drive.stiffness)
    api.CreateDampingAttr(drive.damping)
    if drive.mode == "position":
        api.CreateTargetPositionAttr(convert(drive.target))
    else:
        api.CreateTargetVelocityAttr(convert(drive.target))


def _describe_settings(setting: JointSettings) -> dict[str, Any]:
    """The joint's export settings, in contract units, for its provenance."""
    drive = setting.drive
    coupling = setting.coupling
    return _clean(
        {
            "drive": "none"
            if drive is None
            else json.dumps(
                {
                    "mode": drive.mode,
                    "target": drive.target,
                    "stiffness": drive.stiffness,
                    "damping": drive.damping,
                    "type": drive.drive_type,
                }
            ),
            "limits": json.dumps(list(setting.limits)) if setting.limits else None,
            "start": setting.start,
            "coupling": json.dumps(
                {
                    "leader": coupling.leader,
                    "ratio": coupling.ratio,
                    "offset": coupling.offset,
                    "method": coupling.method,
                }
            )
            if coupling
            else None,
            "note": setting.note,
        }
    )


def _write_coupling(
    stage: Usd.Stage,
    joints: dict[str, tuple[Joint, str]],
    joint_paths: dict[str, Sdf.Path],
    body_paths: dict[str, Sdf.Path],
    follower_id: str,
    setting: JointSettings,
) -> None:
    """Tie the follower to its leader (decision 0019; ``physx_schemas``). Contract units become
    USD's: PhysX's mimic equation is "jointPosition + gearing * referenceJointPosition + offset =
    0", so gearing = -ratio and offset = -offset, scaled to degrees for angles.

    The rack and pinion's ratio takes the same sign as the mimic's gearing. PhysX says its speeds
    "may otherwise have opposite signs, depending on the orientations of the joint frames". With
    the opposite sign, the drill press's handles jammed at their limit in Isaac Sim on 2026-10-23
    [INFERENCE: one check; the sign is to be confirmed]."""
    coupling = setting.coupling
    assert coupling is not None
    follower, leader = joints[follower_id][0], joints[coupling.leader][0]
    per_follower_unit, per_leader_unit = _to_usd(follower, 1.0), _to_usd(leader, 1.0)
    if coupling.method == "mimic":
        apply_mimic(
            stage.GetPrimAtPath(joint_paths[follower_id]),
            "rotX",  # the follower's joint axis: frames turn X onto the contract axis
            joint_paths[coupling.leader],
            -coupling.ratio * per_follower_unit / per_leader_unit,
            -coupling.offset * per_follower_unit,
        )
        return
    path = (
        joint_paths[follower_id]
        .GetParentPath()
        .AppendChild(f"{_identifier(follower_id)}_rack_and_pinion")
    )
    if stage.GetPrimAtPath(path):
        raise ExportError(f"the rack-and-pinion joint's name {path.name} is taken by a joint")
    prim = define_rack_and_pinion(
        stage,
        path,
        pinion_body=body_paths[follower.child_part],
        rack_body=body_paths[leader.child_part],
        hinge=joint_paths[follower_id],
        prismatic=joint_paths[coupling.leader],
        ratio_deg_per_distance=-coupling.ratio * per_follower_unit / per_leader_unit,
    )
    prim.SetDocumentation(
        f"Rack and pinion: joint '{follower_id}' turns as '{coupling.leader}' slides (speeds only)."
    )
    prim.SetCustomDataByKey(
        "moonwalkers",
        {"couples": Vt.StringArray([follower_id, coupling.leader])},
    )


def _with_follower_starts(
    settings: dict[str, JointSettings], joints: dict[str, tuple[Joint, str]]
) -> dict[str, JointSettings]:
    """A follower without its own start begins where its coupling puts it, given its leader's."""
    updated = dict(settings)
    for joint_id, setting in settings.items():
        coupling = setting.coupling
        if coupling is None or setting.start is not None:
            continue
        leader_setting = settings.get(coupling.leader)
        if leader_setting is not None and leader_setting.start is not None:
            start = coupling.ratio * leader_setting.start + coupling.offset
            updated[joint_id] = replace(setting, start=start)
    return updated


def _filter_unjoined_pairs(
    stage: Usd.Stage, body_paths: dict[str, Sdf.Path], joints: dict[str, tuple[Joint, str]]
) -> None:
    """Parts that no joint connects directly do not collide (module docstring)."""
    joined = {frozenset((joint.parent_part, joint.child_part)) for joint, _ in joints.values()}
    part_ids = list(body_paths)
    for i, part_id in enumerate(part_ids):
        others = [
            body_paths[other]
            for other in part_ids[i + 1 :]
            if frozenset((part_id, other)) not in joined
        ]
        if others:
            body = stage.GetPrimAtPath(body_paths[part_id])
            UsdPhysics.FilteredPairsAPI.Apply(body).CreateFilteredPairsRel().SetTargets(others)


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
