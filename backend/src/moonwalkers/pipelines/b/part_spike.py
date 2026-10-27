"""The Phase 4 spike: compare ways to cut one mesh into several parts (drill-press plan, Phase 4).

Methods (``docs/research/2026-10-24-part-cutting-spike.md``):

- (a) shapes in an ordered cut list (``part_cuts``);
- (b) the mesh's own shape: separate pieces, regions between sharp edges (``mesh_segments``);
- (c) a learned segmenter: researched only, nothing installed (Daniel, 2026-10-24);
- (d) parts marked on photos, carried onto the mesh (``photo_marks``). On the synthetic mesh the
  marks are perfect (rendered from the true parts), so the score is the method's ceiling.

Test meshes: the box-and-cylinder drill press of Phase 1 as one mesh, separate, fused and rounded
(``synthetic_parts``), scored face by face; and the T33901's generated mesh, judged by eye against
the manual's figures. Run from ``backend/``::

    uv run python -m moonwalkers.pipelines.b.part_spike <out-folder>
        [--t33901 ../data/machines/grizzly-t33901/runs/2026-10-24_run-001]

It writes ``report.md``, the numbers as ``results.json``, and coloured view sheets (one colour per
part or segment) for each method. Nothing is stored in a run folder or the knowledge base.
"""

from __future__ import annotations

import argparse
import json
import math
import struct
import sys
import time
import zlib
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import trimesh

from moonwalkers.usd.primitive_drill_press import COLUMN_X, HUB

from . import mesh_segments, photo_marks, synthetic_parts
from .mesh_tools import VIEWS, load_mesh, orientation_matrix, read_png, transformed
from .part_cuts import BoxCut, CylinderCut, PartCut, assign, seams

Z = (0.0, 0.0, 1.0)

# ---------------------------------------------------------------- (a) on the synthetic mesh
# Written from the Phase 1 model's own sizes, with ordinary margins, so the score is (a)'s ceiling
# when the inspector reads the geometry right. Twin frame of the test model, metres.
_COLUMN = (COLUMN_X, 0.0, 0.0)
SYNTHETIC_CUTS = [
    PartCut(part="spindle", shapes=[CylinderCut(point=(0, 0, 0), axis=Z, radius=0.03,
                                                start=0.50, end=0.6477)],
            note="the chuck, below the spindle nose"),
    PartCut(part="quill", shapes=[CylinderCut(point=(0, 0, 0), axis=Z, radius=0.035,
                                              start=0.6477, end=0.678)],
            note="the quill between the chuck and the head's bottom"),
    PartCut(part="handle_hub", shapes=[CylinderCut(point=HUB, axis=(0, 1, 0), radius=0.22,
                                                   start=-0.024, end=0.04)],
            note="the hub's disc and the handles' reach, outside the head's side"),
    PartCut(part="table", shapes=[BoxCut(min=(-0.15, -0.15, 0.2172), max=(0.15, 0.15, 0.25))]),
    PartCut(part="table_arm", shapes=[BoxCut(min=(-0.155, -0.035, 0.165),
                                             max=(0.035, 0.035, 0.2172))]),
    PartCut(part="frame", shapes=[
        CylinderCut(point=_COLUMN, axis=Z, radius=0.042, start=0.0, end=0.152),
        CylinderCut(point=_COLUMN, axis=Z, radius=0.042, start=0.243, end=0.6475),
        CylinderCut(point=_COLUMN, axis=Z, radius=0.042, start=0.678, end=0.70),
    ], note="the column's own surface, kept out of the parts that slide and turn on it"),
    PartCut(part="column_rack", shapes=[
        BoxCut(min=(COLUMN_X - 0.009, 0.036, 0.06), max=(COLUMN_X + 0.009, 0.064, 0.665)),
        CylinderCut(point=_COLUMN, axis=Z, radius=0.056, start=0.645, end=0.68),
    ]),
    PartCut(part="table_bracket", shapes=[
        CylinderCut(point=_COLUMN, axis=Z, radius=0.14, start=0.11, end=0.245),
    ], note="the bracket around the column, with its crank"),
]  # fmt: skip

# ------------------------------------------------------------------ (a) on the T33901's mesh
# The generated mesh squared as in the hand-off (+y up, +z front, yaw 49.1), in model units:
# +X the machine's front, +Y its own left (the operator's right, the handles' side), +Z up.
T33901_ORIENT = {"up": "+y", "front": "+z", "yaw_deg": 49.1}
_C = (-0.1385, 0.0052, 0.0)  # the column's axis: round circle fits from z = -0.75 to +0.10, r 0.079
_S = (0.277, -0.022, 0.0)  # the spindle's: the chuck guard's round fits, z = 0.16-0.34, r 0.112
_ROD = (0.334, -0.156, 0.0)  # the depth stop's rod: a small circle in slices z = 0.40-0.70
_HUB = (0.229, 0.0, 0.497)  # the pinion's axis along Y: nearest point to the 3 handles' lines
T33901_CUTS = [
    PartCut(part="spindle", shapes=[CylinderCut(point=_S, axis=Z, radius=0.045, start=0.0,
                                                end=0.137)],
            note="the chuck's nose below its guard (Fig. 4); the guard is clear on the machine, "
            "solid in the mesh, so the rest of the chuck is hidden"),
    PartCut(part="quill", shapes=[
        CylinderCut(point=_S, axis=Z, radius=0.17, start=0.137, end=0.39),
        CylinderCut(point=_ROD, axis=Z, radius=0.02, start=0.37, end=0.785),
    ], note="the quill below the head, with the chuck guard that hangs from it (Fig. 46: the "
            "guard goes down with the quill), the guard collar's arm, and the depth stop's rod, "
            "'attached to the quill' (p. 31; Figs. 4, 35). The ring at z 0.54-0.64, where the "
            "depth stop nut and the stop bracket are fused, stays with the head"),
    PartCut(part="handle_hub", shapes=[
        CylinderCut(point=_HUB, axis=(0, 1, 0), radius=0.06, start=0.072, end=0.2),
        BoxCut(min=(0.13, 0.085, 0.12), max=(0.62, 0.55, 0.785)),
        BoxCut(min=(0.30, 0.07, 0.12), max=(0.62, 0.55, 0.785)),
        BoxCut(min=(-0.10, 0.23, 0.12), max=(0.62, 0.55, 0.785)),
    ], note="the hub, about the pinion's axis (where the three handles' lines meet; the spring "
            "housing on -Y is round about x 0.25, z 0.48), and its three handles, outside the "
            "head's +Y wall (y 0.055-0.077; under 0.064 in front of x 0.30) and in front of the "
            "belt tension lever (x 0.04-0.12, out to y 0.22) (Figs. 3, 46), below the top "
            "casting"),
    PartCut(part="table", shapes=[
        BoxCut(min=(-0.045, -0.30, -0.302), max=(0.60, 0.36, -0.20)),
        BoxCut(min=(-0.045, -0.30, -0.315), max=(0.60, -0.125, -0.20)),
    ], note="the table's plate, z -0.30 to -0.23, and its rim's underside beside the arm "
            "(Figs. 6, 7)"),
    PartCut(part="table_arm", shapes=[BoxCut(min=(-0.02, -0.12, -0.53), max=(0.47, 0.18, -0.302))],
            note="the mounting arm under the table, with the pivot lock handle (Fig. 36)"),
    PartCut(part="frame", shapes=[
        CylinderCut(point=_C, axis=Z, radius=0.083, start=-0.86, end=-0.515),
    ], note="the column below the bracket, kept out of the bracket's shape"),
    PartCut(part="column_rack", shapes=[CylinderCut(point=_C, axis=Z, radius=0.12, start=0.195,
                                                    end=0.29)],
            note="the collar over the rack (Figs. 46, 48); the rack itself is a bump of at most "
            "2.5 mm on the column in the mesh, so it stays with the column"),
    PartCut(part="table_bracket", shapes=[CylinderCut(point=_C, axis=Z, radius=0.34, start=-0.68,
                                                      end=-0.27)],
            note="the column bracket with the height crank and the height lock handle (Figs. 6, "
            "7, 36)"),
]  # fmt: skip
# How the T33901's cut list was reached, pass by pass (each after looking at the coloured views):
T33901_PASSES = [
    "1: a shape per part from the measurements and the manual's figures",
    (
        "2: the hub's box took a patch of the head's +Y wall and the belt tension lever; it "
        "starts at x 0.13 and y 0.085"
    ),
    (
        "3: that left the hub's disc in the head, cutting the up handle off; a cylinder about "
        "the pinion's axis takes the disc"
    ),
    (
        "4: the up handle's root is fused to the wall at y 0.08; a box from y 0.07 in front of "
        "x 0.30 takes it (the handle stays a separate piece of its part)"
    ),
    (
        "5: stray faces left in the frame: the crank's knob (bracket radius 0.30 to 0.34), the "
        "outward handle's knob (everything beyond y 0.23), the table rim's underside, the guard "
        "collar's arm (quill radius 0.15 to 0.17)"
    ),
]

# (d) camera sets: (azimuth from +X towards +Y, elevation), degrees
VIEW_SETS: dict[str, list[tuple[float, float]]] = {
    "two front corners (as the T33901 now)": [(-45.0, 20.0), (45.0, 20.0)],
    "four corners": [(-45.0, 20.0), (45.0, 20.0), (135.0, 20.0), (-135.0, 20.0)],
    "four sides and the top": [(0.0, 0.0), (90.0, 0.0), (180.0, 0.0), (-90.0, 0.0), (0.0, 89.0)],
}
SHARP_ANGLES = (20.0, 30.0, 45.0)
# Where each generator slot's camera stands once the mesh is oriented, before the yaw: degrees
# from +X towards +Y (decision 0022: `left` is the machine's own left, +Y). A corners grid then
# turns by -yaw_deg.
SLOT_AZIMUTHS = {"front": 0.0, "left": 90.0}


@dataclass
class Row:
    """One method on one mesh."""

    mesh: str
    method: str
    seconds: float
    segments: int  # parts or segments it returned
    area_share: float | None = None  # synthetic only: share of the surface in the right part
    face_share: float | None = None
    seen_share: float | None = None  # (d): share of the surface some photo sees
    seen_right: float | None = None  # (d): of that, the share carried to the right part
    open_edges: int = 0
    seam_length: float = 0.0  # mesh units (metres on the synthetic mesh)
    stray_faces: int = 0
    photo_iou: float | None = None  # (d) on a real photo: the fitted silhouette's overlap
    per_part: dict[str, list[float]] = field(default_factory=dict)  # part: [recall, precision]
    note: str = ""


# ----------------------------------------------------------------------------- the spike
def run_synthetic(out: Path, cell: float) -> list[Row]:
    rows = []
    for build in ("separate", "fused", "rounded"):
        started = time.perf_counter()
        truth = synthetic_parts.drill_press(build, cell)
        built = time.perf_counter() - started
        mesh = truth.mesh
        print(f"synthetic {build}: {len(mesh.faces)} faces in {built:.1f} s")
        name = f"synthetic, {build}"
        render_parts(mesh, np.asarray(truth.names)[truth.labels], out / f"synthetic_{build}_truth")

        row, parts = _timed(assign, mesh, SYNTHETIC_CUTS, "frame")
        rows.append(_scored(truth, name, "(a) shapes", parts, row))
        render_parts(mesh, parts, out / f"synthetic_{build}_a")

        row, segments = _timed(mesh_segments.pieces, mesh)
        rows.append(_scored(truth, name, "(b) separate pieces", segments, row, named=False))
        for angle in SHARP_ANGLES:
            row, segments = _timed(mesh_segments.sharp_regions, mesh, angle)
            method = f"(b) sharp edges, {angle:.0f} deg"
            rows.append(_scored(truth, name, method, segments, row, named=False))
            if angle == 30.0:
                render_parts(mesh, segments, out / f"synthetic_{build}_b30")

        for views, angles in VIEW_SETS.items():
            row, carried = _timed(_carry_perfect_marks, truth, angles)
            seen, filled = carried
            names = np.asarray(truth.names, dtype=object)
            predicted = np.where(filled >= 0, names[np.maximum(filled, 0)], "unmarked")
            scored = _scored(truth, name, f"(d) perfect marks, {views}", predicted, row)
            area = mesh.area_faces
            scored.seen_share = float(area[seen >= 0].sum() / area.sum())
            scored.seen_right = float(
                area[(seen >= 0) & (seen == truth.labels)].sum() / area[seen >= 0].sum()
            )
            rows.append(scored)
            if views.startswith("two"):
                render_parts(mesh, predicted, out / f"synthetic_{build}_d2")
    return rows


def run_t33901(run_folder: Path, out: Path) -> list[Row]:
    mesh = transformed(
        load_mesh(run_folder / "generator" / "mesh.glb"),
        orientation_matrix(
            T33901_ORIENT["up"], T33901_ORIENT["front"], float(T33901_ORIENT["yaw_deg"])
        ),
    )
    name = "T33901 (generated)"
    rows = []
    row, parts = _timed(assign, mesh, T33901_CUTS, "frame")
    _seams(row, mesh, parts)
    row.per_part = {
        p.part: [float(p.faces), float(p.pieces), float(p.stray_faces)] for p in seams(mesh, parts)
    }
    row.note = "per_part: faces, pieces, stray faces"
    rows.append(Row(name, "(a) shapes", **_fields(row)))
    render_parts(mesh, parts, out / "t33901_a")
    for name_part, piece in _part_meshes(mesh, parts).items():
        render_parts(piece, np.full(len(piece.faces), name_part), out / f"t33901_a_{name_part}")

    row, segments = _timed(mesh_segments.pieces, mesh)
    rows.append(Row(name, "(b) separate pieces", **_fields(row, segments)))
    for angle in SHARP_ANGLES:
        row, segments = _timed(mesh_segments.sharp_regions, mesh, angle)
        _seams(row, mesh, segments)
        rows.append(Row(name, f"(b) sharp edges, {angle:.0f} deg", **_fields(row, segments)))
        render_parts(mesh, segments, out / f"t33901_b{angle:.0f}")

    # (d)'s first step on real photos: place each fed photo on the mesh by its silhouette
    yaw = float(T33901_ORIENT["yaw_deg"])
    for slot, azimuth in SLOT_AZIMUTHS.items():
        path = run_folder / "generator" / "prepared" / f"{slot}.png"
        if not path.exists():
            continue
        photo = read_png(path)
        guess = azimuth - yaw
        row, fit = _timed(
            photo_marks.fit_camera,
            mesh,
            photo[..., 3] > 127,  # the prepared inputs are RGBA, with the background removed
            np.arange(guess - 30.0, guess + 30.5, 3.0),
            np.arange(0.0, 45.5, 3.0),
        )
        row.photo_iou = fit.iou
        row.note = (
            f"azimuth {fit.azimuth_deg:+.1f} deg (the generator's slot implies {guess:+.1f}), "
            f"elevation {fit.elevation_deg:.1f} deg"
        )
        rows.append(Row(name, f"(d) camera fitted to the {slot} photo", **_fields(row)))
        photo_overlay(mesh, parts, photo, fit, out / f"t33901_a_on_{slot}_photo")
    return rows


# ------------------------------------------------------------------------------ helpers
def _timed(work: Callable[..., Any], *args: Any) -> tuple[Row, Any]:
    started = time.perf_counter()
    result = work(*args)
    return Row("", "", time.perf_counter() - started, 0), result


def _fields(row: Row, segments: object = None) -> dict:
    data = {k: v for k, v in asdict(row).items() if k not in ("mesh", "method")}
    if segments is not None:
        data["segments"] = len(np.unique(np.asarray(segments)))
    return data


def _seams(row: Row, mesh: trimesh.Trimesh, parts: Sequence) -> None:
    found = seams(mesh, list(parts))
    row.segments = len(found)
    row.open_edges = sum(p.open_edges for p in found) // 2  # each seam edge borders two parts
    row.seam_length = sum(p.seam_length for p in found) / 2
    row.stray_faces = sum(p.stray_faces for p in found)


def _scored(
    truth: synthetic_parts.LabelledMesh,
    mesh_name: str,
    method: str,
    result: Sequence,
    row: Row,
    named: bool = True,
) -> Row:
    parts = list(result) if named else synthetic_parts.name_segments(truth, result)
    score = synthetic_parts.score(truth, parts)
    _seams(row, truth.mesh, parts)
    row.mesh, row.method = mesh_name, method
    row.segments = len(np.unique(np.asarray(result)))
    row.area_share, row.face_share = score.area_share, score.face_share
    row.per_part = {k: [round(r, 4), round(p, 4)] for k, (r, p) in score.per_part.items()}
    if not named:
        row.note = "segments named after the part holding most of their area (the best naming)"
    return row


def _carry_perfect_marks(
    truth: synthetic_parts.LabelledMesh, angles: Sequence[tuple[float, float]]
) -> tuple[np.ndarray, np.ndarray]:
    marked = []
    for azimuth, elevation in angles:
        camera = photo_marks.Camera.around(truth.mesh, azimuth, elevation)
        marks, _ = photo_marks.render(truth.mesh, camera, truth.labels)
        marked.append((camera, marks))
    seen = photo_marks.carry(truth.mesh, marked)
    return seen, photo_marks.fill_unseen(truth.mesh, seen)


def _part_meshes(mesh: trimesh.Trimesh, parts: Sequence) -> dict[str, trimesh.Trimesh]:
    parts = np.asarray(parts, dtype=object)
    meshes = {}
    for name in dict.fromkeys(parts):
        if name == "frame":
            continue
        piece = mesh.submesh([np.flatnonzero(parts == name)], append=True)
        meshes[str(name)] = piece
    return meshes


# ------------------------------------------------------------------------- coloured views
PALETTE = np.array(
    [
        (190, 190, 190),  # the first part (frame, or the largest segment): grey
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


def part_colours(mesh: trimesh.Trimesh, parts: Sequence) -> tuple[np.ndarray, list[str]]:
    """A colour per face (N x 3) by its part or segment, and the legend: the fixed part (or the
    largest segment) grey, the others in ``PALETTE``'s colours."""
    parts = np.asarray(parts)
    names, index = np.unique(parts.astype(str), return_inverse=True)
    if "frame" in names:  # the fixed part grey, the moving parts in colour
        order = np.r_[np.flatnonzero(names == "frame"), np.flatnonzero(names != "frame")]
    else:  # segments: the largest grey
        order = np.argsort(-np.bincount(index, weights=mesh.area_faces))
    colour_of = np.empty(len(names), dtype=int)
    colour_of[order] = np.arange(len(names)) % len(PALETTE)
    if len(names) > len(PALETTE):  # many segments: repeat colours, seeded
        colour_of = np.random.default_rng(0).integers(1, len(PALETTE), len(names))
        colour_of[order[0]] = 0
    legend = [f"{names[i]}: rgb{tuple(int(c) for c in PALETTE[colour_of[i]])}" for i in order]
    return PALETTE[colour_of[index]], legend


def render_parts(mesh: trimesh.Trimesh, parts: Sequence, out: Path, size: int = 400) -> Path:
    """The six inspection views (``mesh_tools.VIEWS``), each face coloured by its part or
    segment and shaded by its slope, as ``out``.png; the parts' colours as ``out``.txt."""
    colours, legend = part_colours(mesh, parts)
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
    mesh: trimesh.Trimesh, parts: Sequence, photo: np.ndarray, fit: photo_marks.PhotoFit, out: Path
) -> Path:
    """The photo in grey with the moving parts' colours over it where the fitted camera sees
    them, and the mesh's outline in magenta: a reviewer's check of the cuts against the photo.
    ``photo`` is RGBA, as the generator's prepared inputs are: its alpha is the machine's mask."""
    if photo.ndim != 3 or photo.shape[2] != 4:
        raise ValueError("photo_overlay needs an RGBA photo, whose alpha masks the machine")
    mask = photo[..., 3] > 127
    grey = photo[..., :3].mean(axis=2)
    image = np.repeat(grey[..., None], 3, axis=2)
    faces = photo_marks.in_photo(mesh, mask, fit)
    colours, _ = part_colours(mesh, parts)
    moving = (faces >= 0) & (np.asarray(parts, dtype=object)[np.maximum(faces, 0)] != "frame")
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


# ---------------------------------------------------------------------------------- report
def format_report(rows: Sequence[Row]) -> str:
    lines = [
        "# Phase 4 spike: cutting one mesh into parts",
        "",
        (
            "Written by `python -m moonwalkers.pipelines.b.part_spike`. Shares are of the surface "
            "area (faces in brackets). Seams are edges between two parts; stray faces are faces "
            "in small pieces cut off from the rest of their part (under 2% of its faces)."
        ),
        "",
        (
            "| Mesh | Method | Time (s) | Parts or segments | Right part | Seen by a photo | "
            "Seen and right | Seam edges | Stray faces |"
        ),
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        right = "-" if r.area_share is None else f"{r.area_share:.3f} ({r.face_share:.3f})"
        seen = "-" if r.seen_share is None else f"{r.seen_share:.3f}"
        seen_right = "-" if r.seen_right is None else f"{r.seen_right:.3f}"
        lines.append(
            f"| {r.mesh} | {r.method} | {r.seconds:.2f} | {r.segments} | {right} | {seen} | "
            f"{seen_right} | {r.open_edges} | {r.stray_faces} |"
        )
    fits = [r for r in rows if r.photo_iou is not None]
    if fits:
        lines += ["", "## Photos placed on the T33901's mesh by their silhouettes", ""]
        lines += [
            f"- {r.method}: silhouette IoU {r.photo_iou:.3f}, {r.note} ({r.seconds:.0f} s)"
            for r in fits
        ]
    lines += ["", "## Per part (recall, precision by area; T33901: faces, pieces, stray faces)", ""]
    for r in rows:
        if r.per_part and not r.method.startswith("(b) sharp edges, 2"):
            parts = "; ".join(f"{k} {', '.join(f'{v:g}' for v in vals)}"
                              for k, vals in r.per_part.items())  # fmt: skip
            lines.append(f"- {r.mesh}, {r.method}: {parts}")
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare ways to cut one mesh into parts.")
    parser.add_argument("out", type=Path, help="folder for the report and the view sheets")
    parser.add_argument("--t33901", type=Path, help="the T33901 run folder with generator/mesh.glb")
    parser.add_argument("--cell", type=float, default=synthetic_parts.CELL,
                        help="grid cell of the fused synthetic meshes, metres")  # fmt: skip
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    rows = run_synthetic(args.out, args.cell)
    if args.t33901:
        rows += run_t33901(args.t33901, args.out)
    (args.out / "results.json").write_text(
        json.dumps([asdict(r) for r in rows], indent=2, default=_json), encoding="utf-8"
    )
    (args.out / "report.md").write_text(format_report(rows), encoding="utf-8")
    print(format_report(rows))
    return 0


def _json(value: object) -> object:
    if isinstance(value, float) and math.isinf(value):
        return str(value)
    raise TypeError(type(value))


if __name__ == "__main__":
    sys.exit(main())
