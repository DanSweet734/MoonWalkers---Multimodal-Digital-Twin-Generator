"""The URDF reader (decision 0037): joints and their lines, poses with mimic followers, link
sizes, and the oriented-box overlap test."""

import math
from pathlib import Path

import numpy as np
import pytest
import trimesh

from moonwalkers.pipelines.b.urdf_model import (
    Box,
    UrdfError,
    UrdfModel,
    axis_angle_matrix,
    boxes_overlap,
    matrix_axis_angle,
    overlapping_pairs,
    rpy_matrix,
)

FINGER = """<?xml version="1.0"?>
<robot name="finger">
  <link name="base_link">
    <visual><geometry><mesh filename="package://finger/meshes/base.STL"/></geometry></visual>
  </link>
  <link name="link1">
    <visual>
      <origin xyz="0 0 0.02" rpy="0 0 0"/>
      <geometry><mesh filename="meshes/link1.STL"/></geometry>
    </visual>
  </link>
  <link name="link2">
    <visual><geometry><mesh filename="meshes/link2.STL"/></geometry></visual>
  </link>
  <link name="tip"/>
  <joint name="j1" type="revolute">
    <origin xyz="0 0 0.1" rpy="0 0 0"/>
    <parent link="base_link"/>
    <child link="link1"/>
    <axis xyz="0 1 0"/>
    <limit lower="0" upper="1.4" effort="100" velocity="1"/>
  </joint>
  <joint name="j2" type="revolute">
    <origin xyz="0 0 0.04" rpy="0 0 0"/>
    <parent link="link1"/>
    <child link="link2"/>
    <axis xyz="0 1 0"/>
    <limit lower="0" upper="1.5" effort="100" velocity="1"/>
    <mimic joint="j1" multiplier="0.5" offset="0.1"/>
  </joint>
  <joint
    name="j3"
    type="fixed">
    <origin xyz="0 0 0.03" rpy="0 0 0"/>
    <parent link="link2"/>
    <child link="tip"/>
  </joint>
</robot>
"""


@pytest.fixture
def finger(tmp_path: Path) -> UrdfModel:
    meshes = tmp_path / "meshes"
    meshes.mkdir()
    trimesh.creation.box(extents=(0.04, 0.05, 0.1)).export(meshes / "base.STL")
    trimesh.creation.box(extents=(0.02, 0.016, 0.04)).export(meshes / "link1.STL")
    trimesh.creation.box(extents=(0.018, 0.015, 0.03)).export(meshes / "link2.STL")
    path = tmp_path / "finger.urdf"
    path.write_text(FINGER, encoding="utf-8")
    return UrdfModel.read(path)


def test_reads_joints_with_their_lines(finger: UrdfModel) -> None:
    assert finger.root == "base_link"
    assert list(finger.joints) == ["j1", "j2", "j3"]
    j1, j2 = finger.joints["j1"], finger.joints["j2"]
    assert (j1.lower, j1.upper, j1.velocity, j1.effort) == (0.0, 1.4, 1.0, 100.0)
    assert j2.mimic is not None and (j2.mimic.leader, j2.mimic.multiplier) == ("j1", 0.5)
    lines = FINGER.splitlines()
    assert lines[j1.line - 1].strip().startswith('<joint name="j1"')
    assert lines[finger.links["link1"].line - 1].strip() == '<link name="link1">'
    assert not finger.joints["j3"].moves
    # a joint whose attributes are on the lines below its tag: the tag's line
    assert lines[finger.joints["j3"].line - 1].strip() == "<joint"


def test_followers_take_their_leaders_position(finger: UrdfModel) -> None:
    assert finger.positions({"j1": 1.0}) == {"j1": 1.0, "j2": pytest.approx(0.6)}
    with pytest.raises(UrdfError, match="set its leader"):
        finger.positions({"j2": 0.3})
    with pytest.raises(UrdfError, match="no joint"):
        finger.positions({"nope": 0.3})


def test_link_poses_bend_about_the_joint_axis(finger: UrdfModel) -> None:
    poses = finger.link_poses({"j1": math.pi / 2})
    # j1 at z 0.1 turns +90 degrees about +y, so link1's z axis points along +x
    assert np.allclose(poses["link1"][:3, 3], [0, 0, 0.1])
    assert np.allclose(poses["link1"][:3, 2], [1, 0, 0], atol=1e-12)
    # j2 sits 0.04 along link1's z: now at x 0.04; it adds 0.5 * pi/2 + 0.1 rad more
    assert np.allclose(poses["link2"][:3, 3], [0.04, 0, 0.1], atol=1e-12)
    total = math.pi / 2 + 0.5 * math.pi / 2 + 0.1
    assert np.allclose(poses["link2"][:3, :3], axis_angle_matrix((0, 1, 0), total))
    frames = finger.joint_frames({"j1": math.pi / 2})
    point, axis = frames["j2"]
    assert np.allclose(point, [0.04, 0, 0.1]) and np.allclose(axis, [0, 1, 0])


def test_link_box_in_the_links_own_frame(finger: UrdfModel) -> None:
    lo, hi = finger.link_box("link1")  # the visual origin lifts the mesh by 0.02
    assert np.allclose(lo, [-0.01, -0.008, 0.0]) and np.allclose(hi, [0.01, 0.008, 0.04])
    lo, hi = finger.link_box("base_link")  # package:// names resolve beside the URDF
    assert np.allclose(hi - lo, [0.04, 0.05, 0.1])
    with pytest.raises(UrdfError, match="no visual mesh"):
        finger.link_box("tip")


def test_refuses_a_broken_description(tmp_path: Path) -> None:
    path = tmp_path / "bad.urdf"
    path.write_text(FINGER.replace('<child link="link2"/>', '<child link="ghost"/>'), "utf-8")
    with pytest.raises(UrdfError, match="unknown link 'ghost'"):
        UrdfModel.read(path)
    path.write_text("<robots/>", "utf-8")
    with pytest.raises(UrdfError, match="<robot>"):
        UrdfModel.read(path)


def test_rpy_is_roll_then_pitch_then_yaw() -> None:
    m = rpy_matrix(0.3, -0.2, 1.1)
    expected = (
        axis_angle_matrix((0, 0, 1), 1.1)
        @ axis_angle_matrix((0, 1, 0), -0.2)
        @ axis_angle_matrix((1, 0, 0), 0.3)
    )
    assert np.allclose(m, expected)
    assert np.allclose(rpy_matrix(0, 0, math.pi / 2) @ [1, 0, 0], [0, 1, 0])


@pytest.mark.parametrize("axis,deg", [((0, 0, 1), 0.0), ((1, 2, 3), 40.0), ((0, 1, 0), 180.0)])
def test_matrix_axis_angle_round_trips(axis: tuple[float, ...], deg: float) -> None:
    matrix = axis_angle_matrix(axis, math.radians(deg))
    got_axis, got_deg = matrix_axis_angle(matrix)
    assert got_deg == pytest.approx(deg, abs=1e-6)
    assert np.allclose(axis_angle_matrix(got_axis, math.radians(got_deg)), matrix, atol=1e-9)


def _box(center: tuple[float, ...], half: tuple[float, ...], deg: float = 0.0) -> Box:
    return Box(
        np.array(center, float),
        axis_angle_matrix((0, 0, 1), math.radians(deg)),
        np.array(half, float),
    )


def test_boxes_overlap_and_separate() -> None:
    a = _box((0, 0, 0), (1, 1, 1))
    assert boxes_overlap(a, _box((1.9, 0, 0), (1, 1, 1)))
    assert not boxes_overlap(a, _box((2.1, 0, 0), (1, 1, 1)))
    # a box turned 45 degrees reaches sqrt(2) along x: it touches at 2.3, not at 2.5
    assert boxes_overlap(a, _box((2.3, 0, 0), (1, 1, 1), 45))
    assert not boxes_overlap(a, _box((2.5, 0, 0), (1, 1, 1), 45))
    # two bars crossing, one along x and one along y, above each other or touching
    bar_x = Box(np.zeros(3), np.eye(3), np.array([1.0, 0.1, 0.1]))
    along_y = axis_angle_matrix((0, 0, 1), math.radians(90))
    assert not boxes_overlap(bar_x, Box(np.array([0, 0, 0.25]), along_y, bar_x.half))
    assert boxes_overlap(bar_x, Box(np.array([0, 0, 0.15]), along_y, bar_x.half))


def test_boxes_overlap_agrees_with_sampled_points() -> None:
    """Where points sampled inside one box fall inside the other, the test must say overlap;
    two boxes far apart must not."""
    rng = np.random.default_rng(7)
    for _ in range(200):
        boxes = []
        for _ in range(2):
            axis = rng.normal(size=3)
            boxes.append(
                Box(
                    rng.uniform(-1, 1, size=3),
                    axis_angle_matrix(axis, rng.uniform(0, math.pi)),
                    rng.uniform(0.1, 0.8, size=3),
                )
            )
        a, b = boxes
        points = a.center + (rng.uniform(-1, 1, size=(4000, 3)) * a.half) @ a.rotation.T
        local = (points - b.center) @ b.rotation
        if np.any(np.all(np.abs(local) <= b.half, axis=1)):
            assert boxes_overlap(a, b)
        reach = np.linalg.norm(a.half) + np.linalg.norm(b.half)
        if np.linalg.norm(a.center - b.center) > reach:
            assert not boxes_overlap(a, b)


def test_overlapping_pairs_leaves_out_allowed_ones() -> None:
    boxes = {
        "palm": [_box((0, 0, 0), (1, 1, 1))],
        "knuckle": [_box((0, 0, 1.5), (0.6, 0.6, 0.6))],
        "finger": [_box((0, 0, 2.5), (0.5, 0.5, 0.6)), _box((5, 0, 0), (0.1, 0.1, 0.1))],
    }
    assert overlapping_pairs(boxes, []) == [("palm", "knuckle"), ("knuckle", "finger")]
    assert overlapping_pairs(boxes, [("knuckle", "palm")]) == [("knuckle", "finger")]
