"""Mesh tools for Pipeline B: orient, render for inspection, measure, split, scale (decision 0012).

Twin frame: metres, +Z up, the machine's front (the HA5C's spindle nose) faces +X, so its width
runs along Y. ``orient`` brings a generator's mesh into this frame; the rest work in it.
"""

from __future__ import annotations

import itertools
import math
import struct
import zlib
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np
import trimesh

AXES: dict[str, tuple[float, float, float]] = {
    "+x": (1.0, 0.0, 0.0),
    "-x": (-1.0, 0.0, 0.0),
    "+y": (0.0, 1.0, 0.0),
    "-y": (0.0, -1.0, 0.0),
    "+z": (0.0, 0.0, 1.0),
    "-z": (0.0, 0.0, -1.0),
}

# Inspection views: (direction from the object to the camera, image-up direction), twin frame.
# The machine faces +X with Z up, so its own left side faces +Y.
VIEWS: dict[str, tuple[tuple[float, float, float], tuple[float, float, float]]] = {
    "front": ((1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
    "left": ((0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
    "back": ((-1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
    "right": ((0.0, -1.0, 0.0), (0.0, 0.0, 1.0)),
    "top": ((0.0, 0.0, 1.0), (1.0, 0.0, 0.0)),
    "iso": ((0.6, 0.5, 0.62), (0.0, 0.0, 1.0)),
}
SHEET_LAYOUT = (("front", "left", "back"), ("right", "top", "iso"))
# The base footprint (decision 0022) [INFERENCE]: the lowest 6% of the height held the T33901
# meshes' base plate, and a long axis under 1.1 times the short one is too round to tell a turn.
BASE_BAND = 0.06
FOOTPRINT_RATIO = 1.1


def load_mesh(path: Path) -> trimesh.Trimesh:
    """A mesh file (GLB, OBJ, PLY ...) as one triangle mesh, with scene transforms applied."""
    mesh = trimesh.load(Path(path), force="mesh")
    if not isinstance(mesh, trimesh.Trimesh) or len(mesh.faces) == 0:
        raise ValueError(f"{path} holds no triangle mesh")
    return mesh


def orientation_matrix(up: str, front: str, yaw_deg: float = 0.0) -> np.ndarray:
    """The rotation (3x3) that turns the mesh axis ``up`` into +Z and ``front`` into +X, then
    turns the mesh about +Z by ``-yaw_deg``: a machine front that pointed ``yaw_deg`` from +X
    towards +Y ends on +X (decision 0022, for photos that put the front between two axes)."""
    if up not in AXES or front not in AXES:
        raise ValueError(f"axes must be one of {sorted(AXES)}")
    z, x = np.array(AXES[up]), np.array(AXES[front])
    if abs(float(z @ x)) > 1e-9:
        raise ValueError(f"up ({up}) and front ({front}) must be perpendicular")
    y = np.cross(z, x)
    axes = np.stack([x, y, z])  # rows: the new axes in old coordinates
    if yaw_deg == 0.0:
        return axes
    turn = math.radians(-yaw_deg)
    about_z = np.array(
        [
            [math.cos(turn), -math.sin(turn), 0.0],
            [math.sin(turn), math.cos(turn), 0.0],
            [0.0, 0.0, 1.0],
        ]
    )
    return about_z @ axes


def footprint_angle(
    mesh: trimesh.Trimesh, band: float = BASE_BAND, samples: int = 100_000, seed: int = 0
) -> float | None:
    """The long axis of the mesh's base footprint, in degrees from +X towards +Y, in (-90, 90]:
    the principal direction of the surface in the lowest ``band`` of its height. None when the
    footprint has no long axis (round or square). It tells how far an upright mesh is turned
    from the axes, up to a multiple of 90° (decision 0022)."""
    points, _ = trimesh.sample.sample_surface(mesh, samples, seed=seed)
    low, high = float(mesh.bounds[0][2]), float(mesh.bounds[1][2])
    base = points[points[:, 2] <= low + band * (high - low)][:, :2]
    if len(base) < 3:
        return None
    eigenvalues, eigenvectors = np.linalg.eigh(np.cov((base - base.mean(axis=0)).T))
    if eigenvalues.min() <= 0 or math.sqrt(eigenvalues.max() / eigenvalues.min()) < FOOTPRINT_RATIO:
        return None
    major = eigenvectors[:, int(np.argmax(eigenvalues))]
    angle = math.degrees(math.atan2(float(major[1]), float(major[0])))
    if angle <= -90.0:
        angle += 180.0
    elif angle > 90.0:
        angle -= 180.0
    return round(angle, 1)


def transformed(mesh: trimesh.Trimesh, matrix: np.ndarray) -> trimesh.Trimesh:
    """A copy of ``mesh`` with a 3x3 or 4x4 transform applied."""
    full = np.eye(4)
    if matrix.shape == (3, 3):
        full[:3, :3] = matrix
    else:
        full = matrix
    copy = mesh.copy()
    copy.apply_transform(full)
    return copy


# ------------------------------------------------------------------------------------- render
def render_views(
    mesh: trimesh.Trimesh, out_dir: Path, size: int = 480, samples: int = 300_000, seed: int = 0
) -> dict[str, Path]:
    """Depth-shaded orthographic views of ``mesh`` as PNGs (all at one scale, white background),
    plus ``views.png``: front, left, back on the top row; right, top, iso below."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    points, faces = trimesh.sample.sample_surface(mesh, samples, seed=seed)
    normals = mesh.face_normals[faces]
    center = mesh.bounds.mean(axis=0)
    radius = float(np.linalg.norm(mesh.extents)) / 2.0
    images = {
        name: render_points(points, normals, view, up, size, center, radius)
        for name, (view, up) in VIEWS.items()
    }
    paths = {}
    for name, image in images.items():
        paths[name] = out_dir / f"view_{name}.png"
        write_png(paths[name], image)
    rows = [np.hstack([images[name] for name in row]) for row in SHEET_LAYOUT]
    paths["sheet"] = out_dir / "views.png"
    write_png(paths["sheet"], np.vstack(rows))
    return paths


def render_points(
    points: np.ndarray,
    normals: np.ndarray,
    toward_camera: Sequence[float],
    up: Sequence[float],
    size: int,
    center: np.ndarray,
    radius: float,
) -> np.ndarray:
    """An orthographic grey image of surface samples, nearest sample per pixel (z-buffer)."""
    d = np.asarray(toward_camera, dtype=float)
    d /= np.linalg.norm(d)
    u = np.asarray(up, dtype=float)
    u = u - (u @ d) * d
    u /= np.linalg.norm(u)
    r = np.cross(-d, u)  # image right, for a camera looking along -d
    rel = points - center
    scale = 0.5 * size * 0.95 / radius
    px = np.floor(rel @ r * scale + size / 2).astype(int)
    py = np.floor(size / 2 - rel @ u * scale).astype(int)
    depth = rel @ d
    shade = (60 + 195 * np.clip(normals @ d, 0.0, 1.0)).astype(np.uint8)

    image = np.full((size, size), 255, dtype=np.uint8)
    for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1)):  # 2x2 splats close small gaps
        x, y = px + dx, py + dy
        ok = (x >= 0) & (x < size) & (y >= 0) & (y < size)
        pixel = y[ok] * size + x[ok]
        order = np.lexsort((depth[ok], pixel))  # by pixel, then nearest last
        pixel, values = pixel[order], shade[ok][order]
        last = np.r_[pixel[1:] != pixel[:-1], True]
        flat = image.reshape(-1)
        keep = flat[pixel[last]] == 255  # first splat pass wins over later offsets
        flat[pixel[last][keep]] = values[last][keep]
    return image


def write_png(path: Path, image: np.ndarray) -> None:
    """Write an 8-bit greyscale image (H x W, uint8) as PNG using only the standard library."""
    if image.dtype != np.uint8 or image.ndim != 2:
        raise ValueError("write_png expects an H x W uint8 array")
    height, width = image.shape
    raw = b"".join(b"\x00" + image[row].tobytes() for row in range(height))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
        )

    header = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw, 9))
    Path(path).write_bytes(png + chunk(b"IEND", b""))


PNG_CHANNELS = {0: 1, 2: 3, 4: 2, 6: 4}  # colour type: grey, RGB, grey and alpha, RGBA


def read_png(path: Path) -> np.ndarray:
    """An 8-bit, non-interlaced PNG as an H x W x C uint8 array (C = 1, 2, 3 or 4 channels), using
    only the standard library: the backend has no image library. It undoes the five row filters
    of the PNG specification (https://www.w3.org/TR/png-3/, "Filtering")."""
    data = Path(path).read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path} is not a PNG")
    header, compressed, pos = None, [], 8
    while pos < len(data):
        length, kind = struct.unpack(">I4s", data[pos : pos + 8])
        body = data[pos + 8 : pos + 8 + length]
        if kind == b"IHDR":
            header = struct.unpack(">IIBBBBB", body)
        elif kind == b"IDAT":
            compressed.append(body)
        elif kind == b"IEND":
            break
        pos += 12 + length
    if header is None:
        raise ValueError(f"{path} has no header")
    width, height, depth, colour, _, _, interlace = header
    channels = PNG_CHANNELS.get(colour)
    if depth != 8 or channels is None or interlace:
        raise ValueError("read_png reads 8-bit, non-interlaced grey, RGB and RGBA PNGs")
    stride = width * channels
    raw = np.frombuffer(zlib.decompress(b"".join(compressed)), dtype=np.uint8)
    raw = raw.reshape(height, 1 + stride)
    image = np.zeros((height, stride), dtype=np.uint8)
    above = np.zeros(stride, dtype=np.int64)
    for y in range(height):
        kind, line = int(raw[y, 0]), raw[y, 1:].astype(np.int64)
        if kind == 0:
            row = line
        elif kind == 1:  # Sub: a running sum along the row, per channel
            row = np.cumsum(line.reshape(width, channels), axis=0).reshape(-1) % 256
        elif kind == 2:  # Up
            row = (line + above) % 256
        elif kind in (3, 4):  # Average, Paeth: each byte needs the one before it
            row = np.array(_unfilter(kind, line.tolist(), above.tolist(), channels))
        else:
            raise ValueError(f"unknown PNG filter {kind}")
        image[y] = row
        above = row.astype(np.int64)
    return image.reshape(height, width, channels)


def _unfilter(kind: int, line: list[int], above: list[int], step: int) -> list[int]:
    row = [0] * len(line)
    for i, value in enumerate(line):
        a = row[i - step] if i >= step else 0
        b = above[i]
        c = above[i - step] if i >= step else 0
        if kind == 3:
            row[i] = (value + (a + b) // 2) % 256
            continue
        p = a + b - c
        pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
        nearest = a if pa <= pb and pa <= pc else b if pb <= pc else c
        row[i] = (value + nearest) % 256
    return row


# ------------------------------------------------------------------------------------ measure
@dataclass(frozen=True)
class ProfileSlice:
    t: float  # position along the axis
    radius: float  # largest distance from the axis among samples in this slice (within limit)
    count: int  # surface samples in the slice


def radial_profile(
    mesh: trimesh.Trimesh,
    axis_point: Sequence[float],
    axis_dir: Sequence[float],
    slices: int = 40,
    max_radius: float | None = None,
    samples: int = 200_000,
    seed: int = 0,
) -> list[ProfileSlice]:
    """How far the surface reaches from an axis, slice by slice along it.

    Uses surface samples rather than vertices, so long faces (a coarse cylinder) still show up
    in every slice they cross. Samples farther than ``max_radius`` are ignored, so a wide body
    does not hide a narrow spindle in front of it.
    """
    a = np.asarray(axis_dir, dtype=float)
    a /= np.linalg.norm(a)
    points, _ = trimesh.sample.sample_surface(mesh, samples, seed=seed)
    rel = points - np.asarray(axis_point, dtype=float)
    t = rel @ a
    rho = np.linalg.norm(rel - np.outer(t, a), axis=1)
    if max_radius is not None:
        t, rho = t[rho <= max_radius], rho[rho <= max_radius]
    edges = np.linspace(t.min(), t.max(), slices + 1)
    profile = []
    for lo, hi in itertools.pairwise(edges):
        inside = (t >= lo) & (t <= hi)
        r = float(rho[inside].max()) if inside.any() else 0.0
        profile.append(ProfileSlice(t=float((lo + hi) / 2), radius=r, count=int(inside.sum())))
    return profile


@dataclass(frozen=True)
class TipSlab:
    """The vertices within ``depth`` of the mesh's front-most point (largest x)."""

    depth: float
    count: int
    axis_yz: tuple[float, float]  # the centre of their y-z bounding box
    radius: float  # their largest distance from that centre
    extent_yz: tuple[float, float]  # the bounding box's size: about equal for a round tip
    z_min: float  # their lowest point: at the mesh's bottom, they measured a base or feet


def tip_slabs(mesh: trimesh.Trimesh, depths: Sequence[float] = (0.01, 0.03, 0.06)) -> list[TipSlab]:
    """Where a round nose at the front (+X) is centred, from thin slabs behind its tip.

    Centres that agree across depths mean the tip is round about one line along X: the spindle
    axis. This is how the HA5C's axis was found (decision 0012). It assumes the spindle is the
    front-most part: when something else reaches further forward (the TH240's base feet), the
    slabs measure that instead, so use ``fit_circles`` (decision 0012, "Known limitation").
    """
    v = mesh.vertices
    x_max = float(v[:, 0].max())
    slabs = []
    for depth in depths:
        tip = v[v[:, 0] >= x_max - depth]
        cy = float(tip[:, 1].min() + tip[:, 1].max()) / 2
        cz = float(tip[:, 2].min() + tip[:, 2].max()) / 2
        radius = float(np.hypot(tip[:, 1] - cy, tip[:, 2] - cz).max())
        slabs.append(
            TipSlab(
                depth=depth,
                count=len(tip),
                axis_yz=(cy, cz),
                radius=radius,
                extent_yz=(float(np.ptp(tip[:, 1])), float(np.ptp(tip[:, 2]))),
                z_min=float(tip[:, 2].min()),
            )
        )
    return slabs


# ------------------------------------------------------------------------------------ circles
ROUND_COVERAGE = 0.75  # [INFERENCE] thresholds, from the HA5C and TH240 meshes (decision 0012)
ROUND_INLIERS = 0.25
SECTORS = 36  # coverage is counted in 10-degree sectors around the centre


@dataclass(frozen=True)
class CircleFit:
    """The circle that best fits the surface in a thin slice across X: a round part's outline."""

    x: float  # the slice's position
    samples: int  # surface samples in the slice
    centre_yz: tuple[float, float] | None  # None when the slice has too few samples
    radius: float | None
    inliers: float  # fraction of the slice's samples within the tolerance of the circle
    rms: float | None  # those samples' root-mean-square distance from the circle
    coverage: float  # fraction of 10-degree sectors around the centre holding an inlier
    round: bool  # coverage, inliers and rms all good enough to trust the centre


def fit_circles(
    mesh: trimesh.Trimesh,
    xs: Sequence[float],
    thickness: float | None = None,
    tolerance: float | None = None,
    samples: int = 400_000,
    iterations: int = 3000,
    seed: int = 0,
) -> list[CircleFit]:
    """A circle fitted to the surface in a slice at each x, to find a round part's axis.

    RANSAC: circles through random triples of the slice's surface samples are scored by how many
    samples lie within ``tolerance`` of them; the best is refined by least squares on those
    samples. So a round platter or nose is found even when feet, a cradle or a bore share the
    slice. Concentric rings (a nose and its bore) give the same centre. Both ``thickness`` and
    ``tolerance`` default to 1% of the mesh's largest extent. Seeded, so repeatable.
    """
    size = float(mesh.extents.max())
    thickness = 0.01 * size if thickness is None else thickness
    tolerance = 0.01 * size if tolerance is None else tolerance
    points, _ = trimesh.sample.sample_surface(mesh, samples, seed=seed)
    fits = []
    for x in xs:
        in_slice = points[np.abs(points[:, 0] - x) <= thickness / 2][:, 1:]
        rng = np.random.default_rng(seed)
        fits.append(_fit_circle(float(x), in_slice, tolerance, rng, iterations))
    return fits


# The coordinates in the order that puts the slicing axis first, keeping the frame right-handed.
_ALONG = {"x": (0, 1, 2), "y": (1, 2, 0), "z": (2, 0, 1)}


def fit_circles_along(
    mesh: trimesh.Trimesh, axis: Literal["x", "y", "z"], positions: Sequence[float], **options: Any
) -> list[tuple[CircleFit, tuple[float, float, float] | None]]:
    """``fit_circles`` in slices across any axis, for round parts that are not along X (the
    drill press's column and quill stand along Z). Each fit comes with its centre as a point in
    the mesh's frame, at the slice's position; ``CircleFit.x`` is that position along ``axis``
    and its ``centre_yz`` holds the other two coordinates in cyclic order (y, z; z, x; x, y)."""
    order = _ALONG[axis]
    permuted = trimesh.Trimesh(mesh.vertices[:, order], mesh.faces, process=False)
    fitted = []
    for fit in fit_circles(permuted, positions, **options):
        centre = None
        if fit.centre_yz is not None:
            point = [0.0, 0.0, 0.0]
            point[order[0]], point[order[1]], point[order[2]] = fit.x, *fit.centre_yz
            centre = (point[0], point[1], point[2])
        fitted.append((fit, centre))
    return fitted


def scan_positions(mesh: trimesh.Trimesh, count: int = 8) -> list[float]:
    """x positions over the front 5-40% of the mesh's length, back to front, where a spindle,
    platter or nose usually is [INFERENCE]: the default slices for a circle scan."""
    lo, hi = float(mesh.bounds[0][0]), float(mesh.bounds[1][0])
    return [hi - f * (hi - lo) for f in np.linspace(0.40, 0.05, count)]


def _fit_circle(
    x: float, p: np.ndarray, tolerance: float, rng: np.random.Generator, iterations: int
) -> CircleFit:
    empty = CircleFit(x, len(p), None, None, 0.0, None, 0.0, False)
    if len(p) < 3:
        return empty
    centres, radii = _circles_through_triples(p, rng, iterations)
    if len(centres) == 0:
        return empty
    best, best_count = 0, -1
    for start in range(0, len(centres), 200):  # chunks keep the distance matrix small
        dist = np.linalg.norm(p[None, :, :] - centres[start : start + 200, None, :], axis=2)
        counts = (np.abs(dist - radii[start : start + 200, None]) <= tolerance).sum(axis=1)
        if int(counts.max()) > best_count:
            best, best_count = start + int(counts.argmax()), int(counts.max())
    centre, radius = centres[best], float(radii[best])
    for _ in range(3):  # refine on the samples near the circle
        near = np.abs(np.linalg.norm(p - centre, axis=1) - radius) <= tolerance
        if near.sum() < 3:
            break
        centre, radius = _least_squares_circle(p[near])
    residual = np.linalg.norm(p - centre, axis=1) - radius
    near = np.abs(residual) <= tolerance
    if not near.any():
        return empty
    angles = np.arctan2(p[near, 1] - centre[1], p[near, 0] - centre[0])
    sectors = np.floor((angles + np.pi) / (2 * np.pi) * SECTORS).astype(int) % SECTORS
    coverage = len(np.unique(sectors)) / SECTORS
    inliers = float(near.mean())
    rms = float(np.sqrt(np.mean(residual[near] ** 2)))
    return CircleFit(
        x=x,
        samples=len(p),
        centre_yz=(float(centre[0]), float(centre[1])),
        radius=radius,
        inliers=inliers,
        rms=rms,
        coverage=coverage,
        round=coverage >= ROUND_COVERAGE and inliers >= ROUND_INLIERS and rms <= tolerance / 2,
    )


def _circles_through_triples(
    p: np.ndarray, rng: np.random.Generator, iterations: int
) -> tuple[np.ndarray, np.ndarray]:
    """Centres and radii of the circles through ``iterations`` random triples of points."""
    a, b, c = (p[rng.integers(0, len(p), size=iterations)] for _ in range(3))
    d = 2 * (
        a[:, 0] * (b[:, 1] - c[:, 1])
        + b[:, 0] * (c[:, 1] - a[:, 1])
        + c[:, 0] * (a[:, 1] - b[:, 1])
    )
    ok = np.abs(d) > 1e-12  # three points on one line have no circle
    a, b, c, d = a[ok], b[ok], c[ok], d[ok]
    a2, b2, c2 = (a**2).sum(axis=1), (b**2).sum(axis=1), (c**2).sum(axis=1)
    cy = (a2 * (b[:, 1] - c[:, 1]) + b2 * (c[:, 1] - a[:, 1]) + c2 * (a[:, 1] - b[:, 1])) / d
    cz = (a2 * (c[:, 0] - b[:, 0]) + b2 * (a[:, 0] - c[:, 0]) + c2 * (b[:, 0] - a[:, 0])) / d
    centres = np.column_stack([cy, cz])
    return centres, np.linalg.norm(a - centres, axis=1)


def _least_squares_circle(p: np.ndarray) -> tuple[np.ndarray, float]:
    """The algebraic least-squares circle (Kasa fit) through 2D points."""
    lhs = np.column_stack([2 * p, np.ones(len(p))])
    rhs = (p**2).sum(axis=1)
    (cy, cz, c), *_ = np.linalg.lstsq(lhs, rhs, rcond=None)
    return np.array([cy, cz]), float(np.sqrt(max(c + cy * cy + cz * cz, 0.0)))


# -------------------------------------------------------------------------------------- split
def split_by_cylinder(
    mesh: trimesh.Trimesh,
    axis_point: Sequence[float],
    axis_dir: Sequence[float],
    radius: float,
    t_start: float,
    t_end: float = float("inf"),
) -> tuple[trimesh.Trimesh, trimesh.Trimesh]:
    """``(outside, inside)``: faces whose centroid lies within the cylinder go to ``inside``.

    The cut follows existing faces, so both parts keep their vertices in the same frame; the cut
    leaves open edges, which is acceptable for convex-hull colliders and display.
    """
    a = np.asarray(axis_dir, dtype=float)
    a /= np.linalg.norm(a)
    rel = mesh.triangles_center - np.asarray(axis_point, dtype=float)
    t = rel @ a
    rho = np.linalg.norm(rel - np.outer(t, a), axis=1)
    inside = (rho <= radius) & (t >= t_start) & (t <= t_end)
    if not inside.any() or inside.all():
        raise ValueError("the cylinder must contain some, but not all, faces")
    return _faces(mesh, ~inside), _faces(mesh, inside)


def _faces(mesh: trimesh.Trimesh, mask: np.ndarray) -> trimesh.Trimesh:
    part = mesh.submesh([np.flatnonzero(mask)], append=True)
    part.remove_unreferenced_vertices()
    return part


def face_groups(mesh: trimesh.Trimesh, join: np.ndarray | None = None) -> np.ndarray:
    """A group number per face (0, 1, ...): faces reach each other across shared edges, using
    only the ``mesh.face_adjacency`` pairs where ``join`` is true (all of them by default).

    Union-find in numpy (hooking and pointer jumping), since the backend has no graph library.
    """
    pairs = mesh.face_adjacency if join is None else mesh.face_adjacency[np.asarray(join)]
    label = np.arange(len(mesh.faces))
    while True:
        a, b = label[pairs[:, 0]], label[pairs[:, 1]]
        hooked = label.copy()
        np.minimum.at(hooked, a, np.minimum(a, b))
        np.minimum.at(hooked, b, np.minimum(a, b))
        while not np.array_equal(hooked, hooked[hooked]):
            hooked = hooked[hooked]
        if np.array_equal(hooked, label):
            return np.unique(label, return_inverse=True)[1]
        label = hooked


# --------------------------------------------------------------------------------- mesh faults
@dataclass(frozen=True)
class MeshFaults:
    """What NVIDIA's asset validator would warn about in one mesh (omniverse-asset-validator
    1.18.0, ``_geometry_checker.py``): faces of zero area (``ZeroAreaFaceChecker``), and edges
    with more than two faces, points whose faces form more than one fan (or that no face uses),
    and neighbouring faces wound opposite ways (``ManifoldChecker``). Found the same way, by
    vertex index, as the exporter writes them (lab's machines plan, tool gap 5)."""

    zero_area_faces: int
    nonmanifold_edges: int
    nonmanifold_points: tuple[tuple[float, float, float], ...]  # in the mesh's units
    winding_consistent: bool

    @property
    def clean(self) -> bool:
        return (
            not self.zero_area_faces
            and not self.nonmanifold_edges
            and not self.nonmanifold_points
            and self.winding_consistent
        )


def mesh_faults(mesh: trimesh.Trimesh) -> MeshFaults:
    """The checks of ``MeshFaults``, on a triangle mesh. Areas are computed in 32-bit floats,
    as the validator computes them from USD's float points, so a face is zero exactly when it is
    there."""
    vertices = np.asarray(mesh.vertices, dtype=np.float32)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    if len(faces) == 0:
        return MeshFaults(0, 0, (), True)
    a, b, c = (vertices[faces[:, k]] for k in range(3))
    cross = np.cross(b - a, c - a)
    zero_area = int(np.all(cross == 0, axis=1).sum())

    # Every face's three directed edges; corner 3f + k is face f's k-th vertex.
    count = len(faces)
    starts = faces.T.reshape(-1)  # edge (f, k) runs from faces[f, k] to faces[f, (k + 1) % 3]
    ends = faces[:, [1, 2, 0]].T.reshape(-1)
    face_of = np.tile(np.arange(count), 3)
    k = np.repeat(np.arange(3), count)
    start_corner = 3 * face_of + k
    end_corner = 3 * face_of + (k + 1) % 3
    keys = np.stack([np.minimum(starts, ends), np.maximum(starts, ends)], axis=1)
    _, inverse, sizes = np.unique(keys, axis=0, return_inverse=True, return_counts=True)
    inverse = inverse.reshape(-1)
    nonmanifold_edges = int((sizes > 2).sum())

    # Edges shared by exactly two faces: their two directed copies.
    order = np.argsort(inverse, kind="stable")
    paired = order[sizes[inverse[order]] == 2]
    first, second = paired[0::2], paired[1::2]
    winding_consistent = bool(np.all(starts[first] != starts[second]))

    # Join the faces round each point that share an edge through it (union-find on corners).
    parent = np.arange(3 * count)

    def root(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = int(parent[i])
        return i

    def corner(edge: np.ndarray, vertex: np.ndarray) -> np.ndarray:
        return np.where(starts[edge] == vertex, start_corner[edge], end_corner[edge])

    for end in (starts[first], ends[first]):
        for x, y in zip(corner(first, end), corner(second, end), strict=True):
            parent[root(int(x))] = root(int(y))
    roots = np.array([root(i) for i in range(3 * count)])
    corner_vertex = faces.reshape(-1)
    fans = np.unique(np.stack([corner_vertex, roots], axis=1), axis=0)
    fan_counts = np.bincount(fans[:, 0], minlength=len(vertices))
    # A point no face uses counts too: the validator's empty set of faces is not "connected"
    # (``DisjointSet.connected`` is ``count == 1``, ``_graph_tools.py``).
    bad = np.flatnonzero(fan_counts != 1)
    points = tuple(tuple(float(x) for x in mesh.vertices[v]) for v in bad)
    return MeshFaults(zero_area, nonmanifold_edges, points, winding_consistent)  # type: ignore[arg-type]
