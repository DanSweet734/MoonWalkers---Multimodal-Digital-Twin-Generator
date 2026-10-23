"""Primitive part meshes: right size and place, closed and welded, faces wound outward."""

import math
from collections import Counter

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


def assert_close(a, b, tol: float = 1e-12) -> None:
    assert all(math.isclose(x, y, abs_tol=tol) for x, y in zip(a, b, strict=True)), (a, b)


def assert_faces_point_outward(mesh: MeshData, center) -> None:
    for face, normal in zip(mesh.faces(), mesh.face_normals(), strict=True):
        pts = [mesh.points[i] for i in face]
        centroid = [sum(c) / len(pts) for c in zip(*pts, strict=True)]
        outward = [c - o for c, o in zip(centroid, center, strict=True)]
        assert sum(a * b for a, b in zip(normal, outward, strict=True)) > 0


def assert_closed_and_welded(mesh: MeshData) -> None:
    """No duplicate points, and every edge is shared by exactly two faces in opposite directions."""
    assert len(set(mesh.points)) == len(mesh.points)
    directed = Counter()
    for face in mesh.faces():
        for a, b in zip(face, face[1:] + face[:1], strict=True):
            directed[(a, b)] += 1
    assert all(count == 1 for count in directed.values())
    assert all((b, a) in directed for a, b in directed)


def test_box_mesh() -> None:
    mesh = primitive_mesh(BOX)
    assert len(mesh.points) == 8
    assert mesh.face_vertex_counts == (4,) * 6
    lo, hi = mesh.extent()
    assert_close(lo, (-0.1, -0.08, 0.0))
    assert_close(hi, (0.1, 0.08, 0.14))
    assert_closed_and_welded(mesh)
    assert_faces_point_outward(mesh, (0.0, 0.0, 0.07))


def test_box_face_normals_are_the_axes() -> None:
    normals = primitive_mesh(BOX).face_normals()
    expected = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]
    for normal, axis in zip(normals, expected, strict=True):
        assert_close(normal, axis)


def test_cylinder_mesh_along_x() -> None:
    mesh = primitive_mesh(CYLINDER_X)
    assert len(mesh.points) == 2 * 8
    assert mesh.face_vertex_counts == (4,) * 8 + (8, 8)
    lo, hi = mesh.extent()
    assert math.isclose(lo[0], 0.10) and math.isclose(hi[0], 0.16)
    for _x, y, z in mesh.points:  # every point lies on a cap's rim
        assert math.isclose(math.hypot(y, z - 0.1), 0.03)
    assert_closed_and_welded(mesh)
    assert_faces_point_outward(mesh, (0.13, 0.0, 0.1))
    caps = mesh.face_normals()[-2:]
    assert_close(caps[0], (1, 0, 0), tol=1e-9)  # top cap faces along +axis
    assert_close(caps[1], (-1, 0, 0), tol=1e-9)


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
        {"shape": "compound", "pieces": []},
        {"shape": "compound", "pieces": [{"shape": "compound", "pieces": [BOX]}]},
        {"shape": "compound", "pieces": [{"shape": "sphere", "radius_m": 1.0}]},
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


def test_a_compound_is_its_pieces_side_by_side() -> None:
    """A compound (several shapes that move as one part) keeps each piece's closed mesh."""
    box, cylinder = primitive_mesh(BOX), primitive_mesh(CYLINDER_X)
    compound = primitive_mesh({"shape": "compound", "pieces": [BOX, CYLINDER_X]})
    assert compound.points == box.points + cylinder.points
    assert compound.face_vertex_counts == box.face_vertex_counts + cylinder.face_vertex_counts
    shifted = tuple(i + len(box.points) for i in cylinder.face_vertex_indices)
    assert compound.face_vertex_indices == box.face_vertex_indices + shifted
    assert_closed_and_welded(compound)
    assert compound.extent() == (
        tuple(min(a, b) for a, b in zip(box.extent()[0], cylinder.extent()[0], strict=True)),
        tuple(max(a, b) for a, b in zip(box.extent()[1], cylinder.extent()[1], strict=True)),
    )
