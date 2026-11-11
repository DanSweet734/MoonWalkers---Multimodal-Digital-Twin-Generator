"""A box-and-cylinder ReBeL arm for checking the exporter in Isaac Sim (the lab's machines plan,
Phase 2), as the box-and-cylinder drill press did before the T33901's mesh.

It stands in for the igus REBEL-6DOF-02 before any generated mesh: six revolute joints in series
on the cited frames, and the hand a box on the flange (fixed). It is built in igus's zero pose,
the arm straight up ("Nullstellung", igus's technical documentation, p. 6), so each joint's
limits are igus's own (p. 2). The joints' heights are igus's X1 to X4 where the drawing gives
them, and the ROS model's offsets where it does not (joint 1 above the foot, joint 4 above joint
3, joint 6 above joint 5). The axes are the ROS model's. Link radii, the connector box and the
hand's size are made up, and labelled so. The twin is a test model (``moonwalkers/testarm``), not
the arm itself. Run from ``backend/`` with a run folder (for example
``../data/machines/moonwalkers-testarm/runs/2026-11-09_run-001``)::

    uv run python -m moonwalkers.usd.primitive_arm <run-folder>

That writes one check file per behaviour (``CHECKS``), validates each, copies the joint recorder
and writes ``RUN.md`` with what to look for. The checks are the plan's: each joint turns through
its range, and six driven joints hold a pose under gravity, with the exporter's default drive and
with a stiff one.

Twin frame (decision 0012): metres, +Z up, the front towards +X, the machine's own left towards
+Y, the origin on the floor under joint 1's axis. The front is where the fingertips point in the
photographed pose, fixed to the base (Daniel, 2026-11-09). The ROS model's frame is taken as the
twin's at joint 1's zero [INFERENCE, not confirmed: the reference file's issue on joint 1].
"""

from __future__ import annotations

import argparse
import math
import platform
import shutil
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from importlib.metadata import version as package_version
from pathlib import Path

from moonwalkers.clock import utc_now
from moonwalkers.contracts.pipeline_result import (
    Citation,
    Fact,
    InputType,
    Issue,
    Joint,
    JointMode,
    MachineIdentity,
    Part,
    PipelineId,
    PipelineResult,
    Source,
    TwinRecord,
)
from moonwalkers.kb import machine_key

from .exporter import DriveSettings, JointSettings, write_stage
from .primitive_drill_press import RECORDER, Check, box, check_stage, compound, cylinder, part
from .validate import validate_file

MANUFACTURER = "MoonWalkers"
MODEL = "Test Arm"

DOC = "src-igus-techdoc"
URDF = "src-irc-ros-00"
SYNTHETIC = "src-synthetic"
DOC_URI = (
    "machines/igus-rebel6dof02/inputs/documents/igus-rebel-technical-documentation-2022-08.pdf"
)
DOC_SHA256 = "735c2fbea8ab67d90090c3ae4659399c53e7e91af86d7dbf6b3ba9bb34b68fb3"  # SOURCES.md
URDF_URI = (
    "machines/igus-rebel6dof02/inputs/documents/models/CommonplaceRobotics_iRC_ROS@41701e6/"
    "irc_ros_description/urdf/robots/igus_rebel_6dof_00.description.xacro"
)
URDF_SHA256 = "31d92942b252ae9ea8c49f885ac92ebfc452bf50750680794b113a237d1a16f8"  # MANIFEST
RETRIEVED = datetime(2026, 11, 9, tzinfo=UTC)  # SOURCES.md: "2026-11-09"


def doc(page: int, quote: str) -> Citation:
    return Citation(source_id=DOC, locator=f"PDF p. {page}", quote=quote)


def urdf(where: str, quote: str) -> Citation:
    return Citation(source_id=URDF, locator=where, quote=quote)


MADE_UP = Citation(source_id=SYNTHETIC, locator="made-up size, not in igus's documentation")


def setting(what: str) -> Citation:
    """A value chosen for the test model or a check, not taken from a source."""
    return Citation(source_id=SYNTHETIC, locator=f"setting chosen for the test model: {what}")


SIZES_QUOTE = "ReBeL-6DOF-00 660 252 237 297 126 180"  # p. 6: L1, X1, X2, X3, X4, D1
RANGES = {  # p. 2, "Joint Movement", in degrees
    "joint1": (-179.0, 179.0, "J1: -179° bis to +179°"),
    "joint2": (-80.0, 140.0, "J2: -80° bis to +140°"),
    "joint3": (-80.0, 140.0, "J3: -80° bis to +140°"),
    "joint4": (-179.0, 179.0, "J4: -179° bis to +179°"),
    "joint5": (-95.0, 95.0, "J5: -95° bis to + 95°"),
    "joint6": (-179.0, 179.0, "J6: -179° bis to +179°"),
}
MAX_SPEED = math.radians(45)  # p. 2 "Max. speed 45 [°/s]"; the URDF's velocity="${pi*45/180}"

# ------------------------------------------------------------- heights in the zero pose (m)
FOOT_RADIUS = 0.180 / 2  # p. 2 "Footprint Ø 180 [mm]"; p. 6 D1
J1_Z = 0.100  # URDF joint1 <origin xyz="0.0 0 0.100"/>: the foot's top
J2_Z = 0.252  # p. 6 X1, foot to joint 2's axis
J3_Z = J2_Z + 0.237  # X2
J4_Z = J3_Z + 0.119  # URDF joint4 <origin xyz="0.0 0 ${0.149 - 0.03}"/>
J5_Z = J3_Z + 0.297  # X3
J6_Z = J5_Z + 0.1208  # URDF joint6 <origin xyz="0.0 0 0.1208"/>
FLANGE_Z = J5_Z + 0.126  # X4, joint 5 to the flange's face

# ------------------------------------------------------------------- made-up sizes (stand-ins)
LINK_RADIUS = 0.045
HOUSING_RADIUS, HOUSING_LENGTH = 0.055, 0.12  # the round joint housings across joints 2, 3 and 5
FLANGE_RADIUS = 0.031  # p. 6 D6 "62" is taken as the flange's diameter [INFERENCE]
HAND_SIZE = (0.04, 0.09, 0.19)  # thick (x), wide (y), long (z, from the flange): made up

AXES = {  # the URDF's <axis>, in the twin's frame (module docstring)
    "joint1": ((0.0, 0.0, -1.0), '<axis xyz="0 0 -1"/>'),
    "joint2": ((0.0, 1.0, 0.0), '<axis xyz="0 1 0"/>'),
    "joint3": ((0.0, 1.0, 0.0), '<axis xyz="0 1 0"/>'),
    "joint4": ((0.0, 0.0, 1.0), '<axis xyz="0 0 1"/>'),
    "joint5": ((0.0, 1.0, 0.0), '<axis xyz="0 1 0"/>'),
    "joint6": ((0.0, 0.0, 1.0), '<axis xyz="0 0 1"/>'),
}
HEIGHTS = {
    "joint1": (J1_Z, urdf("joint1's <origin>", '<origin rpy="0.0 0.0 0.0" xyz="0.0 0 0.100"/>')),
    "joint2": (J2_Z, doc(6, SIZES_QUOTE)),
    "joint3": (J3_Z, doc(6, SIZES_QUOTE)),
    "joint4": (J4_Z, urdf("joint4's <origin>", 'xyz="0.0 0 ${0.149 - 0.03}"')),
    "joint5": (J5_Z, doc(6, SIZES_QUOTE)),
    "joint6": (J6_Z, urdf("joint6's <origin>", '<origin rpy="0.0 0.0 0.0" xyz="0.0 0 0.1208"/>')),
}
CHAIN = ("base", "link1", "link2", "link3", "link4", "link5", "flange")
ZERO_OFFSETS = (  # why igus's zero is the URDF's turned by these (reference file's issue)
    urdf("joint2's <origin>", '<origin rpy="0.0 ${pi/6} 0.0" xyz="0.0 0 0.149"/>'),
    urdf("joint5's <origin>", '<origin rpy="0.0 ${-pi/24} 0.0" xyz="0.0 0 ${0.14 + 0.03}"/>'),
)


# ------------------------------------------------------------------------------------- parts
def _along_z(radius: float, z0: float, z1: float) -> dict[str, object]:
    return cylinder(radius, z1 - z0, (0, 0, 1), (0, 0, (z0 + z1) / 2))


def _housing(z: float) -> dict[str, object]:
    return cylinder(HOUSING_RADIUS, HOUSING_LENGTH, (0, 1, 0), (0, 0, z))


def build_parts() -> list[Part]:
    sizes = doc(6, SIZES_QUOTE)
    return [
        part(
            "base",
            "Foot (fixed), with a stand-in connector box on its back (-x)",
            compound(
                _along_z(FOOT_RADIUS, 0.0, J1_Z),
                box((0.06, 0.10, 0.07), (-FOOT_RADIUS - 0.02, 0, 0.035)),
            ),
            doc(2, "Footprint Ø 180 [mm]"),
            urdf("joint1's <origin>", '<origin rpy="0.0 0.0 0.0" xyz="0.0 0 0.100"/>'),
            MADE_UP,
        ),
        part(
            "link1",
            "Link 1: column turning on joint 1, carrying joint 2's housing",
            compound(_along_z(LINK_RADIUS, J1_Z, J2_Z), _housing(J2_Z)),
            sizes,
            MADE_UP,
        ),
        part(
            "link2",
            "Link 2: upper arm, joint 2 to joint 3, carrying joint 3's housing",
            compound(_along_z(LINK_RADIUS, J2_Z + HOUSING_RADIUS, J3_Z), _housing(J3_Z)),
            sizes,
            MADE_UP,
        ),
        part(
            "link3",
            "Link 3: forearm's lower part, joint 3 to joint 4",
            _along_z(LINK_RADIUS, J3_Z + HOUSING_RADIUS, J4_Z),
            sizes,
            MADE_UP,
        ),
        part(
            "link4",
            "Link 4: forearm's upper part, turning on joint 4, carrying joint 5's housing",
            compound(_along_z(LINK_RADIUS * 0.95, J4_Z, J5_Z), _housing(J5_Z)),
            sizes,
            MADE_UP,
        ),
        part(
            "link5",
            "Link 5: wrist, joint 5 to joint 6",
            _along_z(LINK_RADIUS * 0.85, J5_Z + HOUSING_RADIUS, J6_Z),
            sizes,
            MADE_UP,
        ),
        part(
            "flange",
            "Flange, turning on joint 6",
            _along_z(FLANGE_RADIUS, J6_Z, FLANGE_Z),
            sizes,
            MADE_UP,
        ),
        part(
            "hand",
            "Stand-in hand: a box on the flange, wider across y so joint 6's turn shows",
            box(HAND_SIZE, (0, 0, FLANGE_Z + HAND_SIZE[2] / 2)),
            MADE_UP,
        ),
    ]


# ------------------------------------------------------------------------------------ joints
DRIVEN = JointMode(
    kind="driven",
    citations=[doc(2, "Max. speed 45 [°/s]"), urdf("every joint's <limit>", 'effort="330.0"')],
)


def build_joints() -> list[Joint]:
    joints = []
    for i, joint_id in enumerate(RANGES, start=1):
        lower, upper, quote = RANGES[joint_id]
        axis, axis_quote = AXES[joint_id]
        z, where = HEIGHTS[joint_id]
        joints.append(
            Joint(
                joint_id=joint_id,
                joint_type="revolute",
                parent_part=CHAIN[i - 1],
                child_part=CHAIN[i],
                axis=axis,
                origin_m=(0.0, 0.0, z),
                lower_limit=math.radians(lower),
                upper_limit=math.radians(upper),
                max_velocity=MAX_SPEED,
                confidence=0.8,
                citations=[
                    doc(2, quote),
                    urdf(f"{joint_id}'s <axis>", axis_quote),
                    where,
                    *(ZERO_OFFSETS if joint_id in ("joint2", "joint3", "joint5") else ()),
                ],
                mode=DRIVEN,
            )
        )
    joints.append(
        Joint(
            joint_id="hand_on_flange",
            joint_type="fixed",
            parent_part="flange",
            child_part="hand",
            axis=(0.0, 0.0, 1.0),
            origin_m=(0.0, 0.0, FLANGE_Z),
            confidence=0.8,
            citations=[doc(6, SIZES_QUOTE), MADE_UP],
        )
    )
    return joints


def build_test_arm(created_at: datetime) -> tuple[TwinRecord, PipelineResult]:
    """The test twin and the one result it is built from."""
    sources = [
        Source(
            source_id=DOC,
            kind="file",
            input_type=InputType.BROCHURE_DATASHEET,
            uri=DOC_URI,
            title='igus GmbH, "Technical documentation ReBeL", MAT0075179.25, Stand 08/2022, from '
            "https://uploads.unchainedrobotics.de/media/file_upload/"
            "Robolink%20ReBeL_DINA5_v11_a8b0f58f.pdf",
            sha256=DOC_SHA256,
            retrieved_at=RETRIEVED,
            license_note="© igus GmbH; the maker's documentation, kept for internal research only",
        ),
        Source(
            source_id=URDF,
            kind="file",
            input_type=InputType.ONLINE_RESOURCE,
            uri=URDF_URI,
            title="The ReBeL 6DOF version 00 robot description, CommonplaceRobotics/iRC_ROS at "
            "41701e6df3398087d217f0f478622e60f694de41",
            sha256=URDF_SHA256,
            retrieved_at=RETRIEVED,
            license_note="Apache-2.0",
        ),
        Source(
            source_id=SYNTHETIC,
            kind="user_input",
            uri="user",
            title="Box-and-cylinder arm for the lab's machines plan, Phase 2; sizes igus's "
            "documentation and the ROS model do not give are made up",
            retrieved_at=created_at,
        ),
    ]
    result = PipelineResult(
        result_id="res-test-arm-c",
        job_id="test-arm",
        pipeline=PipelineId.C,  # hand-written geometry and kinematics, like a schematic reading
        input_types=[InputType.SCHEMATIC],
        produced_at=created_at,
        produced_by="moonwalkers.usd.primitive_arm (synthetic test model)",
        sources=sources,
        identity=MachineIdentity(
            manufacturer=MANUFACTURER,
            model=MODEL,
            category="test model of a 6-axis arm (the igus ReBeL 6DOF's frames)",
            confidence=1.0,
            citations=[Citation(source_id=SYNTHETIC)],
        ),
        facts=[
            Fact(
                key="max_joint_speed",
                value=MAX_SPEED,
                unit="rad/s",
                original="45 [°/s]",
                confidence=0.9,
                citations=[doc(2, "Max. speed 45 [°/s]")],
            ),
            Fact(
                key="joint2_to_flange",
                value=0.660,
                unit="m",
                original="L1 660",
                confidence=0.85,
                citations=[doc(6, SIZES_QUOTE)],
            ),
        ],
        parts=build_parts(),
        joints=build_joints(),
        issues=ISSUES,
    )
    key = machine_key(MANUFACTURER, MODEL)
    twin = TwinRecord(
        twin_id=f"{key}@v1",
        machine_key=key,
        version=1,
        status="needs_review",
        built_from=[result.result_id],
        created_at=created_at,
    )
    return twin, result


ISSUES = [
    Issue(
        severity="info",
        message="Synthetic test model written by hand to check the USD exporter on the ReBeL's "
        "frames; link radii, the housings, the connector box and the hand are made up.",
    ),
    Issue(
        severity="warning",
        ref="joint1",
        message="Not confirmed: where joint 1's zero points on the base. The ROS model's frame is "
        "taken as the twin's at joint 1's zero, so the arm bends towards +x, the front "
        "[INFERENCE].",
    ),
    Issue(
        severity="info",
        message="Joint heights mix two sources: igus's X1 to X4 (p. 6) for joints 2, 3 and 5 and "
        "the flange; the ROS model's offsets for joint 1 (0.100 m), joint 4 (0.119 m above joint "
        "3) and joint 6 (0.1208 m above joint 5), which igus's drawing does not give.",
    ),
    Issue(
        severity="warning",
        message="The parts do not collide with each other, and there is no floor: joints and "
        "limits alone stop them, so the arm can pass through itself and below its foot.",
    ),
    Issue(
        severity="info",
        message="Masses come from the placeholder density (1000 kg/m^3), not the cited '< 8' kg.",
    ),
]


# ---------------------------------------------------------------------- behaviours to check
DEG = math.radians
# A forward reach for the checks, made up, within every range: the arm leans forward at joint 2,
# bends at joint 3, and the wrist tips at joint 5, so gravity loads joints 2, 3 and 5.
POSE = {
    "joint1": DEG(30),
    "joint2": DEG(45),
    "joint3": DEG(60),
    "joint4": DEG(20),
    "joint5": DEG(45),
    "joint6": DEG(30),
}
STIFF = 10_000.0, 200.0  # w = 100 rad/s, critically damped: the drill press's lock values
SWEEP_DAMPING = 1_000.0  # a velocity drive that keeps to its speed against gravity [INFERENCE]


def _hold(target: float, stiff: bool) -> DriveSettings:
    if not stiff:
        return DriveSettings.hold(target)  # the exporter's default gains (100, 20)
    return DriveSettings(mode="position", target=target, stiffness=STIFF[0], damping=STIFF[1])


def _held_at_pose(stiff: bool, note: str) -> dict[str, JointSettings]:
    return {j: JointSettings(drive=_hold(v, stiff), start=v, note=note) for j, v in POSE.items()}


def _sweep(joint_id: str) -> Check:
    lower, upper, _ = RANGES[joint_id]
    settings = _held_at_pose(True, "held at the check pose by a stiff drive")
    settings[joint_id] = JointSettings(
        drive=DriveSettings(
            mode="velocity", target=MAX_SPEED, stiffness=0.0, damping=SWEEP_DAMPING
        ),
        start=DEG(lower),
        note="turns at the cited 45 degrees a second from its lower limit to its upper",
    )
    seconds = (upper - lower) / 45
    return Check(
        f"{joint_id} turns from {lower:g} to {upper:g} degrees at 45 degrees a second",
        f"On Play {joint_id} jumps to {lower:g} degrees (its start), then turns at 45 degrees a "
        f"second and stops at {upper:g} degrees after about {seconds:.1f} s. The other joints "
        "hold the check pose. The recording should show the joint reach both limits within 1 "
        "degree.",
        settings=settings,
    )


CHECKS: dict[str, Check] = {
    "zero_pose.usdc": Check(
        "igus's zero pose, the arm straight up, every joint held by the default drive",
        "The arm stands straight up and stays there. The hand's wide side faces +y.",
    ),
    "pose_hold_default.usdc": Check(
        "the check pose held by the exporter's default drive (stiffness 100, damping 20)",
        "The arm starts leaning forward with its elbow bent, and should hold that pose. Note how "
        "far it sags: the recording gives each joint's drop from the pose.",
        settings=_held_at_pose(False, "held at the check pose by the exporter's default drive"),
    ),
    "pose_hold_stiff.usdc": Check(
        "the check pose held by a stiff drive (stiffness 10000, damping 200)",
        "The same pose, held by stiffer drives. It should not visibly sag. Shift+drag the hand: "
        "the arm should give a little and return.",
        settings=_held_at_pose(True, "held at the check pose by a stiff drive"),
    ),
    **{f"sweep_{j}.usdc": _sweep(j) for j in RANGES},
}


# ----------------------------------------------------------------------------------- command
def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Write and validate the box-and-cylinder arm's check files."
    )
    parser.add_argument(
        "out_dir", type=Path, help="run folder, e.g. data/machines/<machine>/runs/<run>"
    )
    args = parser.parse_args(argv)

    created_at = utc_now()
    twin, result = build_test_arm(created_at)
    report: list[str] = []
    failed = False
    for name, check in CHECKS.items():
        path = write_stage(check_stage(twin, result, check), args.out_dir / name)
        issues = validate_file(path)
        errors = [i for i in issues if i.severity == "error"]
        failed = failed or bool(errors)
        status = f"{len(errors)} error(s), {len(issues) - len(errors)} other finding(s)"
        print(f"{path}: {status}")
        report += [
            f"### `{name}`",
            f"- Shows: {check.what}.",
            f"- Look for: {check.look_for}",
            f"- Validation: {status}.",
        ]
        for issue in issues:
            print(f"  {issue.severity}: {issue.message} ({issue.ref or '-'})")
            report.append(f"  - {issue.severity}: {issue.message} ({issue.ref or '-'})")
        report += ["- Seen in Isaac Sim (fill in):", ""]
    shutil.copyfile(RECORDER, args.out_dir / "record_joints.py")
    _write_run_notes(args.out_dir, created_at, result, report)
    return 1 if failed else 0


def _write_run_notes(
    out_dir: Path, created_at: datetime, result: PipelineResult, report: list[str]
) -> None:
    versions = (
        f"moonwalkers {package_version('moonwalkers')}, usd-core {package_version('usd-core')}, "
        f"Python {platform.python_version()}"
    )
    pose = ", ".join(f"{j} {math.degrees(v):g}" for j, v in POSE.items())
    lines = [
        "# Run: box-and-cylinder ReBeL arm (the lab's machines plan, Phase 2)",
        "",
        f"- Created (UTC): {created_at.isoformat(timespec='seconds')}",
        f"- Command: `uv run python -m moonwalkers.usd.primitive_arm {out_dir.as_posix()}`",
        f"- Versions: {versions}",
        (
            "- Input: hand-written primitives on the ReBeL's cited frames: heights from igus's "
            "drawing (p. 6) and the ROS model, axes from the ROS model, ranges and speed from "
            "igus (p. 2). Built in igus's zero pose, straight up. No photo, no generator."
        ),
        f"- The check pose (degrees, made up): {pose}.",
        (
            "- Pushing parts: hold Shift and drag with the left mouse button while the "
            'simulation runs (Physics settings, "Mouse Interaction").'
        ),
        (
            "- Measuring: before Play, paste `record_joints.py` into Window > Script Editor and "
            "click Run. It writes every joint's position over time to `recordings/` in this "
            "folder (radians)."
        ),
        "",
        "## Known inaccuracies and stand-ins",
        *[f"- {i.message}" for i in result.issues],
        "",
        "## Files",
        *report,
        "## Isaac Sim check (fill in)",
        "- Isaac Sim version/build:",
        "- Does each joint turn about the expected axis, through its range:",
        "- How far does the default drive sag, against the stiff one:",
        "- Reviewer notes:",
        "",
    ]
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "RUN.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    sys.exit(main())
