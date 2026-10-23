"""PhysX schemas that usd-core does not define, written by name (decision 0019).

usd-core 26.8 has UsdPhysics but none of NVIDIA's PhysX schemas: ``import pxr.PhysxSchema`` fails.
Isaac Sim 6.2.0 reads them from its own schema plugin. The names, types and variability here are
copied from that plugin's ``PhysxSchema/resources/generatedSchema.usda`` (omni.usd.schema.physx
110.4.4; docs/research/2026-10-22-sliding-joints-locks-and-coupling.md). Each helper adds the schema
token to the prim's ``apiSchemas`` (or sets its type) and authors the attributes by name, so the
values resolve as the schema's own once Isaac Sim registers it.
"""

from __future__ import annotations

from pxr import Sdf, Usd

MIMIC_API = "PhysxMimicJointAPI"
MIMIC_AXES = ("rotX", "rotY", "rotZ")  # "The allowed instance name tokens" (schema doc)
RACK_AND_PINION_TYPE = "PhysxPhysicsRackAndPinionJoint"
JOINT_STATE_API = "PhysicsJointStateAPI"
JOINT_STATE_AXES = ("angular", "linear")  # revolute and prismatic joints (schema doc)


def apply_mimic(
    prim: Usd.Prim, axis: str, reference_joint: Sdf.Path, gearing: float, offset: float
) -> None:
    """Make the joint ``prim`` follow ``reference_joint``. PhysX enforces
    ``jointPosition + gearing * referenceJointPosition + offset = 0`` in USD units (degrees for
    angles, stage distance for slides), as a hard constraint (compliance left at 0)."""
    if axis not in MIMIC_AXES:
        raise ValueError(f"a mimic joint's axis must be one of {MIMIC_AXES}, not {axis!r}")
    prim.AddAppliedSchema(f"{MIMIC_API}:{axis}")
    prefix = f"physxMimicJoint:{axis}:"
    prim.CreateRelationship(prefix + "referenceJoint", custom=False).SetTargets([reference_joint])
    _float(prim, prefix + "gearing", gearing)
    _float(prim, prefix + "offset", offset)


def applied_schemas(prim: Usd.Prim) -> list[str]:
    """Every applied schema token on ``prim``, including ones usd-core does not define.
    ``Usd.Prim.GetAppliedSchemas`` leaves those out."""
    return list(prim.GetPrimTypeInfo().GetAppliedAPISchemas())


def mimic_axes(prim: Usd.Prim) -> list[str]:
    """The axes of every ``PhysxMimicJointAPI`` instance applied to ``prim``."""
    prefix = f"{MIMIC_API}:"
    return [t.removeprefix(prefix) for t in applied_schemas(prim) if t.startswith(prefix)]


def define_rack_and_pinion(
    stage: Usd.Stage,
    path: Sdf.Path,
    pinion_body: Sdf.Path,
    rack_body: Sdf.Path,
    hinge: Sdf.Path,
    prismatic: Sdf.Path,
    ratio_deg_per_distance: float,
) -> Usd.Prim:
    """A rack-and-pinion joint between a revolute joint (``hinge``) and a prismatic one. PhysX
    enforces "abs(omega) = abs(V) * R" on their speeds. Its joints are articulation joints, so it
    is kept out of the articulation, as the schema requires."""
    prim = stage.DefinePrim(path, RACK_AND_PINION_TYPE)
    for name, target in (
        ("physics:body0", pinion_body),
        ("physics:body1", rack_body),
        ("physics:hinge", hinge),
        ("physics:prismatic", prismatic),
    ):
        prim.CreateRelationship(name, custom=False).SetTargets([target])
    _float(prim, "physics:ratio", ratio_deg_per_distance)
    prim.CreateAttribute(
        "physics:excludeFromArticulation",
        Sdf.ValueTypeNames.Bool,
        custom=False,
        variability=Sdf.VariabilityUniform,
    ).Set(True)
    return prim


def set_joint_state(prim: Usd.Prim, axis: str, position: float) -> None:
    """Start the articulation joint ``prim`` at ``position`` (degrees for "angular", stage distance
    for "linear") and at rest. PhysX moves the links there on the first simulation step."""
    if axis not in JOINT_STATE_AXES:
        raise ValueError(f"a joint state's axis must be one of {JOINT_STATE_AXES}, not {axis!r}")
    prim.AddAppliedSchema(f"{JOINT_STATE_API}:{axis}")
    _float(prim, f"state:{axis}:physics:position", position)
    _float(prim, f"state:{axis}:physics:velocity", 0.0)


def _float(prim: Usd.Prim, name: str, value: float) -> None:
    prim.CreateAttribute(name, Sdf.ValueTypeNames.Float, custom=False).Set(float(value))
