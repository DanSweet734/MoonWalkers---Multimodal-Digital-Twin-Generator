"""Coloured views and photo overlays for a reviewer (decision 0023), moved out of the Phase 4
spike in Phase 5, and the views of a several-part spec."""

import struct
from pathlib import Path

import numpy as np
import pytest
import trimesh

from moonwalkers.pipelines.b import photo_marks
from moonwalkers.pipelines.b.mesh_tools import read_png
from moonwalkers.pipelines.b.part_views import (
    FIT_PHOTO_PIXELS,
    fit_fed_photos,
    fit_photo,
    part_colours,
    photo_overlay,
    twin_scene,
    write_rgb_png,
    write_spec_views,
)
from moonwalkers.pipelines.b.parts_spec import PartsSpec
from moonwalkers.pipelines.b.stand_ins import Solids


def test_write_rgb_png_checks_its_input(tmp_path: Path) -> None:
    write_rgb_png(tmp_path / "x.png", np.zeros((2, 3, 3), dtype=np.uint8))
    assert struct.unpack(">II", (tmp_path / "x.png").read_bytes()[16:24]) == (3, 2)
    with pytest.raises(ValueError):
        write_rgb_png(tmp_path / "y.png", np.zeros((2, 3), dtype=np.uint8))


def test_the_fixed_part_is_grey_and_the_others_are_coloured() -> None:
    mesh = trimesh.creation.box()
    parts = ["body"] * 6 + ["arm"] * 6
    colours, legend = part_colours(mesh, parts, fixed="body")
    assert tuple(colours[0]) == (190, 190, 190)
    assert tuple(colours[-1]) != (190, 190, 190)
    assert legend[0].startswith("body:")


def test_a_twin_of_twenty_parts_gets_a_colour_each() -> None:
    mesh = trimesh.creation.icosphere(subdivisions=2)  # 320 faces, 16 per part
    parts = ["frame"] + [f"part_{i:02d}" for i in range(19)]
    labels = [parts[i % 20] for i in range(len(mesh.faces))]
    _, legend = part_colours(mesh, labels, fixed="frame")
    colours = [line.split(": ")[1] for line in legend]
    assert len(legend) == 20 and len(set(colours)) == 20


def two_boxes_spec() -> PartsSpec:
    """A 'mesh' of two boxes: the left one stays, the right one is cut out and replaced by a
    stand-in rod at x = 2."""
    return PartsSpec.model_validate(
        {
            "up": "+z",
            "front": "+x",
            "origin_xy": [0.0, 0.0],
            "scale": {"fact": "overall_depth", "how": "x extent"},
            "fixed_part": "frame",
            "cuts": [
                {
                    "part": "old_rod",
                    "shapes": [{"shape": "box", "min": [1.5, -1, -1], "max": [3, 1, 1]}],
                }
            ],
            "parts": [
                {"part_id": "frame", "name": "frame", "kind": "cut", "note": "t"},
                {"part_id": "old_rod", "name": "old", "kind": "removed", "note": "t"},
                {
                    "part_id": "rod",
                    "name": "rod",
                    "kind": "stand_in",
                    "note": "t",
                    "at": [2.0, 0.0, 0.0],
                    "replaces": "old_rod",
                    "citations": [{"source_id": "s"}],
                    "shape": Solids(
                        pieces=[{"shape": "cylinder", "radius_m": 0.1, "length_m": 0.5}]
                    ).model_dump(),
                },
            ],
            "joints": [
                {
                    "joint_id": "j",
                    "joint_type": "fixed",
                    "parent": "frame",
                    "child": "rod",
                    "axis": [0, 0, 1],
                    "point": [2, 0, 0],
                    "note": "t",
                }
            ],
            "decided_by": "test",
            "method": "test",
        }
    )


def two_boxes() -> trimesh.Trimesh:
    left = trimesh.creation.box(extents=(1, 1, 1))
    right = trimesh.creation.box(extents=(1, 1, 1))
    right.apply_translation((2, 0, 0))
    return trimesh.util.concatenate([left, right])


def test_the_twin_scene_drops_removed_faces_and_adds_stand_ins_in_model_units() -> None:
    scene, names = twin_scene(two_boxes(), two_boxes_spec(), scale=0.5)
    assert set(names) == {"frame", "rod"}
    rod = scene.submesh([np.flatnonzero(names == "rod")], append=True)
    # 0.5 m long at 0.5 m per model unit: one model unit, standing at x = 2
    assert rod.extents == pytest.approx([0.4, 0.4, 1.0], abs=0.01)
    assert rod.bounds.mean(axis=0) == pytest.approx([2.0, 0.0, 0.0], abs=0.01)
    assert len(names) == 12 + len(rod.faces)  # the removed box's 12 faces are gone


def test_spec_views_are_written_for_the_reviewer(tmp_path: Path) -> None:
    views = write_spec_views(two_boxes(), two_boxes_spec(), 0.5, tmp_path, size=48)
    assert set(views) == {"cuts", "parts", "part_rod"}
    assert all(p.is_file() for p in views.values())
    legend = (tmp_path / "cuts.txt").read_text(encoding="utf-8")
    assert "(removed) old_rod" in legend


def test_without_prepared_photos_there_is_nothing_to_place(tmp_path: Path) -> None:
    assert fit_fed_photos(two_boxes(), tmp_path / "prepared", 0.0) == []


def test_a_large_photo_is_fitted_on_a_reduced_copy_and_a_small_one_as_it_is() -> None:
    large = np.zeros((4000, 3000, 4), dtype=np.uint8)  # the lab's photos, upright
    assert fit_photo(large).shape == (800, 600, 4)  # every 5th pixel
    assert fit_photo(np.zeros((4001, 10, 4), dtype=np.uint8)).shape[0] <= FIT_PHOTO_PIXELS
    small = np.zeros((600, 800, 4), dtype=np.uint8)
    assert fit_photo(small) is small


def test_the_fed_photos_are_fitted_on_reduced_copies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    masks = []

    def fit_camera(mesh, mask, azimuths, elevations):  # the search itself takes about 50 s
        masks.append(mask)
        return photo_marks.PhotoFit(azimuth_deg=90.0, elevation_deg=0.0, iou=0.9)

    monkeypatch.setattr(photo_marks, "fit_camera", fit_camera)
    prepared = tmp_path / "prepared"
    prepared.mkdir()
    photo = np.zeros((1700, 1700, 4), dtype=np.uint8)
    photo[500:1200, 100:1600, :] = 200
    write_rgba_png(prepared / "left.png", photo)
    (fitted,) = fit_fed_photos(two_boxes(), prepared, 0.0)
    assert fitted.slot == "left" and fitted.photo.shape == (567, 567, 4)  # every 3rd pixel
    assert masks[0].shape == (567, 567) and masks[0].dtype == bool


def write_rgba_png(path: Path, rgba: np.ndarray) -> None:
    """An RGBA PNG with the standard library, as the generator's prepared photos are."""
    import zlib

    rows = b"".join(b"\x00" + row.tobytes() for row in rgba)
    height, width = rgba.shape[:2]

    def chunk(kind: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(kind + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc)

    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(rows))
    path.write_bytes(png + chunk(b"IEND", b""))


def test_an_overlay_draws_the_scene_through_the_fitted_camera(tmp_path: Path) -> None:
    mesh = two_boxes()
    photo = np.zeros((64, 64, 4), dtype=np.uint8)
    photo[20:44, 4:60, :] = 200  # a wide silhouette, as the camera from +Y sees both boxes
    fit = photo_marks.PhotoFit(azimuth_deg=90.0, elevation_deg=0.0, iou=1.0)
    scene, names = twin_scene(mesh, two_boxes_spec(), scale=0.5)
    path = photo_overlay(mesh, names, photo, fit, tmp_path / "on", scene)
    image = read_png(path)
    assert image.shape == (64, 64, 3)
    assert (image == (255, 0, 255)).all(axis=2).any()  # the outline
