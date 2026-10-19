"""Finding the spindle axis (decision 0012): tip slabs when the spindle is in front, warnings and
circle fits when something else is, as on the TH240 (feet in front of the platter).

The synthetic machines are in conftest: the indexer (spindle nose in front, axis y = 0, z = 0.2)
and the rotary table (the same axis, but feet along the bottom reach past the platter).
"""

from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest
import trimesh

from moonwalkers.pipelines.b.inspection import inspect_mesh
from moonwalkers.pipelines.b.mesh_tools import (
    fit_circles,
    orientation_matrix,
    scan_positions,
    tip_slabs,
    transformed,
)


def as_generated(build: Callable[[], trimesh.Trimesh], path: Path) -> Path:
    """Write the machine the way a glTF generator does (+Y up, front facing +Z)."""
    transformed(build(), np.linalg.inv(orientation_matrix(up="+y", front="+z"))).export(path)
    return path


# -------------------------------------------------------------------------------- circle fits
def test_a_circle_is_found_among_other_parts_in_the_slice(rotary_table) -> None:
    platter, feet_only = fit_circles(rotary_table(), [1.15, 1.45])
    assert platter.round and platter.centre_yz == pytest.approx((0.0, 0.2), abs=0.005)
    assert platter.radius == pytest.approx(0.6, abs=0.005)  # a 64-sided platter
    assert platter.coverage == 1.0 and 0.25 <= platter.inliers < 1.0  # the feet share the slice
    assert not feet_only.round  # two rectangles are not a round part


def test_concentric_rings_give_one_centre() -> None:
    ring = trimesh.creation.annulus(r_min=0.3, r_max=0.8, height=1.0, sections=64)
    ring.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, (0, 1, 0)))
    ring.apply_translation((0.0, 0.5, -0.25))
    (fit,) = fit_circles(ring, [0.0])
    assert fit.round and fit.centre_yz == pytest.approx((0.5, -0.25), abs=0.005)
    assert fit.radius == pytest.approx(0.8, abs=0.01) or fit.radius == pytest.approx(0.3, abs=0.01)


def test_a_slice_outside_the_mesh_has_no_circle(indexer) -> None:
    (fit,) = fit_circles(indexer(), [5.0])
    assert (fit.samples, fit.centre_yz, fit.radius, fit.round) == (0, None, None, False)


def test_circle_fits_are_repeatable(rotary_table) -> None:
    assert fit_circles(rotary_table(), [1.1, 1.2]) == fit_circles(rotary_table(), [1.1, 1.2])


def test_the_scan_covers_the_front_of_the_mesh(rotary_table) -> None:
    xs = scan_positions(rotary_table())  # the mesh runs from x = -1 to 1.6
    assert len(xs) == 8 and xs == sorted(xs)
    assert xs[0] == pytest.approx(1.6 - 0.40 * 2.6) and xs[-1] == pytest.approx(1.6 - 0.05 * 2.6)


def test_tip_slabs_on_the_rotary_table_measure_the_feet(rotary_table) -> None:
    slab = tip_slabs(rotary_table())[0]
    assert slab.extent_yz == pytest.approx((2.8, 0.2)) and slab.z_min == pytest.approx(-1.0)


# --------------------------------------------------------------------------------- inspection
def test_a_spindle_in_front_needs_no_warning(indexer, tmp_path: Path) -> None:
    mesh = as_generated(indexer, tmp_path / "indexer.glb")
    result = inspect_mesh(mesh, tmp_path / "views", "+y", "+z")
    assert result.warnings == [] and result.axis_source == "tip_slabs"
    assert result.axis_yz == pytest.approx((0.0, 0.2), abs=1e-6)
    spindle = [f for f in result.circle_scan if f.round and f.x > 1.0]
    assert spindle and all(f.centre_yz == pytest.approx((0.0, 0.2), abs=0.01) for f in spindle)


def test_feet_in_front_are_flagged_and_circle_x_finds_the_platter(
    rotary_table, tmp_path: Path
) -> None:
    mesh = as_generated(rotary_table, tmp_path / "table.glb")
    first = inspect_mesh(mesh, tmp_path / "views", "+y", "+z")
    assert first.axis_source == "tip_slabs" and first.axis_yz[1] == pytest.approx(-0.9)  # feet
    assert any("not round" in w for w in first.warnings)
    assert any("bottom of the mesh" in w for w in first.warnings)
    round_scan = [f for f in first.circle_scan if f.round]
    assert round_scan and all(1.0 < f.x < 1.3 for f in round_scan)  # only inside the platter

    second = inspect_mesh(mesh, tmp_path / "views", "+y", "+z", circle_x=[1.1, 1.2])
    assert second.axis_source == "circle_fits"
    assert second.axis_yz == pytest.approx((0.0, 0.2), abs=0.005)
    in_front = [s.radius for s in second.profile if 1.05 < s.t < 1.25]
    assert in_front and all(r == pytest.approx(0.6, abs=0.01) for r in in_front)


def test_circle_x_that_misses_the_round_part_keeps_the_tip_axis(
    rotary_table, tmp_path: Path
) -> None:
    mesh = as_generated(rotary_table, tmp_path / "table.glb")
    result = inspect_mesh(mesh, tmp_path / "views", "+y", "+z", circle_x=[1.5])
    assert result.axis_source == "tip_slabs"
    assert any("None of the circle fits" in w for w in result.warnings)


def test_circle_x_needs_the_axes(indexer, tmp_path: Path) -> None:
    mesh = as_generated(indexer, tmp_path / "indexer.glb")
    with pytest.raises(ValueError, match="circle_x needs up and front"):
        inspect_mesh(mesh, tmp_path / "views", circle_x=[1.2])
