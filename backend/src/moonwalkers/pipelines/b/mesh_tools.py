"""Mesh tools for Pipeline B: orient, render for inspection, measure, split, scale (decision 0012).

Twin frame: metres, +Z up, the machine's front (the HA5C's spindle nose) faces +X, so its width
runs along Y. ``orient`` brings a generator's mesh into this frame; the rest work in it.
"""

from __future__ import annotations

import itertools
import struct
import zlib
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

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


def load_mesh(path: Path) -> trimesh.Trimesh:
    """A mesh file (GLB, OBJ, PLY ...) as one triangle mesh, with scene transforms applied."""
    mesh = trimesh.load(Path(path), force="mesh")
    if not isinstance(mesh, trimesh.Trimesh) or len(mesh.faces) == 0:
        raise ValueError(f"{path} holds no triangle mesh")
    return mesh


def orientation_matrix(up: str, front: str) -> np.ndarray:
    """The rotation (3x3) that turns the mesh axis ``up`` into +Z and ``front`` into +X."""
    if up not in AXES or front not in AXES:
        raise ValueError(f"axes must be one of {sorted(AXES)}")
    z, x = np.array(AXES[up]), np.array(AXES[front])
    if abs(float(z @ x)) > 1e-9:
        raise ValueError(f"up ({up}) and front ({front}) must be perpendicular")
    y = np.cross(z, x)
    return np.stack([x, y, z])  # rows: the new axes in old coordinates


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
