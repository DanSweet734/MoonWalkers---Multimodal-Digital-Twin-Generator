"""Turn a generated mesh into the twin's parts: orient, split the spindle off, scale (dec. 0012).

The decisions come from a ``GeometrySpec``, written by whoever inspected the mesh (the agent or a
person) and cited as a source in the twin. Output meshes are in the twin frame, in metres: +Z up,
front facing +X, the origin on the base plane directly under the spindle axis at the body's front
face, so the spindle axis is the line y = 0, z = centre height.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, PositiveFloat

from .mesh_tools import load_mesh, orientation_matrix, split_by_cylinder, transformed

AxisName = Literal["+x", "-x", "+y", "-y", "+z", "-z"]
Vec3 = tuple[float, float, float]


class GeometrySpec(BaseModel):
    """Inspection decisions for one generated mesh. Lengths are in the generator's model units,
    measured in the twin frame (after ``up`` and ``front`` are applied)."""

    model_config = ConfigDict(extra="forbid")

    up: AxisName  # the generator axis that points up
    front: AxisName  # the generator axis the spindle nose faces
    spindle_axis_yz: tuple[float, float]  # where the spindle axis crosses the y-z plane
    spindle_radius: PositiveFloat  # faces within this distance of the axis ...
    spindle_start_x: float  # ... and in front of this plane form the spindle; the joint sits here
    base_z: float | None = None  # the base plane; default: the mesh's lowest point
    # Where the machine's front points after up and front, from +X towards +Y; the mesh is turned
    # back by it, so photos that put the front between two axes (corners) can be squared (0022).
    yaw_deg: float = Field(default=0.0, ge=-180.0, le=180.0)
    center_height_m: PositiveFloat  # known spindle-axis height above the base (scale reference)
    decided_by: str
    method: str


@dataclass(frozen=True)
class AssembledParts:
    body_path: Path
    spindle_path: Path
    scale_factor: float  # metres per model unit
    center_height_model: float  # the measured centre height, model units
    body_bounds_m: tuple[Vec3, Vec3]
    spindle_bounds_m: tuple[Vec3, Vec3]
    overall_extents_m: Vec3  # depth (x), width (y), height (z)
    joint_origin_m: Vec3
    body_faces: int
    spindle_faces: int


def assemble(raw_mesh: Path, spec: GeometrySpec, out_dir: Path) -> AssembledParts:
    """Write ``body.glb`` and ``spindle.glb`` (twin frame, metres) into ``out_dir``."""
    mesh = transformed(load_mesh(raw_mesh), orientation_matrix(spec.up, spec.front, spec.yaw_deg))
    base_z = spec.base_z if spec.base_z is not None else float(mesh.bounds[0][2])
    axis_y, axis_z = spec.spindle_axis_yz
    height_model = axis_z - base_z
    if height_model <= 0:
        raise ValueError("the spindle axis must be above the base plane")
    scale = spec.center_height_m / height_model

    body, spindle = split_by_cylinder(
        mesh, (spec.spindle_start_x, axis_y, axis_z), (1.0, 0.0, 0.0), spec.spindle_radius, 0.0
    )
    placement = np.diag([scale, scale, scale, 1.0]) @ _translation(
        -spec.spindle_start_x, -axis_y, -base_z
    )
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, part in (("body", body), ("spindle", spindle)):
        part.apply_transform(placement)
        # Name the part instead of keeping the generator's metadata, which holds a temporary file
        # name; then the same geometry always gives the same file.
        part.metadata = {"name": name}
        paths.append(out_dir / f"{name}.glb")
        part.export(paths[-1])

    lo = np.minimum(body.bounds[0], spindle.bounds[0])
    hi = np.maximum(body.bounds[1], spindle.bounds[1])
    return AssembledParts(
        body_path=paths[0],
        spindle_path=paths[1],
        scale_factor=float(scale),
        center_height_model=float(height_model),
        body_bounds_m=(_vec(body.bounds[0]), _vec(body.bounds[1])),
        spindle_bounds_m=(_vec(spindle.bounds[0]), _vec(spindle.bounds[1])),
        overall_extents_m=_vec(hi - lo),
        joint_origin_m=(0.0, 0.0, float(spec.center_height_m)),
        body_faces=len(body.faces),
        spindle_faces=len(spindle.faces),
    )


def _translation(x: float, y: float, z: float) -> np.ndarray:
    matrix = np.eye(4)
    matrix[:3, 3] = (x, y, z)
    return matrix


def _vec(values: np.ndarray) -> Vec3:
    return (float(values[0]), float(values[1]), float(values[2]))
