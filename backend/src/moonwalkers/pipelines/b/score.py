"""Score a built twin by the scorecard (the lab's machines plan, "How 'accurately' is measured").

The measures, each against the plan's starting target:

- **sizes:** every size check in the run's spec, the inspector's measurement at the twin's scale
  against the cited length (within 6%; over 10% flagged);
- **photo match:** each photo the generator was fed against the twin's silhouette, placed by
  ``photo_marks.fit_camera``, as IoU (no target yet: the first builds set a baseline);
- **shape against the maker's model:** distance from each twin part's surface to the maker's
  mesh of the same link, posed as the twin is, in mm: mean and 95th percentile, both ways;
- **parts and joints:** the twin's against the maker's model (coverage, count accuracy);
- **joint axes and places:** each twin axis's direction (degrees) and position (mm) against the
  maker's joint frames in the same pose;
- **ranges:** from joint recordings made in Isaac Sim, the range each joint reached against the
  twin's limits (within 1 degree, or 1 mm on a sliding joint);
- **evidence:** the twin's quotes found on their cited pages (``quotes.check_quotes``), and its
  stand-ins and issues counted.

The maker's model is a URDF (or a xacro file whose macros are already expanded in place, as
iRC_ROS's ReBeL descriptions are) with COLLADA meshes, both read with the standard library: the
``${...}`` expressions are evaluated by a small arithmetic reader, and ``$(find package)`` comes
from the score file. A score file (``<machine>.score.json`` beside the reference facts) maps the
twin's parts and joints to the model's links and joints, and gives the model's joint values in
the twin's modelled pose; the model is moved so that one joint's point meets the twin's.

No spatial index is installed (rtree, scipy), so distances are between dense surface samples:
the nearest-sample distance overstates the distance to the surface by up to about half the
samples' spacing, which ``SHAPE_SAMPLES`` keeps near a millimetre on an arm's links.

Run from ``backend/``::

    uv run python -m moonwalkers.pipelines.b.score RUN --maker FILE [--recording CSV ...]
        [--no-photos] [--data DATA]

It writes ``RUN/score/score.json`` and ``RUN/score/SCORE.md``, and may be run again (with new
recordings, say): the score is not part of the build, which stays as it was written.
"""

from __future__ import annotations

import argparse
import ast
import csv
import json
import math
import operator
import re
import sys
import xml.etree.ElementTree as ET
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import trimesh
from pydantic import BaseModel, ConfigDict

from moonwalkers.contracts.pipeline_result import PipelineResult

from .dry_run import REFERENCE_FILE
from .part_views import fit_fed_photos, twin_scene
from .parts_spec import PartsSpec, oriented_mesh
from .pipeline import GENERATOR_DIR, SPEC_FILE, cited_length, generated_mesh, load_reference
from .pipeline import read_spec as read_geometry_spec
from .quotes import check_quotes, citations_in

SCORE_DIR = "score"
SIZE_TARGET = 0.06  # the T33901 reached -5.9% to +5.8% (the plan's scorecard)
SIZE_FLAG = 0.10
RANGE_TARGET_DEG = 1.0
RANGE_TARGET_MM = 1.0  # a sliding joint's (the plan's scorecard: "within 1 deg or 1 mm")
SHAPE_SAMPLES = 40_000  # surface samples a part (and a maker's link)
_CHUNK = 500


# ------------------------------------------------------------------------------ the score file
class MakerModel(BaseModel):
    """How a twin is compared with its maker's model (``<machine>.score.json``)."""

    model_config = ConfigDict(extra="forbid")

    urdf: str  # under the data folder
    packages: dict[str, str]  # $(find name): a folder under the data folder
    source_id: str  # the reference facts' source for the model
    parts: dict[str, str]  # twin part -> the model's link
    joints: dict[str, str]  # twin joint -> the model's joint
    pose_deg: dict[str, float] = {}  # the model's joint values in the twin's modelled pose
    align_joint: str  # the twin joint whose point the model's joint point is moved onto
    no_shape: dict[str, str] = {}  # twin part -> why its shape is not compared
    note: str = ""


# ------------------------------------------------------------------------- reading a URDF
_OPERATORS: dict[type, Callable[[float, float], float]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
}
_NAMES = {"pi": math.pi}
_EXPRESSION = re.compile(r"\$\{([^}]*)\}")
_FIND = re.compile(r"\$\(find ([^)]+)\)")


def evaluate(expression: str) -> float:
    """A xacro expression's value: numbers, ``pi``, + - * / ** and brackets only."""

    def value(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return value(node.body)
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return float(node.value)
        if isinstance(node, ast.Name) and node.id in _NAMES:
            return _NAMES[node.id]
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub | ast.UAdd):
            sign = -1.0 if isinstance(node.op, ast.USub) else 1.0
            return sign * value(node.operand)
        if isinstance(node, ast.BinOp) and type(node.op) in _OPERATORS:
            return _OPERATORS[type(node.op)](value(node.left), value(node.right))
        raise ValueError(f"not an arithmetic expression: {expression!r}")

    return value(ast.parse(expression.strip(), mode="eval"))


def expand(text: str, packages: Mapping[str, Path], prefix: str = "") -> str:
    """``text`` with ``${prefix}`` replaced, each other ``${...}`` evaluated, and each
    ``$(find package)`` given its folder."""

    def one(match: re.Match[str]) -> str:
        inner = match.group(1).strip()
        return prefix if inner == "prefix" else repr(evaluate(inner))

    def found(match: re.Match[str]) -> str:
        name = match.group(1).strip()
        if name not in packages:
            raise ValueError(f"no folder given for package {name!r}")
        return Path(packages[name]).as_posix()

    return _FIND.sub(found, _EXPRESSION.sub(one, text))


@dataclass(frozen=True)
class UrdfJoint:
    name: str
    kind: str
    parent: str
    child: str
    xyz: tuple[float, float, float]
    rpy: tuple[float, float, float]
    axis: tuple[float, float, float]


@dataclass(frozen=True)
class UrdfModel:
    joints: list[UrdfJoint]
    meshes: dict[str, Path]  # link -> its visual mesh (visual origins are not read: all zero)

    @property
    def root(self) -> str:
        children = {j.child for j in self.joints}
        roots = [j.parent for j in self.joints if j.parent not in children]
        if not roots:
            raise ValueError("the model has no root link")
        return roots[0]


def _vector(text: str | None, packages: Mapping[str, Path]) -> tuple[float, float, float]:
    if not text:
        return (0.0, 0.0, 0.0)
    x, y, z = (float(v) for v in expand(text, packages).split())
    return (x, y, z)


def read_urdf(path: Path, packages: Mapping[str, Path]) -> UrdfModel:
    """The joints and visual meshes of a URDF, or of a xacro file whose links and joints are
    written out (macros are not run). Where a joint is defined twice (a xacro ``if`` and
    ``unless``), the first is kept: both give the same frames."""
    root = ET.parse(path).getroot()
    joints: dict[str, UrdfJoint] = {}
    meshes: dict[str, Path] = {}
    for element in root.iter():
        tag = element.tag.split("}")[-1]
        if tag == "joint" and element.find("parent") is not None:
            name = expand(element.get("name", ""), packages)
            if name in joints:
                continue
            origin = element.find("origin")
            axis = element.find("axis")
            joints[name] = UrdfJoint(
                name=name,
                kind=element.get("type", ""),
                parent=expand(element.find("parent").get("link", ""), packages),  # type: ignore[union-attr]
                child=expand(element.find("child").get("link", ""), packages),  # type: ignore[union-attr]
                xyz=_vector(origin.get("xyz") if origin is not None else None, packages),
                rpy=_vector(origin.get("rpy") if origin is not None else None, packages),
                axis=_vector(axis.get("xyz") if axis is not None else "1 0 0", packages),
            )
        elif tag == "link":
            mesh = element.find("visual/geometry/mesh")
            if mesh is not None:
                filename = expand(mesh.get("filename", ""), packages)
                filename = filename.removeprefix("file://")
                meshes[expand(element.get("name", ""), packages)] = Path(filename)
    return UrdfModel(list(joints.values()), meshes)


_COLLADA = {"c": "http://www.collada.org/2005/11/COLLADASchema"}


def read_collada(path: Path) -> trimesh.Trimesh:
    """A COLLADA file's triangles, in metres (its ``<unit meter>``). Node transforms are not
    applied: robot description meshes are written in their link's frame."""
    root = ET.parse(path).getroot()
    unit = root.find("c:asset/c:unit", _COLLADA)
    metres = float(unit.get("meter", "1")) if unit is not None else 1.0
    pieces = []
    for geometry in root.findall(".//c:geometry", _COLLADA):
        mesh = geometry.find("c:mesh", _COLLADA)
        if mesh is None:
            continue
        vertices = mesh.find("c:vertices", _COLLADA)
        position = vertices.find("c:input[@semantic='POSITION']", _COLLADA)  # type: ignore[union-attr]
        source = mesh.find(f"c:source[@id='{position.get('source', '').lstrip('#')}']", _COLLADA)  # type: ignore[union-attr]
        points = np.array(source.find("c:float_array", _COLLADA).text.split(), float)  # type: ignore[union-attr]
        points = points.reshape(-1, 3) * metres
        for triangles in mesh.findall("c:triangles", _COLLADA):
            stride = max(int(i.get("offset", "0")) for i in triangles.findall("c:input", _COLLADA))
            p = np.array(triangles.find("c:p", _COLLADA).text.split(), int)  # type: ignore[union-attr]
            offset = int(triangles.find("c:input[@semantic='VERTEX']", _COLLADA).get("offset"))  # type: ignore[union-attr, arg-type]
            faces = p.reshape(-1, stride + 1)[:, offset].reshape(-1, 3)
            pieces.append(trimesh.Trimesh(points, faces, process=False))
    if not pieces:
        raise ValueError(f"{path} has no triangles")
    return trimesh.util.concatenate(pieces)


# ------------------------------------------------------------------------------ kinematics
def rotation_rpy(rpy: Sequence[float]) -> np.ndarray:
    """URDF's fixed-axis roll, pitch, yaw: Rz(yaw) Ry(pitch) Rx(roll)."""
    return (
        _turn((0.0, 0.0, 1.0), rpy[2]) @ _turn((0.0, 1.0, 0.0), rpy[1]) @ _turn((1, 0, 0), rpy[0])
    )


def _turn(axis: Sequence[float], angle: float) -> np.ndarray:
    return trimesh.transformations.rotation_matrix(angle, axis)[:3, :3]


@dataclass(frozen=True)
class JointFrame:
    point: np.ndarray  # on the joint's axis, in the model's root frame
    axis: np.ndarray  # unit


def pose(
    model: UrdfModel, values: Mapping[str, float]
) -> tuple[dict[str, np.ndarray], dict[str, JointFrame]]:
    """Each link's 4x4 transform and each joint's frame in the root link's frame, with the
    joints at ``values`` (radians; 0 for joints not given)."""
    links = {model.root: np.eye(4)}
    frames: dict[str, JointFrame] = {}
    pending = list(model.joints)
    while pending:
        ready = [j for j in pending if j.parent in links]
        if not ready:
            raise ValueError(f"joints not connected to {model.root}: {[j.name for j in pending]}")
        for joint in ready:
            at = np.eye(4)
            at[:3, :3] = rotation_rpy(joint.rpy)
            at[:3, 3] = joint.xyz
            frame = links[joint.parent] @ at
            axis = np.asarray(joint.axis, float)
            norm = float(np.linalg.norm(axis))
            if joint.kind != "fixed" and norm > 0:
                axis /= norm
                frames[joint.name] = JointFrame(frame[:3, 3].copy(), frame[:3, :3] @ axis)
            moved = np.eye(4)
            if joint.kind in ("revolute", "continuous") and norm > 0:
                moved[:3, :3] = _turn(axis, values.get(joint.name, 0.0))
            elif joint.kind == "prismatic" and norm > 0:
                moved[:3, 3] = axis * values.get(joint.name, 0.0)
            links[joint.child] = frame @ moved
            pending.remove(joint)
    return links, frames


# ------------------------------------------------------------------------------ distances
def nearest(points: np.ndarray, targets: np.ndarray) -> np.ndarray:
    """Each point's distance to its nearest target, by brute force in chunks."""
    squared = (targets**2).sum(axis=1)
    out = np.empty(len(points))
    for start in range(0, len(points), _CHUNK):
        a = points[start : start + _CHUNK]
        d2 = (a**2).sum(axis=1)[:, None] + squared[None, :] - 2.0 * a @ targets.T
        out[start : start + _CHUNK] = np.sqrt(np.maximum(d2.min(axis=1), 0.0))
    return out


def samples(mesh: trimesh.Trimesh, count: int = SHAPE_SAMPLES, seed: int = 0) -> np.ndarray:
    points, _ = trimesh.sample.sample_surface(mesh, count, seed=seed)
    return np.asarray(points)


def line_distance(point: np.ndarray, on_line: np.ndarray, direction: np.ndarray) -> float:
    rel = np.asarray(point) - np.asarray(on_line)
    d = np.asarray(direction) / np.linalg.norm(direction)
    return float(np.linalg.norm(rel - (rel @ d) * d))


def angle_deg(a: Sequence[float], b: Sequence[float]) -> float:
    a, b = np.asarray(a, float), np.asarray(b, float)
    cos = a @ b / (np.linalg.norm(a) * np.linalg.norm(b))
    return math.degrees(math.acos(float(np.clip(cos, -1.0, 1.0))))


# ------------------------------------------------------------------------------ the twin
def twin_part_meshes(usd_file: Path) -> dict[str, trimesh.Trimesh]:
    """Each part's mesh in the twin's file, in metres in the twin's frame (the part is the
    mesh's parent prim, decision 0010's layout)."""
    from pxr import Usd, UsdGeom

    stage = Usd.Stage.Open(str(usd_file))
    metres = UsdGeom.GetStageMetersPerUnit(stage)
    parts: dict[str, list[trimesh.Trimesh]] = {}
    for prim in stage.Traverse():
        if not prim.IsA(UsdGeom.Mesh):
            continue
        mesh = UsdGeom.Mesh(prim)
        points = np.asarray(mesh.GetPointsAttr().Get(), float)
        counts = np.asarray(mesh.GetFaceVertexCountsAttr().Get(), int)
        indices = np.asarray(mesh.GetFaceVertexIndicesAttr().Get(), int)
        faces = _triangles(counts, indices)
        world = np.asarray(
            UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        )
        placed = (np.c_[points, np.ones(len(points))] @ world)[:, :3] * metres  # row vectors
        parts.setdefault(prim.GetParent().GetName(), []).append(
            trimesh.Trimesh(placed, faces, process=False)
        )
    return {name: trimesh.util.concatenate(meshes) for name, meshes in parts.items()}


def _triangles(counts: np.ndarray, indices: np.ndarray) -> np.ndarray:
    faces, at = [], 0
    for n in counts:
        polygon = indices[at : at + n]
        faces += [(polygon[0], polygon[i], polygon[i + 1]) for i in range(1, n - 1)]
        at += n
    return np.asarray(faces, int).reshape(-1, 3)


# ------------------------------------------------------------------------------ measures
@dataclass
class SizeScore:
    fact: str
    measured_m: float
    cited_m: float
    difference: float
    within_target: bool
    flagged: bool


@dataclass
class PhotoScore:
    slot: str
    azimuth_deg: float
    elevation_deg: float
    iou: float


@dataclass
class ShapeScore:
    part: str
    link: str
    twin_to_maker_mean_mm: float
    twin_to_maker_p95_mm: float
    maker_to_twin_mean_mm: float
    maker_to_twin_p95_mm: float


@dataclass
class AxisScore:
    joint: str
    maker_joint: str
    direction_error_deg: float
    position_error_mm: float
    aligned_here: bool = False  # the joint the maker's model was moved onto


@dataclass
class RangeScore:
    """A joint's limits and the range it reached, in degrees, or millimetres on a sliding
    joint (``unit``)."""

    joint: str
    lower: float
    upper: float
    reached_min: float
    reached_max: float
    lower_reached: bool  # within RANGE_TARGET_DEG (or _MM) of the lower limit
    upper_reached: bool
    unit: str = "deg"

    @property
    def within_target(self) -> bool:
        return self.lower_reached and self.upper_reached

    @property
    def verdict(self) -> str:
        """Each end on its own: a check that drives a joint one way reaches one end only."""
        ends = {"lower": self.lower_reached, "upper": self.upper_reached}
        return "; ".join(f"{end} {'reached' if ok else 'not reached'}" for end, ok in ends.items())


@dataclass
class Score:
    twin: str
    run: str
    sizes: list[SizeScore] = field(default_factory=list)
    photos: list[PhotoScore] = field(default_factory=list)
    shape: list[ShapeScore] = field(default_factory=list)
    shape_not_compared: dict[str, str] = field(default_factory=dict)
    parts_and_joints: dict[str, object] = field(default_factory=dict)
    axes: list[AxisScore] = field(default_factory=list)
    ranges: list[RangeScore] = field(default_factory=list)
    evidence: dict[str, object] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


def size_scores(spec: PartsSpec, scale: float, reference_path: Path) -> list[SizeScore]:
    reference = load_reference(reference_path)
    scores = []
    for check in spec.size_checks:
        cited = cited_length(reference, check.fact, "a size check")
        measured = check.measured_model_units * scale
        difference = (measured - cited) / cited
        scores.append(
            SizeScore(
                check.fact,
                round(measured, 5),
                cited,
                round(difference, 4),
                abs(difference) <= SIZE_TARGET,
                abs(difference) > SIZE_FLAG,
            )
        )
    return scores


def photo_scores(run_dir: Path, spec: PartsSpec, scale: float) -> list[PhotoScore]:
    mesh = oriented_mesh(generated_mesh(run_dir), spec)
    scene, _ = twin_scene(mesh, spec, scale)
    fitted = fit_fed_photos(scene, run_dir / GENERATOR_DIR / "prepared", spec.yaw_deg)
    return [
        PhotoScore(f.slot, f.fit.azimuth_deg, f.fit.elevation_deg, round(f.fit.iou, 4))
        for f in fitted
    ]


def maker_pose(
    maker: MakerModel, model: UrdfModel, result: PipelineResult
) -> tuple[dict[str, np.ndarray], dict[str, JointFrame]]:
    """The maker's links and joint frames in the twin's frame and pose: posed by
    ``maker.pose_deg``, then moved so the aligning joint's point meets the twin's."""
    values = {name: math.radians(v) for name, v in maker.pose_deg.items()}
    links, frames = pose(model, values)
    twin_joints = {j.joint_id: j for j in result.joints}
    target = np.asarray(twin_joints[maker.align_joint].origin_m, float)
    shift = target - frames[maker.joints[maker.align_joint]].point
    move = np.eye(4)
    move[:3, 3] = shift
    links = {name: move @ t for name, t in links.items()}
    frames = {name: JointFrame(f.point + shift, f.axis) for name, f in frames.items()}
    return links, frames


def shape_scores(
    parts: Mapping[str, trimesh.Trimesh],
    maker: MakerModel,
    model: UrdfModel,
    links: Mapping[str, np.ndarray],
    data_dir: Path,
) -> list[ShapeScore]:
    scores = []
    for part, link in maker.parts.items():
        if part in maker.no_shape or part not in parts or link not in model.meshes:
            continue
        theirs = read_collada(_under(data_dir, model.meshes[link]))
        theirs.apply_transform(links[link])
        ours_points, theirs_points = samples(parts[part]), samples(theirs, seed=1)
        ours_to = nearest(ours_points, theirs_points) * 1000.0
        theirs_to = nearest(theirs_points, ours_points) * 1000.0
        scores.append(
            ShapeScore(
                part,
                link,
                round(float(ours_to.mean()), 1),
                round(float(np.percentile(ours_to, 95)), 1),
                round(float(theirs_to.mean()), 1),
                round(float(np.percentile(theirs_to, 95)), 1),
            )
        )
    return scores


def axis_scores(
    result: PipelineResult, maker: MakerModel, frames: Mapping[str, JointFrame]
) -> list[AxisScore]:
    twin_joints = {j.joint_id: j for j in result.joints}
    scores = []
    for joint_id, maker_joint in maker.joints.items():
        joint = twin_joints.get(joint_id)
        frame = frames.get(maker_joint)
        if joint is None or frame is None:
            continue
        scores.append(
            AxisScore(
                joint_id,
                maker_joint,
                round(angle_deg(joint.axis, frame.axis), 2),
                round(line_distance(np.asarray(joint.origin_m), frame.point, frame.axis) * 1e3, 1),
                joint_id == maker.align_joint,
            )
        )
    return scores


def parts_and_joints(result: PipelineResult, maker: MakerModel, model: UrdfModel) -> dict:
    moving = [j for j in model.joints if j.kind != "fixed"]
    twin_moving = [j for j in result.joints if j.joint_type != "fixed"]
    return {
        "maker_links_with_meshes": sorted(model.meshes),
        "maker_moving_joints": [j.name for j in moving],
        "twin_parts": [p.part_id for p in result.parts],
        "twin_moving_joints": [j.joint_id for j in twin_moving],
        "links_matched": f"{len(set(maker.parts.values()) & set(model.meshes))} of "
        f"{len(model.meshes)}",
        "joints_matched": f"{len(set(maker.joints.values()) & {j.name for j in moving})} of "
        f"{len(moving)}",
        "links_not_in_twin": sorted(set(model.meshes) - set(maker.parts.values())),
        "joints_not_in_twin": sorted({j.name for j in moving} - set(maker.joints.values())),
    }


def range_scores(result: PipelineResult, recordings: Sequence[Path]) -> list[RangeScore]:
    """Each joint's reached range over all ``recordings`` (the joint recorder's CSVs) against
    the twin's limits; joints no recording names are left out."""
    # the recorder's position columns: "<joint> (rad)" turning, "<joint> (m)" sliding
    shown = {"rad)": (math.degrees, "deg", RANGE_TARGET_DEG), "m)": (_mm, "mm", RANGE_TARGET_MM)}
    reached: dict[str, tuple[list[float], str]] = {}
    for path in recordings:
        with open(path, newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        header = rows[0]
        for column, title in enumerate(header):
            name, _, unit = title.partition(" (")
            if unit not in shown:
                continue
            convert, label, _ = shown[unit]
            values = [convert(float(r[column])) for r in rows[1:] if r[column]]
            reached.setdefault(name, ([], label))[0].extend(values)
    scores = []
    for joint in result.joints:
        if joint.joint_id not in reached or joint.lower_limit is None or joint.upper_limit is None:
            continue
        values, label = reached[joint.joint_id]
        if not values:
            continue
        convert, _, target = next(s for s in shown.values() if s[1] == label)
        lower, upper = convert(joint.lower_limit), convert(joint.upper_limit)
        low, high = min(values), max(values)
        scores.append(
            RangeScore(
                joint.joint_id,
                round(lower, 2),
                round(upper, 2),
                round(low, 2),
                round(high, 2),
                abs(low - lower) <= target,
                abs(high - upper) <= target,
                label,
            )
        )
    return scores


def _mm(metres: float) -> float:
    return metres * 1000.0


def evidence(result: PipelineResult, spec: PartsSpec, data_dir: Path) -> dict:
    document = result.model_dump(mode="json")
    checks = check_quotes(result.sources, list(citations_in(document)), data_dir)
    counts = {s: sum(1 for c in checks if c.status == s) for s in _STATUSES}
    return {
        "quotes": counts,
        "quotes_not_on_their_page": [
            f"{c.where} ({c.citation.source_id}, {c.citation.locator}): {c.citation.quote!r}"
            for c in checks
            if c.status in ("not_found", "elsewhere")
        ],
        "stand_ins": [p.part_id for p in spec.parts if p.kind == "stand_in"],
        "issues": {
            s: sum(1 for i in result.issues if i.severity == s)
            for s in ("error", "warning", "info")
        },
    }


_STATUSES = ("found", "elsewhere", "not_found", "not_checked")


# ------------------------------------------------------------------------------ the run
def _under(data_dir: Path, path: Path) -> Path:
    return path if path.is_absolute() else data_dir / path


def built_result(run_dir: Path, data_dir: Path) -> tuple[str, PipelineResult]:
    """The twin's id and its stored result, from the run's job result."""
    job = json.loads((run_dir / "request.job_result.json").read_text(encoding="utf-8"))
    twin = job.get("twin") or {}
    if not twin.get("built_from"):
        raise ValueError(f"{run_dir} has not built a twin (request.job_result.json)")
    result_file = data_dir / "kb" / "results" / f"{twin['built_from'][0]}.json"
    return twin["twin_id"], PipelineResult.model_validate_json(result_file.read_text("utf-8"))


def score_run(
    run_dir: Path,
    data_dir: Path,
    maker: MakerModel | None,
    recordings: Sequence[Path] = (),
    photos: bool = True,
) -> Score:
    run_dir, data_dir = Path(run_dir).resolve(), Path(data_dir).resolve()
    twin_id, result = built_result(run_dir, data_dir)
    spec = read_geometry_spec(run_dir / SPEC_FILE)
    if not isinstance(spec, PartsSpec):
        raise TypeError("the scorer reads a several-part spec (decision 0027)")
    assembly = json.loads((run_dir / "meshes" / "assembly.json").read_text(encoding="utf-8"))
    scale = float(assembly["scale_factor_m_per_unit"])
    score = Score(twin=twin_id, run=run_dir.relative_to(data_dir).as_posix())
    score.sizes = size_scores(spec, scale, run_dir / REFERENCE_FILE)
    if photos:
        score.photos = photo_scores(run_dir, spec, scale)
    else:
        score.notes.append("Photo match not measured (--no-photos).")
    if maker is not None:
        packages = {name: _under(data_dir, Path(p)) for name, p in maker.packages.items()}
        model = read_urdf(_under(data_dir, Path(maker.urdf)), packages)
        links, frames = maker_pose(maker, model, result)
        parts = twin_part_meshes(run_dir / "twin.usdc")
        score.shape = shape_scores(parts, maker, model, links, data_dir)
        score.shape_not_compared = dict(maker.no_shape)
        score.axes = axis_scores(result, maker, frames)
        score.parts_and_joints = parts_and_joints(result, maker, model)
        score.notes.append(
            f"The maker's model ({maker.source_id}) is posed by {maker.pose_deg} (degrees) and "
            f"moved so its {maker.joints[maker.align_joint]} meets the twin's "
            f"{maker.align_joint}. {maker.note}".strip()
        )
    else:
        score.notes.append("No maker's model given: shape, axes, parts and joints not measured.")
    score.ranges = range_scores(result, recordings)
    if not recordings:
        score.notes.append("No joint recordings given: ranges not measured.")
    score.evidence = evidence(result, spec, data_dir)
    return score


# ------------------------------------------------------------------------------ the report
def format_score(score: Score) -> str:
    targets = "the lab's machines plan, \"How 'accurately' is measured: the scorecard\""
    lines = [f"# Score of {score.twin}", "", f"Run: `{score.run}`. Targets: {targets}.", ""]
    lines += ["## Sizes (target: within 6%; over 10% flagged)", ""]
    lines += ["| Size | Twin (m) | Cited (m) | Difference | |", "|---|---|---|---|---|"]
    for s in score.sizes:
        mark = "flagged" if s.flagged else ("within" if s.within_target else "outside")
        lines.append(
            f"| {s.fact} | {s.measured_m:.4f} | {s.cited_m:.4f} | {s.difference:+.1%} | {mark} |"
        )
    lines += ["", "## Match with the photos (silhouette IoU; no target yet)", ""]
    lines += [
        f"- {p.slot}: IoU {p.iou:.3f} (azimuth {p.azimuth_deg:+.0f}, elevation "
        f"{p.elevation_deg:.0f})"
        for p in score.photos
    ] or ["- not measured"]
    lines += ["", "## Shape against the maker's model (mm; no target yet)", ""]
    if score.shape:
        lines += [
            "| Part | Maker's link | Twin to maker: mean | p95 | Maker to twin: mean | p95 |",
            "|---|---|---|---|---|---|",
        ]
        lines += [
            f"| {s.part} | {s.link} | {s.twin_to_maker_mean_mm:.1f} | {s.twin_to_maker_p95_mm:.1f}"
            f" | {s.maker_to_twin_mean_mm:.1f} | {s.maker_to_twin_p95_mm:.1f} |"
            for s in score.shape
        ]
    else:
        lines.append("- not measured")
    lines += [f"- {part}: not compared: {why}" for part, why in score.shape_not_compared.items()]
    lines += ["", "## Parts and joints (target: every moving part the sources name)", ""]
    lines += [f"- {k.replace('_', ' ')}: {v}" for k, v in score.parts_and_joints.items()] or [
        "- not measured"
    ]
    lines += ["", "## Joint axes and places (no target yet)", ""]
    if score.axes:
        lines += ["| Joint | Maker's | Direction (deg) | Position (mm) |", "|---|---|---|---|"]
        lines += [
            f"| {a.joint} | {a.maker_joint} | {a.direction_error_deg:.2f} | "
            f"{a.position_error_mm:.1f}{' (aligned here)' if a.aligned_here else ''} |"
            for a in score.axes
        ]
    else:
        lines.append("- not measured")
    lines += ["", "## Ranges reached in Isaac Sim (target: within 1 degree or 1 mm)", ""]
    if score.ranges:
        lines += ["| Joint | Limits | Reached | |", "|---|---|---|---|"]
        lines += [
            f"| {r.joint} | {r.lower:+.2f} to {r.upper:+.2f} {r.unit} | {r.reached_min:+.2f} "
            f"to {r.reached_max:+.2f} {r.unit} | {r.verdict} |"
            for r in score.ranges
        ]
    else:
        lines.append("- not measured")
    lines += ["", "## Evidence (target: every quote found)", ""]
    lines += [f"- {k.replace('_', ' ')}: {v}" for k, v in score.evidence.items()]
    lines += ["", "## Notes", ""] + [f"- {n}" for n in score.notes]
    return "\n".join(lines) + "\n"


def write_score(score: Score, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    data = out_dir / "score.json"
    data.write_text(json.dumps(asdict(score), indent=2) + "\n", encoding="utf-8")
    report = out_dir / "SCORE.md"
    report.write_text(format_score(score), encoding="utf-8")
    return data, report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score a built twin by the plan's scorecard.")
    parser.add_argument("run_dir", type=Path, help="data/machines/<machine>/runs/<run>")
    parser.add_argument("--maker", type=Path, help="the score file: the maker's model, mapped")
    parser.add_argument(
        "--recording", type=Path, nargs="+", action="extend", default=[], help="joint recordings"
    )
    parser.add_argument("--no-photos", action="store_true", help="skip the photo match")
    parser.add_argument("--data", type=Path, help="data folder (default: from the run folder)")
    args = parser.parse_args(argv)
    run_dir = args.run_dir.resolve()
    data_dir = (args.data or run_dir.parents[3]).resolve()
    maker = (
        MakerModel.model_validate_json(args.maker.read_text(encoding="utf-8"))
        if args.maker
        else None
    )
    score = score_run(run_dir, data_dir, maker, args.recording, photos=not args.no_photos)
    data, report = write_score(score, run_dir / SCORE_DIR)
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    print(format_score(score))
    print(f"written: {data} and {report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
