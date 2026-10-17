"""Primitive part meshes: right size, right place, faces wound outward."""

import math

import pytest
from pydantic import ValidationError

from moonwalkers.usd.geometry import MeshData, primitive_mesh

BOX = {"shape": "box", "size_m": [0.2, 0.16, 0.14], "center_m": [0.0, 0.0, 0.07]}
CYLINDER_X = {
    "shape": "cylinder",
    "radius_m": 0.03,
    "length_m": 0.06,
    "axis": [1, 0, 0],
    "center_m": [0.13, 0.0, 0.1],
    "segments": 8,
}


def newell_normal(points):
    """Face normal by Newell's method; follows the right-hand rule for the vertex order."""
    nx = ny = nz = 0.0
    for i, (x0, y0, z0) in enumerate(points):
        x1, y1, z1 = points[(i + 1) % len(points)]
        nx += (y0 - y1) * (z0 + z1)
        ny += (z0 - z1) * (x0 + x1)
        nz += (x0 - x1) * (y0 + y1)
    return nx, ny, nz


def assert_faces_point_outward(mesh: MeshData, center) -> None:
    for face in mesh.faces():
        pts = [mesh.points[i] for i in face]
        n = newell_normal(pts)
        centroid = [sum(c) / len(pts) for c in zip(*pts, strict=True)]
        outward = [c - o for c, o in zip(centroid, center, strict=True)]
        assert sum(a * b for a, b in zip(n, outward, strict=True)) > 0


def assert_close(a, b, tol: float = 1e-12) -> None:
    assert all(math.isclose(x, y, abs_tol=tol) for x, y in zip(a, b, strict=True)), (a, b)


def test_box_mesh() -> None:
    mesh = primitive_mesh(BOX)
    assert len(mesh.points) == 24
    assert mesh.face_vertex_counts == (4,) * 6
    lo, hi = mesh.extent()
    assert_close(lo, (-0.1, -0.08, 0.0))
    assert_close(hi, (0.1, 0.08, 0.14))
    assert_faces_point_outward(mesh, (0.0, 0.0, 0.07))


def test_cylinder_mesh_along_x() -> None:
    mesh = primitive_mesh(CYLINDER_X)
    assert len(mesh.points) == 6 * 8
    assert mesh.face_vertex_counts == (4,) * 8 + (8, 8)
    lo, hi = mesh.extent()
    assert math.isclose(lo[0], 0.10) and math.isclose(hi[0], 0.16)
    for _x, y, z in mesh.points:  # every point lies on the cylinder surface or a cap edge
        assert math.isclose(math.hypot(y, z - 0.1), 0.03)
    assert_faces_point_outward(mesh, (0.13, 0.0, 0.1))


def test_cylinder_defaults_to_z_axis_and_32_segments() -> None:
    mesh = primitive_mesh({"shape": "cylinder", "radius_m": 0.5, "length_m": 2.0})
    lo, hi = mesh.extent()
    assert math.isclose(lo[2], -1.0) and math.isclose(hi[2], 1.0)
    assert len(mesh.face_vertex_counts) == 32 + 2


@pytest.mark.parametrize(
    "spec",
    [
        {"shape": "sphere", "radius_m": 1.0},
        {"shape": "box", "size_m": [1, 1, 0]},
        {"shape": "box", "size_m": [1, 1, 1], "colour": "red"},
        {"shape": "cylinder", "radius_m": 1.0, "length_m": 1.0, "axis": [0, 0, 0]},
        {"shape": "cylinder", "radius_m": 1.0, "length_m": 1.0, "segments": 2},
        {"size_m": [1, 1, 1]},
    ],
)
def test_bad_primitives_are_rejected(spec) -> None:
    with pytest.raises(ValidationError):
        primitive_mesh(spec)


@pytest.mark.parametrize(
    ("points", "counts", "indices"),
    [
        (((0, 0, 0), (1, 0, 0), (0, 1, 0)), (3,), (0, 1, 5)),  # index out of range
        (((0, 0, 0), (1, 0, 0), (0, 1, 0)), (4,), (0, 1, 2)),  # counts do not add up
        (((0, 0, 0), (1, 0, 0)), (2,), (0, 1)),  # face with 2 vertices
    ],
)
def test_malformed_meshes_are_rejected(points, counts, indices) -> None:
    with pytest.raises(ValueError):
        MeshData(points, counts, indices)
