"""Pipeline B mesh tools on a synthetic 'indexer': a box body with a cylinder spindle along +X."""

import math
import struct
import zlib
from pathlib import Path

import numpy as np
import pytest
import trimesh

from moonwalkers.pipelines.b.mesh_tools import (
    box_within,
    direction_of,
    face_groups,
    fit_circles_across,
    fit_circles_along,
    footprint_angle,
    load_mesh,
    orientation_matrix,
    radial_profile,
    read_png,
    render_views,
    slice_axes,
    split_by_cylinder,
    tip_slabs,
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


@pytest.mark.parametrize("yaw", [45.0, -37.3, 90.0, 180.0])
def test_yaw_turns_a_front_at_that_angle_back_onto_x(yaw) -> None:
    rotation = orientation_matrix("+z", "+x", yaw)
    front = (math.cos(math.radians(yaw)), math.sin(math.radians(yaw)), 0.0)
    assert np.allclose(rotation @ np.array(front), (1, 0, 0))
    assert np.allclose(rotation @ np.array((0, 0, 1)), (0, 0, 1))  # up stays up
    assert math.isclose(np.linalg.det(rotation), 1.0)


def test_no_yaw_leaves_the_orientation_exact() -> None:
    assert np.array_equal(orientation_matrix("+y", "+z", 0.0), orientation_matrix("+y", "+z"))


def test_footprint_angle_gives_the_base_long_axis(indexer) -> None:
    mesh = indexer()  # the box is 2 deep (x) and 3 wide (y)
    assert footprint_angle(mesh) == pytest.approx(90.0, abs=1.0)
    for turn in (30.0, -50.0):
        turned = mesh.copy()
        turned.apply_transform(
            trimesh.transformations.rotation_matrix(math.radians(turn), (0, 0, 1))
        )
        expected = (90.0 + turn + 90.0) % 180.0 - 90.0  # folded into (-90, 90]
        assert footprint_angle(turned) == pytest.approx(expected, abs=1.0)


def test_a_square_footprint_has_no_long_axis() -> None:
    assert footprint_angle(trimesh.creation.box(extents=(2.0, 2.0, 1.0))) is None


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


def test_tip_slabs_find_the_spindle_axis(indexer) -> None:
    slabs = tip_slabs(indexer(), depths=(0.01, 0.1))
    for slab in slabs:  # only the spindle's front ring is within 0.1 of its tip at x = 1.6
        assert slab.axis_yz == pytest.approx((0.0, 0.2), abs=1e-9)
        assert slab.radius == pytest.approx(0.4, abs=1e-9)
    assert slabs[0].count > 0 and slabs[0].depth == 0.01


# ---------------------------------------------------------------- face groups (drill-press Phase 4)
def test_face_groups_finds_separate_pieces(indexer) -> None:
    mesh = indexer()  # a box and a cylinder, side by side
    groups = face_groups(mesh)
    assert groups.max() == 1
    assert len(set(groups[:12])) == 1  # the box's 12 triangles are one piece


def test_face_groups_uses_only_the_joined_edges() -> None:
    box = trimesh.creation.box()
    assert len(set(face_groups(box))) == 1
    alone = face_groups(box, np.zeros(len(box.face_adjacency), dtype=bool))
    assert len(set(alone)) == len(box.faces)


# ------------------------------------------------------------------------------- reading PNGs
def _png(width: int, height: int, colour: int, rows: list[bytes]) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
        )

    header = struct.pack(">IIBBBBB", width, height, 8, colour, 0, 0, 0)
    body = zlib.compress(b"".join(rows))
    return (
        b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", body) + chunk(b"IEND", b"")
    )


def _filtered(kind: int, row: np.ndarray, above: np.ndarray, step: int) -> bytes:
    """``row`` encoded with PNG filter ``kind`` (the inverse of what read_png undoes)."""
    out = []
    for i, value in enumerate(row.tolist()):
        a = int(row[i - step]) if i >= step else 0
        b = int(above[i])
        c = int(above[i - step]) if i >= step else 0
        if kind == 0:
            predicted = 0
        elif kind == 1:
            predicted = a
        elif kind == 2:
            predicted = b
        elif kind == 3:
            predicted = (a + b) // 2
        else:
            p = a + b - c
            pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
            predicted = a if pa <= pb and pa <= pc else b if pb <= pc else c
        out.append((value - predicted) % 256)
    return bytes([kind, *out])


def test_read_png_undoes_every_row_filter(tmp_path: Path) -> None:
    rng = np.random.default_rng(1)
    image = rng.integers(0, 256, size=(10, 7, 4), dtype=np.uint8)
    flat = image.reshape(10, -1)
    rows, above = [], np.zeros(flat.shape[1], dtype=np.uint8)
    for y in range(10):
        rows.append(_filtered(y % 5, flat[y], above, 4))  # filters 0-4 in turn
        above = flat[y]
    path = tmp_path / "filtered.png"
    path.write_bytes(_png(7, 10, 6, rows))
    assert np.array_equal(read_png(path), image)


def test_read_png_reads_what_write_png_writes(tmp_path: Path) -> None:
    image = np.arange(48, dtype=np.uint8).reshape(6, 8)
    write_png(tmp_path / "grey.png", image)
    assert np.array_equal(read_png(tmp_path / "grey.png")[..., 0], image)


def test_read_png_refuses_other_files(tmp_path: Path) -> None:
    (tmp_path / "x.png").write_bytes(b"not a png")
    with pytest.raises(ValueError, match="not a PNG"):
        read_png(tmp_path / "x.png")


@pytest.mark.parametrize("axis", ["x", "y", "z"])
def test_circles_are_fitted_across_any_axis(axis: str) -> None:
    """The drill press's column and quill stand along z (drill-press plan, Phase 5)."""
    rod = trimesh.creation.cylinder(radius=0.3, height=2.0, sections=64)  # along z
    turn = {"x": ((0, 1, 0), math.pi / 2), "y": ((1, 0, 0), math.pi / 2), "z": ((0, 0, 1), 0.0)}
    direction, angle = turn[axis]
    rod.apply_transform(trimesh.transformations.rotation_matrix(angle, direction))
    rod.apply_translation((0.1, -0.2, 0.3))
    index = "xyz".index(axis)
    position = (0.1, -0.2, 0.3)[index] + 0.5
    ((fit, centre),) = fit_circles_along(rod, axis, [position])
    assert fit.round and fit.radius == pytest.approx(0.3, abs=0.01)
    expected = [0.1, -0.2, 0.3]
    expected[index] = position
    assert centre == pytest.approx(expected, abs=0.01)


def two_rods() -> tuple[trimesh.Trimesh, np.ndarray]:
    """A thick upright rod at the origin and a thin rod tilted 30 degrees in x-z, at x = 0.6:
    a slice across z cuts both, as a slice across an arm cuts several links."""
    upright = trimesh.creation.cylinder(radius=0.15, height=1.0, sections=96)
    tilt = trimesh.transformations.rotation_matrix(math.radians(30), (0, 1, 0))
    tilted = trimesh.creation.cylinder(radius=0.05, height=1.0, sections=96)
    tilted.apply_transform(tilt)
    tilted.apply_translation((0.6, 0.0, 0.0))
    return trimesh.util.concatenate([upright, tilted]), tilt[:3, :3] @ (0.0, 0.0, 1.0)


def test_a_box_keeps_one_part_of_a_slice_that_crosses_several() -> None:
    """The lab's machines plan, tool gap 4."""
    rods, _ = two_rods()
    ((whole, _),) = fit_circles_along(rods, "z", [0.0])
    assert whole.radius == pytest.approx(0.15, abs=0.01)  # the larger part wins
    box = box_within({"x": (0.3, 1.0)})
    ((boxed, centre),) = fit_circles_along(rods, "z", [0.0], box=box)
    assert boxed.radius is not None and boxed.radius > 0.05  # the thin rod's ellipse
    assert centre == pytest.approx((0.6, 0.0, 0.0), abs=0.01)


def test_a_slice_across_a_tilted_part_measures_its_true_radius() -> None:
    rods, direction = two_rods()
    position = float(np.dot((0.6, 0.0, 0.1), direction))  # a point on its axis
    box = box_within({"x": (0.3, 1.0)})
    ((fit, centre),) = fit_circles_across(rods, direction, [position], box=box)
    assert fit.round and fit.radius == pytest.approx(0.05, abs=0.002)
    assert np.dot(centre, direction) == pytest.approx(position, abs=1e-9)
    base = np.array([0.6, 0.0, 0.0])  # where the rod's axis crosses z = 0
    axis_point = base + direction * (position - float(base @ direction))
    assert centre == pytest.approx(tuple(axis_point), abs=0.003)


@pytest.mark.parametrize("axis", ["x", "y", "z"])
def test_slices_across_an_axis_direction_are_the_slices_along_it(axis: str) -> None:
    rods, _ = two_rods()
    direction = direction_of(axis)
    assert fit_circles_across(rods, direction, [0.1]) == fit_circles_along(rods, axis, [0.1])


def test_the_slice_axes_are_right_handed_and_square() -> None:
    for direction in ((1, 2, 3), (0, 0, -1), (-0.2, 0.9, 0.1)):
        axes = slice_axes(direction)
        assert axes @ axes.T == pytest.approx(np.eye(3))
        assert np.linalg.det(axes) == pytest.approx(1.0)
        assert axes[0] == pytest.approx(np.asarray(direction) / np.linalg.norm(direction))


def test_bad_directions_and_ranges_are_refused() -> None:
    with pytest.raises(ValueError, match="not all zero"):
        slice_axes((0, 0, 0))
    with pytest.raises(ValueError, match="x, y, z or a direction"):
        direction_of("w")
    with pytest.raises(ValueError, match="three numbers"):
        direction_of([1.0, 0.0])
    with pytest.raises(ValueError, match="lowest value first"):
        box_within({"x": (1.0, 0.0)})
    with pytest.raises(ValueError, match="an axis, x, y or z"):
        box_within({"w": (0.0, 1.0)})
    assert box_within(None) is None and box_within({}) is None
