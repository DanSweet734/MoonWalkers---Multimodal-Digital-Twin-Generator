"""Meshes for primitive parts, in metres (pure Python; decision 0010).

A part with ``geometry_format = "primitive"`` describes its shape in ``Part.primitive``. The
contract leaves that dictionary open; these are the shapes the exporter understands::

    {"shape": "box", "size_m": [0.2, 0.16, 0.16], "center_m": [0, 0, 0.08]}
    {"shape": "cylinder", "radius_m": 0.03, "length_m": 0.06, "axis": [1, 0, 0],
     "center_m": [0.13, 0, 0.1], "segments": 32}
    {"shape": "compound", "pieces": [{"shape": "box", ...}, {"shape": "cylinder", ...}]}

A compound is several boxes and cylinders that move as one rigid part, such as the drill press's
hub with its three handles (docs/drill-press-plan.md, Phase 1).

Primitives become polygon meshes so they take the same path through the exporter as the meshes
that Pipeline B will produce in Phase 3. Faces share their corner points (a closed, welded mesh),
every face is wound counter-clockwise seen from outside (USD's default right-handed orientation),
and ``face_normals`` gives the flat normal of each face for rendering. A compound's mesh is its
pieces' closed meshes side by side.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
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

    def face_normals(self) -> list[Vec3]:
        """The unit normal of each face (Newell's method), following the right-hand rule."""
        normals = []
        for face in self.faces():
            nx = ny = nz = 0.0
            for i, j in zip(face, face[1:] + face[:1], strict=True):
                (x0, y0, z0), (x1, y1, z1) = self.points[i], self.points[j]
                nx += (y0 - y1) * (z0 + z1)
                ny += (z0 - z1) * (x0 + x1)
                nz += (x0 - x1) * (y0 + y1)
            normals.append(normalize((nx, ny, nz)))
        return normals


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


Piece = Annotated[BoxPrimitive | CylinderPrimitive, Field(discriminator="shape")]


class CompoundPrimitive(_Primitive):
    """Several boxes and cylinders that move as one rigid part."""

    shape: Literal["compound"]
    pieces: tuple[Piece, ...] = Field(min_length=1)


AnyPrimitive = BoxPrimitive | CylinderPrimitive | CompoundPrimitive
Primitive = Annotated[AnyPrimitive, Field(discriminator="shape")]
_PRIMITIVE: TypeAdapter[AnyPrimitive] = TypeAdapter(Primitive)


def parse_primitive(spec: Mapping[str, Any]) -> AnyPrimitive:
    """Validate a ``Part.primitive`` dictionary. Raises ``pydantic.ValidationError``."""
    return _PRIMITIVE.validate_python(dict(spec))


def primitive_mesh(spec: Mapping[str, Any]) -> MeshData:
    """The mesh for a ``Part.primitive`` dictionary."""
    primitive = parse_primitive(spec)
    if isinstance(primitive, CompoundPrimitive):
        return merge_meshes([_piece_mesh(piece) for piece in primitive.pieces])
    return _piece_mesh(primitive)


def _piece_mesh(piece: BoxPrimitive | CylinderPrimitive) -> MeshData:
    return box_mesh(piece) if isinstance(piece, BoxPrimitive) else cylinder_mesh(piece)


def merge_meshes(meshes: Sequence[MeshData]) -> MeshData:
    """One mesh holding every face of ``meshes``, each piece's points and faces kept as they are."""
    points: list[Vec3] = []
    counts: list[int] = []
    indices: list[int] = []
    for mesh in meshes:
        offset = len(points)
        points += mesh.points
        counts += mesh.face_vertex_counts
        indices += [i + offset for i in mesh.face_vertex_indices]
    return MeshData(tuple(points), tuple(counts), tuple(indices))


# Corner signs of each box face, counter-clockwise seen from outside the box.
_BOX_FACES: tuple[tuple[tuple[int, int, int], ...], ...] = (
    ((1, -1, -1), (1, 1, -1), (1, 1, 1), (1, -1, 1)),  # +x
    ((-1, -1, -1), (-1, -1, 1), (-1, 1, 1), (-1, 1, -1)),  # -x
    ((-1, 1, -1), (-1, 1, 1), (1, 1, 1), (1, 1, -1)),  # +y
    ((-1, -1, -1), (1, -1, -1), (1, -1, 1), (-1, -1, 1)),  # -y
    ((-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)),  # +z
    ((-1, -1, -1), (-1, 1, -1), (1, 1, -1), (1, -1, -1)),  # -z
)


_BOX_CORNERS = tuple((sx, sy, sz) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1))


def box_mesh(box: BoxPrimitive) -> MeshData:
    hx, hy, hz = (s / 2.0 for s in box.size_m)
    cx, cy, cz = box.center_m
    points = tuple((cx + sx * hx, cy + sy * hy, cz + sz * hz) for sx, sy, sz in _BOX_CORNERS)
    indices = tuple(_BOX_CORNERS.index(corner) for face in _BOX_FACES for corner in face)
    return MeshData(points, (4,) * 6, indices)


def cylinder_mesh(cylinder: CylinderPrimitive) -> MeshData:
    n, r, h = cylinder.segments, cylinder.radius_m, cylinder.length_m / 2.0
    angles = [2 * math.pi * i / n for i in range(n)]
    ring = [(r * math.cos(a), r * math.sin(a)) for a in angles]

    # Points 0..n-1 are the bottom ring (z = -h), n..2n-1 the top ring (z = +h).
    local = [(x, y, -h) for x, y in ring] + [(x, y, h) for x, y in ring]
    indices: list[int] = []
    for i in range(n):  # side quads, one per segment
        j = (i + 1) % n
        indices += [i, j, n + j, n + i]
    indices += [n + i for i in range(n)]  # top cap, counter-clockwise seen from +z
    indices += list(reversed(range(n)))  # bottom cap, counter-clockwise seen from -z
    counts = (4,) * n + (n, n)

    q = quat_between((0.0, 0.0, 1.0), cylinder.axis)
    cx, cy, cz = cylinder.center_m
    points = tuple((cx + px, cy + py, cz + pz) for px, py, pz in (rotate(q, p) for p in local))
    return MeshData(points, counts, tuple(indices))
