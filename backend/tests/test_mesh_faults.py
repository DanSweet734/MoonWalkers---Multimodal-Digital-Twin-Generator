"""What NVIDIA's asset validator would warn about in a part's mesh, found before building (the lab's
machines plan, tool gap 5). The definitions follow omniverse-asset-validator 1.18.0; on 2026-11-09
they gave the same counts as its ``check_manifold_elements`` on 17 T33901 parts and on 12 broken
face subsets of a generated mesh (worklog)."""

from pathlib import Path

import numpy as np
import trimesh

from moonwalkers.pipelines.b.inspection import fault_issue, part_fault_issues
from moonwalkers.pipelines.b.mesh_tools import MeshFaults, mesh_faults


def corner_to_corner() -> trimesh.Trimesh:
    """Two unit boxes touching at one corner, (0.5, 0.5, 0.5): a non-manifold point."""
    a, b = trimesh.creation.box(), trimesh.creation.box()
    b.apply_translation([1.0, 1.0, 1.0])
    mesh = trimesh.util.concatenate([a, b])
    mesh.merge_vertices()
    return mesh


def test_a_closed_box_is_clean() -> None:
    faults = mesh_faults(trimesh.creation.box())
    assert faults == MeshFaults(0, 0, (), True)
    assert faults.clean


def test_two_solids_touching_at_a_point_make_it_non_manifold() -> None:
    faults = mesh_faults(corner_to_corner())
    assert faults.nonmanifold_points == ((0.5, 0.5, 0.5),)
    assert faults.nonmanifold_edges == 0
    assert not faults.clean


def test_a_face_with_two_corners_on_one_point_has_zero_area() -> None:
    box = trimesh.creation.box()
    mesh = trimesh.Trimesh(box.vertices, np.vstack([box.faces, [[0, 0, 1]]]), process=False)
    assert mesh_faults(mesh).zero_area_faces == 1


def test_three_faces_on_one_edge() -> None:
    fin = trimesh.Trimesh(
        [[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1]],
        [[0, 1, 2], [1, 0, 3], [0, 1, 4]],
        process=False,
    )
    faults = mesh_faults(fin)
    assert faults.nonmanifold_edges == 1
    assert faults.nonmanifold_points == ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0))  # as the validator


def test_a_face_turned_over_breaks_the_winding() -> None:
    box = trimesh.creation.box()
    faces = box.faces.copy()
    faces[0] = faces[0][::-1]
    assert not mesh_faults(trimesh.Trimesh(box.vertices, faces, process=False)).winding_consistent


def test_a_point_no_face_uses_counts_as_the_validator_counts_it() -> None:
    box = trimesh.creation.box()
    mesh = trimesh.Trimesh(np.vstack([box.vertices, [[9, 9, 9]]]), box.faces, process=False)
    assert mesh_faults(mesh).nonmanifold_points == ((9.0, 9.0, 9.0),)


def test_the_preview_names_each_faulty_part_with_its_points_in_model_units(
    tmp_path: Path,
) -> None:
    clean, faulty = tmp_path / "clean.glb", tmp_path / "faulty.glb"
    trimesh.creation.box().export(clean)
    corner_to_corner().export(faulty)  # read back as the exporter reads it
    (issue,) = part_fault_issues(
        [("frame", clean), ("arm", faulty)], origin=(1.0, 2.0, 3.0), scale=0.5
    )
    assert issue.ref == "arm" and issue.severity == "warning"
    # 0.5 m at 0.5 m per model unit is 1 model unit, from the origin (1, 2, 3)
    assert "1 non-manifold point(s) (model units, oriented): (+2.0000, +3.0000, +4.0000)" in (
        issue.message
    )


def test_a_long_list_of_points_is_cut_short() -> None:
    points = tuple((float(i), 0.0, 0.0) for i in range(20))
    issue = fault_issue("base", MeshFaults(40, 2, points, False), None, 1.0)
    assert "40 zero-area face(s)" in issue.message
    assert "2 edge(s) with more than two faces" in issue.message
    assert "20 non-manifold point(s) (m)" in issue.message and "and 12 more" in issue.message
    assert "wound opposite ways" in issue.message
