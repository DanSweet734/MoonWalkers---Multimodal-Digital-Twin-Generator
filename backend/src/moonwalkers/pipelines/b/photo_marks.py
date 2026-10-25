"""Carry parts marked on photos onto the mesh (drill-press plan Phase 4, method d).

A mark image says, for each pixel of a photo, which part it shows (or none). With a camera that
places the photo on the mesh, every face the camera sees takes the mark at its centre's pixel.
The mesh's own depth, rendered from the same camera, decides what the camera sees, so a face
behind another takes nothing from that photo. Faces no photo sees take their neighbours' parts
(``fill_unseen``): those are guesses, as the mesh's hidden surfaces are.

Cameras are orthographic, like the inspection views (``mesh_tools.render_points``): a direction
towards the camera, an image-up direction, a centre and a radius that fit the mesh in the image.
``fit_camera`` places a real photo: it searches the camera's azimuth and elevation for the one
whose silhouette of the mesh best overlaps the photo's own (its background-removed mask), after
lining up the two silhouettes' bounding boxes. A photo has perspective and the mesh is the
generator's reading of it, so the fit is approximate; its overlap (IoU) says how approximate.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import trimesh

UNMARKED = -1


@dataclass(frozen=True)
class Camera:
    toward: tuple[float, float, float]  # from the mesh's centre to the camera
    up: tuple[float, float, float]  # image up
    center: tuple[float, float, float]
    radius: float  # half the image's width, in mesh units, is about this
    size: int = 512  # pixels across

    @classmethod
    def around(
        cls, mesh: trimesh.Trimesh, azimuth_deg: float, elevation_deg: float, size: int = 512
    ) -> Camera:
        """A camera at ``azimuth_deg`` from +X towards +Y and ``elevation_deg`` above the
        horizon, image up towards +Z, framing the whole mesh."""
        az, el = math.radians(azimuth_deg), math.radians(elevation_deg)
        toward = (math.cos(az) * math.cos(el), math.sin(az) * math.cos(el), math.sin(el))
        center = mesh.bounds.mean(axis=0)
        radius = float(np.linalg.norm(mesh.extents)) / 2.0
        return cls(toward, (0.0, 0.0, 1.0), tuple(float(c) for c in center), radius, size)

    def project(self, points: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Pixel column, pixel row and depth (larger is nearer the camera) of ``points``."""
        d = np.asarray(self.toward, dtype=float)
        d /= np.linalg.norm(d)
        u = np.asarray(self.up, dtype=float)
        u = u - (u @ d) * d
        u /= np.linalg.norm(u)
        r = np.cross(-d, u)
        rel = points - np.asarray(self.center)
        scale = 0.5 * self.size * 0.95 / self.radius
        column = np.floor(rel @ r * scale + self.size / 2).astype(int)
        row = np.floor(self.size / 2 - rel @ u * scale).astype(int)
        return column, row, rel @ d

    @property
    def pixel(self) -> float:
        """One pixel's width, in mesh units."""
        return self.radius / (0.5 * self.size * 0.95)


def render(
    mesh: trimesh.Trimesh,
    camera: Camera,
    values: np.ndarray | None = None,
    samples: int = 600_000,
    seed: int = 0,
) -> tuple[np.ndarray, np.ndarray]:
    """``(image, depth)``: per pixel, the value of the nearest face (its number, or
    ``values[face]``), and that surface's depth; ``UNMARKED`` and -inf where nothing is."""
    points, faces = trimesh.sample.sample_surface(mesh, samples, seed=seed)
    column, row, depth = camera.project(points)
    per_face = np.arange(len(mesh.faces)) if values is None else np.asarray(values)
    size = camera.size
    image = np.full(size * size, UNMARKED, dtype=np.int64)
    nearest = np.full(size * size, -np.inf)
    for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1)):  # 2x2 splats close small gaps
        x, y = column + dx, row + dy
        ok = (x >= 0) & (x < size) & (y >= 0) & (y < size)
        pixel = y[ok] * size + x[ok]
        order = np.lexsort((depth[ok], pixel))  # by pixel, nearest last
        pixel, d, f = pixel[order], depth[ok][order], faces[ok][order]
        last = np.r_[pixel[1:] != pixel[:-1], True]
        closer = d[last] > nearest[pixel[last]]
        nearest[pixel[last][closer]] = d[last][closer]
        image[pixel[last][closer]] = per_face[f[last][closer]]
    return image.reshape(size, size), nearest.reshape(size, size)


def carry(
    mesh: trimesh.Trimesh,
    marked: Sequence[tuple[Camera, np.ndarray]],
    tolerance_pixels: float = 2.0,
) -> np.ndarray:
    """A part number per face from ``marked`` (camera, mark image) pairs, ``UNMARKED`` where no
    photo sees the face or its pixel is unmarked. Where photos disagree, the one that faces the
    face most squarely wins."""
    centres = mesh.triangles_center
    normals = mesh.face_normals
    parts = np.full(len(centres), UNMARKED, dtype=np.int64)
    best = np.full(len(centres), -np.inf)
    for camera, marks in marked:
        _, depth = render(mesh, camera)
        column, row, d = camera.project(centres)
        size = camera.size
        inside = (column >= 0) & (column < size) & (row >= 0) & (row < size)
        seen = np.zeros(len(centres), dtype=bool)
        at = row[inside] * size + column[inside]
        seen[inside] = d[inside] >= depth.reshape(-1)[at] - tolerance_pixels * camera.pixel
        mark = np.full(len(centres), UNMARKED)
        mark[inside] = marks.reshape(-1)[at]
        facing = normals @ (np.asarray(camera.toward) / np.linalg.norm(camera.toward))
        take = seen & (mark != UNMARKED) & (facing > best)
        parts[take] = mark[take]
        best[take] = facing[take]
    return parts


def fill_unseen(mesh: trimesh.Trimesh, parts: np.ndarray) -> np.ndarray:
    """``parts`` with every ``UNMARKED`` face given the part most of its marked neighbours have,
    in rounds outward from the marked faces. Faces with no marked face in reach stay unmarked."""
    parts = np.asarray(parts).copy()
    pairs = np.concatenate([mesh.face_adjacency, mesh.face_adjacency[:, ::-1]])
    count = int(parts.max()) + 1 if (parts != UNMARKED).any() else 0
    while (parts == UNMARKED).any():
        a, b = pairs[:, 0], pairs[:, 1]
        reach = (parts[a] == UNMARKED) & (parts[b] != UNMARKED)
        if not reach.any():
            return parts
        votes = np.zeros((len(parts), count))
        np.add.at(votes, (a[reach], parts[b[reach]]), 1.0)
        voted = votes.sum(axis=1) > 0
        parts[voted] = votes[voted].argmax(axis=1)
    return parts


# ----------------------------------------------------------------------- placing a photo
@dataclass(frozen=True)
class PhotoFit:
    azimuth_deg: float
    elevation_deg: float
    iou: float  # overlap of the mesh's silhouette and the photo's mask, 0 to 1


def fit_camera(
    mesh: trimesh.Trimesh,
    mask: np.ndarray,
    azimuths: Sequence[float],
    elevations: Sequence[float],
    size: int = 200,
    refine: float = 2.0,
) -> PhotoFit:
    """The azimuth and elevation (``Camera.around``) whose silhouette best overlaps ``mask`` (a
    photo's H x W foreground), searched over the grid given, then every degree within ``refine``
    of the best."""
    best = PhotoFit(0.0, 0.0, -1.0)
    for azimuth in azimuths:
        for elevation in elevations:
            best = max(best, _overlap(mesh, mask, azimuth, elevation, size), key=lambda f: f.iou)
    fine = np.arange(-refine, refine + 0.5, 1.0)
    for da in fine:
        for de in fine:
            fit = _overlap(mesh, mask, best.azimuth_deg + da, best.elevation_deg + de, size)
            best = max(best, fit, key=lambda f: f.iou)
    return best


def in_photo(mesh: trimesh.Trimesh, mask: np.ndarray, fit: PhotoFit, size: int = 600) -> np.ndarray:
    """The face the fitted camera sees at every pixel of the photo (``UNMARKED`` where none)."""
    camera = Camera.around(mesh, fit.azimuth_deg, fit.elevation_deg, size)
    faces, _ = render(mesh, camera, samples=2_000_000)
    return _onto(faces, mask)


def _overlap(
    mesh: trimesh.Trimesh, mask: np.ndarray, azimuth: float, elevation: float, size: int
) -> PhotoFit:
    camera = Camera.around(mesh, azimuth, elevation, size)
    faces, _ = render(mesh, camera, samples=150_000)
    seen = _onto(faces, mask) >= 0
    union = (seen | mask).sum()
    return PhotoFit(float(azimuth), float(elevation), float((seen & mask).sum() / union))


def _onto(faces: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """A render's face numbers moved onto the photo's pixels, its silhouette's bounding box
    centred on the mask's and scaled to the same height (nearest pixel)."""
    hit = faces >= 0
    if not hit.any() or not mask.any():
        return np.full(mask.shape, UNMARKED)
    (r0, r1), (c0, c1) = _extent(hit)
    (m0, m1), (n0, n1) = _extent(mask)
    scale = (r1 - r0) / max(m1 - m0, 1)  # render pixels per photo pixel
    rows, columns = np.mgrid[0 : mask.shape[0], 0 : mask.shape[1]]
    r = np.round((rows - (m0 + m1) / 2) * scale + (r0 + r1) / 2).astype(int)
    c = np.round((columns - (n0 + n1) / 2) * scale + (c0 + c1) / 2).astype(int)
    inside = (r >= 0) & (r < faces.shape[0]) & (c >= 0) & (c < faces.shape[1])
    out = np.full(mask.shape, UNMARKED)
    out[inside] = faces[r[inside], c[inside]]
    return out


def _extent(mask: np.ndarray) -> tuple[tuple[int, int], tuple[int, int]]:
    rows, columns = np.nonzero(mask)
    return (int(rows.min()), int(rows.max())), (int(columns.min()), int(columns.max()))
