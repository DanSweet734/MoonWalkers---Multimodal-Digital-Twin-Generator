"""Coloured views of a mesh's parts, and the parts drawn over each fed photo (decision 0023).

What a reviewer looks at to judge a cut list (Daniel's way of reviewing, Phase 4): every part in
its own colour from six sides, each moving part alone, and the twin's parts over each photo the
generator was fed, through a camera fitted to the photo by its silhouette
(``photo_marks.fit_camera``). Moved here from the Phase 4 spike (``part_spike``), which uses them
too. Images are written with the standard library only (no image package is installed).
"""

from __future__ import annotations

import math
import struct
import zlib
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import trimesh

from . import photo_marks
from .mesh_tools import VIEWS, read_png
from .parts_spec import PartsSpec, face_parts
from .stand_ins import placed, shape_mesh

# Where each generator slot's camera stands once the mesh is oriented, before the yaw: degrees
# from +X towards +Y (decision 0022: `left` is the machine's own left, +Y). A turned mesh (a
# corners grid) moves each camera by -yaw_deg.
SLOT_AZIMUTHS = {"front": 0.0, "left": 90.0, "back": 180.0, "right": -90.0}
FIT_SPAN_DEG = 30.0  # the azimuth search reaches this far either side of the slot's
FIT_ELEVATIONS = np.arange(0.0, 45.5, 3.0)  # photos are taken from about eye level or above
REMOVED = "(removed)"  # the legend's name for faces cut out of the twin

PALETTE = np.array(
    [
        (190, 190, 190),  # the first part (the fixed part, or the largest segment): grey
        (230, 97, 1),
        (94, 60, 153),
        (27, 158, 119),
        (231, 41, 138),
        (31, 120, 180),
        (227, 26, 28),
        (255, 191, 0),
        (166, 86, 40),
        (0, 158, 199),
        (152, 78, 163),
        (102, 166, 30),
    ],
    dtype=float,
)


def part_colours(
    mesh: trimesh.Trimesh, parts: Sequence, fixed: str = "frame"
) -> tuple[np.ndarray, list[str]]:
    """A colour per face (N x 3) by its part or segment, and the legend: the fixed part (or the
    largest segment) grey, the others in ``PALETTE``'s colours, in order of their names."""
    parts = np.asarray(parts)
    names, index = np.unique(parts.astype(str), return_inverse=True)
    if fixed in names:  # the fixed part grey, the moving parts in colour
        order = np.r_[np.flatnonzero(names == fixed), np.flatnonzero(names != fixed)]
    else:  # segments: the largest grey
        order = np.argsort(-np.bincount(index, weights=mesh.area_faces))
    colour_of = np.empty(len(names), dtype=int)
    colour_of[order] = np.arange(len(names)) % len(PALETTE)
    if len(names) > len(PALETTE):  # many segments: repeat colours, seeded
        colour_of = np.random.default_rng(0).integers(1, len(PALETTE), len(names))
        colour_of[order[0]] = 0
    legend = [f"{names[i]}: rgb{tuple(int(c) for c in PALETTE[colour_of[i]])}" for i in order]
    return PALETTE[colour_of[index]], legend


def render_parts(
    mesh: trimesh.Trimesh, parts: Sequence, out: Path, size: int = 400, fixed: str = "frame"
) -> Path:
    """The six inspection views (``mesh_tools.VIEWS``), each face coloured by its part or
    segment and shaded by its slope, as ``out``.png; the parts' colours as ``out``.txt."""
    colours, legend = part_colours(mesh, parts, fixed)
    centre = mesh.bounds.mean(axis=0)
    radius = float(np.linalg.norm(mesh.extents)) / 2.0
    images = {}
    for view, (toward, up) in VIEWS.items():
        camera = photo_marks.Camera(toward, up, tuple(centre), radius, size)
        face, _ = photo_marks.render(mesh, camera)
        image = np.full((size, size, 3), 255.0)
        hit = face >= 0
        d = np.asarray(toward) / np.linalg.norm(toward)
        shade = 0.35 + 0.65 * np.clip(mesh.face_normals[face[hit]] @ d, 0.0, 1.0)
        image[hit] = colours[face[hit]] * shade[:, None]
        images[view] = image.astype(np.uint8)
    rows = [
        np.hstack([images[v] for v in row])
        for row in (("front", "left", "back"), ("right", "top", "iso"))
    ]
    out.parent.mkdir(parents=True, exist_ok=True)
    path = out.with_suffix(".png")
    write_rgb_png(path, np.vstack(rows))
    if len(legend) <= 40:
        out.with_suffix(".txt").write_text("\n".join(legend) + "\n", encoding="utf-8")
    return path


def photo_overlay(
    mesh: trimesh.Trimesh,
    parts: Sequence,
    photo: np.ndarray,
    fit: photo_marks.PhotoFit,
    out: Path,
    scene: trimesh.Trimesh | None = None,
    fixed: str = "frame",
) -> Path:
    """The photo in grey with the moving parts' colours over it where the fitted camera sees
    them, and the outline of what is drawn in magenta: a reviewer's check of the cuts against
    the photo. ``photo`` is RGBA, as the generator's prepared inputs are: its alpha is the
    machine's mask. ``parts`` labels the faces of ``scene`` when it is given (the twin's parts,
    stand-ins included; ``photo_marks.in_photo``), else of ``mesh``."""
    if photo.ndim != 3 or photo.shape[2] != 4:
        raise ValueError("photo_overlay needs an RGBA photo, whose alpha masks the machine")
    mask = photo[..., 3] > 127
    grey = photo[..., :3].mean(axis=2)
    image = np.repeat(grey[..., None], 3, axis=2)
    drawn = mesh if scene is None else scene
    faces = photo_marks.in_photo(mesh, mask, fit, scene=scene)
    colours, _ = part_colours(drawn, parts, fixed)
    labels = np.asarray(parts, dtype=object)
    moving = (faces >= 0) & (labels[np.maximum(faces, 0)] != fixed)
    image[moving] = 0.45 * image[moving] + 0.55 * colours[faces[moving]]
    seen = faces >= 0
    outline = (seen != np.roll(seen, 1, axis=0)) | (seen != np.roll(seen, 1, axis=1))
    image[outline] = (255, 0, 255)
    path = out.with_suffix(".png")
    write_rgb_png(path, image.clip(0, 255).astype(np.uint8))
    return path


def write_rgb_png(path: Path, image: np.ndarray) -> None:
    """Write an 8-bit colour image (H x W x 3, uint8) as PNG using only the standard library."""
    if image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("write_rgb_png expects an H x W x 3 uint8 array")
    height, width, _ = image.shape
    raw = b"".join(b"\x00" + image[row].tobytes() for row in range(height))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
        )

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw, 9))
    Path(path).write_bytes(png + chunk(b"IEND", b""))


# --------------------------------------------------------------------- a several-part spec
def twin_scene(
    mesh: trimesh.Trimesh, spec: PartsSpec, scale: float
) -> tuple[trimesh.Trimesh, np.ndarray]:
    """The twin's parts in the oriented mesh's model units, for views and overlays: the cut
    parts' faces (removed ones left out) and the stand-ins, with each face's part."""
    labels = face_parts(mesh, spec)
    keep = np.isin(labels, [p.part_id for p in spec.parts if p.kind == "cut"])
    pieces = [mesh.submesh([np.flatnonzero(keep)], append=True)]
    names = [labels[keep]]
    for part in spec.parts:
        if part.kind != "stand_in":
            continue
        assert part.shape is not None and part.at is not None
        local = shape_mesh(part.shape)
        local.apply_scale(1.0 / scale)
        piece = placed(local, part.at, part.turn_deg)
        pieces.append(piece)
        names.append(np.full(len(piece.faces), part.part_id, dtype=object))
    return trimesh.util.concatenate(pieces), np.concatenate(names)


@dataclass(frozen=True)
class FittedPhoto:
    slot: str
    photo: np.ndarray  # RGBA, the generator's prepared input
    fit: photo_marks.PhotoFit
    expected_azimuth_deg: float  # where the slot's camera stands once the mesh is squared


def fit_fed_photos(mesh: trimesh.Trimesh, prepared: Path, yaw_deg: float) -> list[FittedPhoto]:
    """Place each photo the generator was fed (``generator/prepared/<slot>.png``) on the oriented
    mesh by its silhouette, searching around where its slot's camera should stand."""
    fitted = []
    for slot, azimuth in SLOT_AZIMUTHS.items():
        path = Path(prepared) / f"{slot}.png"
        if not path.is_file():
            continue
        photo = read_png(path)
        if photo.ndim != 3 or photo.shape[2] != 4:
            continue  # no alpha, so no mask to fit
        guess = _wrap(azimuth - yaw_deg)
        span = np.arange(guess - FIT_SPAN_DEG, guess + FIT_SPAN_DEG + 0.5, 3.0)
        fit = photo_marks.fit_camera(mesh, photo[..., 3] > 127, span, FIT_ELEVATIONS)
        fitted.append(FittedPhoto(slot, photo, fit, guess))
    return fitted


def write_spec_views(
    mesh: trimesh.Trimesh,
    spec: PartsSpec,
    scale: float,
    out_dir: Path,
    photos: Sequence[FittedPhoto] = (),
    size: int = 400,
) -> dict[str, Path]:
    """The views a reviewer needs, in ``out_dir``:

    - ``cuts.png``: the generated mesh coloured by the cut list, removed faces included;
    - ``parts.png``: the twin's parts, stand-ins included;
    - ``part_<id>.png``: each part but the fixed one, alone;
    - ``on_<slot>_photo.png``: the twin's parts over each fed photo."""
    out_dir = Path(out_dir)
    labels = face_parts(mesh, spec)
    removed = {p.part_id for p in spec.parts if p.kind == "removed"}
    shown = np.array([f"{REMOVED} {x}" if x in removed else x for x in labels], dtype=object)
    views = {"cuts": render_parts(mesh, shown, out_dir / "cuts", size, spec.fixed_part)}
    scene, names = twin_scene(mesh, spec, scale)
    views["parts"] = render_parts(scene, names, out_dir / "parts", size, spec.fixed_part)
    for part in spec.parts:
        if part.kind == "removed" or part.part_id == spec.fixed_part:
            continue
        mine = np.flatnonzero(names == part.part_id)
        piece = scene.submesh([mine], append=True)
        views[f"part_{part.part_id}"] = render_parts(
            piece, names[mine], out_dir / f"part_{part.part_id}", size, spec.fixed_part
        )
    for fitted in photos:
        name = f"on_{fitted.slot}_photo"
        views[name] = photo_overlay(
            mesh, names, fitted.photo, fitted.fit, out_dir / name, scene, spec.fixed_part
        )
    return views


def _wrap(angle: float) -> float:
    return (angle + 180.0) % 360.0 - 180.0 if not math.isclose(angle, 180.0) else 180.0
