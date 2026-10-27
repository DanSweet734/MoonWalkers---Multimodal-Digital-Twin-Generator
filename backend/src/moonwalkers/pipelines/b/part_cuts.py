"""Cut one mesh into several parts with shapes (drill-press plan Phase 4, method a).

A cut list names parts in order, each with one or more shapes in the twin frame: a cylinder, a
box or a half-space. A face goes to the first part with a shape that holds its centre; faces that
no shape holds stay in the fixed part. This extends decision 0012's spindle split, which is one
cylinder, to any number of parts. As there, cuts follow the mesh's faces: no face is split, and
each part has open edges along its seams.

``seams`` measures what a cut leaves behind: open edges, seam length, and stray faces (faces in
small pieces cut off from the rest of their part, which usually means a shape caught a neighbour's
surface). A part may rightly be in a few large pieces: the bracket cuts the column in two.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Annotated, Literal

import numpy as np
import trimesh
from pydantic import BaseModel, ConfigDict, Field, PositiveFloat

from .mesh_tools import face_groups

Vec3 = tuple[float, float, float]
STRAY_SHARE = 0.02  # [INFERENCE] a piece under 2% of its part's faces is a stray, not a member


class _Shape(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CylinderCut(_Shape):
    """Points within ``radius`` of the axis through ``point`` along ``axis``, between ``start``
    and ``end`` (measured along the axis from ``point``)."""

    shape: Literal["cylinder"] = "cylinder"
    point: Vec3
    axis: Vec3
    radius: PositiveFloat
    start: float = -math.inf
    end: float = math.inf


class BoxCut(_Shape):
    """Points inside an axis-aligned box."""

    shape: Literal["box"] = "box"
    min: Vec3
    max: Vec3


class HalfSpaceCut(_Shape):
    """Points on the side of the plane through ``point`` that ``normal`` points to."""

    shape: Literal["half_space"] = "half_space"
    point: Vec3
    normal: Vec3


Shape = Annotated[CylinderCut | BoxCut | HalfSpaceCut, Field(discriminator="shape")]


class PartCut(BaseModel):
    """One part's shapes. A face whose centre is in any of them (and in no earlier part's)
    belongs to the part. A part may appear more than once in a cut list, for example the fixed
    part first, to keep its surface out of a later part's shape."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    part: str
    shapes: list[Shape] = Field(min_length=1)
    note: str = ""  # what the shapes are drawn around, and from which evidence


def contains(shape: CylinderCut | BoxCut | HalfSpaceCut, points: np.ndarray) -> np.ndarray:
    """Which of ``points`` (N x 3) the shape holds."""
    if isinstance(shape, BoxCut):
        return np.all((points >= shape.min) & (points <= shape.max), axis=1)
    if isinstance(shape, HalfSpaceCut):
        return (points - np.asarray(shape.point)) @ _unit(shape.normal) >= 0
    axis = _unit(shape.axis)
    rel = points - np.asarray(shape.point)
    t = rel @ axis
    radial = np.linalg.norm(rel - np.outer(t, axis), axis=1)
    return (radial <= shape.radius) & (t >= shape.start) & (t <= shape.end)


def assign(mesh: trimesh.Trimesh, cuts: Sequence[PartCut], rest: str) -> np.ndarray:
    """The part of every face: the first cut holding its centre, else ``rest``."""
    centres = mesh.triangles_center
    parts = np.full(len(centres), rest, dtype=object)
    free = np.ones(len(centres), dtype=bool)
    for cut in cuts:
        held = np.zeros(len(centres), dtype=bool)
        for shape in cut.shapes:
            held |= contains(shape, centres)
        parts[free & held] = cut.part
        free &= ~held
    return parts


def split(mesh: trimesh.Trimesh, parts: Sequence[str]) -> dict[str, trimesh.Trimesh]:
    """One mesh per part, in the same frame."""
    parts = np.asarray(parts, dtype=object)
    meshes = {}
    for name in dict.fromkeys(parts):
        piece = mesh.submesh([np.flatnonzero(parts == name)], append=True)
        piece.remove_unreferenced_vertices()
        meshes[str(name)] = piece
    return meshes


# --------------------------------------------------------------------------------- seams
@dataclass(frozen=True)
class PartSeams:
    part: str
    faces: int
    area: float  # model units squared
    pieces: int  # connected pieces: 1 for a clean cut
    stray_faces: int  # faces in pieces under STRAY_SHARE of the part's faces
    open_edges: int  # edges with no neighbour in the part: its seams, plus any holes
    seam_length: float  # their total length, model units


def seams(mesh: trimesh.Trimesh, parts: Sequence[str]) -> list[PartSeams]:
    """What cutting ``mesh`` into ``parts`` (one per face) leaves on each part."""
    parts = np.asarray(parts, dtype=object)
    pairs = mesh.face_adjacency
    same = parts[pairs[:, 0]] == parts[pairs[:, 1]]
    groups = face_groups(mesh, same)
    edge_length = np.linalg.norm(
        np.diff(mesh.vertices[mesh.face_adjacency_edges], axis=1)[:, 0], axis=1
    )
    # Edges used by one face only: holes in the mesh itself (none in a watertight mesh).
    edges = mesh.edges_sorted
    unique, counts = np.unique(edges, axis=0, return_counts=True)
    lonely = {tuple(e) for e in unique[counts == 1]}
    lonely_face = np.array([tuple(e) in lonely for e in edges]) if lonely else None

    result = []
    for name in dict.fromkeys(parts):
        mine = parts == name
        crossing = ~same & (mine[pairs[:, 0]] | mine[pairs[:, 1]])
        own_holes = 0
        if lonely_face is not None:
            own_holes = int(lonely_face[np.repeat(mine, 3)].sum())
        sizes = np.bincount(groups[mine])
        sizes = sizes[sizes > 0]
        result.append(
            PartSeams(
                part=str(name),
                faces=int(mine.sum()),
                area=float(mesh.area_faces[mine].sum()),
                pieces=len(sizes),
                stray_faces=int(sizes[sizes < STRAY_SHARE * sizes.sum()].sum()),
                open_edges=int(crossing.sum()) + own_holes,
                seam_length=float(edge_length[crossing].sum()),
            )
        )
    return result


def _unit(vector: Sequence[float]) -> np.ndarray:
    v = np.asarray(vector, dtype=float)
    return v / np.linalg.norm(v)
