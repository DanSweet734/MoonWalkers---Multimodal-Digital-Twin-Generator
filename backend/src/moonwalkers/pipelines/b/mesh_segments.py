"""Split a mesh by its own shape, with no shapes or photos (drill-press plan Phase 4, method b).

- ``pieces``: the mesh's separate pieces. A generated mesh is usually one piece, since the
  generator fuses touching parts into one surface.
- ``sharp_regions``: regions bounded by sharp edges, where the faces on either side meet at more
  than ``angle_deg``. Regions smaller than ``min_share`` of the faces are merged into the
  neighbour they share most edge length with, so specks along a crease do not count as parts.

Both return unnamed segments: someone still has to say which part each one is.
"""

from __future__ import annotations

import numpy as np
import trimesh

from .mesh_tools import face_groups


def pieces(mesh: trimesh.Trimesh) -> np.ndarray:
    """A segment number per face: the mesh's separate pieces."""
    return face_groups(mesh)


def sharp_regions(
    mesh: trimesh.Trimesh, angle_deg: float = 30.0, min_share: float = 0.002
) -> np.ndarray:
    """A segment number per face: regions between edges sharper than ``angle_deg``, small ones
    merged into their neighbours."""
    smooth = np.degrees(mesh.face_adjacency_angles) <= angle_deg
    return merge_small(mesh, face_groups(mesh, smooth), max(1, int(min_share * len(mesh.faces))))


def merge_small(mesh: trimesh.Trimesh, segments: np.ndarray, min_faces: int) -> np.ndarray:
    """``segments`` with every segment under ``min_faces`` merged into the larger neighbour it
    shares the longest boundary with, in rounds, until no small segment has a larger neighbour.
    Merging only into larger segments (ties broken by number) means merges never form a loop."""
    segments = np.unique(np.asarray(segments), return_inverse=True)[1]
    pairs = mesh.face_adjacency
    length = np.linalg.norm(np.diff(mesh.vertices[mesh.face_adjacency_edges], axis=1)[:, 0], axis=1)
    while True:
        sizes = np.bincount(segments)
        count = len(sizes)
        a, b = segments[pairs[:, 0]], segments[pairs[:, 1]]
        across = a != b
        # Both directions of every boundary edge: (segment, neighbour, length).
        own = np.concatenate([a[across], b[across]])
        other = np.concatenate([b[across], a[across]])
        weight = np.concatenate([length[across], length[across]])
        rank = sizes * count + np.arange(count)  # larger segments rank higher; ties by number
        keep = (sizes[own] < min_faces) & (rank[other] > rank[own])
        if not keep.any():
            return np.unique(segments, return_inverse=True)[1]
        keys, where = np.unique(own[keep] * count + other[keep], return_inverse=True)
        totals = np.bincount(where, weights=weight[keep])
        order = np.lexsort((-totals, keys // count))  # by segment, longest boundary first
        first = np.r_[True, np.diff(keys[order] // count) != 0]
        target = np.arange(count)
        target[keys[order][first] // count] = keys[order][first] % count
        while not np.array_equal(target, target[target]):
            target = target[target]
        segments = target[segments]
