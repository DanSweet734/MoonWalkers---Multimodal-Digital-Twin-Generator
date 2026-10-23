"""A box-and-cylinder drill press for checking the exporter in Isaac Sim (drill-press plan,
Phase 1).

It stands in for the Grizzly T33901 before any generated mesh: eight parts on seven joints, as the
manual's photos and exploded view show them (docs/research/2026-10-22-t33901-handle-ratio-and-
figures.md). Sizes are the manual's where it gives them, cited with the PDF page and a quote, and
made up where it does not; every made-up value and stand-in is labelled in the twin. The twin is a
test model (``moonwalkers/testdrillpress``), not the T33901 itself. Run from ``backend/`` with a run
folder (for example ``../data/machines/moonwalkers-testdrillpress/runs/2026-10-22_run-001``)::

    uv run python -m moonwalkers.usd.primitive_drill_press <run-folder>

That writes one check file per behaviour (``CHECKS``), validates each, and writes ``RUN.md`` with
what to look for in Isaac Sim. The joints state their behaviour in contract v0.2.0 (decision 0020,
plan Phase 2): the quill's spring and depth stop, the handles' link to the quill, the driven
spindle and the table's four locks. Each check adds only its scenario: a machine setting changed
in the contract (the depth stop moved, the locks loosened), starting positions, or a simulation
choice (a spin speed, the coupling method, a lock by drive).

Twin frame (decision 0012): metres, +Z up, the front (where the operator stands) towards +X, the
operator's right towards +Y, and the origin on the floor under the spindle.
"""

from __future__ import annotations

import argparse
import math
import platform
import shutil
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from importlib.metadata import version as package_version
from pathlib import Path
from typing import Any

from pxr import Usd

from moonwalkers.clock import utc_now
from moonwalkers.contracts.pipeline_result import (
    AdjustableStop,
    Citation,
    Fact,
    InputType,
    Issue,
    Joint,
    JointLink,
    JointMode,
    MachineIdentity,
    Part,
    PipelineId,
    PipelineResult,
    Source,
    TwinRecord,
)
from moonwalkers.kb import machine_key

from .exporter import CouplingMethod, DriveSettings, JointSettings, build_stage, write_stage
from .validate import validate_file

RECORDER = Path(__file__).with_name("isaac_recorder.py")

MANUFACTURER = "MoonWalkers"
MODEL = "Test Drill Press"
INCH = 0.0254

MANUAL = "src-t33901-manual"
SYNTHETIC = "src-synthetic"
MANUAL_URI = "machines/grizzly-t33901/inputs/documents/grizzly-t33901-t33902-manual-2023.pdf"
MANUAL_SHA256 = "cf117e5eccad47730cd3a04120863f4e25cfa5fc59cd0a9765d864e2c8817df5"  # SOURCES.md
MANUAL_RETRIEVED = datetime(2026, 10, 20, 3, 41, tzinfo=UTC)  # "about 03:41 UTC Oct 20"


TILT_QUOTE = "Max. Table Tilt (Left/Right) ... 0 - 45 deg."
SPEEDS_QUOTE = (
    "12 Speed Settings: 340, 500, 530, 660, 740, 790, 1380, 1420, 1680, 1860, 2200, 2860 RPM"
)


def cite(page: int, quote: str) -> Citation:
    return Citation(source_id=MANUAL, locator=f"PDF p. {page}", quote=quote)


MADE_UP = Citation(source_id=SYNTHETIC, locator="made-up size, not in the manual")


def setting(what: str) -> Citation:
    """A value chosen for the test model or a check, not taken from the manual."""
    return Citation(source_id=SYNTHETIC, locator=f"setting chosen for the test model: {what}")


# --------------------------------------------------------------------------- the manual's sizes
SPINDLE_TRAVEL = 3.25 * INCH  # p. 8 "Spindle Travel ... 3-1/4 in."
COLUMN_RADIUS = 3.125 * INCH / 2  # p. 9 "Column Diameter ... 3-1/8 in."
QUILL_RADIUS = 1.85 * INCH / 2  # p. 9 "Quill Diameter ... 1.85 in."
TABLE_SIDE = 11.25 * INCH  # p. 9 "Table Length ... 11-1/4 in.", "Table Width ... 11-1/4 in."
TABLE_THICKNESS = 1.0625 * INCH  # p. 9 "Table Thickness ... 1-1/16 in."
BASE_LENGTH, BASE_WIDTH = 18 * INCH, 10.5 * INCH  # p. 9 "Base Length ... 18 in.", "Base Width ..."
OVERALL_HEIGHT = 39 * INCH  # p. 8 "15 x 25-1/2 x 39 in."
SPINDLE_TO_COLUMN = 7 * INCH  # p. 8 "Max. Distance From Spindle to Column ... 7 in."
SPINDLE_TO_BASE = 23.375 * INCH  # p. 9 "Distance From Spindle to Base ... 23-3/8 in."
SPINDLE_TO_TABLE = 15.875 * INCH  # p. 8 "Max. Distance From Spindle to Table ... 15-7/8 in."
FLOOR_TO_TABLE_LOW = 9.625 * INCH  # p. 9 "Floor-To-Table Height ... 9-5/8 - 24 in."
TABLE_TRAVEL = 14.375 * INCH  # p. 9 "Vertical Table Travel ... 14-3/8 in."
TABLE_TILT = math.radians(45)  # p. 9 "Max. Table Tilt (Left/Right) ... 0 - 45 deg."
LOWEST_SPEED = 340 * 2 * math.pi / 60  # p. 9 "12 Speed Settings: 340, ..., 2860 RPM", in rad/s
HANDLE_LENGTH, HANDLE_RADIUS = 0.178, 0.006  # p. 50 part 102 "STUD-DE M12-1.75 X 178, 15"
KNOB_RADIUS = 0.035 / 2  # p. 50 part 101 "KNOB M12-1.75, D35"

# --------------------------------------------- derived from the manual's sizes [INFERENCE]
# The column's axis: "Spindle to Column" is taken to the column's surface, since the swing is 14 in.
COLUMN_X = -(SPINDLE_TO_COLUMN + COLUMN_RADIUS)
# The base's top: the lowest table is 23-3/8 - 15-7/8 = 7-1/2 in above it, and 9-5/8 in above the
# floor, so the base is 2-1/8 in thick.
BASE_TOP = FLOOR_TO_TABLE_LOW - (SPINDLE_TO_BASE - SPINDLE_TO_TABLE)
SPINDLE_NOSE = BASE_TOP + SPINDLE_TO_BASE  # the spindle's end, with the quill all the way up

# ------------------------------------------------------------------- made-up sizes (stand-ins)
HEAD_BOTTOM = SPINDLE_NOSE + 0.035
BASE_BACK = COLUMN_X - 0.08  # the column stands near the base's back edge
HEAD_FRONT, HEAD_BACK, HEAD_HALF_WIDTH = 0.10, COLUMN_X - 0.10, 0.11
QUILL_LENGTH = 0.20
QUILL_CENTER_Z = SPINDLE_NOSE + QUILL_LENGTH / 2
CHUCK_RADIUS, CHUCK_LENGTH = 0.022, 0.09
HUB = (-0.04, HEAD_HALF_WIDTH + 0.025, HEAD_BOTTOM + 0.075)  # on the operator's right
HUB_RADIUS, HUB_LENGTH = 0.03, 0.05
HANDLE_ANGLES_DEG = (-30.0, 90.0, 210.0)  # in the x-z plane, from the front towards up
HANDLE_START = 0.02  # where a handle's stud starts, inside the hub: its thread depth
ARM_HEIGHT = 0.04
TABLE_LOW_TOP = FLOOR_TO_TABLE_LOW
ARM_Z = TABLE_LOW_TOP - TABLE_THICKNESS - ARM_HEIGHT / 2  # the arm's centre, table at its lowest
TILT_X = COLUMN_X + 0.065  # where the arm leaves the bracket

# -------------------------------------------------------------------- stand-in behaviour values
# The manual gives no handle-to-quill ratio (research note). Stand-in: 270 degrees of handle turn
# over the full stroke, so pulling the front handle down lowers the quill ("Moves spindle down
# when pulled down", p. 7). The spring's numbers are the exporter's (decision 0018).
HANDLE_RATIO = math.radians(270) / SPINDLE_TRAVEL  # rad per m
LOCK_STIFFNESS, LOCK_DAMPING = 10_000.0, 200.0  # a stiff drive at the setting
DEPTH_STOP = 1.5 * INCH  # a depth setting for the check, within the 3-1/4 in travel
TABLE_SETTING = {  # where the locked table is set for the checks
    "table_height": 0.15,
    "table_around_column": math.radians(30),
    "table_tilt": math.radians(30),
    "table_around_center": math.radians(45),
}

# The manual's words for each table lock (p. 7 and p. 32)
HEIGHT_LOCK = cite(
    7,
    "Table Height Lock Handle: Loosens to allow adjustment of table position on column; tightens "
    "to lock table position",
)
TABLE_LOCKS = {
    "table_height": (HEIGHT_LOCK, cite(32, "then tighten table height lock handle to secure")),
    "table_around_column": (HEIGHT_LOCK,),
    "table_tilt": (cite(32, "Tighten hex bolt from Step 1 to secure table angle"),),
    "table_around_center": (
        cite(
            7,
            "Table Pivot Lock Handle: Loosens to allow rotation of table; tightens to lock table "
            "rotation",
        ),
    ),
}
DEPTH_STOP_QUOTES = (
    cite(7, "Depth Stop: Stops spindle travel at predetermined drilling depth"),
    cite(
        31,
        "a threaded rod attached to the quill with a depth stop nut that can be lowered or raised "
        "against a stop bracket",
    ),
)


# ------------------------------------------------------------------------------------- parts
def box(size: Sequence[float], center: Sequence[float]) -> dict[str, Any]:
    return {"shape": "box", "size_m": list(size), "center_m": list(center)}


def cylinder(
    radius: float, length: float, axis: Sequence[float], center: Sequence[float], segments: int = 24
) -> dict[str, Any]:
    return {
        "shape": "cylinder",
        "radius_m": radius,
        "length_m": length,
        "axis": list(axis),
        "center_m": list(center),
        "segments": segments,
    }


def compound(*pieces: dict[str, Any]) -> dict[str, Any]:
    return {"shape": "compound", "pieces": list(pieces)}


def part(part_id: str, name: str, primitive: dict[str, Any], *citations: Citation) -> Part:
    return Part(
        part_id=part_id,
        name=name,
        geometry_format="primitive",
        primitive=primitive,
        citations=list(citations),
    )


def build_parts() -> list[Part]:
    column_top = HEAD_BOTTOM + 0.22
    head_height = OVERALL_HEIGHT - HEAD_BOTTOM
    frame = compound(
        box(
            (BASE_LENGTH, BASE_WIDTH, BASE_TOP),
            (BASE_BACK + BASE_LENGTH / 2, 0, BASE_TOP / 2),
        ),
        cylinder(0.06, 0.02, (0, 0, 1), (COLUMN_X, 0, BASE_TOP + 0.01)),  # the column base
        cylinder(
            COLUMN_RADIUS,
            column_top - BASE_TOP,
            (0, 0, 1),
            (COLUMN_X, 0, (BASE_TOP + column_top) / 2),
        ),
        box(
            (HEAD_FRONT - HEAD_BACK, 2 * HEAD_HALF_WIDTH, head_height),
            ((HEAD_FRONT + HEAD_BACK) / 2, 0, HEAD_BOTTOM + head_height / 2),
        ),
    )
    handles = []
    for angle in map(math.radians, HANDLE_ANGLES_DEG):
        direction = (math.cos(angle), 0.0, math.sin(angle))
        bar = [
            h + d * (HANDLE_START + HANDLE_LENGTH / 2) for h, d in zip(HUB, direction, strict=True)
        ]
        knob = [
            h + d * (HANDLE_START + HANDLE_LENGTH - 0.02)
            for h, d in zip(HUB, direction, strict=True)
        ]
        handles += [
            cylinder(HANDLE_RADIUS, HANDLE_LENGTH, direction, bar, segments=12),
            cylinder(KNOB_RADIUS, 0.04, direction, knob, segments=12),
        ]
    rack_bottom, rack_top = BASE_TOP + 0.01, HEAD_BOTTOM - 0.02
    bracket_crank = (COLUMN_X, 0.09, ARM_Z)
    return [
        part(
            "frame",
            "Base, column and head (fixed); the head and motor are one stand-in box",
            frame,
            cite(9, "Base Length ... 18 in."),
            cite(9, "Column Diameter ... 3-1/8 in."),
            cite(8, "15 x 25-1/2 x 39 in."),
            MADE_UP,
        ),
        part(
            "quill",
            "Quill",
            cylinder(QUILL_RADIUS, QUILL_LENGTH, (0, 0, 1), (0, 0, QUILL_CENTER_Z)),
            cite(9, "Quill Diameter ... 1.85 in."),
            MADE_UP,
        ),
        part(
            "spindle",
            "Spindle and chuck (8 sides, so its turning shows)",
            cylinder(
                CHUCK_RADIUS, CHUCK_LENGTH, (0, 0, 1), (0, 0, SPINDLE_NOSE - CHUCK_LENGTH / 2), 8
            ),
            MADE_UP,
        ),
        part(
            "handle_hub",
            "Downfeed hub with its three handles",
            compound(cylinder(HUB_RADIUS, HUB_LENGTH, (0, 1, 0), HUB), *handles),
            cite(18, "Downfeed Handles ... 3"),
            cite(50, "STUD-DE M12-1.75 X 178, 15"),
            cite(50, "KNOB M12-1.75, D35"),
            MADE_UP,
        ),
        part(
            "column_rack",
            "Column rack and collar (turn around the column with the table)",
            compound(
                box(
                    (0.012, 0.02, rack_top - rack_bottom),
                    (COLUMN_X, COLUMN_RADIUS + 0.01, (rack_bottom + rack_top) / 2),
                ),
                cylinder(COLUMN_RADIUS + 0.012, 0.03, (0, 0, 1), (COLUMN_X, 0, rack_top)),
            ),
            cite(22, "rack is seated firmly between collar and column base"),
            cite(32, "making sure to guide column rack with table"),
            MADE_UP,
        ),
        part(
            "table_bracket",
            "Column bracket with the table height crank",
            compound(
                box((0.12, 0.11, 0.09), (COLUMN_X, 0, ARM_Z)),
                cylinder(0.01, 0.06, (0, 1, 0), bracket_crank),
                box((0.012, 0.012, 0.09), (COLUMN_X, 0.12, ARM_Z - 0.04)),
            ),
            cite(50, "COLUMN BRACKET"),
            cite(9, "Hand-Crank Enabled Rack and Pinion Table Elevation"),
            MADE_UP,
        ),
        part(
            "table_arm",
            "Table mounting arm (tilts in the bracket)",
            compound(
                box((0.03 - TILT_X, 0.06, ARM_HEIGHT), ((TILT_X + 0.03) / 2, 0, ARM_Z)),
                cylinder(0.03, 0.04, (1, 0, 0), (TILT_X + 0.02, 0, ARM_Z)),
            ),
            cite(50, "TABLE MOUNTING ARM"),
            MADE_UP,
        ),
        part(
            "table",
            "Table (turns about its centre on the arm)",
            compound(
                box(
                    (TABLE_SIDE, TABLE_SIDE, TABLE_THICKNESS),
                    (0, 0, TABLE_LOW_TOP - TABLE_THICKNESS / 2),
                ),
                cylinder(0.02, 0.03, (0, 0, 1), (0, 0, TABLE_LOW_TOP - TABLE_THICKNESS - 0.015)),
            ),
            cite(9, "Table Length ... 11-1/4 in."),
            cite(9, "Table Thickness ... 1-1/16 in."),
            cite(9, "Floor-To-Table Height ... 9-5/8 - 24 in."),
        ),
    ]


# ------------------------------------------------------------------------------------ joints
def joint(
    joint_id: str,
    joint_type: str,
    parent: str,
    child: str,
    axis: tuple[float, float, float],
    origin: tuple[float, float, float],
    *citations: Citation,
    lower: float | None = None,
    upper: float | None = None,
    **behaviour: Any,  # contract v0.2.0: mode, adjustable_stop, follows
) -> Joint:
    return Joint(
        joint_id=joint_id,
        joint_type=joint_type,
        parent_part=parent,
        child_part=child,
        axis=axis,
        origin_m=origin,
        lower_limit=lower,
        upper_limit=upper,
        confidence=1.0,
        citations=list(citations),
        **behaviour,
    )


def locked(joint_id: str, position: float | None = None) -> JointMode:
    """A table motion held by its lock: at the modelled pose, or at a check's setting."""
    where = [] if position is None else [setting(f"locked at {position:.4g} for the check")]
    return JointMode(kind="locked", position=position, citations=[*TABLE_LOCKS[joint_id], *where])


def loosened(joint_id: str) -> JointMode:
    """A table motion with its lock loosened. The height then drops: the manual does not say
    whether the crank's worm holds it, and a similar drill press's table fell (decision 0018)."""
    return JointMode(kind="free", citations=list(TABLE_LOCKS[joint_id]))


def depth_stop(position: float, what: str) -> AdjustableStop:
    return AdjustableStop(
        position=position, side="upper", citations=[*DEPTH_STOP_QUOTES, setting(what)]
    )


def build_joints() -> list[Joint]:
    pivot = (TILT_X, 0.0, ARM_Z)
    return [
        joint(
            "quill_travel", "prismatic", "frame", "quill", (0, 0, -1), (0, 0, HEAD_BOTTOM),
            cite(8, "Spindle Travel ... 3-1/4 in."),
            cite(7, "Spindle Return Spring: Automatically returns quill into headstock"),
            lower=0.0, upper=SPINDLE_TRAVEL,
            mode=JointMode(kind="spring_return", position=0.0, citations=[
                cite(7, "Spindle Return Spring: Automatically returns quill into headstock"),
                cite(7, "Spindle automatically returns to top position when released"),
            ]),
            adjustable_stop=depth_stop(SPINDLE_TRAVEL, "depth stop at full depth (no stop)"),
        ),
        joint(
            "spindle_rotation", "revolute", "quill", "spindle", (0, 0, -1), (0, 0, SPINDLE_NOSE),
            cite(9, SPEEDS_QUOTE),
            mode=JointMode(kind="driven", citations=[
                cite(30, "Spindle speed is controlled by the configuration of V-belts and pulleys"),
            ]),
        ),
        joint(
            "downfeed_handles", "revolute", "frame", "handle_hub", (0, 1, 0), HUB,
            cite(7, "Moves spindle down when pulled down"),
            cite(35, "Lubricate column rack and quill rack and pinion"),
            lower=-0.05, upper=HANDLE_RATIO * SPINDLE_TRAVEL + 0.05,
            follows=JointLink(leader="quill_travel", ratio=HANDLE_RATIO, stand_in=True, citations=[
                cite(35, "Lubricate column rack and quill rack and pinion"),
                Citation(source_id=SYNTHETIC, locator="stand-in ratio: 270 degrees over the "
                         "3-1/4 in stroke (decision 0019)"),
            ]),
        ),
        joint(
            "table_around_column", "revolute", "frame", "column_rack", (0, 0, 1),
            (COLUMN_X, 0, BASE_TOP),
            cite(9, "Table Swivel Around Column ... 360 deg."),
            cite(32, "Rotate table to desired location on column"),
            mode=locked("table_around_column"),
        ),
        joint(
            "table_height", "prismatic", "column_rack", "table_bracket", (0, 0, 1),
            (COLUMN_X, 0, ARM_Z),
            cite(9, "Vertical Table Travel ... 14-3/8 in."),
            lower=0.0, upper=TABLE_TRAVEL,
            mode=locked("table_height"),
        ),
        joint(
            "table_tilt", "revolute", "table_bracket", "table_arm", (1, 0, 0), pivot,
            cite(9, TILT_QUOTE),
            cite(32, "Tilt table until pointer aligns with desired angle on scale"),
            lower=-TABLE_TILT, upper=TABLE_TILT,
            mode=locked("table_tilt"),
        ),
        joint(
            "table_around_center", "revolute", "table_arm", "table", (0, 0, 1),
            (0, 0, TABLE_LOW_TOP - TABLE_THICKNESS),
            cite(9, "Table Swivel Around Center ... 360 deg."),
            cite(32, "Rotate table to desired position"),
            mode=locked("table_around_center"),
        ),
    ]  # fmt: skip


def build_test_drill_press(created_at: datetime) -> tuple[TwinRecord, PipelineResult]:
    """The test twin and the one result it is built from."""
    sources = [
        Source(
            source_id=MANUAL,
            kind="file",
            uri=MANUAL_URI,
            title="Grizzly T33901/T33902 manual (revised December 2023), from "
            "https://cdn0.grizzly.com/manuals/t33901_m.pdf",
            sha256=MANUAL_SHA256,
            retrieved_at=MANUAL_RETRIEVED,
            license_note="Copyright Grizzly Industrial, Inc.; local copy for internal research",
        ),
        Source(
            source_id=SYNTHETIC,
            kind="user_input",
            uri="user",
            title="Box-and-cylinder drill press for the Phase 1 exporter check; sizes the manual "
            "does not give are made up",
            retrieved_at=created_at,
        ),
    ]
    result = PipelineResult(
        result_id="res-test-drill-press-c",
        job_id="test-drill-press",
        pipeline=PipelineId.C,  # hand-written geometry and kinematics, like a schematic reading
        input_types=[InputType.SCHEMATIC],
        produced_at=created_at,
        produced_by="moonwalkers.usd.primitive_drill_press (synthetic test model)",
        sources=sources,
        identity=MachineIdentity(
            manufacturer=MANUFACTURER,
            model=MODEL,
            category="test model of a benchtop drill press",
            confidence=1.0,
            citations=[Citation(source_id=SYNTHETIC)],
        ),
        facts=[
            Fact(
                key="spindle_travel",
                value=SPINDLE_TRAVEL,
                unit="m",
                original="3-1/4 in.",
                confidence=0.9,
                citations=[cite(8, "Spindle Travel ... 3-1/4 in.")],
            ),
            Fact(
                key="vertical_table_travel",
                value=TABLE_TRAVEL,
                unit="m",
                original="14-3/8 in.",
                confidence=0.9,
                citations=[cite(9, "Vertical Table Travel ... 14-3/8 in.")],
            ),
            Fact(
                key="max_table_tilt",
                value=TABLE_TILT,
                unit="rad",
                original="0 - 45 deg.",
                confidence=0.9,
                citations=[cite(9, TILT_QUOTE)],
            ),
            Fact(
                key="lowest_spindle_speed",
                value=LOWEST_SPEED,
                unit="rad/s",
                original="340 RPM",
                confidence=0.9,
                citations=[cite(9, SPEEDS_QUOTE)],
            ),
            Fact(
                key="overall_height",
                value=OVERALL_HEIGHT,
                unit="m",
                original="39 in.",
                confidence=0.9,
                citations=[cite(8, "15 x 25-1/2 x 39 in.")],
            ),
        ],
        parts=build_parts(),
        joints=build_joints(),
        issues=[
            Issue(
                severity="info",
                message="Synthetic test model written by hand to check the USD exporter; sizes "
                "the manual does not give (head, motor, rack, bracket, arm, chuck, hub) are "
                "made up.",
            ),
            *STAND_IN_ISSUES,
        ],
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


STAND_IN_ISSUES = [
    Issue(
        severity="warning",
        ref="downfeed_handles",
        message="Stand-in ratio: the handles turn 270 degrees over the 3-1/4 in stroke. The "
        "manual gives no pinion size (docs/research/2026-10-22-t33901-handle-ratio-and-"
        "figures.md).",
    ),
    Issue(
        severity="warning",
        ref="quill_travel",
        message="Stand-in spring: stiffness 600 and a preload 0.03 m above the top of travel, "
        "chosen so the quill does not sag. The manual gives no spring force.",
    ),
    Issue(
        severity="warning",
        ref="table_height",
        message="Assumption: with its lock loosened, the table drops, because the crank's worm "
        "does not hold it. The manual does not say; a similar drill press's table fell "
        "(a 1950s Craftsman 103.23140; Daniel, 2026-10-23; decision 0018).",
    ),
    Issue(
        severity="warning",
        message="The parts do not collide with each other: joints and limits stop them. A raised "
        "table can pass through the chuck, which the real one cannot.",
    ),
    Issue(
        severity="info",
        message="Masses come from the placeholder density (1000 kg/m^3), not the cited 108 lb.",
    ),
]


# ---------------------------------------------------------------------- behaviours to check
@dataclass(frozen=True)
class Check:
    """One check file: the test model with only this scenario added (module docstring)."""

    what: str  # what the file shows
    look_for: str  # what Daniel should see in Isaac Sim
    machine: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)  # contract changes
    settings: Mapping[str, JointSettings] = field(default_factory=dict)  # replace the contract's
    starts: Mapping[str, float] = field(default_factory=dict)
    coupling_method: CouplingMethod = "mimic"

    def scenario(self) -> str:
        parts = [
            f"{j}: {', '.join(_describe(v) for v in changes.values())}"
            for j, changes in self.machine.items()
        ]
        parts += [f"{j}: {s.note or 'own drive'}" for j, s in self.settings.items()]
        parts += [f"{j} starts at {v:.4g}" for j, v in self.starts.items()]
        if self.coupling_method != "mimic":
            parts.append(f"links written as {self.coupling_method.replace('_', ' ')}")
        return "; ".join(parts) or "the test model as it is"


def _describe(value: Any) -> str:
    """A machine setting a check changes, in words for RUN.md."""
    if isinstance(value, JointMode):
        at = "" if value.position is None else f" at {value.position:.4g}"
        return f"{value.kind.replace('_', ' ')}{at}"
    if isinstance(value, AdjustableStop):
        return f"adjustable stop at {value.position:.4g}"
    return str(value)


def check_result(result: PipelineResult, check: Check) -> PipelineResult:
    """The result with the check's machine settings changed in the contract (validated again)."""
    if not check.machine:
        return result
    data = result.model_dump()
    for joint_data in data["joints"]:
        joint_data.update(check.machine.get(joint_data["joint_id"], {}))
    return PipelineResult.model_validate(data)


def check_stage(twin: TwinRecord, result: PipelineResult, check: Check) -> Usd.Stage:
    return build_stage(
        twin,
        [check_result(result, check)],
        joint_settings=check.settings,
        starts=check.starts,
        coupling_method=check.coupling_method,
    )


SPIN_SLOW = math.radians(30)
QUILL_DOWN = {"quill_travel": SPINDLE_TRAVEL}  # the quill starts at full depth
TABLE_LOCKED_AT_SETTING = {j: {"mode": locked(j, v)} for j, v in TABLE_SETTING.items()}

CHECKS: dict[str, Check] = {
    "spindle_spin.usdc": Check(
        "the spindle turns at 340 RPM, the lowest cited speed",
        "The spindle (8-sided) turns fast; at 60 frames a second it turns 34 degrees a frame, "
        "close to its 45-degree symmetry, so it may look slow or backwards. Nothing else moves.",
        settings={"spindle_rotation": JointSettings(drive=DriveSettings.spin(LOWEST_SPEED))},
    ),
    "spindle_spin_slow.usdc": Check(
        "the spindle turns at 30 degrees a second, for the eye",
        "The spindle turns slowly, clockwise seen from above, without a push. Nothing else moves.",
        settings={"spindle_rotation": JointSettings(drive=DriveSettings.spin(SPIN_SLOW))},
    ),
    "quill_spring_return.usdc": Check(
        "the quill starts at full depth and the spring returns it",
        "On Play the quill first jumps to full depth (its stored start, applied on the first "
        "physics step), then rises 3-1/4 in to the top and stays there.",
        starts=QUILL_DOWN,
    ),
    "depth_stop.usdc": Check(
        "a feed to full depth stops at a depth stop set at 1-1/2 in",
        "On Play the quill moves down 1-1/2 in (38 mm) and stops there, short of its full "
        "3-1/4 in. It already sticks 1.38 in out of the head at the top, so it ends 2.88 in out.",
        machine={"quill_travel": {"adjustable_stop": depth_stop(DEPTH_STOP, "1-1/2 in deep")}},
        settings={
            "quill_travel": JointSettings(
                drive=DriveSettings.hold(SPINDLE_TRAVEL),
                note="an operator's feed past a depth stop set at 1-1/2 in",
            )
        },
    ),
    "handles_follow_mimic.usdc": Check(
        "the handles follow the quill through PhysxMimicJointAPI",
        "On Play the quill rises and the handles turn back 270 degrees with it. Shift+drag a "
        "handle: the quill moves too (the mimic is two-way). A push on the quill itself barely "
        "moves it: through the coupling, the handles' lever is about 10 times stronger.",
        starts=QUILL_DOWN,
    ),
    "handles_follow_rack_pinion.usdc": Check(
        "the handles follow the quill through a rack-and-pinion joint",
        "On Play the quill rises and the handles turn back with it, the same way as in the "
        "mimic file.",
        starts=QUILL_DOWN,
        coupling_method="rack_and_pinion",
    ),
    "table_free.usdc": Check(
        "the table's four locks loosened: it drops, then slides, swings, tilts and turns freely",
        "The table starts 0.15 m up. On Play it drops to the bottom of its travel, as the "
        "assumed loose height lock lets it (decision 0018). Then Shift+drag the table: it slides "
        "up and down, swings around the column, tilts up to 45 degrees each way, and turns about "
        "its centre.",
        machine={j: {"mode": loosened(j)} for j in TABLE_SETTING},
        starts={j: (v if j == "table_height" else 0.0) for j, v in TABLE_SETTING.items()},
    ),
    "table_locked_drive.usdc": Check(
        "every table motion locked by a stiff drive, at 0.15 m up, 30, 30 and 45 degrees",
        "The table starts raised, swung 30 degrees, tilted 30 degrees and turned 45 degrees, and "
        "holds there. Shift+drag it hard: note whether it gives at all.",
        settings={
            j: JointSettings(
                drive=DriveSettings(
                    mode="position", target=v, stiffness=LOCK_STIFFNESS, damping=LOCK_DAMPING
                ),
                start=v,
                note="locked by a drive",
            )
            for j, v in TABLE_SETTING.items()
        },
    ),
    "table_locked_limits.usdc": Check(
        "the same, locked by equal limits",
        "The same pose, held by limits. Shift+drag it: it should not move at all. Compare with "
        "the drive lock.",
        machine=TABLE_LOCKED_AT_SETTING,
    ),
    "all_motions.usdc": Check(
        "everything at once",
        "The spindle turns slowly, the quill rises with the handles turning, and the table holds "
        "its locked pose.",
        machine=TABLE_LOCKED_AT_SETTING,
        settings={"spindle_rotation": JointSettings(drive=DriveSettings.spin(SPIN_SLOW))},
        starts=QUILL_DOWN,
    ),
}


# ----------------------------------------------------------------------------------- command
def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Write and validate the box-and-cylinder drill press check files."
    )
    parser.add_argument(
        "out_dir", type=Path, help="run folder, e.g. data/machines/<machine>/runs/<run>"
    )
    args = parser.parse_args(argv)

    created_at = utc_now()
    twin, result = build_test_drill_press(created_at)
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
            f"- Scenario: {check.scenario()}.",
            f"- Look for: {check.look_for}",
        ]
        report.append(f"- Validation: {status}.")
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
    stand_ins = [f"- {i.message}" for i in result.issues]
    lines = [
        "# Run: box-and-cylinder drill press (drill-press plan; contract v0.2.0 since Phase 2)",
        "",
        f"- Created (UTC): {created_at.isoformat(timespec='seconds')}",
        f"- Command: `uv run python -m moonwalkers.usd.primitive_drill_press {out_dir.as_posix()}`",
        f"- Versions: {versions}",
        (
            "- Input: hand-written primitives. Sizes from the Grizzly T33901 manual where it "
            "gives them (cited in each part), the rest made up. No photo, no generator."
        ),
        (
            "- Behaviour: the joints state it in contract v0.2.0 (decision 0020): the quill's "
            "spring and depth stop, the handles following the quill, the driven spindle and the "
            "table's four locks. Each file's scenario is listed with it."
        ),
        (
            "- Pushing parts: hold Shift and drag with the left mouse button while the "
            'simulation runs (Physics settings, "Mouse Interaction").'
        ),
        (
            "- Measuring: before Play, paste `record_joints.py` into Window > Script Editor and "
            "click Run. It writes every joint's position over time to `recordings/` in this "
            "folder (radians or metres)."
        ),
        "",
        "## Known inaccuracies and stand-ins",
        *stand_ins,
        "",
        "## Files",
        *report,
        "## Isaac Sim check (fill in)",
        "- Isaac Sim version/build:",
        "- Do the handles turn with the quill in every file where the quill moves:",
        "- `table_free`: does the table drop on Play, then slide, swing, tilt and turn if pushed:",
        "- Does anything behave differently from the run checked before:",
        "- Reviewer notes:",
        "",
    ]
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "RUN.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    sys.exit(main())
