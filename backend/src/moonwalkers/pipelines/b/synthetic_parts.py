"""A test mesh whose right part is known for every face, and scores against it (drill-press plan,
Phase 4).

The box-and-cylinder drill press of Phase 1 (``moonwalkers.usd.primitive_drill_press``) becomes one
mesh in the twin frame (metres, +Z up, front +X), in two ways:

- **separate:** each part's closed primitives side by side, as the exporter meshes them. The parts
  overlap but share no surface, so they are separate pieces of one mesh: the easy case.
- **fused:** one surface around the union of every part, as an image-to-3D generator extracts it
  from an occupancy grid. Touching parts share a surface and become one piece, as the T33901's
  generated mesh is [INFERENCE: Hunyuan3D-2 extracts its surface from a grid, octree resolution
  380]. The surface comes from the parts' exact signed distances on a grid of ``cell`` metres by
  naive surface nets: the simplest form of S. F. F. Gibson's SurfaceNets ("Constrained Elastic
  SurfaceNets", MICCAI'98, pp. 888-898; MERL TR99-24, https://www.merl.com/publications/TR99-24),
  one vertex per cell at the mean of its edges' crossings, without the paper's relaxation. Each
  face takes the part whose surface is nearest its centre.
- **rounded:** the fused mesh with its edges rounded and the creases where parts meet filled
  (``ROUNDING``), as a generated mesh's are soft. Sharp creases between parts make method (b)'s
  job easy, so this is the fairer test for it.

A labelling is scored by the share of the surface (by area, and by face count) that lands in the
right part. Methods that return unnamed segments are scored after naming each segment after the
part that holds most of its area: the best naming a reviewer could give.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

import numpy as np
import trimesh

from moonwalkers.usd.geometry import (
    BoxPrimitive,
    CompoundPrimitive,
    CylinderPrimitive,
    parse_primitive,
    primitive_mesh,
)
from moonwalkers.usd.primitive_drill_press import build_parts

Build = Literal["separate", "fused", "rounded"]
# m: the handles' studs (12 mm across) still span three grid lines. One vertex per cell cannot
# close a part thinner than about two cells, so a coarser grid leaves the surface open there.
CELL = 0.004
# The "rounded" build's fillet radius [INFERENCE: chosen by eye; the generated T33901 mesh's edges
# and joints are soft, with 921 of its 59,976 edges sharper than 45 degrees]
ROUNDING = 0.006


@dataclass(frozen=True)
class LabelledMesh:
    mesh: trimesh.Trimesh
    labels: np.ndarray  # per face: an index into names
    names: tuple[str, ...]  # part ids, in the Phase 1 model's order


def drill_press(build: Build = "fused", cell: float = CELL) -> LabelledMesh:
    """The Phase 1 drill press as one labelled mesh (module docstring)."""
    parts = build_parts()
    names = tuple(p.part_id for p in parts)
    if build == "separate":
        meshes, labels = [], []
        for index, part in enumerate(parts):
            data = primitive_mesh(part.primitive or {})
            mesh = trimesh.Trimesh(np.array(data.points), _triangles(data.faces()), process=False)
            meshes.append(mesh)
            labels.append(np.full(len(mesh.faces), index))
        return LabelledMesh(trimesh.util.concatenate(meshes), np.concatenate(labels), names)
    pieces = [_pieces(part.primitive or {}) for part in parts]
    lo, hi = _bounds(pieces)
    if build == "rounded":
        mesh = surface_nets(lambda p: _blended(pieces, p, ROUNDING), lo, hi, cell)
    else:
        mesh = surface_nets(lambda p: _union(pieces, p).min(axis=0), lo, hi, cell)
    labels = _union(pieces, mesh.triangles_center).argmin(axis=0)
    return LabelledMesh(mesh, labels, names)


# ----------------------------------------------------------------------------------- scoring
@dataclass(frozen=True)
class Score:
    area_share: float  # of the whole surface, in the right part
    face_share: float  # the same, counting faces
    per_part: dict[str, tuple[float, float]]  # part: (recall, precision), by area


def score(truth: LabelledMesh, predicted: Sequence[str]) -> Score:
    """How much of the surface ``predicted`` (a part id per face) puts in the right part."""
    predicted = np.asarray(predicted)
    actual = np.asarray(truth.names)[truth.labels]
    area = truth.mesh.area_faces
    right = predicted == actual
    per_part = {}
    for name in truth.names:
        true_area = area[actual == name].sum()
        said_area = area[predicted == name].sum()
        both = area[(actual == name) & right].sum()
        per_part[name] = (
            float(both / true_area) if true_area else 0.0,
            float(both / said_area) if said_area else 0.0,
        )
    return Score(float(area[right].sum() / area.sum()), float(right.mean()), per_part)


def name_segments(truth: LabelledMesh, segments: Sequence[int]) -> list[str]:
    """Each segment named after the part holding most of its area (the best naming possible)."""
    segments = np.asarray(segments)
    area = truth.mesh.area_faces
    names = np.empty(len(segments), dtype=object)
    for segment in np.unique(segments):
        inside = segments == segment
        totals = np.bincount(truth.labels[inside], weights=area[inside], minlength=len(truth.names))
        names[inside] = truth.names[int(totals.argmax())]
    return list(names)


# ---------------------------------------------------------------------- signed distances
Piece = BoxPrimitive | CylinderPrimitive


def _pieces(primitive: dict) -> list[Piece]:
    parsed = parse_primitive(primitive)
    return list(parsed.pieces) if isinstance(parsed, CompoundPrimitive) else [parsed]


def signed_distance(piece: Piece, points: np.ndarray, rounding: float = 0.0) -> np.ndarray:
    """The exact signed distance from ``points`` (N x 3) to a box or a round cylinder: negative
    inside. A cylinder is round here, though the exporter meshes it with flat sides. With
    ``rounding``, the edges are rounded off by that radius (at most half the piece's thinnest
    half-size), keeping its overall size."""
    rel = points - np.asarray(piece.center_m)
    if isinstance(piece, BoxPrimitive):
        half = np.asarray(piece.size_m) / 2
        r = min(rounding, 0.5 * float(half.min()))
        q = np.abs(rel) - (half - r)
    else:
        axis = np.asarray(piece.axis, dtype=float)
        axis /= np.linalg.norm(axis)
        t = rel @ axis
        radial = np.linalg.norm(rel - np.outer(t, axis), axis=1)
        r = min(rounding, 0.5 * min(piece.radius_m, piece.length_m / 2))
        q = np.column_stack([radial - (piece.radius_m - r), np.abs(t) - (piece.length_m / 2 - r)])
    outside = np.linalg.norm(np.maximum(q, 0.0), axis=1)
    return outside + np.minimum(q.max(axis=1), 0.0) - r


def _union(pieces: Sequence[Sequence[Piece]], points: np.ndarray) -> np.ndarray:
    """Each part's signed distance (the nearest of its pieces) at ``points``: parts x N."""
    return np.stack([np.min([signed_distance(p, points) for p in part], axis=0) for part in pieces])


def _blended(pieces: Sequence[Sequence[Piece]], points: np.ndarray, radius: float) -> np.ndarray:
    """The signed distance to every piece with rounded edges, joined by a smooth minimum, so the
    creases where pieces meet are filled with fillets of about ``radius``. The quadratic
    polynomial form, min(a, b) - h^2 k / 4 with h = max(k - |a - b|, 0) / k, from I. Quilez's
    article on smooth minimums (https://iquilezles.org/articles/smin)."""
    result = None
    for piece in (p for part in pieces for p in part):
        d = signed_distance(piece, points, radius)
        if result is None:
            result = d
            continue
        h = np.maximum(radius - np.abs(result - d), 0.0) / radius
        result = np.minimum(result, d) - h * h * radius / 4
    assert result is not None
    return result


def _bounds(pieces: Sequence[Sequence[Piece]]) -> tuple[np.ndarray, np.ndarray]:
    corners = []
    for part in pieces:
        for piece in part:
            if isinstance(piece, BoxPrimitive):
                half = np.asarray(piece.size_m) / 2
            else:
                half = np.full(3, max(piece.radius_m, piece.length_m / 2))
            corners += [np.asarray(piece.center_m) - half, np.asarray(piece.center_m) + half]
    corners = np.array(corners)
    return corners.min(axis=0), corners.max(axis=0)


# ------------------------------------------------------------------------------ surface nets
_CORNERS = [(i, j, k) for i in (0, 1) for j in (0, 1) for k in (0, 1)]
CUBE_EDGES = [  # the 12 edges of a grid cell, as pairs of corners one step apart
    (a, b)
    for a in _CORNERS
    for b in _CORNERS
    if a < b and sum(x != y for x, y in zip(a, b, strict=True)) == 1
]


def surface_nets(sdf, lo: np.ndarray, hi: np.ndarray, cell: float) -> trimesh.Trimesh:
    """A closed triangle mesh of the zero level of ``sdf`` (points N x 3 -> values N, negative
    inside) between ``lo`` and ``hi``. One vertex per grid cell the surface crosses, at the mean
    of the crossings on its edges; one quad per grid edge the surface crosses, joining the four
    cells around it, wound so its normal points out."""
    lo = np.asarray(lo, dtype=float) - 2 * cell
    hi = np.asarray(hi, dtype=float) + 2 * cell
    axes = [np.arange(a, b + cell, cell) for a, b in zip(lo, hi, strict=True)]
    shape = tuple(len(a) for a in axes)
    grid = np.stack(np.meshgrid(*axes, indexing="ij"), axis=-1).reshape(-1, 3)
    values = np.concatenate([sdf(chunk) for chunk in np.array_split(grid, 64)]).reshape(shape)
    values[[0, -1], :, :] = values[:, [0, -1], :] = values[:, :, [0, -1]] = cell  # closed
    inside = values < 0

    # A vertex in every cell the surface crosses.
    cells = np.array(shape) - 1
    base = np.stack(np.meshgrid(*[np.arange(n) for n in cells], indexing="ij"), axis=-1)
    total = np.zeros((*cells, 3))
    count = np.zeros(tuple(cells))
    for a, b in CUBE_EDGES:
        va, vb = _corner(values, a, cells), _corner(values, b, cells)
        crossed = (va < 0) != (vb < 0)
        t = np.where(crossed, va / np.where(crossed, va - vb, 1.0), 0.0)
        position = base + np.asarray(a) + t[..., None] * (np.asarray(b) - np.asarray(a))
        total += np.where(crossed[..., None], position, 0.0)
        count += crossed
    active = count > 0
    index = np.full(tuple(cells), -1)
    index[active] = np.arange(int(active.sum()))
    vertices = lo + cell * (total[active] / count[active][:, None])

    quads = []
    for axis in range(3):
        u, v = (axis + 1) % 3, (axis + 2) % 3  # u x v = axis
        here = [slice(None)] * 3
        nxt = [slice(None)] * 3
        here[axis], nxt[axis] = slice(0, -1), slice(1, None)
        crossed = inside[tuple(here)] != inside[tuple(nxt)]
        out = inside[tuple(here)]  # inside at the lower end: the normal points along +axis
        edge = np.argwhere(crossed)
        keep = (edge[:, u] > 0) & (edge[:, v] > 0)  # cells on both sides exist
        keep &= (edge[:, u] < cells[u]) & (edge[:, v] < cells[v])
        edge = edge[keep]
        ring = []
        for du, dv in ((-1, -1), (0, -1), (0, 0), (-1, 0)):  # counter-clockwise about +axis
            c = edge.copy()
            c[:, u] += du
            c[:, v] += dv
            ring.append(index[c[:, 0], c[:, 1], c[:, 2]])
        ring = np.stack(ring, axis=1)
        flip = ~out[edge[:, 0], edge[:, 1], edge[:, 2]]
        ring[flip] = ring[flip][:, ::-1]
        quads.append(ring)
    quads = np.concatenate(quads)
    triangles = np.concatenate([quads[:, [0, 1, 2]], quads[:, [0, 2, 3]]])
    return trimesh.Trimesh(vertices, triangles, process=False)


def _corner(values: np.ndarray, corner: tuple[int, int, int], cells: np.ndarray) -> np.ndarray:
    i, j, k = corner
    return values[i : i + cells[0], j : j + cells[1], k : k + cells[2]]


def _triangles(faces: Sequence[Sequence[int]]) -> np.ndarray:
    """Fans of triangles for convex polygons."""
    return np.array([(f[0], f[i], f[i + 1]) for f in faces for i in range(1, len(f) - 1)])
