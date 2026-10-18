"""Look at a generated mesh before writing its geometry spec (decision 0012).

``inspect_mesh`` renders views and, once the up and front axes are known, measures where a front
spindle's axis is. ``preview_parts`` applies a draft spec without recording anything, so the split
and the scale can be checked before a build.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import trimesh

from .assemble import AssembledParts, AxisName, GeometrySpec, Vec3, assemble
from .mesh_tools import (
    ProfileSlice,
    TipSlab,
    load_mesh,
    orientation_matrix,
    radial_profile,
    render_views,
    tip_slabs,
    transformed,
)
from .pipeline import ReferenceFacts, size_checks

PROFILE_SLICES = 24
WINDOW_FRACTION = 0.25  # default profile window: a quarter of the mesh's largest extent


@dataclass(frozen=True)
class Inspection:
    mesh_path: Path
    faces: int
    oriented: bool  # False: the generator's axes; True: twin axes (x front, y left, z up)
    bounds: tuple[Vec3, Vec3]  # model units
    views: Path  # the sheet of six views
    tip: list[TipSlab] = field(default_factory=list)
    axis_yz: tuple[float, float] | None = None  # from the middle tip slab
    window: float | None = None  # profile samples farther than this from the axis are ignored
    profile: list[ProfileSlice] = field(default_factory=list)


@dataclass(frozen=True)
class Preview:
    parts: AssembledParts
    views: dict[str, Path]  # "assembled", "body" and "spindle" view sheets


def inspect_mesh(
    mesh_path: Path,
    out_dir: Path,
    up: AxisName | None = None,
    front: AxisName | None = None,
    window: float | None = None,
) -> Inspection:
    """Render the mesh into ``out_dir``; with ``up`` and ``front``, also measure the spindle axis
    (tip slabs) and how far the surface reaches from it along +X (radial profile)."""
    if (up is None) != (front is None):
        raise ValueError("give both up and front, or neither")
    mesh = load_mesh(mesh_path)
    if up is not None and front is not None:
        mesh = transformed(mesh, orientation_matrix(up, front))
    views = render_views(mesh, out_dir)["sheet"]
    bounds = (_vec(mesh.bounds[0]), _vec(mesh.bounds[1]))
    if up is None:
        return Inspection(Path(mesh_path), len(mesh.faces), False, bounds, views)
    tip = tip_slabs(mesh)
    axis = tip[len(tip) // 2].axis_yz
    window = window if window is not None else WINDOW_FRACTION * float(mesh.extents.max())
    profile = radial_profile(
        mesh, (0.0, *axis), (1.0, 0.0, 0.0), slices=PROFILE_SLICES, max_radius=window
    )
    return Inspection(
        Path(mesh_path), len(mesh.faces), True, bounds, views, tip, axis, window, profile
    )


def preview_parts(mesh_path: Path, spec: GeometrySpec, out_dir: Path) -> Preview:
    """Assemble with a draft spec into ``out_dir`` and render the result and each part."""
    out_dir = Path(out_dir)
    parts = assemble(mesh_path, spec, out_dir)
    body, spindle = load_mesh(parts.body_path), load_mesh(parts.spindle_path)
    views = {
        "assembled": render_views(trimesh.util.concatenate([body, spindle]), out_dir / "assembled"),
        "body": render_views(body, out_dir / "body"),
        "spindle": render_views(spindle, out_dir / "spindle"),
    }
    return Preview(parts, {name: paths["sheet"] for name, paths in views.items()})


def format_inspection(inspection: Inspection) -> str:
    frame = "twin axes: x front, y left, z up" if inspection.oriented else "generator axes"
    lo, hi = inspection.bounds
    lines = [
        f"mesh: {inspection.mesh_path} ({inspection.faces} faces)",
        (
            f"bounds ({frame}), model units: min {_fmt(lo)}, max {_fmt(hi)}, "
            f"extents {_fmt([h - low for low, h in zip(lo, hi, strict=True)])}"
        ),
        f"views: {inspection.views}",
    ]
    if inspection.axis_yz is None:
        return "\n".join(lines)
    lines.append(f"tip slabs behind the front-most point (x = {hi[0]:+.4f}):")
    for s in inspection.tip:
        lines.append(
            f"  depth {s.depth:.2f}: {s.count:6d} vertices, centre (y, z) = "
            f"({s.axis_yz[0]:+.4f}, {s.axis_yz[1]:+.4f}), radius {s.radius:.4f}"
        )
    y, z = inspection.axis_yz
    lines.append(f"axis height above the lowest point: {z - lo[2]:.4f}")
    lines.append(
        f"radial profile along +x about (y, z) = ({y:+.4f}, {z:+.4f}), "
        f"samples within {inspection.window:.3f} of the axis:"
    )
    for s in inspection.profile:
        lines.append(f"  x = {s.t:+.3f}  r_max = {s.radius:.3f}  samples = {s.count}")
    return "\n".join(lines)


def format_preview(preview: Preview, reference: ReferenceFacts | None = None) -> str:
    p = preview.parts
    lines = [
        (
            f"scale: {p.scale_factor:.6f} m per model unit "
            f"(centre height {p.center_height_model:.4f} model units)"
        ),
        (
            f"overall extents (m): depth x {p.overall_extents_m[0]:.4f}, "
            f"width y {p.overall_extents_m[1]:.4f}, height z {p.overall_extents_m[2]:.4f}"
        ),
        (
            f"body: {p.body_faces} faces, bounds (m) {_fmt(p.body_bounds_m[0])} to "
            f"{_fmt(p.body_bounds_m[1])}"
        ),
        (
            f"spindle: {p.spindle_faces} faces, bounds (m) {_fmt(p.spindle_bounds_m[0])} to "
            f"{_fmt(p.spindle_bounds_m[1])}"
        ),
        *(f"{i.severity}: {i.message}" for i in size_checks(p, reference)),
        *(f"views ({name}): {path}" for name, path in preview.views.items()),
    ]
    return "\n".join(lines)


def _fmt(values: Sequence[float]) -> str:
    return "(" + ", ".join(f"{v:+.4f}" for v in values) + ")"


def _vec(values: Sequence[float]) -> Vec3:
    return (float(values[0]), float(values[1]), float(values[2]))
