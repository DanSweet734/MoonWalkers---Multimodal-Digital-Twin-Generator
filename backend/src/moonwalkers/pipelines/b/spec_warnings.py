"""Warnings for a several-part spec's faults that no validator sees (decision 0041): the faults
Daniel rejected ``haas/tm1@v4`` for (2026-11-18), found by the lab report's section 8.3:

- gap 2, **a base on a small slab**: the twin stands on a generated pedestal narrower than the
  machine (v4 left ``base_z`` unset and kept a block about 0.62 x 0.45 m, 0.25 m tall);
- gap 3, **shards where a moving part passes**: loose pieces of a kept cut part inside a stand-in
  that takes a removed part's place, anywhere along its travel (pieces of v4's generated table
  block through its stand-in table);
- gap 9, **no size checks**: a spec of several parts with no ``size_checks`` (v4's agent skipped
  ``set_size_checks``).

``preview_twin`` lists them among its issues and ``dry_run_twin`` in its ``spec_warnings``. They
do not change a dry run's ``clean``: each is a reason to look, and the agent fixes it or records
why not (decision 0041, Daniel's choice of 2026-11-25).
"""

from __future__ import annotations

import itertools
import math

import numpy as np
import trimesh

from moonwalkers.contracts.pipeline_result import Issue

from .mesh_tools import face_groups
from .parts_spec import PartsSpec, SpecPart, face_parts, removed_labels
from .stand_ins import BoxPiece, CylinderPiece, SlottedTable, Solids, table_distance

# [INFERENCE] Measured on 2026-11-25 (worklog): the bottom 5% of the height is 0.05 as wide as
# the widest band on v4, and 0.61 to 1.00 on haas/tm1@v3, haas/vf3@v1, igus/rebel6dof02@v3 and
# v5, and grizzly/t33901@v11. The box-and-cylinder drill press of the tests, on its cited 18 x
# 10.5 in base under wider handles, is 0.24: a real base can be that narrow, so the line is
# drawn between it and v4.
SLAB_BANDS = 20  # the height in bands of 5%
SLAB_RATIO = 0.15
# Steps along each sliding joint's travel at which a stand-in is placed to look for shards.
TRAVEL_STEPS = 9


def spec_warnings(mesh: trimesh.Trimesh, spec: PartsSpec, scale: float) -> list[Issue]:
    """The warnings for the oriented mesh ``mesh`` cut by ``spec`` at ``scale`` metres per model
    unit (``assemble_parts``' scale)."""
    labels = face_parts(mesh, spec)
    return [
        *slab_warnings(mesh, spec, labels),
        *shard_warnings(mesh, spec, labels, scale),
        *size_check_warnings(spec),
    ]


def size_check_warnings(spec: PartsSpec) -> list[Issue]:
    if spec.size_checks:
        return []
    return [
        Issue(
            severity="warning",
            ref="size_checks",
            message=(
                "The spec has no size checks, so nothing compares the twin's parts with their "
                "cited sizes (the lab report's gap 9). Measure two or three cited lengths on the "
                "mesh (fit_circles, the inspect views) and give them with set_size_checks."
            ),
        )
    ]


def band_footprints(mesh: trimesh.Trimesh, spec: PartsSpec, labels: np.ndarray) -> np.ndarray:
    """The area of the box round the twin's kept mesh, seen from above, in each band of 5% of
    its height from the base plane up (model units squared): the box round every face that
    reaches into the band, so a tall face counts in each band it crosses."""
    kept = ~np.isin(labels, list(removed_labels(spec)))
    base = spec.base_z if spec.base_z is not None else float(mesh.bounds[0][2])
    triangles = mesh.triangles[kept]  # faces x 3 corners x 3
    z_low, z_high = triangles[:, :, 2].min(axis=1), triangles[:, :, 2].max(axis=1)
    above = z_high > base
    triangles, z_low, z_high = triangles[above], z_low[above], z_high[above]
    areas = np.zeros(SLAB_BANDS)
    if not len(triangles):
        return areas
    height = float(z_high.max()) - base
    xy_low, xy_high = triangles[:, :, :2].min(axis=1), triangles[:, :, :2].max(axis=1)
    for k in range(SLAB_BANDS):
        low, high = base + k * height / SLAB_BANDS, base + (k + 1) * height / SLAB_BANDS
        crossing = (z_low <= high) & (z_high >= low)
        if crossing.any():
            extent = xy_high[crossing].max(axis=0) - xy_low[crossing].min(axis=0)
            areas[k] = extent[0] * extent[1]
    return areas


def slab_warnings(mesh: trimesh.Trimesh, spec: PartsSpec, labels: np.ndarray) -> list[Issue]:
    areas = band_footprints(mesh, spec, labels)
    widest = float(areas.max())
    if widest == 0 or areas[0] >= SLAB_RATIO * widest:
        return []
    wide = int(np.argmax(areas >= 0.5 * widest))
    base = (
        f"base_z {spec.base_z}"
        if spec.base_z is not None
        else "base_z unset, so the mesh's lowest point"
    )
    return [
        Issue(
            severity="warning",
            ref="base_z",
            message=(
                f"The twin's lowest 5% of its height is {areas[0] / widest:.0%} as wide, seen "
                f"from above, as its widest; it widens to half at {wide * 5}% of the height "
                f"({base}). It may stand on a generated pedestal or slab that the photos do not "
                "show (the lab report's gap 2, haas/tm1@v4). If the machine stands on the floor "
                "or on its own base there, set base_z at that level with set_spec_frame and cut "
                "what is below as a removed part (haas/tm1@v3: base_z -0.75, a cut under z "
                "-0.763); else say why in an issue."
            ),
        )
    ]


def shard_warnings(
    mesh: trimesh.Trimesh, spec: PartsSpec, labels: np.ndarray, scale: float
) -> list[Issue]:
    """Loose pieces (all but the largest) of each cut part that keeps them, inside a stand-in
    that replaces a removed part, at its modelled place or anywhere along its sliding joints'
    travel."""
    base = spec.base_z if spec.base_z is not None else float(mesh.bounds[0][2])
    origin = np.array([*spec.origin_xy, base])
    centres_m = (mesh.triangles_center - origin) * scale  # the twin frame, metres
    parents = {j.child: j for j in spec.joints}
    replacing = [p for p in spec.parts if p.kind == "stand_in" and p.replaces is not None]
    issues = []
    for part in spec.parts:
        if part.kind != "cut" or part.loose_pieces != "keep":
            continue
        mine = labels == part.part_id
        if not mine.any():
            continue
        pairs = mesh.face_adjacency
        groups = face_groups(mesh, mine[pairs[:, 0]] & mine[pairs[:, 1]])
        ids, counts = np.unique(groups[mine], return_counts=True)
        loose = np.flatnonzero(mine & (groups != ids[counts.argmax()]))
        if not len(loose):
            continue
        for stand_in in replacing:
            hit = np.zeros(len(loose), dtype=bool)
            first: dict[str, float] | None = None  # the first pose with faces inside
            for offset, pose in travel_offsets(stand_in, parents):
                inside = inside_stand_in(stand_in, centres_m[loose] - offset, origin, scale)
                if inside.any() and first is None:
                    first = pose
                hit |= inside
            if not hit.any():
                continue
            sizes = sorted({int((groups == g).sum()) for g in groups[loose[hit]]})
            where = centres_m[loose[hit]].mean(axis=0) / scale + origin
            at = (
                "where it is modelled"
                if not first
                else "with " + ", ".join(f"{j} at {v:.4g}" for j, v in first.items())
            )
            issues.append(
                Issue(
                    severity="warning",
                    ref=part.part_id,
                    message=(
                        f"{hit.sum()} faces of loose pieces of '{part.part_id}' (pieces of "
                        f"{', '.join(map(str, sizes))} faces) lie inside the stand-in "
                        f"'{stand_in.part_id}', which replaces '{stand_in.replaces}', first "
                        f"{at}; about ({', '.join(f'{v:.3f}' for v in where)}) in model units. "
                        "Either the cut list left shards of the removed part in a kept part "
                        "(the lab report's gap 3, haas/tm1@v4): set loose_pieces 'remove' on "
                        f"'{part.part_id}' or cut them into the removed part; or the stand-in "
                        "passes into the machine there: check its place and travel, and record "
                        "it as an issue if it stays."
                    ),
                )
            )
    return issues


def travel_offsets(stand_in: SpecPart, parents: dict) -> list[tuple[np.ndarray, dict[str, float]]]:
    """Where the stand-in can be moved, as offsets in metres with the sliding joints' positions
    that give them: its modelled place first, then steps along each sliding joint's travel from
    it up its chain. A turning joint keeps its modelled pose [INFERENCE: v4's shards were in
    sliding parts' way]."""
    travel = []
    node = stand_in.part_id
    while node in parents:
        joint = parents[node]
        if joint.joint_type == "prismatic" and joint.lower is not None and joint.upper is not None:
            axis = np.asarray(joint.axis, dtype=float) / np.linalg.norm(joint.axis)
            steps = np.linspace(joint.lower, joint.upper, TRAVEL_STEPS)
            travel.append([(joint.joint_id, float(t), axis * t) for t in steps])
        node = joint.parent
    poses: list[tuple[np.ndarray, dict[str, float]]] = [(np.zeros(3), {})]
    for combo in itertools.product(*travel):
        poses.append((np.sum([c[2] for c in combo], axis=0), {joint: t for joint, t, _ in combo}))
    return poses


def inside_stand_in(
    stand_in: SpecPart, points_m: np.ndarray, origin: np.ndarray, scale: float
) -> np.ndarray:
    """Which ``points_m`` (twin frame, metres) are inside the stand-in's shape where the spec
    places it: the inverse of ``stand_ins.placed``."""
    assert stand_in.shape is not None and stand_in.at is not None
    at_m = (np.asarray(stand_in.at) - origin) * scale
    local = rotate_z(points_m - at_m, -stand_in.turn_deg)
    return inside_shape(stand_in.shape, local)


def inside_shape(shape: Solids | SlottedTable, p: np.ndarray) -> np.ndarray:
    """Which points ``p`` (N x 3, the shape's own frame, metres) are inside it."""
    if isinstance(shape, SlottedTable):
        return table_distance(shape, p) < 0
    inside = np.zeros(len(p), dtype=bool)
    for piece in shape.pieces:
        for i in range(piece.repeat):
            centre = np.asarray(piece.center_m) + np.asarray(piece.step_m) * i
            inside |= inside_piece(piece, p - centre)
    return inside


def inside_piece(piece: BoxPiece | CylinderPiece, p: np.ndarray) -> np.ndarray:
    """Which points ``p``, relative to the piece's centre, are inside it."""
    if isinstance(piece, BoxPiece):
        if piece.turn_deg:
            matrix = trimesh.transformations.rotation_matrix(
                math.radians(-piece.turn_deg), piece.turn_axis
            )[:3, :3]
            p = p @ matrix.T
        return np.all(np.abs(p) <= np.asarray(piece.size_m) / 2, axis=1)
    axis = np.asarray(piece.axis, dtype=float) / np.linalg.norm(piece.axis)
    along = p @ axis
    radial = np.linalg.norm(p - np.outer(along, axis), axis=1)
    return (np.abs(along) <= piece.length_m / 2) & (radial <= piece.radius_m)


def rotate_z(p: np.ndarray, degrees: float) -> np.ndarray:
    c, s = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
    return p @ np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]]).T
