"""The Phase 4 test mesh: the box-and-cylinder drill press as one mesh, each face labelled."""

import math

import numpy as np
import pytest

from moonwalkers.pipelines.b.synthetic_parts import (
    drill_press,
    name_segments,
    score,
    signed_distance,
    surface_nets,
)
from moonwalkers.usd.geometry import BoxPrimitive, CylinderPrimitive

PARTS = {
    "frame",
    "quill",
    "spindle",
    "handle_hub",
    "column_rack",
    "table_bracket",
    "table_arm",
    "table",
}


def test_signed_distance_to_a_box_and_a_cylinder() -> None:
    box = BoxPrimitive(shape="box", size_m=(2.0, 2.0, 2.0))
    d = signed_distance(box, np.array([[0.0, 0, 0], [3.0, 0, 0], [2.0, 2.0, 1.0]]))
    assert np.allclose(d, [-1.0, 2.0, math.sqrt(2.0)])
    cylinder = CylinderPrimitive(shape="cylinder", radius_m=1.0, length_m=2.0, axis=(1, 0, 0))
    d = signed_distance(cylinder, np.array([[0.0, 0, 0], [0.0, 3.0, 0], [3.0, 0, 0]]))
    assert np.allclose(d, [-1.0, 2.0, 2.0])


def test_rounding_keeps_the_size_and_rounds_the_corners() -> None:
    box = BoxPrimitive(shape="box", size_m=(2.0, 2.0, 2.0))
    face, corner = np.array([[1.0, 0, 0]]), np.array([[1.0, 1.0, 1.0]])
    assert signed_distance(box, face, rounding=0.2)[0] == pytest.approx(0.0)
    assert signed_distance(box, corner, rounding=0.2)[0] > 0.0  # the corner is cut off


def test_surface_nets_closes_a_sphere() -> None:
    def sphere(points: np.ndarray) -> np.ndarray:
        return np.linalg.norm(points, axis=1) - 1.0

    mesh = surface_nets(sphere, np.array([-1.0, -1, -1]), np.array([1.0, 1, 1]), 0.1)
    assert mesh.is_watertight and mesh.is_winding_consistent
    assert mesh.volume == pytest.approx(4 / 3 * math.pi, rel=0.05)  # positive: normals point out


def test_the_separate_drill_press_holds_every_part() -> None:
    truth = drill_press("separate")
    assert set(truth.names) == PARTS
    assert len(truth.labels) == len(truth.mesh.faces)
    assert set(np.unique(truth.labels)) == set(range(len(PARTS)))


@pytest.mark.parametrize("build", ["fused", "rounded"])
def test_a_fused_drill_press_labels_its_surface(build) -> None:
    truth = drill_press(build, cell=0.012)  # coarse, for speed: too coarse to close thin parts
    assert truth.mesh.volume > 0
    labelled = {truth.names[i] for i in np.unique(truth.labels)}
    assert {"frame", "table", "table_bracket", "handle_hub"} <= labelled


@pytest.mark.slow
@pytest.mark.parametrize("build", ["fused", "rounded"])
def test_at_the_spike_cell_the_fused_drill_press_is_one_closed_surface(build) -> None:
    truth = drill_press(build)  # CELL: the 12 mm handles span three grid lines
    assert truth.mesh.is_watertight and truth.mesh.is_winding_consistent
    assert len(np.unique(truth.labels)) == len(PARTS)


def test_score_and_segment_naming() -> None:
    truth = drill_press("separate")
    actual = np.asarray(truth.names)[truth.labels]
    perfect = score(truth, actual)
    assert perfect.area_share == 1.0 and perfect.face_share == 1.0
    assert all(r == p == 1.0 for r, p in perfect.per_part.values())
    everything_frame = score(truth, np.full(len(actual), "frame"))
    assert 0 < everything_frame.area_share < 1 and everything_frame.per_part["table"] == (0, 0)
    # one segment per part, numbered arbitrarily, is named back to the parts exactly
    named = name_segments(truth, (truth.labels * 7 + 3) % 101)
    assert list(named) == list(actual)
