"""Stand-in shapes for parts the generated mesh hides or gets wrong (drill-press plan, Phase 5).

Daniel's rule (2026-10-24, extended on 2026-10-26): a labelled stand-in where a detail is visible
or needed, and where the mesh contradicts the photos, a stand-in matched to the photos. The
geometry spec places each one (decision 0027); this module only makes its mesh.

A shape is built in its own frame, in metres: the twin's axes (+X front, +Y the machine's own
left, +Z up), with its origin where the spec's ``at`` puts it, then turned about +Z by
``turn_deg``. Two kinds:

- ``solids``: boxes and cylinders, each possibly repeated along a step (a rack's teeth), joined
  by listing their faces together. Overlapping closed pieces render and collide (as one convex
  hull) like one solid, which is all a stand-in needs.
- ``slotted_table``: a machine table with a rim, a gutter inside it, a raised plate cut by slots
  from its corners towards the centre, and a centre hole. Primitives cannot cut holes, so it is
  a signed distance meshed by surface nets (``synthetic_parts.surface_nets``), the hand-off's
  suggestion (plan, Phase 5). Its top is at z = 0 of its frame and its centre on the z axis.
"""

from __future__ import annotations

import math
from typing import Annotated, Literal

import numpy as np
import trimesh
from pydantic import BaseModel, ConfigDict, Field, PositiveFloat, PositiveInt, model_validator

from .synthetic_parts import surface_nets

Vec3 = tuple[float, float, float]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class BoxPiece(_Model):
    """A box of ``size_m`` centred at ``center_m``, turned by ``turn_deg`` about ``turn_axis``
    through its centre; ``repeat`` copies, each ``step_m`` from the last."""

    shape: Literal["box"] = "box"
    size_m: tuple[PositiveFloat, PositiveFloat, PositiveFloat]
    center_m: Vec3 = (0.0, 0.0, 0.0)
    turn_deg: float = 0.0
    turn_axis: Vec3 = (0.0, 0.0, 1.0)
    repeat: PositiveInt = 1
    step_m: Vec3 = (0.0, 0.0, 0.0)


class CylinderPiece(_Model):
    """A cylinder of ``radius_m`` and ``length_m`` along ``axis``, centred at ``center_m``."""

    shape: Literal["cylinder"] = "cylinder"
    radius_m: PositiveFloat
    length_m: PositiveFloat
    axis: Vec3 = (0.0, 0.0, 1.0)
    center_m: Vec3 = (0.0, 0.0, 0.0)
    segments: int = Field(default=32, ge=3)
    repeat: PositiveInt = 1
    step_m: Vec3 = (0.0, 0.0, 0.0)


Piece = Annotated[BoxPiece | CylinderPiece, Field(discriminator="shape")]


class Solids(_Model):
    kind: Literal["solids"] = "solids"
    pieces: list[Piece] = Field(min_length=1)


class SlottedTable(_Model):
    """A square table, seen from above as in the T33901's ``table_top.png``: an outer rim with
    rounded corners, a gutter between the rim and a raised plate, slots from the plate's corners
    towards the centre (along the diagonals when ``slot_angle_deg`` is 45), a hole through the
    centre, and a round post under the centre that the table turns on, reaching down into its
    arm."""

    kind: Literal["slotted_table"] = "slotted_table"
    side_m: PositiveFloat
    thickness_m: PositiveFloat
    corner_radius_m: float = Field(ge=0.0)
    rim_width_m: PositiveFloat
    gutter_width_m: PositiveFloat
    gutter_depth_m: PositiveFloat
    slots: int = Field(default=4, ge=0)
    slot_width_m: PositiveFloat
    slot_depth_m: PositiveFloat
    slot_start_m: float = Field(ge=0.0)  # from the centre to a slot's inner end
    slot_angle_deg: float = 45.0  # the first slot's direction, from +X towards +Y
    hole_diameter_m: float = Field(default=0.0, ge=0.0)
    post_diameter_m: float = Field(default=0.0, ge=0.0)
    post_length_m: float = Field(default=0.0, ge=0.0)  # below the table's underside
    cell_m: PositiveFloat = 0.002  # surface nets grid; edges are bevelled by about half of it

    @model_validator(mode="after")
    def _check(self) -> SlottedTable:
        half = self.side_m / 2
        if self.rim_width_m + self.gutter_width_m >= half:
            raise ValueError("the rim and the gutter leave no plate")
        if max(self.gutter_depth_m, self.slot_depth_m) >= self.thickness_m:
            raise ValueError("the gutter and the slots must be shallower than the table")
        if self.corner_radius_m >= half:
            raise ValueError("the corner radius must be under half the side")
        if (self.post_diameter_m > 0) != (self.post_length_m > 0):
            raise ValueError("a post needs both a diameter and a length")
        if self.post_diameter_m and self.post_diameter_m <= self.hole_diameter_m:
            raise ValueError("the post must be wider than the hole through it")
        return self


Shape = Annotated[Solids | SlottedTable, Field(discriminator="kind")]


def shape_mesh(shape: Solids | SlottedTable) -> trimesh.Trimesh:
    """The shape's mesh in its own frame, metres."""
    if isinstance(shape, SlottedTable):
        return table_mesh(shape)
    meshes = []
    for index, piece in enumerate(shape.pieces):
        for i in range(piece.repeat):
            offset = np.asarray(piece.step_m) * i
            meshes.append((index, _piece_mesh(piece, offset)))
    _check_no_shared_points(meshes)
    mesh = trimesh.util.concatenate([m for _, m in meshes])
    mesh.metadata = {}
    return mesh


def _check_no_shared_points(meshes: list[tuple[int, trimesh.Trimesh]]) -> None:
    """Pieces that meet exactly end to end (a stack of cylinders) leave points on top of each
    other, which NVIDIA's asset validator warns about; welding them instead leaves non-manifold
    points, a warning too (worklog 2026-10-27). So the pieces must overlap."""
    seen: dict[tuple[float, float, float], int] = {}
    for index, mesh in meshes:
        mine = {tuple(v) for v in np.round(mesh.vertices, 7)}
        for point in mine:
            other = seen.setdefault(point, index)
            if other != index:
                raise ValueError(
                    f"pieces {other} and {index} share the point {point}: let them overlap "
                    "instead of meeting end to end"
                )


def placed(mesh: trimesh.Trimesh, at_m: Vec3, turn_deg: float) -> trimesh.Trimesh:
    """``mesh`` turned about +Z by ``turn_deg``, then moved to ``at_m``."""
    out = mesh.copy()
    matrix = trimesh.transformations.rotation_matrix(math.radians(turn_deg), (0, 0, 1))
    matrix[:3, 3] = at_m
    out.apply_transform(matrix)
    return out


def _piece_mesh(piece: BoxPiece | CylinderPiece, offset: np.ndarray) -> trimesh.Trimesh:
    centre = np.asarray(piece.center_m) + offset
    if isinstance(piece, BoxPiece):
        mesh = trimesh.creation.box(extents=piece.size_m)
        if piece.turn_deg:
            mesh.apply_transform(
                trimesh.transformations.rotation_matrix(
                    math.radians(piece.turn_deg), piece.turn_axis
                )
            )
    else:
        mesh = trimesh.creation.cylinder(
            radius=piece.radius_m, height=piece.length_m, sections=piece.segments
        )
        mesh.apply_transform(_z_onto(piece.axis))
    mesh.apply_translation(centre)
    return mesh


def _z_onto(axis: Vec3) -> np.ndarray:
    """A rotation taking +Z onto ``axis`` (trimesh's cylinders run along +Z)."""
    a = np.asarray(axis, dtype=float)
    a /= np.linalg.norm(a)
    z = np.array([0.0, 0.0, 1.0])
    if np.allclose(a, z):
        return np.eye(4)
    if np.allclose(a, -z):
        return trimesh.transformations.rotation_matrix(math.pi, (1, 0, 0))
    angle = math.acos(float(np.clip(a @ z, -1.0, 1.0)))
    return trimesh.transformations.rotation_matrix(angle, np.cross(z, a))


# ----------------------------------------------------------------------------------- table
def table_mesh(table: SlottedTable) -> trimesh.Trimesh:
    """The table meshed from its signed distance (module docstring)."""
    half = table.side_m / 2
    lo = np.array([-half, -half, -table.thickness_m - table.post_length_m])
    hi = np.array([half, half, 0.0])
    mesh = surface_nets(lambda p: table_distance(table, p), lo, hi, table.cell_m)
    mesh.metadata = {}
    return mesh


def table_distance(table: SlottedTable, p: np.ndarray) -> np.ndarray:
    """The signed distance to the table at points ``p`` (N x 3, metres): negative inside."""
    x, y, z = p[:, 0], p[:, 1], p[:, 2]
    half = table.side_m / 2
    t = table.thickness_m
    block = np.maximum(
        _rounded_square(x, y, half, table.corner_radius_m), np.abs(z + t / 2) - t / 2
    )

    inner = half - table.rim_width_m  # the rim's inner edge
    plate = inner - table.gutter_width_m  # the plate's edge
    inner_radius = max(table.corner_radius_m - table.rim_width_m, 0.0)
    above = -(z + table.gutter_depth_m)  # negative above the gutter's floor
    gutter = np.maximum.reduce(
        [_rounded_square(x, y, inner, inner_radius), -_rounded_square(x, y, plate, 0.0), above]
    )
    result = np.maximum(block, -gutter)

    for k in range(table.slots):
        angle = math.radians(table.slot_angle_deg + 360.0 * k / table.slots)
        # A slot runs out through the plate's edge into the gutter, and leaves the rim whole.
        edge = plate / max(abs(math.cos(angle)), abs(math.sin(angle)))
        reach = edge + table.gutter_width_m / 2
        s = x * math.cos(angle) + y * math.sin(angle)  # along the slot
        across = -x * math.sin(angle) + y * math.cos(angle)
        middle = (table.slot_start_m + reach) / 2
        slot = np.maximum.reduce(
            [
                np.abs(s - middle) - (reach - table.slot_start_m) / 2,
                np.abs(across) - table.slot_width_m / 2,
                -(z + table.slot_depth_m),
            ]
        )
        # the slot's inner end is round, as milled slots are
        end = np.hypot(s - table.slot_start_m, across) - table.slot_width_m / 2
        rounded = np.minimum(slot, np.maximum(end, -(z + table.slot_depth_m)))
        result = np.maximum(result, -rounded)
    if table.post_length_m:
        top, bottom = -t / 2, -t - table.post_length_m  # from inside the table to below it
        post = np.maximum(
            np.hypot(x, y) - table.post_diameter_m / 2,
            np.abs(z - (top + bottom) / 2) - (top - bottom) / 2,
        )
        result = np.minimum(result, post)
    if table.hole_diameter_m:
        result = np.maximum(result, -(np.hypot(x, y) - table.hole_diameter_m / 2))
    return result


def _rounded_square(x: np.ndarray, y: np.ndarray, half: float, radius: float) -> np.ndarray:
    """The 2D signed distance to a square of half-side ``half`` with corners of ``radius``."""
    qx = np.abs(x) - (half - radius)
    qy = np.abs(y) - (half - radius)
    outside = np.hypot(np.maximum(qx, 0.0), np.maximum(qy, 0.0))
    return outside + np.minimum(np.maximum(qx, qy), 0.0) - radius
