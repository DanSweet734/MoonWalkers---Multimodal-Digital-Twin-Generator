"""Method (b) of the drill-press plan's Phase 4: splitting a mesh by its own shape."""

import numpy as np
import trimesh

from moonwalkers.pipelines.b.mesh_segments import merge_small, pieces, sharp_regions


def test_pieces_are_the_separate_parts(indexer) -> None:
    segments = pieces(indexer())
    assert segments.max() == 1


def test_sharp_edges_split_a_box_into_its_sides() -> None:
    box = trimesh.creation.box().subdivide()  # each side 8 triangles, sides meet at 90 degrees
    segments = sharp_regions(box, angle_deg=30.0, min_share=0.0)
    assert segments.max() + 1 == 6
    assert set(np.bincount(segments)) == {8}


def test_a_gentle_angle_keeps_a_smooth_surface_whole() -> None:
    sphere = trimesh.creation.icosphere(subdivisions=3)  # neighbours meet at a few degrees
    assert sharp_regions(sphere, angle_deg=30.0).max() == 0


def test_small_regions_merge_into_the_neighbour_they_share_most_with() -> None:
    box = trimesh.creation.box().subdivide().subdivide()  # 192 faces, 32 per side
    segments = np.zeros(len(box.faces), dtype=int)
    top = box.triangles_center[:, 2] > 0.49
    segments[top] = 1
    speck = np.flatnonzero(top)[0]
    segments[speck] = 2  # one face alone, inside the top
    merged = merge_small(box, segments, min_faces=5)
    assert merged.max() == 1
    assert merged[speck] == merged[np.flatnonzero(top)[1]]
