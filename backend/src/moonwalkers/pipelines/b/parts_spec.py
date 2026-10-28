"""A geometry spec for several parts and joints (decisions 0023 and 0027; plan, Phase 5).

Decision 0012's spec splits one spindle off with one cylinder. This one, ``PartsSpec``, holds:

- **The cut list** (decision 0023): ``part_cuts.PartCut`` shapes in the oriented mesh's model
  units. A face goes to the first part whose shape holds its centre; the rest stays in
  ``fixed_part``.
- **The parts**, each ``cut`` (its faces from the cut list), ``stand_in`` (a shape from
  ``stand_ins``, labelled as such in the twin) or ``removed`` (faces cut out of the twin because a
  stand-in replaces them, or nothing should keep them).
- **The joints**, each with its axis and a point on it measured in model units, its limits in
  contract units (rad or m, about the modelled pose), and the contract's v0.2.0 behaviour (mode,
  adjustable stop, link; decision 0020), each cited. A stand-in that does not move on its own is
  held by a ``fixed`` joint to the part it belongs to.
- **The scale:** a cited length (a fact in the reference facts, in m) over the same length
  measured in model units. For ``overall_depth``, ``overall_width`` and ``overall_height`` the
  pipeline measures the oriented mesh itself.
- **Size checks:** other cited lengths with the inspector's measurement and how it was taken.
- **Patches** (decision 0027, update of 2026-10-27): a hole that a removed part leaves in a cut
  part, where no stand-in covers it, closed flat. Each names a point near the hole and why.

The twin frame is decision 0012's: metres, +Z up, the front towards +X, the origin on the base
plane under ``origin_xy`` (the spindle's axis on a drill press).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import trimesh
from pydantic import BaseModel, ConfigDict, Field, PositiveFloat, model_validator

from moonwalkers.contracts.pipeline_result import AdjustableStop, Citation, JointLink, JointMode

from .assemble import AxisName, Vec3
from .mesh_tools import load_mesh, orientation_matrix, transformed
from .part_cuts import PartCut, PartSeams, assign, seams
from .stand_ins import Shape, placed, shape_mesh

# A scale fact the pipeline can measure on the oriented mesh: fact key -> axis of its extent.
EXTENT_FACTS = {"overall_depth": 0, "overall_width": 1, "overall_height": 2}
# How far a patch's point may be from the centre of the hole it closes, in model units.
PATCH_REACH = 0.02


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HolePatch(_Model):
    """A hole in a cut part, closed flat: the part's open edge loop whose centre is nearest
    ``near`` (model units, after orienting; within ``PATCH_REACH``)."""

    near: Vec3
    note: str  # where the hole is, and why nothing else covers it


class SpecPart(_Model):
    part_id: str
    name: str
    kind: Literal["cut", "stand_in", "removed"]
    note: str  # what it is, and from which evidence
    inaccuracy: str | None = None  # a known way it differs from the machine: a warning in the twin
    # a stand-in's shape and where it goes: ``at`` in model units, after orienting
    shape: Shape | None = None
    at: Vec3 | None = None
    turn_deg: float = 0.0
    replaces: str | None = None  # the removed part a stand-in takes the place of
    citations: list[Citation] = Field(default_factory=list)  # cited sizes, matched photos
    patches: list[HolePatch] = Field(default_factory=list)  # a cut part's holes, closed flat

    @model_validator(mode="after")
    def _check(self) -> SpecPart:
        if self.kind == "stand_in":
            if self.shape is None or self.at is None:
                raise ValueError(f"stand-in '{self.part_id}' needs a shape and 'at'")
            if not self.citations:
                raise ValueError(f"stand-in '{self.part_id}' needs citations for its sizes")
        elif self.shape is not None or self.at is not None or self.replaces is not None:
            raise ValueError(f"only a stand-in takes a shape, 'at' or 'replaces' ({self.part_id})")
        if self.patches and self.kind != "cut":
            raise ValueError(f"only a cut part has holes to patch ({self.part_id})")
        return self


class SpecJoint(_Model):
    joint_id: str
    joint_type: Literal["revolute", "prismatic", "fixed"]
    parent: str
    child: str
    axis: Vec3  # direction, in the oriented mesh's axes
    point: Vec3  # a point on the axis, model units
    lower: float | None = None  # contract units, about the modelled pose
    upper: float | None = None
    max_velocity_fact: str | None = None  # a cited speed in the reference facts (rad/s or m/s)
    mode: JointMode | None = None
    adjustable_stop: AdjustableStop | None = None
    follows: JointLink | None = None
    confidence: float = Field(default=0.6, ge=0.0, le=1.0)
    note: str  # how the axis and the point were measured
    inaccuracy: str | None = None
    citations: list[Citation] = Field(default_factory=list)  # what says it moves, and how far


class ScaleReference(_Model):
    fact: str  # a cited length in the reference facts, in m
    measured_model_units: PositiveFloat | None = None  # None: the mesh's extent (EXTENT_FACTS)
    how: str


class SizeCheck(_Model):
    fact: str  # a cited length in the reference facts, in m
    measured_model_units: PositiveFloat
    how: str


class PartsSpec(_Model):
    up: AxisName
    front: AxisName
    yaw_deg: float = Field(default=0.0, ge=-180.0, le=180.0)
    origin_xy: tuple[float, float]  # model units: the twin origin, on the base plane below it
    base_z: float | None = None  # the base plane; default: the mesh's lowest point
    scale: ScaleReference
    fixed_part: str
    cuts: list[PartCut]
    parts: list[SpecPart] = Field(min_length=1)
    joints: list[SpecJoint]
    size_checks: list[SizeCheck] = Field(default_factory=list)
    decided_by: str
    method: str

    @model_validator(mode="after")
    def _check(self) -> PartsSpec:
        kinds = {p.part_id: p.kind for p in self.parts}
        if len(kinds) != len(self.parts):
            raise ValueError("duplicate part ids")
        if kinds.get(self.fixed_part) != "cut":
            raise ValueError(f"the fixed part '{self.fixed_part}' must be a cut part")
        for cut in self.cuts:
            if kinds.get(cut.part) not in ("cut", "removed"):
                raise ValueError(
                    f"the cut list names '{cut.part}', which is not a cut or removed part"
                )
        for part in self.parts:
            if part.replaces is not None and kinds.get(part.replaces) != "removed":
                raise ValueError(f"'{part.part_id}' replaces '{part.replaces}', not a removed part")
        ids = [j.joint_id for j in self.joints]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate joint ids")
        for joint in self.joints:
            for end in (joint.parent, joint.child):
                if kinds.get(end) not in ("cut", "stand_in"):
                    raise ValueError(f"joint '{joint.joint_id}' joins '{end}', not a twin part")
            if not np.linalg.norm(joint.axis):
                raise ValueError(f"joint '{joint.joint_id}' has no axis")
        return self

    def part(self, part_id: str) -> SpecPart:
        return next(p for p in self.parts if p.part_id == part_id)

    @property
    def twin_parts(self) -> list[SpecPart]:
        return [p for p in self.parts if p.kind != "removed"]


@dataclass(frozen=True)
class BuiltPart:
    part_id: str
    kind: Literal["cut", "stand_in"]
    path: Path
    faces: int
    bounds_m: tuple[Vec3, Vec3]


@dataclass(frozen=True)
class BuiltJoint:
    joint_id: str
    axis: Vec3  # unit length
    origin_m: Vec3


@dataclass(frozen=True)
class AssembledModel:
    parts: list[BuiltPart]
    joints: list[BuiltJoint]
    scale_factor: float  # metres per model unit
    scale_measured_model_units: float
    overall_extents_m: Vec3  # depth (x), width (y), height (z) of the twin's parts
    seams: list[PartSeams]  # what the cut list left on each part, removed ones included
    removed_faces: dict[str, int]


def oriented_mesh(raw_mesh: Path, spec: PartsSpec) -> trimesh.Trimesh:
    return transformed(load_mesh(raw_mesh), orientation_matrix(spec.up, spec.front, spec.yaw_deg))


def measured_scale_length(mesh: trimesh.Trimesh, spec: PartsSpec) -> float:
    if spec.scale.measured_model_units is not None:
        return spec.scale.measured_model_units
    if spec.scale.fact not in EXTENT_FACTS:
        raise ValueError(
            f"the scale fact '{spec.scale.fact}' is not an overall extent, so the spec must give "
            "measured_model_units"
        )
    return float(mesh.extents[EXTENT_FACTS[spec.scale.fact]])


def face_parts(mesh: trimesh.Trimesh, spec: PartsSpec) -> np.ndarray:
    """The part of every face of the oriented mesh, removed parts included."""
    return assign(mesh, spec.cuts, spec.fixed_part)


def assemble_parts(
    raw_mesh: Path, spec: PartsSpec, known_length_m: float, out_dir: Path
) -> AssembledModel:
    """Cut, place the stand-ins and scale: one GLB per twin part in ``out_dir``, in the twin
    frame and in metres. ``known_length_m`` is the cited value of ``spec.scale.fact``."""
    mesh = oriented_mesh(raw_mesh, spec)
    base_z = spec.base_z if spec.base_z is not None else float(mesh.bounds[0][2])
    measured = measured_scale_length(mesh, spec)
    scale = known_length_m / measured
    origin = np.array([*spec.origin_xy, base_z])
    placement = np.diag([scale, scale, scale, 1.0])
    placement[:3, 3] = -origin * scale

    labels = face_parts(mesh, spec)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    built: list[BuiltPart] = []
    meshes: list[trimesh.Trimesh] = []
    for part in spec.twin_parts:
        if part.kind == "cut":
            piece = cut_part_mesh(mesh, labels, part)
            piece.apply_transform(placement)
        else:
            assert part.shape is not None and part.at is not None
            at_m = (np.asarray(part.at) - origin) * scale
            piece = placed(shape_mesh(part.shape), tuple(at_m), part.turn_deg)
        # Name the part instead of keeping trimesh's metadata, so the same geometry always
        # gives the same file (as assemble.py does).
        piece.metadata = {"name": part.part_id}
        path = out_dir / f"{part.part_id}.glb"
        piece.export(path)
        meshes.append(piece)
        built.append(
            BuiltPart(
                part.part_id,
                part.kind,
                path,
                len(piece.faces),
                (_vec(piece.bounds[0]), _vec(piece.bounds[1])),
            )
        )

    joints = [
        BuiltJoint(
            j.joint_id,
            _vec(np.asarray(j.axis) / np.linalg.norm(j.axis)),
            _vec((np.asarray(j.point) - origin) * scale),
        )
        for j in spec.joints
    ]
    everything = trimesh.util.concatenate(meshes)
    removed = [p.part_id for p in spec.parts if p.kind == "removed"]
    return AssembledModel(
        parts=built,
        joints=joints,
        scale_factor=float(scale),
        scale_measured_model_units=float(measured),
        overall_extents_m=_vec(everything.extents),
        seams=seams(mesh, list(labels)),
        removed_faces={r: int((labels == r).sum()) for r in removed},
    )


def cut_part_mesh(mesh: trimesh.Trimesh, labels: np.ndarray, part: SpecPart) -> trimesh.Trimesh:
    """A cut part's faces of the oriented mesh, in model units, with its holes patched."""
    faces = np.flatnonzero(labels == part.part_id)
    if not len(faces):
        raise ValueError(f"the cut list gives part '{part.part_id}' no faces")
    piece = mesh.submesh([faces], append=True)
    piece.remove_unreferenced_vertices()
    for patch in part.patches:
        piece = patch_hole(piece, patch.near, part.part_id)
    return piece


@dataclass(frozen=True)
class OpenLoop:
    """An open edge loop of a cut part, after its patches: where it was cut from its
    neighbours, or where the generated mesh itself is open."""

    part: str
    centre: Vec3  # model units, after orienting: a patch's ``near``
    size: Vec3
    edges: int
    across: tuple[str, ...]  # the parts that share its points; none: open in the mesh


def open_loops(mesh: trimesh.Trimesh, spec: PartsSpec) -> list[OpenLoop]:
    """Every cut part's open edge loops, found as the patches find them, with the parts on the
    other side. One across a removed part is a hole that only a patch or a stand-in fills."""
    labels = face_parts(mesh, spec)
    owners: dict[tuple[float, ...], set[str]] = {}
    for face, label in zip(mesh.faces, labels, strict=True):
        for vertex in face:
            owners.setdefault(tuple(mesh.vertices[vertex]), set()).add(str(label))
    loops = []
    for part in spec.parts:
        if part.kind != "cut":
            continue
        piece = cut_part_mesh(mesh, labels, part)
        for loop in boundary_loops(piece):
            points = piece.vertices[loop]
            across = set().union(*(owners.get(tuple(p), set()) for p in points))
            loops.append(
                OpenLoop(
                    part.part_id,
                    _vec(points.mean(axis=0)),
                    _vec(np.ptp(points, axis=0)),
                    len(loop),
                    tuple(sorted(across - {part.part_id})),
                )
            )
    return loops


def boundary_loops(mesh: trimesh.Trimesh) -> list[np.ndarray]:
    """The mesh's open edge loops, each as its vertex indices in order. An open edge runs the way
    its one face winds; a chain of open edges that does not close is left out."""
    open_edges = mesh.edges[trimesh.grouping.group_rows(mesh.edges_sorted, require_count=1)]
    following: dict[int, list[int]] = {}
    for a, b in open_edges:
        following.setdefault(int(a), []).append(int(b))
    loops = []
    while following:
        start = current = next(iter(following))
        loop = [start]
        while current in following:
            ahead = following[current].pop()
            if not following[current]:
                del following[current]
            if ahead == start:
                loops.append(np.array(loop))
                break
            loop.append(ahead)
            current = ahead
    return loops


def simple_loops(loop: np.ndarray) -> list[np.ndarray]:
    """A loop that passes a vertex twice, two holes touching at a point, as loops that do not.
    Fanning such a loop from one centre would give the spoke to that vertex four faces, a
    non-manifold edge (NVIDIA's asset validator on the T33901's table arm, 2026-10-27)."""
    stack: list[int] = []
    seen: dict[int, int] = {}
    loops = []
    for vertex in map(int, loop):
        if vertex in seen:  # the loop came back to it: what it went round since is one loop
            start = seen[vertex]
            loops.append(np.array(stack[start:]))
            for passed in stack[start + 1 :]:
                del seen[passed]
            del stack[start + 1 :]
        else:
            seen[vertex] = len(stack)
            stack.append(vertex)
    loops.append(np.array(stack))
    return [simple for simple in loops if len(simple) >= 3]


def patch_hole(mesh: trimesh.Trimesh, near: Vec3, part_id: str = "") -> trimesh.Trimesh:
    """``mesh`` with the open edge loop nearest ``near`` closed by fans of triangles, one from
    the centre of each simple loop in it (``simple_loops``). Each open edge a -> b belongs to a
    face that runs a -> b; its patch triangle runs b -> a, so the patch winds the same way as the
    faces around it."""
    loops = boundary_loops(mesh)
    if not loops:
        raise ValueError(f"part '{part_id}' has no open edge loop to patch")
    centres = np.array([mesh.vertices[loop].mean(axis=0) for loop in loops])
    distances = np.linalg.norm(centres - np.asarray(near), axis=1)
    nearest = int(np.argmin(distances))
    if distances[nearest] > PATCH_REACH:
        raise ValueError(
            f"part '{part_id}' has no open edge loop within {PATCH_REACH} model units of "
            f"{tuple(near)}; the nearest is centred at {tuple(np.round(centres[nearest], 3))}"
        )
    vertices, faces = [mesh.vertices], [mesh.faces]
    for number, loop in enumerate(simple_loops(loops[nearest])):
        centre = len(mesh.vertices) + number
        vertices.append(mesh.vertices[loop].mean(axis=0, keepdims=True))
        faces.append(np.column_stack([np.roll(loop, -1), loop, np.full(len(loop), centre)]))
    return trimesh.Trimesh(np.vstack(vertices), np.vstack(faces), process=False)


def _vec(values: np.ndarray) -> Vec3:
    return (float(values[0]), float(values[1]), float(values[2]))
