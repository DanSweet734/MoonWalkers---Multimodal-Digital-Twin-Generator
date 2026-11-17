"""A maker's robot description (URDF), read for its joints, their frames and its links' sizes
(lab's machines plan, Phase 7; decision 0037).

The maker's model is a source of facts, never the twin's geometry (decision 0031; Daniel,
2026-11-09: "The maker's meshes are not imported"). From it this module reads:

- each joint: its type, parent and child links, origin, axis, limits, velocity, and the joint it
  copies (``<mimic>``), with the line of the file it starts on, so a spec can cite it;
- each link's pose for given joint positions (forward kinematics), followers moved by their
  ``<mimic>`` (position = multiplier * leader + offset, as URDF defines it);
- each link's size: the bounding box of its visual mesh in the link's own frame. The mesh file is
  read for its extents only; nothing of it is written into a twin.

``Box`` and ``boxes_overlap`` test whether two oriented boxes overlap (the separating axis
test), so a spec can check that stand-ins built from those sizes do not overlap where the twin
would make them collide (decision 0032: parts no joint joins collide).

Angles are radians and lengths metres, as in URDF.
"""

from __future__ import annotations

import itertools
import math
import re
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import trimesh


class UrdfError(ValueError):
    pass


@dataclass(frozen=True)
class Mimic:
    leader: str
    multiplier: float = 1.0
    offset: float = 0.0


@dataclass(frozen=True)
class UrdfJoint:
    name: str
    joint_type: str  # "revolute", "prismatic", "fixed", "continuous"
    parent: str
    child: str
    xyz: tuple[float, float, float]
    rpy: tuple[float, float, float]
    axis: tuple[float, float, float]
    lower: float | None
    upper: float | None
    velocity: float | None
    effort: float | None
    mimic: Mimic | None
    line: int  # the line of the file where the joint's element starts

    @property
    def moves(self) -> bool:
        return self.joint_type != "fixed"


@dataclass(frozen=True)
class UrdfLink:
    name: str
    mesh: str | None  # the visual mesh's file name, as written
    visual_xyz: tuple[float, float, float] = (0.0, 0.0, 0.0)
    visual_rpy: tuple[float, float, float] = (0.0, 0.0, 0.0)
    scale: tuple[float, float, float] = (1.0, 1.0, 1.0)
    line: int = 0


@dataclass
class UrdfModel:
    path: Path
    name: str
    root: str
    links: dict[str, UrdfLink]
    joints: dict[str, UrdfJoint]  # in file order
    _boxes: dict[str, tuple[np.ndarray, np.ndarray]] = field(default_factory=dict, repr=False)

    @classmethod
    def read(cls, path: Path) -> UrdfModel:
        path = Path(path)
        text = path.read_text(encoding="utf-8")
        try:
            robot = ET.fromstring(text)
        except ET.ParseError as exc:
            raise UrdfError(f"{path.name} is not well-formed XML: {exc}") from exc
        if robot.tag != "robot":
            raise UrdfError(f"{path.name}: a URDF's root element is <robot>, not <{robot.tag}>")
        lines = _element_lines(text)
        links = {}
        for element in robot.findall("link"):
            name = element.get("name", "")
            mesh = element.find("visual/geometry/mesh")
            origin = element.find("visual/origin")
            links[name] = UrdfLink(
                name=name,
                mesh=mesh.get("filename") if mesh is not None else None,
                visual_xyz=_triple(origin, "xyz"),
                visual_rpy=_triple(origin, "rpy"),
                scale=_triple(mesh, "scale", "1 1 1") if mesh is not None else (1.0, 1.0, 1.0),
                line=lines.get(("link", name), 0),
            )
        joints = {}
        for element in robot.findall("joint"):
            name = element.get("name", "")
            parent, child = element.find("parent"), element.find("child")
            if parent is None or child is None:
                raise UrdfError(f"{path.name}: joint '{name}' needs a parent and a child")
            limit, mimic = element.find("limit"), element.find("mimic")
            joints[name] = UrdfJoint(
                name=name,
                joint_type=element.get("type", ""),
                parent=parent.get("link", ""),
                child=child.get("link", ""),
                xyz=_triple(element.find("origin"), "xyz"),
                rpy=_triple(element.find("origin"), "rpy"),
                axis=_triple(element.find("axis"), "xyz", "1 0 0"),
                lower=_number(limit, "lower"),
                upper=_number(limit, "upper"),
                velocity=_number(limit, "velocity"),
                effort=_number(limit, "effort"),
                mimic=Mimic(
                    mimic.get("joint", ""),
                    float(mimic.get("multiplier", 1.0)),
                    float(mimic.get("offset", 0.0)),
                )
                if mimic is not None
                else None,
                line=lines.get(("joint", name), 0),
            )
        for joint in joints.values():
            for end in (joint.parent, joint.child):
                if end not in links:
                    raise UrdfError(f"{path.name}: joint '{joint.name}' names unknown link '{end}'")
            if joint.mimic is not None and joint.mimic.leader not in joints:
                raise UrdfError(
                    f"{path.name}: joint '{joint.name}' copies unknown joint '{joint.mimic.leader}'"
                )
        children = {j.child for j in joints.values()}
        roots = [name for name in links if name not in children]
        if len(roots) != 1:
            raise UrdfError(f"{path.name}: expected one root link, found {roots}")
        return cls(path, robot.get("name", ""), roots[0], links, joints)

    # ------------------------------------------------------------------------- positions
    def positions(self, q: Mapping[str, float] | None = None) -> dict[str, float]:
        """Every moving joint's position: ``q``'s, 0 where it gives none, and each follower's
        from its leader (URDF's mimic: multiplier * leader + offset). Giving a follower's
        position is refused: it is its leader's to set."""
        q = dict(q or {})
        for name in q:
            joint = self.joints.get(name)
            if joint is None:
                raise UrdfError(f"no joint '{name}' in {self.path.name}")
            if joint.mimic is not None:
                raise UrdfError(f"'{name}' follows '{joint.mimic.leader}': set its leader")
        out: dict[str, float] = {}
        for joint in self.joints.values():
            if joint.moves and joint.mimic is None:
                out[joint.name] = float(q.get(joint.name, 0.0))
        for joint in self.joints.values():
            if joint.mimic is not None:
                leader = out[joint.mimic.leader]
                out[joint.name] = joint.mimic.multiplier * leader + joint.mimic.offset
        return out

    def link_poses(self, q: Mapping[str, float] | None = None) -> dict[str, np.ndarray]:
        """Each link's 4x4 pose in the root link's frame."""
        position = self.positions(q)
        poses = {self.root: np.eye(4)}
        pending = list(self.joints.values())
        while pending:
            ready = [j for j in pending if j.parent in poses]
            if not ready:
                raise UrdfError(f"{self.path.name}: joints not connected to '{self.root}'")
            for joint in ready:
                poses[joint.child] = (
                    poses[joint.parent]
                    @ self.origin(joint)
                    @ self.motion(joint, position.get(joint.name, 0.0))
                )
                pending.remove(joint)
        return poses

    def joint_frames(
        self, q: Mapping[str, float] | None = None
    ) -> dict[str, tuple[np.ndarray, np.ndarray]]:
        """Each joint's point and unit axis in the root link's frame (the axis as it stands in
        the joint's origin frame, before the joint's own motion, which does not move it)."""
        poses = self.link_poses(q)
        frames = {}
        for joint in self.joints.values():
            at = poses[joint.parent] @ self.origin(joint)
            axis = np.asarray(joint.axis, dtype=float)
            norm = np.linalg.norm(axis)
            frames[joint.name] = (at[:3, 3].copy(), at[:3, :3] @ (axis / norm if norm else axis))
        return frames

    @staticmethod
    def origin(joint: UrdfJoint) -> np.ndarray:
        matrix = np.eye(4)
        matrix[:3, :3] = rpy_matrix(*joint.rpy)
        matrix[:3, 3] = joint.xyz
        return matrix

    @staticmethod
    def motion(joint: UrdfJoint, position: float) -> np.ndarray:
        matrix = np.eye(4)
        if joint.joint_type in ("revolute", "continuous"):
            matrix[:3, :3] = axis_angle_matrix(joint.axis, position)
        elif joint.joint_type == "prismatic":
            axis = np.asarray(joint.axis, dtype=float)
            matrix[:3, 3] = axis / np.linalg.norm(axis) * position
        return matrix

    # ----------------------------------------------------------------------------- sizes
    def mesh_path(self, link: str) -> Path:
        name = self.links[link].mesh
        if name is None:
            raise UrdfError(f"link '{link}' has no visual mesh")
        relative = name.split("://", 1)[1].split("/", 1)[1] if "://" in name else name
        return self.path.parent / relative

    def link_box(self, link: str) -> tuple[np.ndarray, np.ndarray]:
        """The low and high corners of the link's visual mesh, in the link's own frame (m)."""
        if link not in self._boxes:
            mesh = trimesh.load(self.mesh_path(link), force="mesh")
            info = self.links[link]
            visual = np.eye(4)
            visual[:3, :3] = rpy_matrix(*info.visual_rpy) @ np.diag(info.scale)
            visual[:3, 3] = info.visual_xyz
            points = trimesh.transform_points(mesh.vertices, visual)
            self._boxes[link] = (points.min(axis=0), points.max(axis=0))
        lo, hi = self._boxes[link]
        return lo.copy(), hi.copy()


# ------------------------------------------------------------------------------ boxes
@dataclass(frozen=True)
class Box:
    """An oriented box: its centre, its axes (the columns of ``rotation``) and half sizes."""

    center: np.ndarray
    rotation: np.ndarray
    half: np.ndarray

    @classmethod
    def from_corners(cls, pose: np.ndarray, lo: np.ndarray, hi: np.ndarray) -> Box:
        """The box between ``lo`` and ``hi`` in a frame placed by ``pose`` (4x4)."""
        lo, hi = np.asarray(lo, dtype=float), np.asarray(hi, dtype=float)
        centre = pose[:3, :3] @ ((lo + hi) / 2) + pose[:3, 3]
        return cls(centre, pose[:3, :3].copy(), (hi - lo) / 2)

    def shrunk(self, by: float) -> Box:
        return Box(self.center, self.rotation, np.maximum(self.half - by, 0.0))


def boxes_overlap(a: Box, b: Box) -> bool:
    """Whether two oriented boxes overlap: no separating axis among the 15 candidates (each
    box's three axes and the nine cross products), the standard test for convex boxes."""
    axes = [a.rotation[:, i] for i in range(3)] + [b.rotation[:, i] for i in range(3)]
    for i, j in itertools.product(range(3), range(3)):
        cross = np.cross(a.rotation[:, i], b.rotation[:, j])
        if np.linalg.norm(cross) > 1e-9:
            axes.append(cross / np.linalg.norm(cross))
    gap = b.center - a.center
    for axis in axes:
        reach_a = np.sum(a.half * np.abs(a.rotation.T @ axis))
        reach_b = np.sum(b.half * np.abs(b.rotation.T @ axis))
        if abs(gap @ axis) > reach_a + reach_b:
            return False
    return True


def overlapping_pairs(
    boxes: Mapping[str, Iterable[Box]], allowed: Iterable[tuple[str, str]]
) -> list[tuple[str, str]]:
    """The pairs of parts whose boxes overlap, leaving out ``allowed`` pairs (joined parts, which
    do not collide). Each part may be several boxes."""
    skip = {frozenset(pair) for pair in allowed}
    found = []
    for (name_a, boxes_a), (name_b, boxes_b) in itertools.combinations(boxes.items(), 2):
        if frozenset((name_a, name_b)) in skip:
            continue
        if any(boxes_overlap(a, b) for a in boxes_a for b in boxes_b):
            found.append((name_a, name_b))
    return found


# ---------------------------------------------------------------------------- rotations
def rpy_matrix(roll: float, pitch: float, yaw: float) -> np.ndarray:
    """URDF's fixed-axis roll, pitch, yaw: about x, then y, then z (Rz @ Ry @ Rx)."""
    return (
        axis_angle_matrix((0, 0, 1), yaw)
        @ axis_angle_matrix((0, 1, 0), pitch)
        @ axis_angle_matrix((1, 0, 0), roll)
    )


def axis_angle_matrix(axis: Iterable[float], angle: float) -> np.ndarray:
    a = np.asarray(list(axis), dtype=float)
    norm = np.linalg.norm(a)
    if not norm:
        return np.eye(3)
    a = a / norm
    k = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + math.sin(angle) * k + (1 - math.cos(angle)) * k @ k


def matrix_axis_angle(matrix: np.ndarray) -> tuple[tuple[float, float, float], float]:
    """A rotation matrix as a unit axis and an angle in degrees (0 degrees about +Z for none)."""
    cos = float(np.clip((np.trace(matrix) - 1) / 2, -1.0, 1.0))
    angle = math.acos(cos)
    if angle < 1e-9:
        return (0.0, 0.0, 1.0), 0.0
    if math.pi - angle < 1e-6:  # a half turn: the axis from the symmetric part
        b = (matrix + np.eye(3)) / 2
        k = int(np.argmax(np.diag(b)))
        axis = b[:, k] / math.sqrt(b[k, k])
    else:
        axis = np.array(
            [matrix[2, 1] - matrix[1, 2], matrix[0, 2] - matrix[2, 0], matrix[1, 0] - matrix[0, 1]]
        ) / (2 * math.sin(angle))
    axis = axis / np.linalg.norm(axis)
    return (float(axis[0]), float(axis[1]), float(axis[2])), math.degrees(angle)


# ------------------------------------------------------------------------------ helpers
def _triple(
    element: ET.Element | None, name: str, default: str = "0 0 0"
) -> tuple[float, float, float]:
    text = element.get(name) if element is not None else None
    values = [float(v) for v in (text or default).split()]
    if len(values) != 3:
        raise UrdfError(f"'{name}' needs three numbers, not {text!r}")
    return (values[0], values[1], values[2])


def _number(element: ET.Element | None, name: str) -> float | None:
    if element is None or element.get(name) is None:
        return None
    return float(element.get(name))  # type: ignore[arg-type]


_NAMED_ELEMENT = re.compile(r'<(link|joint)\s[^>]*?\bname\s*=\s*"([^"]*)"', re.DOTALL)


def _element_lines(text: str) -> dict[tuple[str, str], int]:
    """The line where each ``<link name=...>`` and ``<joint name=...>`` starts, its attributes
    on that line or the next ones (SolidWorks' exporter writes one attribute per line)."""
    lines: dict[tuple[str, str], int] = {}
    for match in _NAMED_ELEMENT.finditer(text):
        number = text.count("\n", 0, match.start()) + 1
        lines.setdefault((match.group(1), match.group(2)), number)
    return lines
