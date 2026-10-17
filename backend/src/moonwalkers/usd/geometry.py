"""Meshes for primitive parts, in metres (pure Python; decision 0010).

A part with ``geometry_format = "primitive"`` describes its shape in ``Part.primitive``. The
contract leaves that dictionary open; these are the shapes the exporter understands::

    {"shape": "box", "size_m": [0.2, 0.16, 0.16], "center_m": [0, 0, 0.08]}
    {"shape": "cylinder", "radius_m": 0.03, "length_m": 0.06, "axis": [1, 0, 0],
     "center_m": [0.13, 0, 0.1], "segments": 32}

Primitives become polygon meshes so they take the same path through the exporter as the meshes
that Pipeline B will produce in Phase 3. Faces do not share vertices, so they render with flat
shading, and every face is wound counter-clockwise seen from outside (USD's default right-handed
orientation).
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, PositiveFloat, TypeAdapter, model_validator

from .frames import Vec3, normalize, quat_between, rotate


@dataclass(frozen=True)
class MeshData:
    """A polygon mesh: points in metres and faces as vertex counts plus vertex indices."""

    points: tuple[Vec3, ...]
    face_vertex_counts: tuple[int, ...]
    face_vertex_indices: tuple[int, ...]

    def __post_init__(self) -> None:
        if not self.points or not self.face_vertex_counts:
            raise ValueError("a mesh needs at least one point and one face")
        if any(count < 3 for count in self.face_vertex_counts):
            raise ValueError("every face needs at least 3 vertices")
        if sum(self.face_vertex_counts) != len(self.face_vertex_indices):
            raise ValueError("face vertex counts do not add up to the number of face indices")
        if not all(0 <= i < len(self.points) for i in self.face_vertex_indices):
            raise ValueError("a face index points outside the point list")

    def extent(self) -> tuple[Vec3, Vec3]:
        """The axis-aligned bounds ``(min, max)`` of the points."""
        xs, ys, zs = zip(*self.points, strict=True)
        return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))

    def faces(self) -> list[tuple[int, ...]]:
        """Vertex indices of each face."""
        faces, start = [], 0
        for count in self.face_vertex_counts:
            faces.append(self.face_vertex_indices[start : start + count])
            start += count
        return faces


class _Primitive(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class BoxPrimitive(_Primitive):
    """An axis-aligned box; ``size_m`` is the full edge length along x, y and z."""

    shape: Literal["box"]
    size_m: tuple[PositiveFloat, PositiveFloat, PositiveFloat]
    center_m: Vec3 = (0.0, 0.0, 0.0)


class CylinderPrimitive(_Primitive):
    """A cylinder of ``radius_m`` and ``length_m`` around ``axis``, centred on ``center_m``."""

    shape: Literal["cylinder"]
    radius_m: PositiveFloat
    length_m: PositiveFloat
    axis: Vec3 = (0.0, 0.0, 1.0)
    center_m: Vec3 = (0.0, 0.0, 0.0)
    segments: int = Field(default=32, ge=3, le=256)

    @model_validator(mode="after")
    def _axis_has_length(self) -> CylinderPrimitive:
        normalize(self.axis)  # raises ValueError for a zero vector
        return self


Primitive = Annotated[BoxPrimitive | CylinderPrimitive, Field(discriminator="shape")]
_PRIMITIVE: TypeAdapter[BoxPrimitive | CylinderPrimitive] = TypeAdapter(Primitive)


def parse_primitive(spec: Mapping[str, Any]) -> BoxPrimitive | CylinderPrimitive:
    """Validate a ``Part.primitive`` dictionary. Raises ``pydantic.ValidationError``."""
    return _PRIMITIVE.validate_python(dict(spec))


def primitive_mesh(spec: Mapping[str, Any]) -> MeshData:
    """The mesh for a ``Part.primitive`` dictionary."""
    primitive = parse_primitive(spec)
    if isinstance(primitive, BoxPrimitive):
        return box_mesh(primitive)
    return cylinder_mesh(primitive)


# Corner signs of each box face, counter-clockwise seen from outside the box.
_BOX_FACES: tuple[tuple[tuple[int, int, int], ...], ...] = (
    ((1, -1, -1), (1, 1, -1), (1, 1, 1), (1, -1, 1)),  # +x
    ((-1, -1, -1), (-1, -1, 1), (-1, 1, 1), (-1, 1, -1)),  # -x
    ((-1, 1, -1), (-1, 1, 1), (1, 1, 1), (1, 1, -1)),  # +y
    ((-1, -1, -1), (1, -1, -1), (1, -1, 1), (-1, -1, 1)),  # -y
    ((-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)),  # +z
    ((-1, -1, -1), (-1, 1, -1), (1, 1, -1), (1, -1, -1)),  # -z
)


def box_mesh(box: BoxPrimitive) -> MeshData:
    hx, hy, hz = (s / 2.0 for s in box.size_m)
    cx, cy, cz = box.center_m
    points = tuple(
        (cx + sx * hx, cy + sy * hy, cz + sz * hz) for face in _BOX_FACES for sx, sy, sz in face
    )
    return MeshData(points, (4,) * 6, tuple(range(24)))


def cylinder_mesh(cylinder: CylinderPrimitive) -> MeshData:
    n, r, h = cylinder.segments, cylinder.radius_m, cylinder.length_m / 2.0
    angles = [2 * math.pi * i / n for i in range(n)]
    ring = [(r * math.cos(a), r * math.sin(a)) for a in angles]

    local: list[Vec3] = []
    counts: list[int] = []
    for i in range(n):  # side quads, one per segment
        (x0, y0), (x1, y1) = ring[i], ring[(i + 1) % n]
        local += [(x0, y0, -h), (x1, y1, -h), (x1, y1, h), (x0, y0, h)]
        counts.append(4)
    local += [(x, y, h) for x, y in ring]  # top cap, counter-clockwise seen from +z
    local += [(x, y, -h) for x, y in reversed(ring)]  # bottom cap, seen from -z
    counts += [n, n]

    q = quat_between((0.0, 0.0, 1.0), cylinder.axis)
    cx, cy, cz = cylinder.center_m
    points = tuple((cx + px, cy + py, cz + pz) for px, py, pz in (rotate(q, p) for p in local))
    return MeshData(points, tuple(counts), tuple(range(len(points))))
