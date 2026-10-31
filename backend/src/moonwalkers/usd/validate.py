"""Check an exported twin with pxr before anyone opens it in Isaac Sim (decision 0010).

Run from ``backend/``::

    uv run python -m moonwalkers.usd.validate path/to/twin.usda   (or .usdc)

The physics checks use OpenUSD's own UsdPhysics parser (``UsdPhysicsLoadStageFromPrimRange``), which
reads the stage the way a physics engine would. Findings use the contract's ``Issue`` model; the
command exits with status 1 if there is any error.
"""

from __future__ import annotations

import argparse
import math
import sys
from collections.abc import Sequence
from pathlib import Path

from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics

from moonwalkers.contracts.pipeline_result import Issue

from .exporter import WORLD_JOINT
from .physx_schemas import JOINT_STATE_API, RACK_AND_PINION_TYPE, applied_schemas, mimic_axes
from .units import KILOGRAMS_PER_UNIT, METERS_PER_UNIT

POSITION_TOLERANCE = 1e-5  # stage units (metres)
ANGLE_TOLERANCE_DEG = 1e-3

JOINT_TYPES = (
    UsdPhysics.ObjectType.RevoluteJoint,
    UsdPhysics.ObjectType.PrismaticJoint,
    UsdPhysics.ObjectType.FixedJoint,
    UsdPhysics.ObjectType.SphericalJoint,
    UsdPhysics.ObjectType.DistanceJoint,
    UsdPhysics.ObjectType.D6Joint,
    UsdPhysics.ObjectType.CustomJoint,
)
MOVING_JOINT_TYPES = {
    UsdPhysics.ObjectType.RevoluteJoint: "revolute",
    UsdPhysics.ObjectType.PrismaticJoint: "prismatic",
}
# Triangle meshes suit "objects that are either static or kinematic" (NVIDIA Omni Physics docs).
NON_CONVEX_APPROXIMATIONS = {"none", "meshSimplification"}

_SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


def validate_file(path: Path) -> list[Issue]:
    """Open ``path`` and validate it; an unreadable file is reported as an error."""
    try:
        stage = Usd.Stage.Open(str(path))
    except Exception as exc:  # noqa: BLE001 - pxr raises Tf.ErrorException
        return [Issue(severity="error", message=f"cannot open stage: {exc}", ref=str(path))]
    if stage is None:
        return [Issue(severity="error", message="cannot open stage", ref=str(path))]
    return validate_stage(stage)


def validate_stage(stage: Usd.Stage) -> list[Issue]:
    """Every problem found in ``stage``, errors first."""
    issues: list[Issue] = []
    _check_stage_metadata(stage, issues)
    root = stage.GetDefaultPrim()
    if not root:
        issues.append(Issue(severity="error", message="the stage has no default prim"))
        return issues
    parsed = UsdPhysics.UsdPhysicsLoadStageFromPrimRange(stage, [Sdf.Path.absoluteRootPath])
    _check_joint_relationships(stage, root, parsed, issues)
    _check_physics(stage, parsed, issues)
    _check_meshes(root, issues)
    _check_provenance(root, issues)
    return sorted(issues, key=lambda i: (_SEVERITY_ORDER[i.severity], i.ref or ""))


# ------------------------------------------------------------------------------ stage metadata
def _check_stage_metadata(stage: Usd.Stage, issues: list[Issue]) -> None:
    if UsdGeom.GetStageUpAxis(stage) != UsdGeom.Tokens.z:
        issues.append(Issue(severity="error", message="upAxis must be Z (Isaac Sim's world up)"))
    if not UsdGeom.StageHasAuthoredMetersPerUnit(stage):
        issues.append(Issue(severity="error", message="metersPerUnit is not authored"))
    elif not math.isclose(UsdGeom.GetStageMetersPerUnit(stage), METERS_PER_UNIT):
        issues.append(
            Issue(
                severity="error",
                message=f"metersPerUnit is {UsdGeom.GetStageMetersPerUnit(stage)}, expected 1",
            )
        )
    if not UsdPhysics.StageHasAuthoredKilogramsPerUnit(stage):
        issues.append(Issue(severity="error", message="kilogramsPerUnit is not authored"))
    elif not math.isclose(UsdPhysics.GetStageKilogramsPerUnit(stage), KILOGRAMS_PER_UNIT):
        issues.append(
            Issue(
                severity="error",
                message=f"kilogramsPerUnit is {UsdPhysics.GetStageKilogramsPerUnit(stage)}",
            )
        )
    if not stage.HasAuthoredTimeCodeRange() or (stage.GetEndTimeCode() <= stage.GetStartTimeCode()):
        issues.append(
            Issue(
                severity="warning",
                message="no usable time-code range: Isaac Sim's timeline would loop over a single "
                "frame (author distinct startTimeCode and endTimeCode)",
            )
        )


# ------------------------------------------------------------------------------------- physics
def _check_joint_relationships(
    stage: Usd.Stage, root: Usd.Prim, parsed: dict, issues: list[Issue]
) -> None:
    """Check joint prims directly: the physics parser silently drops a joint whose body is missing
    and re-points one whose body is not a rigid body, so its output alone can hide both mistakes.
    """
    parsed_joints = {p for t in JOINT_TYPES for p in parsed.get(t, ([], []))[0]}
    for prim in Usd.PrimRange(root):
        if not prim.IsA(UsdPhysics.Joint):
            continue
        joint, ref = UsdPhysics.Joint(prim), str(prim.GetPath())
        targets = {
            "body0": joint.GetBody0Rel().GetTargets(),
            "body1": joint.GetBody1Rel().GetTargets(),
        }
        if not any(targets.values()):
            issues.append(Issue(severity="error", message="joint connects no bodies", ref=ref))
        for label, paths in targets.items():
            if len(paths) > 1:
                issues.append(
                    Issue(severity="error", message=f"{label} has several targets", ref=ref)
                )
            for path in paths:
                body = stage.GetPrimAtPath(path)
                if not body:
                    issues.append(
                        Issue(
                            severity="error",
                            message=f"{label} points to a missing prim {path}",
                            ref=ref,
                        )
                    )
                elif not body.HasAPI(UsdPhysics.RigidBodyAPI):
                    issues.append(
                        Issue(
                            severity="error", message=f"{label} {path} is not a rigid body", ref=ref
                        )
                    )
        if prim.GetPath() not in parsed_joints:
            issues.append(
                Issue(severity="error", message="the physics parser skipped this joint", ref=ref)
            )


def _check_physics(stage: Usd.Stage, parsed: dict, issues: list[Issue]) -> None:
    def descs(object_type: UsdPhysics.ObjectType) -> list[tuple[Sdf.Path, object]]:
        paths, values = parsed.get(object_type, ([], []))
        return list(zip(paths, values, strict=True))

    if not descs(UsdPhysics.ObjectType.Scene):
        issues.append(Issue(severity="warning", message="no PhysicsScene in the stage"))

    bodies = dict(descs(UsdPhysics.ObjectType.RigidBody))
    joints = [(p, d) for t in JOINT_TYPES for p, d in descs(t)]
    articulations = descs(UsdPhysics.ObjectType.Articulation)
    xforms = UsdGeom.XformCache()
    followers, links = _check_couplings(stage, dict(joints), issues)
    driven = {p for p, j in joints if j.type in MOVING_JOINT_TYPES and j.drive.enabled}
    _check_joint_states(stage, dict(joints), issues)

    for path, joint in joints:
        ends = [joint.body0, joint.body1]
        if all(e.isEmpty for e in ends):
            issues.append(
                Issue(severity="error", message="joint connects no bodies", ref=str(path))
            )
            continue
        if ends[0] == ends[1]:
            issues.append(
                Issue(severity="error", message="joint connects a body to itself", ref=str(path))
            )
        for label, end in zip(("body0", "body1"), ends, strict=True):
            if not end.isEmpty and end not in bodies:
                issues.append(
                    Issue(
                        severity="error",
                        message=f"{label} {end} is not a rigid body",
                        ref=str(path),
                    )
                )
        if joint.type in MOVING_JOINT_TYPES:
            kind = MOVING_JOINT_TYPES[joint.type]
            locked = joint.limit.enabled and joint.limit.lower == joint.limit.upper
            moved_by_link = path in followers or bool(links.get(path, set()) & driven)
            if not joint.drive.enabled and not moved_by_link and not locked:
                issues.append(
                    Issue(severity="warning", message=f"{kind} joint has no drive", ref=str(path))
                )
            if joint.limit.enabled and joint.limit.lower > joint.limit.upper:
                issues.append(
                    Issue(
                        severity="error",
                        message="joint lower limit is not below the upper limit",
                        ref=str(path),
                    )
                )
            elif locked:
                issues.append(
                    Issue(severity="info", message="joint is locked by equal limits", ref=str(path))
                )
        if not any(e.isEmpty for e in ends) and all(e in bodies for e in ends):
            _check_joint_frames(stage, xforms, path, joint, issues)

    connected = [p for p, j in joints if not j.body0.isEmpty and not j.body1.isEmpty]
    if connected and len(articulations) != 1:
        issues.append(
            Issue(
                severity="error",
                message=f"expected one articulation, found {len(articulations)}",
            )
        )
    for path, articulation in articulations:
        roots = list(articulation.rootPrims)
        fixed_to_world = [
            r
            for r in roots
            if any(
                p == r and j.type == UsdPhysics.ObjectType.FixedJoint and j.body0.isEmpty
                for p, j in joints
            )
        ]
        if not fixed_to_world:
            issues.append(
                Issue(
                    severity="warning",
                    message="articulation is floating (no fixed joint to the world)",
                    ref=str(path),
                )
            )
        articulated = set(articulation.articulatedBodies)
        for body in bodies:
            if body not in articulated:
                issues.append(
                    Issue(
                        severity="warning",
                        message="rigid body is not in the articulation",
                        ref=str(body),
                    )
                )

    for path, body in bodies.items():
        if not list(body.collisions):
            issues.append(
                Issue(
                    severity="warning",
                    message="rigid body has no collider, so its mass falls back to 1.0",
                    ref=str(path),
                )
            )
    for path, mesh in descs(UsdPhysics.ObjectType.MeshShape):
        if not mesh.rigidBody.isEmpty and str(mesh.approximation) in NON_CONVEX_APPROXIMATIONS:
            issues.append(
                Issue(
                    severity="error",
                    message=f"moving body uses collision approximation '{mesh.approximation}'; "
                    "use a convex one",
                    ref=str(path),
                )
            )


def _check_couplings(
    stage: Usd.Stage, joints: dict, issues: list[Issue]
) -> tuple[set[Sdf.Path], dict[Sdf.Path, set[Sdf.Path]]]:
    """PhysX couplings, which usd-core's parser does not read (decision 0019). Returns the
    joints that follow another, since those need no drive of their own, and each leader's
    followers: a leader whose follower carries its spring needs none either (decision 0025)."""
    followers: set[Sdf.Path] = set()
    links: dict[Sdf.Path, set[Sdf.Path]] = {}
    for prim in stage.Traverse():
        path, ref = prim.GetPath(), str(prim.GetPath())
        for axis in mimic_axes(prim):
            followers.add(path)
            rel = prim.GetRelationship(f"physxMimicJoint:{axis}:referenceJoint")
            targets = rel.GetTargets() if rel else []
            follower = joints.get(path)
            if follower is None:
                issues.append(Issue(severity="error", message="mimic API on a non-joint", ref=ref))
                continue
            if len(targets) != 1 or targets[0] not in joints or targets[0] == path:
                issues.append(
                    Issue(
                        severity="error", message="mimic joint must follow one other joint", ref=ref
                    )
                )
                continue
            links.setdefault(targets[0], set()).add(path)
            if follower.type == UsdPhysics.ObjectType.RevoluteJoint and not follower.limit.enabled:
                issues.append(
                    Issue(
                        severity="error",
                        message="a turning mimic joint needs limits (PhysX supports "
                        '"PhysicsRevoluteJoint (with a limit set)")',
                        ref=ref,
                    )
                )
            if joints[targets[0]].type != follower.type:
                issues.append(
                    Issue(
                        severity="info",
                        message="PhysxMimicJointAPI couples a turning joint and a sliding "
                        "one. It is deprecated in Isaac Sim 6.2, but NewtonMimicAPI cannot do "
                        "this: do not accept the Newton migration for this joint",
                        ref=ref,
                    )
                )
        if prim.GetTypeName() == RACK_AND_PINION_TYPE:
            hinge = prim.GetRelationship("physics:hinge").GetTargets()
            slide = prim.GetRelationship("physics:prismatic").GetTargets()
            if len(hinge) != 1 or _joint_type(joints, hinge[0]) != "revolute":
                issues.append(
                    Issue(severity="error", message="rack and pinion needs one hinge", ref=ref)
                )
            else:
                followers.add(hinge[0])
                if len(slide) == 1:
                    links.setdefault(slide[0], set()).add(hinge[0])
            if len(slide) != 1 or _joint_type(joints, slide[0]) != "prismatic":
                issues.append(
                    Issue(severity="error", message="rack and pinion needs one slide", ref=ref)
                )
            exclude = prim.GetAttribute("physics:excludeFromArticulation")
            if not (exclude and exclude.Get()):
                # "excludeFromArticulation must be set to true ... otherwise an error occurs."
                issues.append(
                    Issue(
                        severity="error",
                        message="rack and pinion between articulation joints must be excluded "
                        "from the articulation",
                        ref=ref,
                    )
                )
    return followers, links


def _joint_type(joints: dict, path: Sdf.Path) -> str | None:
    joint = joints.get(path)
    return None if joint is None else MOVING_JOINT_TYPES.get(joint.type)


def _check_joint_states(stage: Usd.Stage, joints: dict, issues: list[Issue]) -> None:
    """Starting positions (``PhysicsJointStateAPI``) must suit their joint and lie within its
    limits, or PhysX would start the joint somewhere it cannot be."""
    expected = {"revolute": "angular", "prismatic": "linear"}
    for prim in stage.Traverse():
        for token in applied_schemas(prim):
            if not token.startswith(f"{JOINT_STATE_API}:"):
                continue
            axis, ref = token.removeprefix(f"{JOINT_STATE_API}:"), str(prim.GetPath())
            kind = _joint_type(joints, prim.GetPath())
            if kind is None or expected[kind] != axis:
                issues.append(
                    Issue(
                        severity="error",
                        message=f"joint state '{axis}' does not suit this joint",
                        ref=ref,
                    )
                )
                continue
            attr = prim.GetAttribute(f"state:{axis}:physics:position")
            position = attr.Get() if attr else None
            limit = joints[prim.GetPath()].limit
            tolerance = ANGLE_TOLERANCE_DEG if axis == "angular" else POSITION_TOLERANCE
            if (
                position is not None
                and limit.enabled
                and not (limit.lower - tolerance <= position <= limit.upper + tolerance)
            ):
                issues.append(
                    Issue(
                        severity="warning",
                        message=f"starting position {position:g} is outside the joint's limits",
                        ref=ref,
                    )
                )


def _check_joint_frames(
    stage: Usd.Stage, xforms: UsdGeom.XformCache, path: Sdf.Path, joint: object, issues: list[Issue]
) -> None:
    """Both joint frames must be the same place and orientation in world space."""
    frames = []
    for body, position, orientation in (
        (joint.body0, joint.localPose0Position, joint.localPose0Orientation),
        (joint.body1, joint.localPose1Position, joint.localPose1Orientation),
    ):
        world = xforms.GetLocalToWorldTransform(stage.GetPrimAtPath(body))
        point = world.Transform(Gf.Vec3d(position))
        body_rotation = world.RemoveScaleShear().ExtractRotationQuat()
        frames.append((point, body_rotation * Gf.Quatd(orientation)))
    (p0, q0), (p1, q1) = frames
    if (p0 - p1).GetLength() > POSITION_TOLERANCE:
        issues.append(
            Issue(
                severity="error",
                message=f"joint frames are {(p0 - p1).GetLength():.6f} m apart in world space",
                ref=str(path),
            )
        )
    angle = Gf.Rotation(q0 * q1.GetInverse()).GetAngle()
    if min(angle, 360.0 - angle) > ANGLE_TOLERANCE_DEG:
        issues.append(
            Issue(
                severity="error",
                message=f"joint frames differ by {angle:.4f} degrees in world space",
                ref=str(path),
            )
        )


# -------------------------------------------------------------------------------------- meshes
def _check_meshes(root: Usd.Prim, issues: list[Issue]) -> None:
    for prim in Usd.PrimRange(root):
        if not prim.IsA(UsdGeom.Mesh):
            continue
        mesh, ref = UsdGeom.Mesh(prim), str(prim.GetPath())
        points = mesh.GetPointsAttr().Get() or []
        counts = mesh.GetFaceVertexCountsAttr().Get() or []
        indices = mesh.GetFaceVertexIndicesAttr().Get() or []
        if not points or not counts:
            issues.append(Issue(severity="error", message="mesh has no points or faces", ref=ref))
            continue
        if sum(counts) != len(indices) or any(i < 0 or i >= len(points) for i in indices):
            issues.append(Issue(severity="error", message="mesh topology is inconsistent", ref=ref))
        extent = mesh.GetExtentAttr().Get()
        computed = UsdGeom.Mesh.ComputeExtent(points)
        if not extent or any(
            not Gf.IsClose(extent[i], computed[i], POSITION_TOLERANCE) for i in range(2)
        ):
            issues.append(
                Issue(severity="warning", message="mesh extent is missing or stale", ref=ref)
            )
        if mesh.GetSubdivisionSchemeAttr().Get() != UsdGeom.Tokens.none:
            issues.append(
                Issue(severity="warning", message="mesh is a subdivision surface", ref=ref)
            )


# ---------------------------------------------------------------------------------- provenance
def _check_provenance(root: Usd.Prim, issues: list[Issue]) -> None:
    """Twins carry their own provenance (docs/methodology.md)."""
    twin = root.GetCustomDataByKey("moonwalkers:twin") or {}
    if not twin.get("twin_id"):
        issues.append(
            Issue(severity="error", message="root has no twin provenance", ref=str(root.GetPath()))
        )
    for prim in Usd.PrimRange(root):
        data = prim.GetCustomDataByKey("moonwalkers") or {}
        ref = str(prim.GetPath())
        if prim.HasAPI(UsdPhysics.RigidBodyAPI) or (
            prim.GetParent() == root and prim.IsA(UsdGeom.Xform)
        ):
            if not data.get("part_id"):
                issues.append(Issue(severity="error", message="part has no provenance", ref=ref))
            elif not list(data.get("citations", [])):
                issues.append(Issue(severity="warning", message="part cites no source", ref=ref))
        if prim.IsA(UsdPhysics.Joint) and prim.GetName() != WORLD_JOINT:
            if not data.get("joint_id"):
                issues.append(Issue(severity="error", message="joint has no provenance", ref=ref))
            elif not list(data.get("citations", [])):
                issues.append(Issue(severity="error", message="joint cites no source", ref=ref))


# ----------------------------------------------------------------------------------------- CLI
def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate an exported MoonWalkers twin.")
    parser.add_argument("path", type=Path, help="the .usda or .usdc file to check")
    args = parser.parse_args(argv)
    issues = validate_file(args.path)
    for issue in issues:
        print(f"{issue.severity:7} {issue.ref or '-'}: {issue.message}")
    errors = sum(i.severity == "error" for i in issues)
    warnings = sum(i.severity == "warning" for i in issues)
    print(f"{args.path}: {errors} error(s), {warnings} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
