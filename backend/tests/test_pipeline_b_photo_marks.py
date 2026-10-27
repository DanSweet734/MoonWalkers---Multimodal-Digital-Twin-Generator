"""Method (d) of the drill-press plan's Phase 4: carrying parts marked on photos onto the mesh."""

import math

import numpy as np
import pytest
import trimesh

from moonwalkers.pipelines.b.photo_marks import (
    UNMARKED,
    Camera,
    carry,
    fill_unseen,
    fit_camera,
    in_photo,
    render,
)


def two_boxes() -> tuple[trimesh.Trimesh, np.ndarray]:
    """A big box (part 0) with a small box standing on its top (part 1)."""
    base = trimesh.creation.box(extents=(2.0, 1.0, 1.0)).subdivide().subdivide()
    top = trimesh.creation.box(extents=(0.5, 0.5, 0.5)).subdivide().subdivide()
    top.apply_translation((0.4, 0.0, 0.75))
    mesh = trimesh.util.concatenate([base, top])
    return mesh, np.r_[np.zeros(len(base.faces), int), np.ones(len(top.faces), int)]


def test_a_camera_around_the_mesh_looks_from_its_angle() -> None:
    mesh, _ = two_boxes()
    camera = Camera.around(mesh, azimuth_deg=90.0, elevation_deg=0.0)
    assert np.allclose(camera.toward, (0.0, 1.0, 0.0), atol=1e-12)
    column, _, depth = camera.project(np.array([[0.0, 1.0, 0.0], [1.0, 0.0, 0.0]]))
    assert depth[0] > depth[1]  # the point at +Y is nearer a camera at +Y
    assert column[1] < column[0]  # seen from +Y, +X is on the image's left


def test_render_draws_the_nearest_surface() -> None:
    mesh, labels = two_boxes()
    camera = Camera.around(mesh, 0.0, 89.0, size=128)  # from above
    image, depth = render(mesh, camera, labels, samples=100_000)
    assert {0, 1, UNMARKED} == set(np.unique(image).tolist())
    assert np.isinf(depth[0, 0])  # a corner shows nothing


def test_perfect_marks_from_all_round_put_seen_faces_right() -> None:
    mesh, labels = two_boxes()
    marked = []
    for azimuth, elevation in ((0, 20), (90, 20), (180, 20), (270, 20), (0, 89)):
        camera = Camera.around(mesh, azimuth, elevation, size=256)
        marked.append((camera, render(mesh, camera, labels, samples=200_000)[0]))
    parts = carry(mesh, marked)
    seen = parts != UNMARKED
    area = mesh.area_faces
    assert area[seen].sum() / area.sum() > 0.6  # the bottom and the hidden contact stay unseen
    assert area[seen & (parts == labels)].sum() / area[seen].sum() > 0.97


def test_a_face_behind_another_takes_no_mark() -> None:
    mesh, labels = two_boxes()
    camera = Camera.around(mesh, 0.0, 0.0, size=256)  # from the front: +X
    marks = render(mesh, camera, labels, samples=200_000)[0]
    parts = carry(mesh, [(camera, marks)])
    back = mesh.face_normals[:, 0] < -0.9
    assert (parts[back] == UNMARKED).all()


def test_unseen_faces_take_their_neighbours_parts() -> None:
    mesh = trimesh.creation.box().subdivide().subdivide()
    parts = np.full(len(mesh.faces), UNMARKED)
    top = mesh.triangles_center[:, 2] > 0.49
    parts[top] = 3
    filled = fill_unseen(mesh, parts)
    assert (filled == 3).all()


def test_fill_unseen_leaves_faces_out_of_reach() -> None:
    mesh, _ = two_boxes()
    parts = np.full(len(mesh.faces), UNMARKED)
    parts[0] = 0  # only the big box is reached
    filled = fill_unseen(mesh, parts)
    assert (filled[-1] == UNMARKED) and (filled[:10] == 0).all()


def test_fit_camera_finds_the_angle_a_photo_was_taken_from() -> None:
    mesh, _ = two_boxes()
    photo = Camera.around(mesh, azimuth_deg=-35.0, elevation_deg=18.0, size=300)
    faces, _ = render(mesh, photo, samples=300_000)
    mask = np.zeros((360, 400), dtype=bool)
    mask[30:330, 50:350] = faces >= 0  # the "photo" is larger, with a margin
    fit = fit_camera(mesh, mask, np.arange(-55.0, -14.0, 10.0), np.arange(0.0, 41.0, 10.0))
    assert fit.azimuth_deg == pytest.approx(-35.0, abs=3.0)
    assert fit.elevation_deg == pytest.approx(18.0, abs=4.0)
    assert fit.iou > 0.9
    seen = in_photo(mesh, mask, fit) >= 0
    assert (seen & mask).sum() / (seen | mask).sum() == pytest.approx(fit.iou, abs=0.05)
    assert math.isfinite(fit.iou)
