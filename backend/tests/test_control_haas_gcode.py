"""A Haas mill program in G and M codes (decision 0035): reading, planning on a box mill laid out
as the TM-1 twin is, the program folder, the runner, the measures against a recording and the
command line."""

import csv
import importlib.util
import itertools
import json
import math
from datetime import datetime
from pathlib import Path

import pytest
from pxr import Usd, UsdGeom, UsdPhysics

from moonwalkers.contracts.pipeline_result import (
    Citation,
    Fact,
    InputType,
    Joint,
    MachineIdentity,
    PipelineId,
    PipelineResult,
    Source,
    TwinRecord,
)
from moonwalkers.control import (
    GcodeProgram,
    MillSettings,
    ProgramError,
    ProgramFile,
    bind_mill,
    packaged_programs,
    run_gcode_program,
    write_program_folder,
)
from moonwalkers.control.cli import main as control_cli
from moonwalkers.control.compare import _at_point, compare, read_recording
from moonwalkers.control.haas_gcode import MillGeometry, setup_of
from moonwalkers.control.mill_export import measure_geometry
from moonwalkers.kb import JsonKnowledgeBase, machine_key
from moonwalkers.usd.exporter import DriveSettings, build_stage
from moonwalkers.usd.primitive_drill_press import box, cylinder, part
from moonwalkers.usd.validate import validate_file

IN = 0.0254
SRC = "src-synthetic"
MADE_UP = Citation(source_id=SRC, locator="made-up size for the box mill")
RAPID = 200 * IN / 60  # 200 in/min, the TM-1's cited rapid
NO_ACC = MillSettings(acceleration_mm_s2=None)
# The box mill at its 0: the spindle nose's face at z 0.8 over the table's top at 0.55.
NOSE_Z, TABLE_TOP = 0.8, 0.55
GEOMETRY = MillGeometry(nose_m=(0.0, 0.0, NOSE_Z), table_top_m=TABLE_TOP)
MACHINE = {
    "axes": {
        "X": {"joint_id": "x_axis", "direction": [0.0, 1.0, 0.0], "home": "plus_end"},
        "Y": {"joint_id": "y_axis", "direction": [-1.0, 0.0, 0.0], "home": "plus_end"},
        "Z": {"joint_id": "z_axis", "direction": [0.0, 0.0, 1.0], "home": "plus_end"},
    },
    "tool_part": "spindle",
    "work_part": "table",
    "spindle": "spindle_rotation",
    "carousel": "carousel_index",
    "pockets": 10,
}
SETUP = {  # the TM-1's: the path centred on the table, tools touched off on the twin
    "units": "inch",
    "work_offsets": {"G54": {"X": -15.0, "Y": -6.0, "Z": 0.0}},
    "tools": {"1": {"length": 3.0, "diameter": 0.5}, "2": {"length_offset": -10.0}},
    "stock_height": 2.0,
}


def slide(joint_id: str, parent: str, child: str, axis, lower: float, upper: float) -> Joint:
    return Joint(
        joint_id=joint_id,
        joint_type="prismatic",
        parent_part=parent,
        child_part=child,
        axis=axis,
        origin_m=(0.0, 0.0, 0.5),
        lower_limit=lower,
        upper_limit=upper,
        max_velocity=RAPID,
        confidence=0.5,
        citations=[MADE_UP],
    )


def turn(joint_id: str, parent: str, child: str, origin, rpm: float | None) -> Joint:
    return Joint(
        joint_id=joint_id,
        joint_type="revolute",
        parent_part=parent,
        child_part=child,
        axis=(0.0, 0.0, 1.0),
        origin_m=origin,
        max_velocity=None if rpm is None else rpm * 2 * math.pi / 60,
        confidence=0.5,
        citations=[MADE_UP],
    )


def build_box_mill(created_at: datetime) -> tuple[TwinRecord, PipelineResult]:
    """Frame, saddle (Y), table (X on the saddle), head (Z), spindle and carousel, with the TM-1
    twin's axes and travels: X 30 in, Y 12 in, Z 16 in (home at its top)."""
    parts = [
        part("frame", "Frame (fixed)", box((0.6, 1.2, 0.3), (0.0, 0.0, 0.15)), MADE_UP),
        part("saddle", "Saddle", box((0.4, 0.5, 0.1), (0.0, 0.0, 0.40)), MADE_UP),
        part("table", "Table", box((0.3, 1.0, 0.1), (0.0, 0.0, TABLE_TOP - 0.05)), MADE_UP),
        part("head", "Head", box((0.3, 0.2, 0.2), (-0.1, 0.0, 1.0)), MADE_UP),
        part(
            "spindle",
            "Spindle",
            cylinder(0.04, 0.1, (0, 0, 1), (0.0, 0.0, NOSE_Z + 0.05), segments=32),
            MADE_UP,
        ),
        part("carousel", "Carousel", cylinder(0.15, 0.05, (0, 0, 1), (-0.3, 0.3, 1.0)), MADE_UP),
    ]
    joints = [
        slide("y_axis", "frame", "saddle", (1.0, 0.0, 0.0), -6 * IN, 6 * IN),
        slide("x_axis", "saddle", "table", (0.0, 1.0, 0.0), -15 * IN, 15 * IN),
        slide("z_axis", "frame", "head", (0.0, 0.0, 1.0), -6 * IN, 10 * IN),
        turn("spindle_rotation", "head", "spindle", (0.0, 0.0, NOSE_Z), 6000),
        turn("carousel_index", "frame", "carousel", (-0.3, 0.3, 1.0), None),
    ]
    result = PipelineResult(
        result_id="res-test-mill-c",
        job_id="test-mill",
        pipeline=PipelineId.C,
        input_types=[InputType.SCHEMATIC],
        produced_at=created_at,
        produced_by="tests (synthetic box mill)",
        sources=[
            Source(
                source_id=SRC,
                kind="user_input",
                uri="user",
                title="A box mill for the tests",
                retrieved_at=created_at,
            )
        ],
        identity=MachineIdentity(
            manufacturer="MoonWalkers",
            model="Test Mill",
            category="test model of a vertical mill",
            confidence=1.0,
            citations=[Citation(source_id=SRC)],
        ),
        facts=[
            Fact(
                key="max_cutting_feed",
                value=100 * IN / 60,
                unit="m/s",
                original="100 in/min (made up)",
                confidence=0.5,
                citations=[MADE_UP],
            )
        ],
        parts=parts,
        joints=joints,
    )
    key = machine_key("MoonWalkers", "Test Mill")
    twin = TwinRecord(
        twin_id=f"{key}@v1",
        machine_key=key,
        version=1,
        status="needs_review",
        built_from=[result.result_id],
        created_at=created_at,
    )
    return twin, result


@pytest.fixture
def box_mill(fixed_time):
    return build_box_mill(fixed_time)


def program_file(text: str, setup: dict | None = None, name: str = "test-mill-program"):
    return ProgramFile.model_validate(
        {
            "name": name,
            "sources": [
                {
                    "source_id": "src-test",
                    "kind": "user_input",
                    "uri": "user",
                    "title": "a test",
                    "retrieved_at": "2026-11-16T00:00:00Z",
                }
            ],
            "behavior": {
                "behavior_id": "test_program",
                "name": "a test program",
                "kind": "program_interpreter",
                "description": "test",
                "drives_joints": list(MACHINE["axes"]),
                "spec": {
                    "program": {
                        "format": "haas_gcode",
                        "text": text,
                        "machine": MACHINE,
                        "setup": setup or SETUP,
                    }
                },
                "confidence": 0.5,
                "citations": [{"source_id": "src-test", "locator": "here", "quote": "test"}],
            },
        }
    )


def gcode(*blocks: str) -> str:
    return "%\nO00001 (test)\n" + "\n".join(f"{b} ;" for b in blocks) + "\nM30 ;\n%\n"


def plan(text: str, box_mill, settings: MillSettings = NO_ACC, setup: dict | None = None):
    _, result = box_mill
    program = program_file(text, setup)
    binding = bind_mill(program.behavior, [result])
    return run_gcode_program(
        GcodeProgram.from_behavior(program.behavior),
        binding,
        setup_of(program.behavior),
        settings,
        GEOMETRY,
    )


def at(trajectory, t: float) -> list[float]:
    """The tip's machine position (in) at plan time ``t``."""
    return [v / 25.4 for v in _at_point(trajectory.times, trajectory.machine_mm, t)]


def event(trajectory, line: int):
    return next(e for e in trajectory.events if e.line == line)


# ------------------------------------------------------------------------------- reading
def test_haas_s_basic_program_is_read_as_printed() -> None:
    program = ProgramFile.load(packaged_programs()["haas-o40001-basic-program"])
    gcode_program = GcodeProgram.from_behavior(program.behavior)
    assert gcode_program.number == "O40001"
    assert [b.line for b in gcode_program.blocks] == [7, 8, 9, 10, 11, 12, 14, 15, 17, 18, 19, 20]
    assert gcode_program.blocks[1].codes("G") == [0, 90, 17, 40, 49, 54]
    o6 = GcodeProgram.from_behavior(
        ProgramFile.load(packaged_programs()["haas-o40006-cutter-comp"]).behavior
    )
    assert o6.number == "O40006" and len(o6.blocks) == 24  # lines 7-32, less 3 comments


@pytest.mark.parametrize(
    ("block", "reason"),
    [
        ("/G00 X1.", "block delete"),
        ("#101=1.", "macros"),
        ("G01 X1. ,R0.1 F10.", "corner rounding"),
        ("G00 X1", "no decimal point"),
        ("M08 M03", "Only one M code"),
        ("G00 G01 X1.", "same group"),
        ("G81 Z-1. R0.1 F10.", "canned cycles"),
        ("M98 P1000", "sub-programs"),
        ("M00", "Cycle Start"),
        ("G18", "only the XY plane"),
        ("G00 X1. X2.", "given twice"),
        ("G00 Q1.", "address Q"),
    ],
)
def test_what_the_reader_refuses_and_why(block: str, reason: str) -> None:
    with pytest.raises(ProgramError, match=reason):
        GcodeProgram.from_text(gcode(block))


def test_a_program_must_end_and_nothing_follows_its_end() -> None:
    with pytest.raises(ProgramError, match="no end"):
        GcodeProgram.from_text("G00 X1. ;\n")
    with pytest.raises(ProgramError, match="after the program's end"):
        GcodeProgram.from_text("G00 X1. ;\nM30 ;\nG00 X2. ;\n")
    with pytest.raises(ProgramError, match="parentheses"):
        GcodeProgram.from_text("G00 X1. (open ;\nM30 ;\n")


def test_the_machine_map_must_name_three_sliding_axes(box_mill) -> None:
    program = program_file(gcode("G00 X1."))
    data = program.model_dump(mode="json")
    data["behavior"]["spec"]["program"]["machine"]["axes"].pop("Z")
    with pytest.raises(ValueError, match="must map X, Y and Z"):
        ProgramFile.model_validate(data)
    data["behavior"]["spec"]["program"]["machine"]["axes"]["Z"] = {
        "joint_id": "spindle_rotation",
        "direction": [0.0, 0.0, 1.0],
        "home": "plus_end",
    }
    bad = ProgramFile.model_validate(data)
    with pytest.raises(ProgramError, match="not a sliding joint"):
        bind_mill(bad.behavior, [box_mill[1]])


# ------------------------------------------------------------------------------- binding
def test_each_axis_is_bound_with_its_side_sign_and_home(box_mill) -> None:
    binding = bind_mill(program_file(gcode("G00 X1.")).behavior, [box_mill[1]])
    x, y, z = binding.axes
    assert (x.joint_id, x.side, x.sign, x.home_m) == ("x_axis", "work", -1, -15 * IN)
    assert (y.joint_id, y.side, y.sign, y.home_m) == ("y_axis", "work", 1, 6 * IN)
    assert (z.joint_id, z.side, z.sign, z.home_m) == ("z_axis", "tool", 1, 10 * IN)
    # the twin's 0 is the middle of X and Y and 10 in below Z's home, as on the TM-1
    zero = binding.machine({"x_axis": 0.0, "y_axis": 0.0, "z_axis": 0.0})
    assert [v / IN for v in zero] == pytest.approx([-15.0, -6.0, -10.0])
    assert binding.spindle_max_rpm == pytest.approx(6000)
    assert binding.max_feed_m_s == pytest.approx(100 * IN / 60)


# ------------------------------------------------------------------------------- planning
def test_o40001_on_the_box_mill(box_mill) -> None:
    program = ProgramFile.load(packaged_programs()["haas-o40001-basic-program"])
    binding = bind_mill(program.behavior, [box_mill[1]])
    setup = setup_of(program.behavior)
    t = run_gcode_program(
        GcodeProgram.from_behavior(program.behavior), binding, setup, NO_ACC, GEOMETRY
    )
    gap_at_home = (NOSE_Z + 10 * IN - TABLE_TOP) / IN  # the nose over the table, Z at home
    (offset,) = t.tool_offsets
    assert offset.h == pytest.approx(-(gap_at_home - 2.0 - 3.0))  # stock 2 in, tool 3 in
    cut = event(t, 15)  # X-4. Y-4. at F20, from G54 (X -13, Y -4)
    assert cut.kind == "feed"
    assert cut.end_s - cut.start_s == pytest.approx(math.hypot(4, 4) / 20 * 60)
    assert [v / 25.4 for v in cut.to_mm] == pytest.approx([-17.0, -8.0, offset.h - 0.1])
    assert [v / 25.4 for v in t.events[-1].to_mm] == pytest.approx([-17.0, 0.0, 0.0])
    assert t.cutting[0][0] == pytest.approx(event(t, 14).start_s)
    # the power-up's zero return goes first: Z (10 in), then X (15 in) and Y, at the rapid
    up = t.events[0]
    assert up.kind == "power_up" and up.end_s == pytest.approx((10 + 15) * IN / RAPID)
    # the spindle turns at 1000 rpm from line 10 until M05 on line 18
    spin = t.positions["spindle_rotation"]
    k0 = t.times.index(event(t, 14).start_s)
    k1 = t.times.index(event(t, 15).end_s)
    rate = (spin[k1] - spin[k0]) / (t.times[k1] - t.times[k0])
    assert rate == pytest.approx(6000.0)  # degrees per second
    assert spin[-1] == spin[t.times.index(event(t, 18).end_s)]


def test_a_rapid_moves_each_axis_at_the_rapid_not_together(box_mill) -> None:
    t = plan(gcode("G00 G90 G54 X0 Y0", "G00 X-10. Y-1."), box_mill)
    move = event(t, 4)
    assert move.end_s - move.start_s == pytest.approx(10 * IN / RAPID)
    half = at(t, move.start_s + 1 * IN / RAPID + 0.01)
    assert half[1] == pytest.approx(-7.0)  # Y has arrived (G54 Y -6, Y-1.)
    assert -25.0 < half[0] < -15.5  # X has not


def test_a_feed_moves_the_axes_together_in_a_straight_line(box_mill) -> None:
    t = plan(gcode("G00 G90 G54 X0 Y0", "G01 X3. Y4. F10."), box_mill)
    move = event(t, 4)
    assert move.end_s - move.start_s == pytest.approx(5 / 10 * 60)
    mid = at(t, (move.start_s + move.end_s) / 2)
    assert mid[:2] == pytest.approx([-15 + 1.5, -6 + 2.0])


def test_an_arc_by_r_and_by_ij_follow_the_same_circle(box_mill) -> None:
    by_r = plan(gcode("G00 G90 G54 X1. Y0", "G03 X0 Y1. R1. F10."), box_mill)
    by_ij = plan(gcode("G00 G90 G54 X1. Y0", "G03 X0 Y1. I-1. J0 F10."), box_mill)
    flat = [v for p in by_r.machine_mm for v in p]
    assert flat == pytest.approx([v for p in by_ij.machine_mm for v in p])
    arc = event(by_r, 4)
    assert arc.kind == "arc" and arc.end_s - arc.start_s == pytest.approx(math.pi / 2 / 10 * 60)
    for k, t in enumerate(by_r.times):
        if arc.start_s <= t <= arc.end_s:
            x, y, _ = (v / 25.4 for v in by_r.machine_mm[k])
            assert math.hypot(x + 15, y + 6) == pytest.approx(1.0)  # about G54's X0 Y0
            assert y + 6 >= -1e-9  # counter-clockwise from X1 Y0 to X0 Y1: through +Y


def test_a_full_circle_takes_i_and_j_and_a_helix_moves_z_along(box_mill) -> None:
    t = plan(gcode("G00 G90 G54 X1. Y0", "G02 X1. Y0 I-1. J0 F10."), box_mill)
    arc = event(t, 4)
    assert arc.end_s - arc.start_s == pytest.approx(2 * math.pi / 10 * 60)
    lowest = min(v[1] for v in t.machine_mm) / 25.4
    assert lowest == pytest.approx(-7.0, abs=1e-3)  # clockwise passes X0 Y-1
    with pytest.raises(ProgramError, match="full circle"):
        plan(gcode("G00 G90 G54 X1. Y0", "G02 X1. Y0 R1. F10."), box_mill)
    helix = plan(gcode("G00 G90 G54 X1. Y0", "G03 X-1. Y0 Z-0.5 I-1. J0 F10."), box_mill)
    turn_ = event(helix, 4)
    mid = at(helix, (turn_.start_s + turn_.end_s) / 2)
    assert mid == pytest.approx([-15.0, -5.0, -0.25], abs=1e-3)


def test_incremental_machine_and_home_positions(box_mill) -> None:
    t = plan(
        gcode(
            "G00 G90 G54 X1. Y1.",
            "G91 G01 X1. Z-1. F20.",
            "G90 G53 X-2. Y-3.",
            "G28",
        ),
        box_mill,
    )
    assert [v / 25.4 for v in event(t, 4).to_mm] == pytest.approx([-13.0, -5.0, -1.0])
    assert [v / 25.4 for v in event(t, 5).to_mm] == pytest.approx([-2.0, -3.0, -1.0])
    assert event(t, 6).to_mm == pytest.approx([0.0, 0.0, 0.0])


def test_millimetres_feed_and_a_dwell(box_mill) -> None:
    setup = {"units": "mm", "work_offsets": {"G54": {"X": -381.0, "Y": -152.4, "Z": 0.0}}}
    t = plan(
        gcode("G21 G00 G90 G54 X10. Y5.", "G01 X20. F600.", "G04 P1000", "G04 P1.5"),
        box_mill,
        setup=setup,
    )
    assert event(t, 3).to_mm == pytest.approx([-371.0, -147.4, 0.0])
    assert event(t, 4).end_s - event(t, 4).start_s == pytest.approx(1.0)
    assert event(t, 5).end_s - event(t, 5).start_s == pytest.approx(1.0)  # P without "." is ms
    assert event(t, 6).end_s - event(t, 6).start_s == pytest.approx(1.5)


def test_acceleration_slows_a_move_by_the_ramps(box_mill) -> None:
    text = gcode("G00 G90 G54 X0 Y0", "G01 X1. F20.")
    flat = plan(text, box_mill)
    ramped = plan(text, box_mill, MillSettings(acceleration_mm_s2=100.0))
    v = 20 * IN / 60
    extra = (event(ramped, 4).end_s - event(ramped, 4).start_s) - (
        event(flat, 4).end_s - event(flat, 4).start_s
    )
    assert extra == pytest.approx(v / 0.1, rel=1e-3)  # a trapezoid takes v/a longer


def test_a_tool_change_turns_the_carousel_the_shorter_way(box_mill) -> None:
    t = plan(gcode("T4 M06", "T2 M06", "T9 M06"), box_mill)
    carousel = t.positions["carousel_index"]
    assert carousel[t.times.index(event(t, 3).end_s)] == pytest.approx(3 * 36.0)
    assert carousel[t.times.index(event(t, 4).end_s)] == pytest.approx(36.0)
    assert carousel[-1] == pytest.approx(36.0 - 3 * 36.0)  # pocket 2 to 9: three back
    assert event(t, 3).end_s - event(t, 3).start_s >= 3.0  # 1 s a pocket, a stand-in


def test_the_plan_refuses_what_the_machine_cannot_do(box_mill) -> None:
    with pytest.raises(ProgramError, match="outside the travel"):
        plan(gcode("G00 G53 X-31."), box_mill)
    with pytest.raises(ProgramError, match="maximum cutting feed"):
        plan(gcode("G00 G90 G54 X0 Y0", "G01 X1. F150."), box_mill)
    with pytest.raises(ProgramError, match="over the spindle's cited 6000 rpm"):
        plan(gcode("S7000 M03"), box_mill)
    with pytest.raises(ProgramError, match="before any F"):
        plan(gcode("G00 G90 G54 X0 Y0", "G01 X1."), box_mill)
    with pytest.raises(ProgramError, match="only D = 0"):
        setup = {**SETUP, "tools": {"1": {"length": 3.0, "diameter_offset": 0.125}}}
        plan(gcode("G00 G90 G54 X0 Y0", "G41 G01 X1. D01 F10."), box_mill, setup=setup)


# ---------------------------------------------------------------------------- the folder
def test_the_box_mills_nose_and_table_are_measured(box_mill) -> None:
    twin, result = box_mill
    program = program_file(gcode("G00 X1."))
    stage = build_stage(twin, [result], None, None)
    geometry = measure_geometry(stage, bind_mill(program.behavior, [result]))
    assert geometry.nose_m == pytest.approx((0.0, 0.0, NOSE_Z), abs=1e-6)
    assert geometry.table_top_m == pytest.approx(TABLE_TOP)


def _named(stage: Usd.Stage, tail: str) -> Usd.Prim:
    (prim,) = [p for p in stage.Traverse() if str(p.GetPath()).endswith("/" + tail)]
    return prim


def _load_runner(folder: Path):
    spec = importlib.util.spec_from_file_location("mill_runner", folder / "run_program.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_program_folder(tmp_path: Path, box_mill) -> None:
    twin, result = box_mill
    program = ProgramFile.load(packaged_programs()["haas-o40001-basic-program"])
    hold = DriveSettings(mode="position", target=0.0, stiffness=100_000.0, damping=632.5)
    output = write_program_folder(tmp_path / "p", program, twin, [result], tmp_path, hold=hold)
    folder = output.folder
    assert sorted(p.name for p in folder.iterdir()) == [
        "PROGRAM.md",
        "program.json",
        "program.nc",
        "program.usdc",
        "record_joints.py",
        "run_program.py",
        "trajectory.json",
    ]
    assert [i for i in validate_file(folder / "program.usdc") if i.severity == "error"] == []
    stage = Usd.Stage.Open(str(folder / "program.usdc"))
    found = {p.joint_path.rsplit("/", 1)[-1]: p for p in _load_runner(folder).find_programs(stage)}
    assert sorted(found) == [
        "carousel_index",
        "spindle_rotation",
        "x_axis",
        "y_axis",
        "z_axis",
    ]
    assert found["x_axis"].kind == "linear" and not found["x_axis"].speed_only
    assert found["spindle_rotation"].speed_only and found["carousel_index"].kind == "angular"
    trajectory = output.trajectory
    assert found["z_axis"].angles == pytest.approx(trajectory.positions["z_axis"])
    z = stage.GetPrimAtPath(found["z_axis"].joint_path)
    drive = UsdPhysics.DriveAPI(z, "linear")
    assert drive.GetStiffnessAttr().Get() == pytest.approx(100_000.0)
    assert drive.GetTargetPositionAttr().Get() == 0.0  # the twin's 0: the plan starts there
    spindle = UsdPhysics.DriveAPI(
        stage.GetPrimAtPath(found["spindle_rotation"].joint_path), "angular"
    )
    assert spindle.GetStiffnessAttr().Get() == 0.0 and spindle.GetDampingAttr().Get() > 0

    # the pictures: the stand-in tool on the nose, the stock and the path on the table
    tool = UsdGeom.Cylinder(_named(stage, "spindle/stand_in_tool"))
    assert tool and tool.GetHeightAttr().Get() == pytest.approx(3 * IN)
    stock = _named(stage, "table/stand_in_stock")
    assert stock and stock.GetCustomDataByKey("moonwalkers")["stand_in"]
    cut = UsdGeom.BasisCurves(_named(stage, "table/programmed_path_cutting"))
    points = cut.GetPointsAttr().Get()
    # O40001 cuts 0.1 in into 2 in of stock, from G54 X0 Y0 (machine X -13, Y -4); at the
    # twin's 0 (X -15, Y -6) the table puts that 2 in to the operator's right (+y) and back (-x)
    deep = TABLE_TOP + 2 * IN - 0.1 * IN
    down, _ = cut.GetCurveVertexCountsAttr().Get()  # line 14's feed down, then line 15's cut
    assert points[0][2] == pytest.approx(TABLE_TOP + 2 * IN + 0.1 * IN, abs=1e-6)  # Z0.1
    across = points[down:]
    assert all(p[2] == pytest.approx(deep, abs=1e-6) for p in across)
    assert list(across[0]) == pytest.approx([-2 * IN, 2 * IN, deep], abs=1e-6)
    assert list(across[-1]) == pytest.approx([2 * IN, -2 * IN, deep], abs=1e-6)

    plan_json = json.loads((folder / "trajectory.json").read_text(encoding="utf-8"))
    assert plan_json["kind"] == "haas_gcode_program" and plan_json["hold"]["damping"] == 632.5
    notes = (folder / "PROGRAM.md").read_text(encoding="utf-8")
    assert "machine X -15.0000, Y -6.0000, Z -10.0000 inch" in notes
    assert "| 14.059" not in notes and "G01 F20. Z-0.1" in notes
    assert (folder / "program.nc").read_text(encoding="utf-8").startswith("%\nO40001")
    with pytest.raises(Exception, match="never overwritten"):
        write_program_folder(folder, program, twin, [result], tmp_path)


def test_the_runner_names_each_joint_when_it_finishes(tmp_path: Path, box_mill) -> None:
    twin, result = box_mill
    program = program_file(gcode("G00 G90 G54 X1. Y1."))
    folder = write_program_folder(tmp_path / "p", program, twin, [result], tmp_path).folder
    runner = _load_runner(folder)
    programs = runner.find_programs(Usd.Stage.Open(str(folder / "program.usdc")))
    progress = runner.Progress(programs)
    progress.lines(0.0)
    lines = progress.lines(1000.0)
    assert any("on x_axis finished at" in line and " m" in line for line in lines)
    assert any("on spindle_rotation finished at" in line and "speed 0" in line for line in lines)
    x = next(p for p in programs if p.joint_path.endswith("x_axis"))
    position, speed = x.target_at(x.duration / 2)
    assert -0.4 < position < 0.4 and abs(speed) <= RAPID + 1e-9


# --------------------------------------------------------------------- recording, CLI
def _perfect(plan_json: dict, lag: float = 0.0) -> dict[str, list[float]]:
    times = [k / 60 for k in range(int((plan_json["duration_s"] + 2) * 60))]
    rec: dict[str, list[float]] = {"time_s": times}
    axes = {a["joint_id"] for a in plan_json["axes"]}
    for joint_id, values in plan_json["positions"].items():
        series = [[v] for v in values]
        col = [_at_point(plan_json["times"], series, max(t - lag, 0.0))[0] for t in times]
        if joint_id in axes:
            rec[f"{joint_id} (m)"] = col
        else:
            rec[f"{joint_id} (rad)"] = [math.radians(v) for v in col]
            rec[f"{joint_id} (rad/s)"] = [0.0] + [
                math.radians(b - a) * 60 for a, b in itertools.pairwise(col)
            ]
    return rec


def test_compare_measures_the_tool_tip(tmp_path: Path, box_mill) -> None:
    twin, result = box_mill
    program = ProgramFile.load(packaged_programs()["haas-o40006-cutter-comp"])
    setup = program.behavior.spec["program"]["setup"]
    assert setup["work_offsets"]["G54"]["X"] == -17.0  # fits the box mill's travel too
    folder = write_program_folder(tmp_path / "p", program, twin, [result], tmp_path).folder
    plan_json = json.loads((folder / "trajectory.json").read_text(encoding="utf-8"))
    perfect = {m.what: m for m in compare(_perfect(plan_json), plan_json)}
    assert perfect[
        "tip's distance from the plan at the same time, whole program"
    ].recorded.startswith("largest 0.000 mm")
    last = perfect["the program's last move arrived"]  # within 0.1 mm a step before the end
    assert float(last.recorded.split()[0]) == pytest.approx(
        float(last.planned.split()[0]), abs=0.02
    )
    assert perfect["spindle's speed while cutting, median"].recorded == "1000.0 RPM"
    top = perfect["X (x_axis): top speed, from positions"]
    assert top.recorded == "84.7 mm/s"
    late = {m.what: m for m in compare(_perfect(plan_json, lag=0.05), plan_json)}
    same_time = late["tip's distance from the plan at the same time, cutting (feeds and arcs)"]
    assert float(same_time.recorded.split()[1]) > 0.5  # 50 ms late at 50 in/min: 1 mm
    on_path = late["tip's distance from the programmed path, cutting (feeds and arcs)"]
    assert float(on_path.recorded.split()[1]) < 0.01  # late, but on the path


def test_the_command_line(tmp_path: Path, box_mill, capsys) -> None:
    twin, result = box_mill
    kb = JsonKnowledgeBase(tmp_path / "kb")
    kb.save_result(result)
    kb.save_twin(twin)
    assert control_cli(["show", "haas-o40001-basic-program"]) == 0
    assert "line  15  X-4. Y-4. (linear motion) ;" in capsys.readouterr().out
    args = ["run", "haas-o40001-basic-program", "--twin", twin.machine_key, "--data", str(tmp_path)]
    assert control_cli([*args, "--acceleration", "0", "--pocket-time", "2"]) == 0
    out = capsys.readouterr().out
    assert "line  15  feed" in out and "tool tip's machine X, Y, Z in inch" in out
    (folder,) = (tmp_path / "machines" / "moonwalkers-testmill" / "programs").iterdir()
    plan_json = json.loads((folder / "trajectory.json").read_text(encoding="utf-8"))
    assert plan_json["settings"]["acceleration_mm_s2"] is None
    assert plan_json["settings"]["seconds_per_pocket"] == 2.0
    recording = tmp_path / "rec.csv"
    rec = _perfect(plan_json)
    with recording.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(list(rec))
        writer.writerows(zip(*rec.values(), strict=True))
    assert read_recording(recording)["time_s"][1] == pytest.approx(1 / 60)
    assert control_cli(["compare", str(recording), str(folder / "trajectory.json")]) == 0
    assert "line 15 feed: tip within 0.1 mm of its end" in capsys.readouterr().out


# ------------------------------------------------------- a trunnion's A and B (decision 0036)
A_ORIGIN, B_ORIGIN, PLATTER_TOP = 0.66, 0.655, 0.665
TOP_SPEED = math.radians(80.0)  # the TR160's 80 deg/s
TRUNNION_MACHINE = {
    **MACHINE,
    "work_part": "platter",
    "rotary": {
        "A": {"joint_id": "a_axis", "direction": [0.0, 1.0, 0.0]},
        "B": {"joint_id": "b_axis", "direction": [0.0, 0.0, 1.0]},
    },
}
TRUNNION_SETUP = {  # G54 X0 Y0 on the platter's centre, under the spindle at the twin's 0
    "units": "inch",
    "work_offsets": {"G54": {"X": -15.0, "Y": -6.0, "Z": 0.0}},
    "tools": {"1": {"length": 3.0, "diameter": 0.5}},
    "stock_height": 1.0,
    "rotary_diameters": {"B": 4.0},
}


def build_trunnion_mill(created_at: datetime) -> tuple[TwinRecord, PipelineResult]:
    """The box mill with a trunnion on its table: a base, a cradle on A (about the table's long
    axis, +-120 deg) and a platter on B (about its normal, no limit), as on the VF-3 twin."""
    twin, result = build_box_mill(created_at)
    parts = [
        *result.parts,
        part("trunnion_base", "Base", box((0.2, 0.6, 0.04), (0.0, 0.0, 0.62)), MADE_UP),
        part("cradle", "Cradle", box((0.15, 0.4, 0.02), (0.0, 0.0, 0.645)), MADE_UP),
        part(
            "platter",
            "Platter",
            cylinder(0.08, 0.01, (0, 0, 1), (0.0, 0.0, PLATTER_TOP - 0.005), segments=32),
            MADE_UP,
        ),
    ]

    def rotary(joint_id, parent, child, axis, origin, limit):
        return Joint(
            joint_id=joint_id,
            joint_type="revolute",
            parent_part=parent,
            child_part=child,
            axis=axis,
            origin_m=origin,
            lower_limit=None if limit is None else -limit,
            upper_limit=limit,
            max_velocity=TOP_SPEED,
            confidence=0.5,
            citations=[MADE_UP],
        )

    joints = [
        *result.joints,
        Joint(
            joint_id="trunnion_mount",
            joint_type="fixed",
            parent_part="table",
            child_part="trunnion_base",
            axis=(0.0, 0.0, 1.0),
            origin_m=(0.0, 0.0, 0.6),
            confidence=0.5,
            citations=[MADE_UP],
        ),
        rotary("a_axis", "trunnion_base", "cradle", (0.0, 1.0, 0.0), (0, 0, A_ORIGIN), 2.0944),
        rotary("b_axis", "cradle", "platter", (0.0, 0.0, 1.0), (0, 0, B_ORIGIN), None),
    ]
    return twin, result.model_copy(update={"parts": parts, "joints": joints})


@pytest.fixture
def trunnion_mill(fixed_time):
    return build_trunnion_mill(fixed_time)


def trunnion_program(text: str, setup: dict | None = None, machine: dict | None = None):
    data = program_file(text).model_dump(mode="json")
    data["behavior"]["spec"]["program"]["machine"] = machine or TRUNNION_MACHINE
    data["behavior"]["spec"]["program"]["setup"] = setup or TRUNNION_SETUP
    data["behavior"]["drives_joints"] = ["x_axis", "y_axis", "z_axis", "a_axis", "b_axis"]
    return ProgramFile.model_validate(data)


def rplan(text: str, mill, setup: dict | None = None, settings: MillSettings = NO_ACC):
    _, result = mill
    program = trunnion_program(text, setup)
    return run_gcode_program(
        GcodeProgram.from_behavior(program.behavior),
        bind_mill(program.behavior, [result]),
        setup_of(program.behavior),
        settings,
        MillGeometry(nose_m=(0.0, 0.0, NOSE_Z), table_top_m=PLATTER_TOP),
    )


def test_a_and_b_are_bound_on_the_work_nearest_the_frame_first(trunnion_mill) -> None:
    binding = bind_mill(trunnion_program(gcode("G00 A1.")).behavior, [trunnion_mill[1]])
    a, b = binding.rotary
    # the joints turn the work, so opposite to Haas's + for the tool (2011 rotary manual, p. 34)
    assert (a.axis, a.joint_id, a.sign, a.home_deg) == ("A", "a_axis", -1, 0.0)
    assert a.lower_deg == pytest.approx(-120.0, abs=1e-3) and a.rapid_deg_s == pytest.approx(80)
    assert (b.axis, b.sign, b.lower_deg, b.upper_deg) == ("B", -1, None, None)
    assert a.origin_m == (0.0, 0.0, A_ORIGIN)
    flipped = {
        **TRUNNION_MACHINE,
        "rotary": dict(reversed(list(TRUNNION_MACHINE["rotary"].items()))),
    }
    again = bind_mill(
        trunnion_program(gcode("G00 A1."), machine=flipped).behavior, [trunnion_mill[1]]
    )
    assert [r.axis for r in again.rotary] == ["A", "B"]  # B rides on A, whatever the order


def test_a_rapid_turns_a_and_b_each_at_its_top_speed(trunnion_mill) -> None:
    t = rplan(gcode("G00 G90 A30. B-90."), trunnion_mill)
    move = event(t, 3)
    assert move.kind == "rapid" and move.to_deg == pytest.approx([30.0, -90.0])
    assert move.end_s - move.start_s == pytest.approx(90 / 80)  # B's 90 deg at 80 deg/s
    a_done = min(range(len(t.times)), key=lambda k: abs(t.times[k] - move.start_s - 30 / 80))
    assert t.machine_deg[a_done][0] == pytest.approx(30.0)  # A arrives first, as G00 says
    assert t.positions["a_axis"][-1] == pytest.approx(-30.0)  # the joints turn the other way
    assert t.positions["b_axis"][-1] == pytest.approx(90.0)
    assert any("Rapid moves are not allowed" in n for n in t.notes)
    incremental = rplan(gcode("G00 G90 A30.", "G91 A-10."), trunnion_mill)
    assert incremental.events[-2].to_deg == pytest.approx([20.0, 0.0])


def test_a_rotary_feed_is_units_per_minute_at_the_parts_diameter(trunnion_mill) -> None:
    t = rplan(gcode("G01 B90. F20."), trunnion_mill)
    move = event(t, 3)
    rate = 20 / 60 / (math.pi * 4.0) * 360  # Setting 79's 4 in: 9.55 deg/s
    assert move.end_s - move.start_s == pytest.approx(90 / rate)
    assert "at Setting 79's 4 in" in move.what and [move.start_s, move.end_s] in t.cutting
    during = [x for x in t.times if move.start_s <= x <= move.end_s]
    assert max(b - a for a, b in itertools.pairwise(during)) <= 2.0 / rate + 1e-9


@pytest.mark.parametrize(
    ("block", "reason"),
    [
        ("G01 A10. F20.", "Setting 34"),
        ("G01 X1. B10. F10.", "G93"),
        ("G01 A10. B10. F10.", "G93"),
        ("G01 B90. F2000.", "max feedrate exceeded"),
        ("G00 B200.", r"\+-180"),
        ("G00 A130.", "outside its range"),
        ("G02 X1. Y1. R1. B10. F10.", "arc cannot turn"),
    ],
)
def test_what_the_plan_refuses_on_a_and_b(trunnion_mill, block: str, reason: str) -> None:
    with pytest.raises(ProgramError, match=reason):
        rplan(gcode("G00 G90 G54 X0 Y0", block), trunnion_mill)


def test_a_and_b_need_a_decimal_point_and_a_map(box_mill) -> None:
    with pytest.raises(ProgramError, match="no decimal point"):
        GcodeProgram.from_text(gcode("G00 A10"))
    with pytest.raises(ProgramError, match="no A axis"):
        plan(gcode("G00 A10."), box_mill)


def test_g28_returns_a_and_b_and_the_brakes_are_logged(trunnion_mill) -> None:
    t = rplan(gcode("G00 G90 A30. B45.", "M11", "G28"), trunnion_mill)
    assert t.events[-2].to_deg == [0.0, 0.0]
    assert "A brake off (logged)" in event(t, 4).what
    named = rplan(gcode("G00 G90 A30. B45.", "G91 G28 B0."), trunnion_mill)
    assert named.events[-2].to_deg == pytest.approx([30.0, 0.0])


def test_a_point_on_the_platter_is_taken_back_through_a_and_b(trunnion_mill) -> None:
    from moonwalkers.control.haas_gcode import _turn

    binding = bind_mill(trunnion_program(gcode("G00 A1.")).behavior, [trunnion_mill[1]])
    a, b = binding.rotary
    m = [-10 * IN, -3 * IN, -2 * IN]  # machine X, Y, Z
    on_platter = (0.03, -0.02, PLATTER_TOP)
    p = _turn(on_platter, b.origin_m, b.joint_axis, b.joint(40.0))
    p = _turn(p, a.origin_m, a.joint_axis, a.joint(-25.0))
    d = binding.displacement(m, "work")
    world = [p[i] + d[i] for i in range(3)]
    assert binding.to_work(world, m, [-25.0, 40.0]) == pytest.approx(on_platter, abs=1e-12)


TILT_AND_TURN = (
    "T1 M06",
    "G00 G90 G54 X-1. Y0",
    "S1000 M03",
    "G43 H01 Z0.1",
    "G01 Z0 F20.",
    "X1.",
    "G00 Z0.1",
    "B90.",
    "X-1.",
    "G01 Z0",
    "X1.",
    "G00 Z0.1",
)


def test_the_path_is_drawn_on_the_platter_as_it_turned(tmp_path: Path, trunnion_mill) -> None:
    twin, result = trunnion_mill
    program = trunnion_program(gcode(*TILT_AND_TURN))
    output = write_program_folder(tmp_path / "p", program, twin, [result], tmp_path)
    stage = Usd.Stage.Open(str(output.folder / "program.usdc"))
    found = {
        p.joint_path.rsplit("/", 1)[-1]: p for p in _load_runner(output.folder).find_programs(stage)
    }
    assert found["b_axis"].kind == "angular" and not found["b_axis"].speed_only
    assert found["b_axis"].angles[-1] == pytest.approx(-90.0)
    cut = UsdGeom.BasisCurves(_named(stage, "platter/programmed_path_cutting"))
    counts = list(cut.GetCurveVertexCountsAttr().Get())
    points = [list(p) for p in cut.GetPointsAttr().Get()]
    top = PLATTER_TOP + 1.0 * IN
    first = points[counts[0] : counts[0] + counts[1]]  # line 8's cut, at A0 B0: along twin y
    assert all(p[0] == pytest.approx(0.0, abs=1e-6) for p in first)
    assert [first[0][1], first[-1][1]] == pytest.approx([-IN, IN], abs=1e-6)
    second = points[sum(counts[:3]) :]  # line 13's cut, at B90: turned back onto twin x
    assert all(p[1] == pytest.approx(0.0, abs=1e-6) for p in second)
    assert all(p[2] == pytest.approx(top, abs=1e-6) for p in first + second)
    assert {round(second[0][0] / IN, 6), round(second[-1][0] / IN, 6)} == {-1.0, 1.0}
    assert _named(stage, "platter/stand_in_stock")
    notes = (output.folder / "PROGRAM.md").read_text(encoding="utf-8")
    assert "| B | `b_axis` |" in notes and "Setting 79 (B's part diameter" in notes
    assert "To (X, Y, Z, A, B)" in notes

    plan_json = json.loads((output.folder / "trajectory.json").read_text(encoding="utf-8"))
    perfect = {m.what: m for m in compare(_perfect(plan_json), plan_json)}
    gap = perfect["B (b_axis): distance from the plan at the same time"]
    assert gap.recorded.startswith("largest 0.000 deg")
    assert perfect["B (b_axis): top speed, from positions"].recorded == "80.00 deg/s"
    name = "line 10 rapid: tip within 0.1 mm, A and B within 0.05 deg, of its end"
    arrived = perfect[name]
    assert float(arrived.recorded.split()[0]) == pytest.approx(
        float(arrived.planned.split()[0]), abs=0.02
    )


def test_recorded_angles_are_unwrapped() -> None:
    from moonwalkers.control.compare import unwrap_deg

    assert unwrap_deg([350.0, 359.9, -359.5, -350.0]) == pytest.approx([350, 359.9, 360.5, 370])
    assert unwrap_deg([-10.0, -20.0]) == [-10.0, -20.0]


@pytest.mark.parametrize(
    "name", ["haas-o40001-basic-program-vf3", "moonwalkers-vf3-test-tilt-and-turn"]
)
def test_the_vf3_programs_plan_on_a_trunnion(trunnion_mill, name: str) -> None:
    program = ProgramFile.load(packaged_programs()[name])
    t = run_gcode_program(
        GcodeProgram.from_behavior(program.behavior),
        bind_mill(program.behavior, [trunnion_mill[1]]),
        setup_of(program.behavior),
        NO_ACC,
        MillGeometry(nose_m=(0.0, 0.0, NOSE_Z), table_top_m=PLATTER_TOP),
    )
    assert t.events[-1].kind == "end" and t.machine_deg[-1] == [0.0, 0.0]
    if name.startswith("moonwalkers"):
        assert max(r[0] for r in t.machine_deg) == pytest.approx(30.0)  # tilted on A
        assert max(r[1] for r in t.machine_deg) == pytest.approx(90.0)  # turned on B
