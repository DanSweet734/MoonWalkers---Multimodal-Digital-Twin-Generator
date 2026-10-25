"""Method (a) of the drill-press plan's Phase 4: cutting one mesh into parts with ordered shapes."""

import math

import numpy as np
import pytest
import trimesh
from pydantic import ValidationError

from moonwalkers.pipelines.b.part_cuts import (
    BoxCut,
    CylinderCut,
    HalfSpaceCut,
    PartCut,
    assign,
    contains,
    seams,
    split,
)


def test_each_shape_holds_what_it_should() -> None:
    points = np.array([[0.0, 0.0, 0.5], [0.0, 0.3, 0.5], [0.0, 0.0, 1.5], [2.0, 0.0, 0.0]])
    cylinder = CylinderCut(point=(0, 0, 0), axis=(0, 0, 2), radius=0.2, start=0.0, end=1.0)
    assert contains(cylinder, points).tolist() == [True, False, False, False]
    box = BoxCut(min=(-1, -1, 0), max=(1, 1, 1))
    assert contains(box, points).tolist() == [True, True, False, False]
    half = HalfSpaceCut(point=(1, 0, 0), normal=(1, 0, 0))
    assert contains(half, points).tolist() == [False, False, False, True]


def test_an_endless_cylinder_by_default() -> None:
    cylinder = CylinderCut(point=(0, 0, 0), axis=(1, 0, 0), radius=1.0)
    assert contains(cylinder, np.array([[-100.0, 0.0, 0.5], [100.0, 0.5, 0.0]])).all()


def test_the_first_part_that_holds_a_face_wins(indexer) -> None:
    mesh = indexer()  # a box (x -1..1) and a spindle (x 1..1.6, radius 0.4, about z = 0.2)
    spindle = PartCut(
        part="spindle",
        shapes=[CylinderCut(point=(1, 0, 0.2), axis=(1, 0, 0), radius=0.45, start=0.0)],
    )
    everything = PartCut(part="all", shapes=[BoxCut(min=(-9, -9, -9), max=(9, 9, 9))])
    parts = assign(mesh, [spindle, everything], rest="body")
    assert set(parts[:12]) == {"all"} and set(parts[12:]) == {"spindle"}
    parts = assign(mesh, [everything, spindle], rest="body")
    assert set(parts) == {"all"}
    assert set(assign(mesh, [spindle], rest="body")[:12]) == {"body"}


def test_a_part_may_have_several_shapes(indexer) -> None:
    mesh = indexer()
    either = PartCut(
        part="ends",
        shapes=[
            HalfSpaceCut(point=(1.5, 0, 0), normal=(1, 0, 0)),
            HalfSpaceCut(point=(-0.9, 0, 0), normal=(-1, 0, 0)),
        ],
    )
    parts = assign(mesh, [either], rest="middle")
    centres = mesh.triangles_center[:, 0]
    assert np.array_equal(parts == "ends", (centres >= 1.5) | (centres <= -0.9))


def test_a_cut_list_needs_shapes_and_known_fields() -> None:
    with pytest.raises(ValidationError):
        PartCut(part="nothing", shapes=[])
    with pytest.raises(ValidationError):
        BoxCut(min=(0, 0, 0), max=(1, 1, 1), radius=2)
    parsed = PartCut.model_validate(
        {"part": "table", "shapes": [{"shape": "box", "min": [0, 0, 0], "max": [1, 1, 1]}]}
    )
    assert isinstance(parsed.shapes[0], BoxCut)


def test_split_keeps_every_face_once(indexer) -> None:
    mesh = indexer()
    parts = assign(
        mesh, [PartCut(part="spindle", shapes=[HalfSpaceCut(point=(1, 0, 0), normal=(1, 0, 0))])],
        rest="body",
    )  # fmt: skip
    meshes = split(mesh, parts)
    assert set(meshes) == {"body", "spindle"}
    assert sum(len(m.faces) for m in meshes.values()) == len(mesh.faces)
    assert meshes["spindle"].bounds[0][0] >= 1.0 - 1e-9


def test_seams_of_separate_closed_pieces_are_empty(indexer) -> None:
    mesh = indexer()
    parts = ["body"] * 12 + ["spindle"] * (len(mesh.faces) - 12)
    found = {s.part: s for s in seams(mesh, parts)}
    assert found["body"].open_edges == 0 and found["spindle"].open_edges == 0
    assert found["body"].pieces == 1 and found["spindle"].pieces == 1


def test_seams_of_a_cut_through_one_surface() -> None:
    mesh = trimesh.creation.box(extents=(2.0, 1.0, 1.0)).subdivide().subdivide()
    parts = assign(
        mesh, [PartCut(part="front", shapes=[HalfSpaceCut(point=(0, 0, 0), normal=(1, 0, 0))])],
        rest="back",
    )  # fmt: skip
    found = {s.part: s for s in seams(mesh, parts)}
    # both halves are open along the same loop round the box at x = 0: perimeter 4
    assert found["front"].open_edges == found["back"].open_edges > 0
    assert math.isclose(found["front"].seam_length, 4.0, rel_tol=0.25)
    assert found["front"].stray_faces == 0 and found["front"].pieces == 1


def test_stray_faces_are_small_pieces_away_from_their_part() -> None:
    mesh = trimesh.creation.box()
    for _ in range(4):
        mesh = mesh.subdivide()  # 3072 faces, 512 a side
    parts = np.full(len(mesh.faces), "frame", dtype=object)
    parts[mesh.triangles_center[:, 2] > 0.49] = "table"
    parts[np.flatnonzero(mesh.triangles_center[:, 2] < -0.49)[0]] = "table"  # one face far off
    found = {s.part: s for s in seams(mesh, parts)}
    assert found["table"].pieces == 2 and found["table"].stray_faces == 1
    assert found["frame"].pieces == 1 and found["frame"].stray_faces == 0
