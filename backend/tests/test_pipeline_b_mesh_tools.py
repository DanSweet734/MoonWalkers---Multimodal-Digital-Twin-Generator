"""Pipeline B mesh tools on a synthetic 'indexer': a box body with a cylinder spindle along +X."""

import math
import struct
import zlib
from pathlib import Path

import numpy as np
import pytest

from moonwalkers.pipelines.b.mesh_tools import (
    load_mesh,
    orientation_matrix,
    radial_profile,
    render_views,
    split_by_cylinder,
    transformed,
    write_png,
)


def read_png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    return struct.unpack(">II", data[16:24])


@pytest.mark.parametrize(
    ("up", "front", "expect_up", "expect_front"),
    [
        ("+y", "+z", (0, 1, 0), (0, 0, 1)),
        ("+z", "+x", (0, 0, 1), (1, 0, 0)),
        ("-x", "+y", (-1, 0, 0), (0, 1, 0)),
    ],
)
def test_orientation_maps_up_to_z_and_front_to_x(up, front, expect_up, expect_front) -> None:
    rotation = orientation_matrix(up, front)
    assert np.allclose(rotation @ np.array(expect_up), (0, 0, 1))
    assert np.allclose(rotation @ np.array(expect_front), (1, 0, 0))
    assert math.isclose(np.linalg.det(rotation), 1.0)  # a rotation, not a mirror


def test_orientation_needs_perpendicular_axes() -> None:
    with pytest.raises(ValueError, match="perpendicular"):
        orientation_matrix("+z", "-z")


def test_glb_round_trip_and_orient(tmp_path: Path, indexer) -> None:
    path = tmp_path / "indexer.glb"
    # Store it like a glTF generator would: +Y up, front facing +Z.
    to_gltf = np.linalg.inv(orientation_matrix(up="+y", front="+z"))
    transformed(indexer(), to_gltf).export(path)
    mesh = transformed(load_mesh(path), orientation_matrix(up="+y", front="+z"))
    assert np.allclose(mesh.bounds, indexer().bounds, atol=1e-5)


def test_radial_profile_finds_the_spindle_radius(indexer) -> None:
    profile = radial_profile(indexer(), (0, 0, 0.2), (1, 0, 0), slices=26, max_radius=1.0)
    in_front = [s.radius for s in profile if s.t > 1.05]
    # a 32-sided cylinder of radius 0.4: its faces lie between r = 0.4 cos(pi/32) and 0.4
    assert in_front and all(0.4 * math.cos(math.pi / 32) - 1e-9 <= r <= 0.4 for r in in_front)
    behind = [s.radius for s in profile if -0.9 < s.t < 0.9]
    assert all(math.isclose(r, 1.0, abs_tol=0.02) for r in behind)  # the box, cut off by the window


def test_split_by_cylinder_separates_body_and_spindle(indexer) -> None:
    body, spindle = split_by_cylinder(indexer(), (0, 0, 0.2), (1, 0, 0), radius=0.45, t_start=1.0)
    assert spindle.bounds[0][0] >= 1.0 - 1e-9 and math.isclose(spindle.bounds[1][0], 1.6)
    assert np.allclose(body.bounds, [[-1, -1.5, -1], [1, 1.5, 1]])
    assert len(body.faces) + len(spindle.faces) == len(indexer().faces)


def test_split_must_cut_something(indexer) -> None:
    with pytest.raises(ValueError, match="some, but not all"):
        split_by_cylinder(indexer(), (0, 0, 0.2), (1, 0, 0), radius=0.45, t_start=5.0)


def test_render_views_writes_pngs_with_content(tmp_path: Path, indexer) -> None:
    paths = render_views(indexer(), tmp_path, size=64, samples=20_000)
    assert set(paths) == {"front", "left", "back", "right", "top", "iso", "sheet"}
    assert read_png_size(paths["front"]) == (64, 64)
    assert read_png_size(paths["sheet"]) == (192, 128)
    # the front view sees the spindle disc: some pixels are drawn, the corners stay background
    raw = zlib.decompress(paths["front"].read_bytes()[41:-12])
    pixels = np.frombuffer(raw, dtype=np.uint8).reshape(64, 65)[:, 1:]
    assert (pixels < 255).sum() > 200 and pixels[0, 0] == 255


def test_write_png_rejects_colour_images(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        write_png(tmp_path / "x.png", np.zeros((4, 4, 3), dtype=np.uint8))
