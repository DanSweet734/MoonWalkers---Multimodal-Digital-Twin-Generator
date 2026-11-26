"""Warnings for the faults behind haas/tm1@v4's rejection (decision 0041; the lab report's
section 8.3, gaps 2, 3 and 9), on a small synthetic machine built from boxes, never the run
folders: a v3-like spec stays quiet and a v4-like one warns.

The machine, in metres (model units are metres here): a body 1 x 1 x 1 m whose bottom is the
floor, a generated block on its front (the cut list removes it) and a stand-in table in its
place, sliding 0.3 m along +y. The v4-like machine also stands on a pedestal 0.2 x 0.2 x 0.25 m
under the body, and keeps a shard of the block in the table's way.
"""

from typing import Any

import numpy as np
import pytest
import trimesh

from moonwalkers.pipelines.b.parts_spec import PartsSpec, face_parts
from moonwalkers.pipelines.b.spec_warnings import (
    band_footprints,
    inside_shape,
    shard_warnings,
    slab_warnings,
    spec_warnings,
    travel_offsets,
)
from moonwalkers.pipelines.b.stand_ins import Solids

CITED = [{"source_id": "src-test", "locator": "test"}]
BLOCK = ((0.52, -0.2, 0.6), (0.72, 0.2, 0.7))  # the generated block, clear of the body
TABLE_AT = (0.62, 0.0, 0.65)  # the stand-in table, 0.2 x 0.4 x 0.1 m, centred there
SHARD = ((0.60, 0.28, 0.63), (0.64, 0.32, 0.67))  # a piece of the block left 0.3 m along


def box(lo: tuple[float, float, float], hi: tuple[float, float, float]) -> trimesh.Trimesh:
    lo_, hi_ = np.asarray(lo), np.asarray(hi)
    mesh = trimesh.creation.box(extents=hi_ - lo_)
    mesh.apply_translation((lo_ + hi_) / 2)
    return mesh


def machine(pedestal: bool, shard: bool) -> trimesh.Trimesh:
    lift = 0.25 if pedestal else 0.0
    meshes = [box((-0.5, -0.5, lift), (0.5, 0.5, 1.0 + lift))]  # the body
    meshes.append(box(BLOCK[0], BLOCK[1]).apply_translation((0, 0, lift)))  # the block
    if pedestal:
        meshes.append(box((-0.1, -0.1, 0.0), (0.1, 0.1, 0.26)))  # overlaps the body by 1 cm
    if shard:
        meshes.append(box(SHARD[0], SHARD[1]).apply_translation((0, 0, lift)))
    return trimesh.util.concatenate(meshes)


def spec(
    lift: float = 0.0,
    loose_pieces: str = "remove",
    size_checks: bool = True,
    base_z: float | None = 0.0,
) -> PartsSpec:
    lo, hi = BLOCK
    data: dict[str, Any] = {
        "up": "+z",
        "front": "+x",
        "origin_xy": [0.0, 0.0],
        "base_z": base_z,
        "scale": {"fact": "overall_height", "how": "the mesh's height"},
        "fixed_part": "frame",
        "cuts": [
            {
                "part": "generated_block",
                "shapes": [
                    {
                        "shape": "box",
                        "min": [lo[0] - 0.01, lo[1] - 0.01, lo[2] - 0.01 + lift],
                        "max": [hi[0] + 0.01, hi[1] + 0.01, hi[2] + 0.01 + lift],
                    }
                ],
            }
        ],
        "parts": [
            {
                "part_id": "frame",
                "name": "frame",
                "kind": "cut",
                "note": "test",
                "loose_pieces": loose_pieces,
            },
            {"part_id": "generated_block", "name": "block", "kind": "removed", "note": "test"},
            {
                "part_id": "table",
                "name": "Stand-in: table",
                "kind": "stand_in",
                "replaces": "generated_block",
                "at": [TABLE_AT[0], TABLE_AT[1], TABLE_AT[2] + lift],
                "shape": {
                    "kind": "solids",
                    "pieces": [{"shape": "box", "size_m": [0.2, 0.4, 0.1]}],
                },
                "note": "test",
                "citations": CITED,
            },
        ],
        "joints": [
            {
                "joint_id": "y_axis",
                "joint_type": "prismatic",
                "parent": "frame",
                "child": "table",
                "axis": [0.0, 1.0, 0.0],
                "point": [TABLE_AT[0], 0.0, TABLE_AT[2] + lift],
                "lower": 0.0,
                "upper": 0.3,
                "note": "test",
            }
        ],
        "size_checks": (
            [{"fact": "overall_width", "measured_model_units": 1.0, "how": "the body"}]
            if size_checks
            else []
        ),
        "decided_by": "test",
        "method": "synthetic",
    }
    return PartsSpec.model_validate(data)


def v3_like() -> tuple[trimesh.Trimesh, PartsSpec]:
    """As v3: the floor at the body's bottom, loose pieces removed, size checks given."""
    return machine(pedestal=False, shard=True), spec()


def v4_like() -> tuple[trimesh.Trimesh, PartsSpec]:
    """As v4: base_z unset over a pedestal, loose pieces kept, no size checks."""
    return (
        machine(pedestal=True, shard=True),
        spec(lift=0.25, loose_pieces="keep", size_checks=False, base_z=None),
    )


def refs(issues) -> list[str | None]:
    return [i.ref for i in issues]


def test_a_v3_like_spec_has_no_warnings() -> None:
    mesh, parts = v3_like()
    assert spec_warnings(mesh, parts, scale=1.0) == []


def test_a_v4_like_spec_warns_of_its_slab_its_shard_and_no_size_checks() -> None:
    mesh, parts = v4_like()
    issues = spec_warnings(mesh, parts, scale=1.0)
    assert refs(issues) == ["base_z", "frame", "size_checks"]
    assert all(i.severity == "warning" for i in issues)
    slab, shard, sizes = (i.message for i in issues)
    assert "base_z unset" in slab and "gap 2" in slab
    assert "inside the stand-in 'table'" in shard and "gap 3" in shard
    assert "with y_axis at 0." in shard  # found along the table's travel, not where it is
    assert "set_size_checks" in sizes


def test_the_slab_is_measured_from_above_band_by_band() -> None:
    mesh, parts = v4_like()
    areas = band_footprints(mesh, parts, face_parts(mesh, parts))
    assert areas[0] == pytest.approx(0.2 * 0.2)  # the pedestal alone
    assert areas[-1] == pytest.approx(1.0)  # the body alone at the top
    assert areas.max() == pytest.approx(1.0 * 1.14)  # the body and the shard beside it
    flat, _ = v3_like()
    assert slab_warnings(flat, spec(), face_parts(flat, spec())) == []


def test_a_base_set_at_the_floor_under_a_pedestal_still_warns() -> None:
    """Setting base_z alone is not the fix: what stands on it must be cut too."""
    mesh = machine(pedestal=True, shard=False)
    parts = spec(lift=0.25, base_z=0.0)
    assert refs(slab_warnings(mesh, parts, face_parts(mesh, parts))) == ["base_z"]


def test_a_shard_out_of_the_tables_way_or_removed_is_quiet() -> None:
    mesh = machine(pedestal=False, shard=False)
    loose = spec(loose_pieces="keep")
    assert shard_warnings(mesh, loose, face_parts(mesh, loose), 1.0) == []
    mesh, removed = v3_like()  # the shard is there, but loose pieces are removed
    assert shard_warnings(mesh, removed, face_parts(mesh, removed), 1.0) == []


def test_a_shard_is_found_only_where_the_travel_reaches() -> None:
    mesh = machine(pedestal=False, shard=True)
    short = spec(loose_pieces="keep")
    short.joints[0].upper = 0.05  # the table stops short of the shard (0.3 m along)
    assert shard_warnings(mesh, short, face_parts(mesh, short), 1.0) == []


def test_a_stand_ins_poses_start_where_it_is_modelled() -> None:
    _, parts = v4_like()
    poses = travel_offsets(parts.part("table"), {j.child: j for j in parts.joints})
    assert poses[0][1] == {} and np.allclose(poses[0][0], 0)
    assert len(poses) == 1 + 9
    assert poses[-1][1] == {"y_axis": 0.3}
    assert np.allclose(poses[-1][0], (0, 0.3, 0))


def test_points_inside_boxes_cylinders_and_turned_boxes() -> None:
    shape = Solids.model_validate(
        {
            "pieces": [
                {"shape": "box", "size_m": [0.2, 0.1, 0.1], "turn_deg": 90},  # now 0.1 along x
                {
                    "shape": "cylinder",
                    "radius_m": 0.05,
                    "length_m": 0.4,
                    "axis": [1, 0, 0],
                    "center_m": [1.0, 0.0, 0.0],
                },
            ]
        }
    )
    points = np.array(
        [[0.0, 0.09, 0.0], [0.09, 0.0, 0.0], [1.19, 0.0, 0.04], [1.0, 0.06, 0.0], [0.5, 0, 0]]
    )
    assert inside_shape(shape, points).tolist() == [True, False, True, False, False]
