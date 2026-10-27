"""Stand-in shapes (drill-press plan, Phase 5; decision 0027): solids and the slotted table."""

import math

import numpy as np
import pytest
from pydantic import ValidationError

from moonwalkers.pipelines.b.stand_ins import (
    BoxPiece,
    CylinderPiece,
    SlottedTable,
    Solids,
    placed,
    shape_mesh,
    table_distance,
)

IN = 0.0254


def table(**changes) -> SlottedTable:
    values = {
        "side_m": 11.25 * IN,
        "thickness_m": 1.0625 * IN,
        "corner_radius_m": 1.5 * IN,
        "rim_width_m": 0.75 * IN,
        "gutter_width_m": 0.5 * IN,
        "gutter_depth_m": 0.375 * IN,
        "slot_width_m": 9 / 16 * IN,
        "slot_depth_m": 0.5 * IN,
        "slot_start_m": 1.6 * IN,
        "hole_diameter_m": 1.0 * IN,
        "cell_m": 0.004,
    }
    return SlottedTable(**(values | changes))


def test_a_box_is_turned_about_its_centre_and_repeated() -> None:
    box = BoxPiece(size_m=(0.2, 0.02, 0.01), turn_deg=90.0, repeat=3, step_m=(0, 0, 0.1))
    mesh = shape_mesh(Solids(pieces=[box]))
    assert mesh.bounds[0] == pytest.approx([-0.01, -0.1, -0.005])
    assert mesh.bounds[1] == pytest.approx([0.01, 0.1, 0.205])
    assert len(mesh.faces) == 3 * 12


def test_a_cylinder_lies_along_its_axis() -> None:
    piece = CylinderPiece(radius_m=0.01, length_m=0.1, axis=(0, 1, 0), center_m=(0, 0.05, 0))
    mesh = shape_mesh(Solids(pieces=[piece]))
    assert mesh.bounds[0] == pytest.approx([-0.01, 0.0, -0.01], abs=1e-9)
    assert mesh.bounds[1] == pytest.approx([0.01, 0.1, 0.01], abs=1e-9)
    down = shape_mesh(Solids(pieces=[piece.model_copy(update={"axis": (0, 0, -1)})]))
    assert down.extents == pytest.approx([0.02, 0.02, 0.1], abs=1e-9)


def test_pieces_that_meet_end_to_end_share_no_points() -> None:
    """NVIDIA's asset validator warns about points on top of each other (worklog 2026-10-27)."""
    stack = [
        CylinderPiece(radius_m=0.02, length_m=0.05, center_m=(0, 0, 0.025)),
        CylinderPiece(radius_m=0.03, length_m=0.05, center_m=(0, 0, 0.075)),
    ]
    mesh = shape_mesh(Solids(pieces=stack))
    rounded = np.round(mesh.vertices, 9)
    assert len(np.unique(rounded, axis=0)) == len(rounded)


def test_placed_turns_about_z_then_moves() -> None:
    mesh = shape_mesh(Solids(pieces=[BoxPiece(size_m=(0.1, 0.02, 0.02), center_m=(0.05, 0, 0))]))
    moved = placed(mesh, (1.0, 2.0, 3.0), 90.0)
    assert moved.bounds[0] == pytest.approx([0.99, 2.0, 2.99])
    assert moved.bounds[1] == pytest.approx([1.01, 2.1, 3.01])
    assert mesh.bounds[0][0] == pytest.approx(0.0)  # the original is unchanged


def test_the_table_has_its_cited_size_and_is_closed() -> None:
    shape = table()
    mesh = shape_mesh(shape)
    # surface nets bevel the edges by up to a cell
    assert mesh.extents[:2] == pytest.approx([11.25 * IN, 11.25 * IN], abs=shape.cell_m)
    assert mesh.extents[2] == pytest.approx(1.0625 * IN, abs=shape.cell_m)
    assert mesh.bounds[1][2] == pytest.approx(0.0, abs=shape.cell_m)  # its top at z = 0
    assert mesh.is_watertight


def test_the_table_has_slots_a_gutter_a_hole_and_a_whole_rim() -> None:
    shape = table()
    half = shape.side_m / 2
    just_below_top = -0.001
    diagonal = np.array([1.0, 1.0, 0.0]) / math.sqrt(2)

    def inside(*points) -> list[bool]:
        p = np.array([[x, y, just_below_top] for x, y in points])
        return list(table_distance(shape, p) < 0)

    plate_edge = half - shape.rim_width_m - shape.gutter_width_m
    gutter = half - shape.rim_width_m - shape.gutter_width_m / 2
    slot = 3 * IN * diagonal  # along a diagonal, past the slot's start
    assert (
        inside(
            (0.5 * plate_edge, 0.0),  # the plate
            (half - shape.rim_width_m / 2, 0.0),  # the rim
            (gutter, 0.0),  # the gutter
            (0.0, 0.0),  # the hole
            tuple(slot[:2]),  # a slot
            tuple(1.0 * IN * diagonal[:2]),  # between the hole and the slot's start
        )
        == [True, True, False, False, False, True]
    )
    # the slots stop at the gutter, so the rim's corners are whole
    corner = (half - shape.corner_radius_m) + shape.corner_radius_m * 0.6
    assert inside((corner, corner)) == [True]


def test_the_table_can_stand_on_a_post() -> None:
    shape = table(post_diameter_m=1.5 * IN, post_length_m=0.01)
    mesh = shape_mesh(shape)
    assert mesh.bounds[0][2] == pytest.approx(-1.0625 * IN - 0.01, abs=shape.cell_m)
    below = np.array([[0.0, 0.0175, -1.0625 * IN - 0.005], [0.03, 0.0, -1.0625 * IN - 0.005]])
    assert list(table_distance(shape, below) < 0) == [True, False]  # the post, then air


@pytest.mark.parametrize(
    "changes",
    [
        {"rim_width_m": 0.1, "gutter_width_m": 0.1},  # no plate left
        {"gutter_depth_m": 0.03},  # deeper than the table
        {"corner_radius_m": 0.2},
        {"post_diameter_m": 0.03},  # a post needs a length too
        {"post_diameter_m": 0.01, "post_length_m": 0.01},  # narrower than the hole
    ],
)
def test_impossible_tables_are_refused(changes) -> None:
    with pytest.raises(ValidationError):
        table(**changes)
