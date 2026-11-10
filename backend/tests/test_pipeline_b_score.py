"""The scorer (the lab's machines plan, Phase 2): reading a maker's URDF and COLLADA meshes with
the standard library, posing it, and the measures that need no generated mesh."""

import json
import math
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest
import trimesh

from moonwalkers.pipelines.b import score
from moonwalkers.usd import primitive_arm as arm

PACKAGE = Path(score.__file__).parent

URDF = """<?xml version="1.0" ?>
<robot xmlns:xacro="http://www.ros.org/wiki/xacro" name="two">
  <xacro:macro name="two_description" params="prefix continuous_last_joint">
    <link name="${prefix}base_link">
      <visual><geometry>
        <mesh filename="file://$(find two_description)/meshes/Base.dae"/>
      </geometry></visual>
    </link>
    <joint name="${prefix}joint1" type="revolute">
      <parent link="${prefix}base_link"/>
      <child link="${prefix}link_1"/>
      <origin rpy="0.0 0.0 0.0" xyz="0.0 0 0.100"/>
      <axis xyz="0 0 -1"/>
      <limit lower="${-pi*179/180}" upper="${pi*179/180}" velocity="${pi*45/180}"/>
    </joint>
    <link name="${prefix}link_1"/>
    <xacro:if value="${continuous_last_joint}">
      <joint name="${prefix}joint2" type="continuous">
        <parent link="${prefix}link_1"/>
        <child link="${prefix}link_2"/>
        <origin rpy="0.0 ${pi/6} 0.0" xyz="0.0 0 ${0.252 - 0.100}"/>
        <axis xyz="0 1 0"/>
      </joint>
    </xacro:if>
    <xacro:unless value="${continuous_last_joint}">
      <joint name="${prefix}joint2" type="revolute">
        <parent link="${prefix}link_1"/>
        <child link="${prefix}link_2"/>
        <origin rpy="0.0 ${pi/6} 0.0" xyz="0.0 0 ${0.252 - 0.100}"/>
        <axis xyz="0 1 0"/>
      </joint>
    </xacro:unless>
    <link name="${prefix}link_2"/>
    <joint name="${prefix}joint3" type="revolute">
      <parent link="${prefix}link_2"/>
      <child link="${prefix}link_3"/>
      <origin rpy="0 0 0" xyz="0 0 0.237"/>
      <axis xyz="0 1 0"/>
    </joint>
    <link name="${prefix}link_3"/>
  </xacro:macro>
</robot>
"""


def collada_box(extent_mm: float) -> str:
    """A COLLADA cube written in millimetres, as the unit element says."""
    box = trimesh.creation.box(extents=(extent_mm,) * 3)
    points = " ".join(f"{v:g}" for v in box.vertices.ravel())
    faces = " ".join(str(i) for i in box.faces.ravel())  # one input: the vertex index alone
    return f"""<?xml version="1.0" encoding="utf-8"?>
<COLLADA xmlns="http://www.collada.org/2005/11/COLLADASchema" version="1.4.1">
  <asset><unit name="millimeter" meter="0.001"/><up_axis>Z_UP</up_axis></asset>
  <library_geometries><geometry id="g"><mesh>
    <source id="p"><float_array id="pa" count="{box.vertices.size}">{points}</float_array></source>
    <vertices id="v"><input semantic="POSITION" source="#p"/></vertices>
    <triangles count="{len(box.faces)}"><input semantic="VERTEX" source="#v" offset="0"/>
      <p>{faces}</p></triangles>
  </mesh></geometry></library_geometries>
</COLLADA>
"""


@pytest.fixture
def two(tmp_path: Path) -> score.UrdfModel:
    package = tmp_path / "two_description"
    (package / "meshes").mkdir(parents=True)
    (package / "meshes" / "Base.dae").write_text(collada_box(100.0), encoding="utf-8")
    (package / "two.xacro").write_text(URDF, encoding="utf-8")
    return score.read_urdf(package / "two.xacro", {"two_description": package})


def test_xacro_expressions_are_arithmetic_with_pi_only() -> None:
    assert score.evaluate("pi*179/180") == pytest.approx(math.radians(179))
    assert score.evaluate("-pi/24") == pytest.approx(math.radians(-7.5))
    assert score.evaluate("0.149 - 0.03") == pytest.approx(0.119)
    for unsafe in ("__import__('os')", "rebel_version == '00'", "x"):
        with pytest.raises(ValueError):
            score.evaluate(unsafe)


def test_a_xacro_file_is_read_with_its_expressions_and_its_first_definitions(two) -> None:
    joints = {j.name: j for j in two.joints}
    assert list(joints) == ["joint1", "joint2", "joint3"]  # joint2 once: its first definition
    assert joints["joint2"].kind == "continuous"
    assert joints["joint2"].rpy == pytest.approx((0.0, math.pi / 6, 0.0))
    assert joints["joint2"].xyz == pytest.approx((0.0, 0.0, 0.152))
    assert joints["joint1"].axis == (0.0, 0.0, -1.0)
    assert two.root == "base_link"
    assert two.meshes["base_link"].name == "Base.dae" and two.meshes["base_link"].is_file()


def test_a_collada_mesh_is_read_in_metres(two) -> None:
    mesh = score.read_collada(two.meshes["base_link"])
    assert mesh.extents == pytest.approx([0.1, 0.1, 0.1])
    assert len(mesh.faces) == 12


def test_posing_adds_the_origin_pitch_to_the_joint_value(two) -> None:
    _, frames = score.pose(two, {"joint2": math.radians(-30)})
    assert frames["joint2"].point == pytest.approx([0.0, 0.0, 0.252])
    # joint2's origin pitch (+30) and its value (-30) cancel: joint3 stands straight above it
    assert frames["joint3"].point == pytest.approx([0.0, 0.0, 0.489])
    assert frames["joint1"].axis == pytest.approx([0.0, 0.0, -1.0])
    _, bent = score.pose(two, {"joint2": math.radians(60)})  # +90 in all: leaning towards +x
    assert bent["joint3"].point == pytest.approx([0.237, 0.0, 0.252])


def test_distances_and_angles() -> None:
    points = np.array([[0.0, 0.0, 0.0], [3.0, 4.0, 0.0]])
    assert score.nearest(points, np.array([[0.0, 0.0, 1.0]])) == pytest.approx(
        [1.0, math.hypot(5, 1)]
    )
    assert score.line_distance(np.array([1.0, 2.0, 5.0]), np.zeros(3), np.array([0, 0, 2.0])) == (
        pytest.approx(math.sqrt(5))
    )
    assert score.angle_deg((0, 0, 1), (0, 0, -1)) == pytest.approx(180.0)


def test_the_box_arm_against_a_matching_model_scores_its_axes_exactly(
    two, fixed_time: datetime
) -> None:
    _, result = arm.build_test_arm(fixed_time)
    maker = score.MakerModel(
        urdf="two.xacro",
        packages={},
        source_id="t",
        parts={"base": "base_link"},
        joints={"joint1": "joint1", "joint2": "joint2", "joint3": "joint3"},
        pose_deg={"joint2": -30.0},  # straight up, as the box arm is built
        align_joint="joint2",
    )
    _, frames = score.maker_pose(maker, two, result)
    axes = {a.joint: a for a in score.axis_scores(result, maker, frames)}
    assert axes["joint2"].aligned_here and axes["joint2"].position_error_mm == 0.0
    assert axes["joint3"].direction_error_deg == pytest.approx(0.0)
    assert axes["joint3"].position_error_mm == pytest.approx(0.0, abs=0.05)
    assert axes["joint1"].direction_error_deg == pytest.approx(0.0)
    counts = score.parts_and_joints(result, maker, two)
    assert counts["joints_matched"] == "3 of 3"  # the model's three moving joints
    assert counts["links_matched"] == "1 of 1"


def test_ranges_are_read_from_joint_recordings(tmp_path: Path, fixed_time: datetime) -> None:
    _, result = arm.build_test_arm(fixed_time)
    lower, upper = (math.radians(v) for v in arm.RANGES["joint5"][:2])
    lines = ["time_s,joint5 (rad),joint2 (rad),joint5 (rad/s)"]
    lines += [f"{t / 10},{lower + (upper - lower) * t / 10},0.1,0.8" for t in range(11)]
    (tmp_path / "sweep.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    ranges = {r.joint: r for r in score.range_scores(result, [tmp_path / "sweep.csv"])}
    assert ranges["joint5"].within_target
    assert ranges["joint5"].reached_min_deg == pytest.approx(arm.RANGES["joint5"][0])
    assert not ranges["joint2"].within_target  # held still at 5.7 degrees
    assert ranges["joint2"].verdict == "lower not reached; upper not reached"
    assert "joint1" not in ranges  # no recording names it


def test_each_end_of_a_range_is_scored_on_its_own(tmp_path: Path, fixed_time: datetime) -> None:
    _, result = arm.build_test_arm(fixed_time)
    upper = math.radians(arm.RANGES["joint5"][1])
    lines = ["time_s,joint5 (rad)"] + [f"{t / 10},{upper * t / 10}" for t in range(11)]
    (tmp_path / "spin.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (joint5,) = score.range_scores(result, [tmp_path / "spin.csv"])  # from 0 up only
    assert (joint5.lower_reached, joint5.upper_reached) == (False, True)
    assert joint5.verdict == "lower not reached; upper reached"


def test_the_arms_score_file_maps_every_part_and_joint_in_its_photographed_pose() -> None:
    maker = score.MakerModel.model_validate_json(
        (PACKAGE / "igus_rebel6dof02.score.json").read_text(encoding="utf-8")
    )
    assert set(maker.parts) == {"base", "link1", "link2", "link3", "link4", "link5", "hand"}
    assert set(maker.joints) == {f"joint{i}" for i in range(1, 7)}
    assert set(maker.no_shape) == {"hand"}
    # igus's angles in the photographed pose (decision 0031) less the 00 model's origin pitches
    igus = {"joint2": -21.81, "joint3": 118.82, "joint5": 10.46}
    pitch = {"joint2": 30.0, "joint3": 30.0, "joint5": -7.5}
    assert maker.pose_deg == pytest.approx({j: igus[j] - pitch[j] for j in igus})


def test_a_score_report_lists_every_measure(tmp_path: Path) -> None:
    result = score.Score(twin="x/y@v1", run="machines/x/runs/r")
    result.sizes = [score.SizeScore("reach", 0.7, 0.66, 0.06, True, False)]
    result.ranges = [score.RangeScore("joint1", -179.0, 179.0, -178.5, 178.9, True, True)]
    data, report = score.write_score(result, tmp_path / "score")
    text = report.read_text(encoding="utf-8")
    for heading in ("## Sizes", "## Match with the photos", "## Shape", "## Parts and joints",
                    "## Joint axes", "## Ranges", "## Evidence"):  # fmt: skip
        assert heading in text
    assert "| reach | 0.7000 | 0.6600 | +6.0% | within |" in text
    assert json.loads(data.read_text(encoding="utf-8"))["twin"] == "x/y@v1"
