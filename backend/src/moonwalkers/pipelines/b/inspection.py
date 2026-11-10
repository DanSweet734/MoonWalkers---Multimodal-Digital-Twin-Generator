"""Look at a generated mesh before writing its geometry spec (decision 0012).

``inspect_mesh`` renders views and, once the up and front axes are known, measures where the
spindle's axis is:

- **Tip slabs** behind the mesh's front-most point find a round nose at the front (the HA5C).
  Warnings say when the slabs are not round, disagree, or reach the bottom of the mesh: then the
  front-most part is something else, such as the TH240's base feet.
- **A circle scan** fits a circle to the surface in slices over the front of the mesh, so the
  round part shows up wherever it is.
- **Circle fits at chosen x** (``circle_x``), through the round moving part, set the axis when
  they find it, instead of the tip slabs (decision 0012, "Known limitation", fixed).
- **The base footprint's long axis** shows how far an upright mesh is turned from the axes, for
  photos that put the machine's front between two of them (``yaw_deg``, decision 0022).

The radial profile is then measured about the axis in use. ``preview_parts`` applies a draft spec
without recording anything, so the split and the scale can be checked before a build.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import numpy as np
import trimesh

from moonwalkers.contracts.pipeline_result import Issue

from .assemble import AssembledParts, AxisName, GeometrySpec, Vec3, assemble
from .mesh_tools import (
    CircleFit,
    MeshFaults,
    ProfileSlice,
    TipSlab,
    fit_circles,
    footprint_angle,
    load_mesh,
    mesh_faults,
    orientation_matrix,
    radial_profile,
    render_views,
    scan_positions,
    tip_slabs,
    transformed,
)
from .part_views import FittedPhoto, fit_fed_photos, write_spec_views
from .parts_spec import (
    AssembledModel,
    OpenLoop,
    PartsSpec,
    assemble_parts,
    open_loops,
    oriented_mesh,
)
from .pipeline import (
    ReferenceFacts,
    cited_length,
    parts_issues,
    size_checks,
    spec_size_checks,
)

PROFILE_SLICES = 24
WINDOW_FRACTION = 0.25  # default profile window: a quarter of the mesh's largest extent
# [INFERENCE] thresholds, from the HA5C (round tip) and TH240 (feet in front) meshes:
ROUND_RATIO = 0.8  # tip slabs whose smaller extent is under 80% of the larger are not round
BOTTOM_FRACTION = 0.02  # tip slabs within 2% of the height of the mesh's bottom: base or feet
SLAB_SPREAD = 0.10  # slab centres apart by more than 10% of their radius disagree
CIRCLE_SPREAD = 0.05  # round circle fits apart by more than 5% of their radius disagree
# With the axis from circle fits, the default window reaches past the fitted radius, so the
# profile shows the round part's rim and what lies just outside it (the TH240's platter, 0.58
# model units, is wider than a quarter of that mesh, 0.50).
FIT_WINDOW = 1.05

AxisSource = Literal["tip_slabs", "circle_fits"]


@dataclass(frozen=True)
class Inspection:
    mesh_path: Path
    faces: int
    oriented: bool  # False: the generator's axes; True: twin axes (x front, y left, z up)
    bounds: tuple[Vec3, Vec3]  # model units
    views: Path  # the sheet of six views
    tip: list[TipSlab] = field(default_factory=list)
    axis_yz: tuple[float, float] | None = None  # the axis in use (see axis_source)
    window: float | None = None  # profile samples farther than this from the axis are ignored
    profile: list[ProfileSlice] = field(default_factory=list)
    axis_source: AxisSource | None = None  # the middle tip slab, or the round circle fits
    circle_scan: list[CircleFit] = field(default_factory=list)  # over the front of the mesh
    circle_fits: list[CircleFit] = field(default_factory=list)  # at the chosen circle_x
    warnings: list[str] = field(default_factory=list)
    yaw_deg: float = 0.0  # the turn applied after up and front
    footprint_deg: float | None = None  # the base footprint's long axis, after that turn


@dataclass(frozen=True)
class Preview:
    parts: AssembledParts
    views: dict[str, Path]  # "assembled", "body" and "spindle" view sheets
    mesh_faults: list[Issue] = field(default_factory=list)  # what NVIDIA's validator would warn


FAULT_POINTS_LISTED = 8  # non-manifold points listed in a warning; the count gives the rest


def fault_issue(part_id: str, faults: MeshFaults, origin: Vec3 | None, scale: float) -> Issue:
    """A warning naming what NVIDIA's asset validator would warn about in a part's mesh, with
    its first non-manifold points: in model units, after orienting, when ``origin`` is given
    (where a cut list's boxes are), else in metres (lab's machines plan, tool gap 5)."""
    found = []
    if faults.zero_area_faces:
        found.append(f"{faults.zero_area_faces} zero-area face(s)")
    if faults.nonmanifold_edges:
        found.append(f"{faults.nonmanifold_edges} edge(s) with more than two faces")
    if faults.nonmanifold_points:
        points = faults.nonmanifold_points[:FAULT_POINTS_LISTED]
        if origin is not None:
            points = [tuple(p / scale + o for p, o in zip(q, origin, strict=True)) for q in points]
        unit = "model units, oriented" if origin is not None else "m"
        listed = ", ".join(_fmt(p) for p in points)  # type: ignore[arg-type]
        more = len(faults.nonmanifold_points) - len(points)
        extra = f" and {more} more" if more > 0 else ""
        found.append(
            f"{len(faults.nonmanifold_points)} non-manifold point(s) ({unit}): {listed}{extra}"
        )
    if not faults.winding_consistent:
        found.append("neighbouring faces wound opposite ways")
    return Issue(
        severity="warning",
        ref=part_id,
        message=(
            f"Part '{part_id}': NVIDIA's asset validator would warn about {'; '.join(found)}. "
            "Usually a cut boundary or a stand-in's edge on the meshing grid, or two pieces "
            "touching at a point: move it slightly and preview again."
        ),
    )


def part_fault_issues(
    paths: Sequence[tuple[str, Path]], origin: Vec3 | None = None, scale: float = 1.0
) -> list[Issue]:
    """``fault_issue`` for each part file whose mesh is not clean, read as the exporter reads
    it."""
    issues = []
    for part_id, path in paths:
        faults = mesh_faults(load_mesh(path))
        if not faults.clean:
            issues.append(fault_issue(part_id, faults, origin, scale))
    return issues


def inspect_mesh(
    mesh_path: Path,
    out_dir: Path,
    up: AxisName | None = None,
    front: AxisName | None = None,
    window: float | None = None,
    circle_x: Sequence[float] | None = None,
    yaw_deg: float = 0.0,
) -> Inspection:
    """Render the mesh into ``out_dir``. With ``up`` and ``front`` (and ``yaw_deg``, the turn
    about +Z that squares a front lying between two axes), also measure the base footprint, the
    spindle axis (tip slabs, a circle scan, and circle fits at ``circle_x`` if given) and how far
    the surface reaches from that axis along +X (radial profile)."""
    if (up is None) != (front is None):
        raise ValueError("give both up and front, or neither")
    if circle_x is not None and up is None:
        raise ValueError("circle_x needs up and front")
    if yaw_deg and up is None:
        raise ValueError("yaw_deg needs up and front")
    mesh = load_mesh(mesh_path)
    if up is not None and front is not None:
        mesh = transformed(mesh, orientation_matrix(up, front, yaw_deg))
    views = render_views(mesh, out_dir)["sheet"]
    bounds = (_vec(mesh.bounds[0]), _vec(mesh.bounds[1]))
    if up is None:
        return Inspection(Path(mesh_path), len(mesh.faces), False, bounds, views)
    tip = tip_slabs(mesh)
    scan = fit_circles(mesh, scan_positions(mesh))
    fits = fit_circles(mesh, list(circle_x)) if circle_x else []
    warnings = tip_warnings(tip, bounds)
    axis: tuple[float, float] = tip[len(tip) // 2].axis_yz
    source: AxisSource = "tip_slabs"
    default_window = WINDOW_FRACTION * float(mesh.extents.max())
    if circle_x:
        centre, fit_warnings = circle_axis(fits)
        warnings += fit_warnings
        if centre is not None:
            axis, source = centre, "circle_fits"
            radii = [f.radius for f in fits if f.round and f.radius is not None]
            default_window = max(default_window, FIT_WINDOW * statistics.median(radii))
    window = window if window is not None else default_window
    profile = radial_profile(
        mesh, (0.0, *axis), (1.0, 0.0, 0.0), slices=PROFILE_SLICES, max_radius=window
    )
    return Inspection(
        Path(mesh_path),
        len(mesh.faces),
        True,
        bounds,
        views,
        tip,
        axis,
        window,
        profile,
        source,
        scan,
        fits,
        warnings,
        yaw_deg,
        footprint_angle(mesh),
    )


def tip_warnings(tip: Sequence[TipSlab], bounds: tuple[Vec3, Vec3]) -> list[str]:
    """What to doubt about the tip slabs: they find the axis only if the spindle is in front."""
    warnings = []
    flat = [s for s in tip if min(s.extent_yz) < ROUND_RATIO * max(s.extent_yz)]
    if flat:
        s = flat[0]
        warnings.append(
            f"The tip slabs are not round (at depth {s.depth:.2f} they span {s.extent_yz[0]:.3f} "
            f"in y and {s.extent_yz[1]:.3f} in z): the front-most part is probably not the "
            "spindle. Find the round moving part in circle_scan, then inspect again with "
            "circle_x through it."
        )
    height = bounds[1][2] - bounds[0][2]
    low = [s for s in tip if s.z_min - bounds[0][2] <= BOTTOM_FRACTION * height]
    if low:
        warnings.append(
            f"The tip slabs reach the bottom of the mesh (z = {low[0].z_min:.3f}): they measured "
            "something on the base, such as feet, not a spindle."
        )
    centres = np.array([s.axis_yz for s in tip])
    spread = float(np.linalg.norm(centres - centres.mean(axis=0), axis=1).max())
    radius = statistics.median(s.radius for s in tip)
    if radius > 0 and spread > SLAB_SPREAD * radius:
        warnings.append(
            f"The tip slab centres disagree by up to {spread:.4f} (more than "
            f"{SLAB_SPREAD:.0%} of their radius): the tip is not round about one line along x."
        )
    return warnings


def circle_axis(fits: Sequence[CircleFit]) -> tuple[tuple[float, float] | None, list[str]]:
    """The axis from the round circle fits (the median of their centres), with warnings."""
    good = [f for f in fits if f.round and f.centre_yz is not None and f.radius is not None]
    if not good:
        message = (
            "None of the circle fits at circle_x found a round outline, so the axis is still "
            "the tip slabs'. Choose x positions inside the round moving part (see circle_scan)."
        )
        return None, [message]
    centre = (
        statistics.median(f.centre_yz[0] for f in good if f.centre_yz),
        statistics.median(f.centre_yz[1] for f in good if f.centre_yz),
    )
    warnings = []
    skipped = [f"{f.x:+.3f}" for f in fits if f not in good]
    if skipped:
        warnings.append(f"Circle fits not round, left out of the axis: x = {', '.join(skipped)}.")
    spread = max(
        float(np.hypot(f.centre_yz[0] - centre[0], f.centre_yz[1] - centre[1]))
        for f in good
        if f.centre_yz
    )
    radius = statistics.median(f.radius for f in good if f.radius is not None)
    if spread > CIRCLE_SPREAD * radius:
        warnings.append(
            f"The round circle fits disagree by up to {spread:.4f} (more than "
            f"{CIRCLE_SPREAD:.0%} of their radius): they may belong to different parts."
        )
    return centre, warnings


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
    faults = part_fault_issues([("body", parts.body_path), ("spindle", parts.spindle_path)])
    return Preview(parts, {name: paths["sheet"] for name, paths in views.items()}, faults)


@dataclass(frozen=True)
class PartsPreview:
    """A several-part spec tried without storing anything (decisions 0023 and 0027)."""

    model: AssembledModel
    views: dict[str, Path]  # cuts, parts, part_<id>, on_<slot>_photo
    photos: list[FittedPhoto]
    size_checks: list[Issue]
    issues: list[Issue]  # stand-ins, removed parts, inaccuracies, pieces, seams, mesh faults
    holes: list[OpenLoop]  # open loops across a removed part: patch them, or cover them


def preview_parts_spec(
    mesh_path: Path,
    spec: PartsSpec,
    reference: ReferenceFacts | None,
    out_dir: Path,
    prepared: Path | None = None,
) -> PartsPreview:
    """Cut, place the stand-ins and scale into ``out_dir``/meshes, and write the reviewer's
    views (``part_views.write_spec_views``). With ``prepared`` (the run's
    ``generator/prepared``), each fed photo is placed on the mesh and the parts are drawn over
    it; that takes about a minute a photo."""
    known = cited_length(reference, spec.scale.fact, "the scale")
    out_dir = Path(out_dir)
    model = assemble_parts(mesh_path, spec, known, out_dir / "meshes")
    mesh = oriented_mesh(mesh_path, spec)
    fitted = fit_fed_photos(mesh, prepared, spec.yaw_deg) if prepared is not None else []
    views = write_spec_views(mesh, spec, model.scale_factor, out_dir, fitted)
    checks = [
        *size_checks(model, reference),
        *spec_size_checks(spec, model.scale_factor, reference),
    ]
    removed = {p.part_id for p in spec.parts if p.kind == "removed"}
    holes = [loop for loop in open_loops(mesh, spec) if removed & set(loop.across)]
    faults = part_fault_issues(
        [(p.part_id, p.path) for p in model.parts], model.origin_model_units, model.scale_factor
    )
    issues = [*parts_issues(spec, model), *faults]
    return PartsPreview(model, views, fitted, checks, issues, holes)


def format_parts_preview(preview: PartsPreview) -> str:
    m = preview.model
    seams = {s.part: s for s in m.seams}
    lines = [
        (
            f"scale: {m.scale_factor:.6f} m per model unit "
            f"({m.scale_measured_model_units:.4f} model units)"
        ),
        (
            f"overall extents (m): depth x {m.overall_extents_m[0]:.4f}, "
            f"width y {m.overall_extents_m[1]:.4f}, height z {m.overall_extents_m[2]:.4f}"
        ),
        "parts:",
    ]
    for part in m.parts:
        seam = seams.get(part.part_id)
        pieces = f", {seam.pieces} piece(s), {seam.stray_faces} stray faces" if seam else ""
        lines.append(
            f"  {part.part_id} ({part.kind}): {part.faces} faces{pieces}, bounds (m) "
            f"{_fmt(part.bounds_m[0])} to {_fmt(part.bounds_m[1])}"
        )
    lines += [f"  removed {name}: {faces} faces" for name, faces in m.removed_faces.items()]
    lines.append("joints:")
    lines += [f"  {j.joint_id}: axis {_fmt(j.axis)} at {_fmt(j.origin_m)} m" for j in m.joints]
    for fitted in preview.photos:
        f = fitted.fit
        lines.append(
            f"photo {fitted.slot}: azimuth {f.azimuth_deg:+.1f} deg (slot implies "
            f"{fitted.expected_azimuth_deg:+.1f}), elevation {f.elevation_deg:.1f}, "
            f"silhouette IoU {f.iou:.3f}"
        )
    lines += [f"{i.severity}: {i.message}" for i in preview.size_checks]
    lines += [f"{i.severity} ({i.ref or '-'}): {i.message}" for i in preview.issues]
    lines += [
        f"hole in {h.part} across {', '.join(h.across)}: centre {_fmt(h.centre)}, size "
        f"{_fmt(h.size)}, {h.edges} edges (patch it, or check that a stand-in covers it)"
        for h in preview.holes
    ]
    lines += [f"views ({name}): {path}" for name, path in preview.views.items()]
    return "\n".join(lines)


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
    footprint = (
        "no long axis (round or square)"
        if inspection.footprint_deg is None
        else f"{inspection.footprint_deg:+.1f} deg from +x towards +y (up to a multiple of 90)"
    )
    lines.append(f"turned by yaw_deg {inspection.yaw_deg:+.1f}; base footprint: {footprint}")
    lines += [f"warning: {w}" for w in inspection.warnings]
    lines.append(f"tip slabs behind the front-most point (x = {hi[0]:+.4f}):")
    for s in inspection.tip:
        lines.append(
            f"  depth {s.depth:.2f}: {s.count:6d} vertices, centre (y, z) = "
            f"({s.axis_yz[0]:+.4f}, {s.axis_yz[1]:+.4f}), radius {s.radius:.4f}, "
            f"spans {s.extent_yz[0]:.3f} x {s.extent_yz[1]:.3f}"
        )
    for title, fits in (
        ("circle scan over the front of the mesh:", inspection.circle_scan),
        ("circle fits at circle_x:", inspection.circle_fits),
    ):
        if fits:
            lines.append(title)
            lines += [f"  {_circle(f)}" for f in fits]
    y, z = inspection.axis_yz
    source = "round circle fits" if inspection.axis_source == "circle_fits" else "middle tip slab"
    lines.append(f"axis in use, from the {source}: (y, z) = ({y:+.4f}, {z:+.4f})")
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
        *(f"{i.severity}: {i.message}" for i in preview.mesh_faults),
        *(f"views ({name}): {path}" for name, path in preview.views.items()),
    ]
    return "\n".join(lines)


def _circle(fit: CircleFit) -> str:
    if fit.centre_yz is None or fit.radius is None:
        return f"x = {fit.x:+.3f}: no circle ({fit.samples} samples)"
    return (
        f"x = {fit.x:+.3f}: centre (y, z) = ({fit.centre_yz[0]:+.4f}, {fit.centre_yz[1]:+.4f}), "
        f"radius {fit.radius:.4f}, inliers {fit.inliers:.0%}, rms {fit.rms or 0:.4f}, "
        f"coverage {fit.coverage:.0%}{', round' if fit.round else ''}"
    )


def _fmt(values: Sequence[float]) -> str:
    return "(" + ", ".join(f"{v:+.4f}" for v in values) + ")"


def _vec(values: Sequence[float]) -> Vec3:
    return (float(values[0]), float(values[1]), float(values[2]))
