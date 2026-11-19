"""Write the files that run a Haas program on a mill's twin in Isaac Sim (decision 0035).

A program folder holds, as decisions 0016 and 0033's do::

    program.json         the program that was run: its behaviour, set-up and the sources it cites
    program.nc           the program's text, as Haas's manual prints it
    trajectory.json      the plan: each joint's targets over time, the tool tip's machine
                         position, what each block did, the set-up and the notes
    program.usdc         the twin at its 0 pose, with each joint's planned motion for the runner,
                         a stand-in tool in the spindle, a stand-in block of stock on the table,
                         and the programmed path drawn on the table
    run_program.py       the runner for Isaac Sim's Script Editor (isaac_runner.py)
    record_joints.py     the joint recorder (usd/isaac_recorder.py), for ``control compare``
    PROGRAM.md           the blocks, the timeline, what to check, and room for the result

Each axis joint carries ``moonwalkers:program:times`` and ``moonwalkers:program:positions`` (m,
the stage's unit), the carousel its planned angles (degrees), and the spindle its angles with
``moonwalkers:program:speedOnly``: the runner gives the spindle only its speed, on a velocity drive
(the exporter's spin damping, 20), since a turning joint without limits wraps its position. The
twin's own hold (``hold_drive``) and collisions (``self_collision``) are passed in. There is no
``program_native.usdc``: the spindle's speed cannot be a time-sampled position target. The tool,
the stock and the path are pictures: no collision, no mass. A folder is never overwritten.
"""

from __future__ import annotations

import json
import math
import shutil
from collections.abc import Sequence
from datetime import UTC, datetime
from importlib.metadata import version as package_version
from pathlib import Path

from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics, Vt

from moonwalkers.contracts.pipeline_result import PipelineResult, TwinRecord
from moonwalkers.usd.exporter import (
    TIME_CODES_PER_SECOND,
    Collisions,
    DriveSettings,
    ExportError,
    build_stage,
    write_stage,
)
from moonwalkers.usd.validate import validate_file

from .haas_gcode import (
    GcodeProgram,
    MillBinding,
    MillGeometry,
    MillSettings,
    MillTrajectory,
    Setup,
    bind_mill,
    run_gcode_program,
    setup_of,
)
from .isaac_runner import NAME, POSITIONS, SPEED_ONLY, TIMES
from .program import PROGRAM_KEY, ProgramError, ProgramFile

PLANNED = "moonwalkers:program:plannedPosition"
RUNNER = Path(__file__).with_name("isaac_runner.py")
RECORDER = Path(__file__).parents[1] / "usd" / "isaac_recorder.py"
KIND = "haas_gcode_program"  # trajectory.json's kind, which ``control compare`` reads
SPINDLE_DAMPING = DriveSettings.spin(0.0).damping  # the exporter's velocity drive (20 per s)
NOSE_MIN_POINTS = 16  # the nose's face: the lowest level of the tool part with this many points
TOP_AREA_SHARE = 0.5  # the table's top: the highest level with this share of the largest's area
STOCK_MARGIN_M = 0.00635  # the stand-in stock reaches 0.25 in past the path on every side
CUTTING_COLOR = (0.85, 0.1, 0.1)
RAPID_COLOR = (0.1, 0.35, 0.9)


def write_mill_program_folder(
    out_dir: Path,
    program: ProgramFile,
    twin: TwinRecord,
    results: Sequence[PipelineResult],
    data_dir: Path,
    settings: MillSettings | None = None,
    hold: DriveSettings | None = None,
    collide_unjoined: bool | Collisions = False,
    hidden_parts: Sequence[str] = (),
) -> tuple[Path, MillBinding, MillTrajectory, MillSettings]:
    """Run the Haas ``program`` on ``twin``'s axes and write the folder ``out_dir``."""
    out_dir = Path(out_dir)
    if out_dir.exists():
        raise ExportError(f"{out_dir} exists; program folders are never overwritten")
    settings = settings or MillSettings()
    gcode = GcodeProgram.from_behavior(program.behavior)
    binding = bind_mill(program.behavior, results)
    setup = setup_of(program.behavior)

    base = hold or DriveSettings.hold(0.0)
    drive = DriveSettings(  # the twin's 0 is where the program starts
        mode="position", target=0.0, stiffness=base.stiffness, damping=base.damping
    )
    stage = build_stage(
        twin, results, drive, data_dir, collide_unjoined=collide_unjoined, hidden_parts=hidden_parts
    )
    geometry = measure_geometry(stage, binding)
    trajectory = run_gcode_program(gcode, binding, setup, settings, geometry)

    for joint_id, values in trajectory.positions.items():
        prim = _joint_prim(stage, joint_id)
        _add_program(
            prim, program, trajectory.times, values, speed_only=joint_id == binding.spindle
        )
    if binding.spindle is not None:
        api = UsdPhysics.DriveAPI(_joint_prim(stage, binding.spindle), "angular")
        api.GetStiffnessAttr().Set(0.0)
        api.GetDampingAttr().Set(SPINDLE_DAMPING)
        api.GetTargetVelocityAttr().Set(0.0)
    tool = _drawn_tool(setup, trajectory)
    _add_pictures(stage, binding, geometry, setup, trajectory, tool)
    _add_provenance(_joint_prim(stage, binding.axes[0].joint_id), program, trajectory, settings)

    tmp = out_dir.with_name(f".{out_dir.name}.tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    try:
        path = write_stage(stage, tmp / "program.usdc")
        errors = [i for i in validate_file(path) if i.severity == "error"]
        if errors:
            raise ExportError(f"program.usdc failed validation: {errors[0].message}")
        shutil.copyfile(RUNNER, tmp / "run_program.py")
        shutil.copyfile(RECORDER, tmp / "record_joints.py")
        _write_text(tmp / "program.json", program.model_dump_json(indent=2))
        _write_text(tmp / "program.nc", program.behavior.spec[PROGRAM_KEY]["text"])
        _write_text(
            tmp / "trajectory.json",
            trajectory_json(trajectory, settings, binding, geometry, setup, twin, drive, tool),
        )
        _write_text(
            tmp / "PROGRAM.md",
            mill_program_notes(
                program,
                gcode,
                twin,
                binding,
                geometry,
                setup,
                trajectory,
                settings,
                drive,
                collide_unjoined,
                tool,
            ),
        )
        tmp.rename(out_dir)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return out_dir, binding, trajectory, settings


# ------------------------------------------------------------------------------- geometry
def measure_geometry(stage: Usd.Stage, binding: MillBinding) -> MillGeometry:
    """The spindle nose's face and the table's top, on the twin at its 0.

    The face is the lowest level of the tool part's mesh that holds at least
    ``NOSE_MIN_POINTS`` points: the stand-in nose is a 32-sided cylinder, and its drive keys hang
    below the face with four points each [INFERENCE: a turned nose's rim]. Its centre is where
    the spindle's joint axis, when vertical, crosses it; else the mean of the face's points. The
    mean alone is off the axis when a key lies on the face (the agent's TM-1, `haas/tm1@v4`:
    one lug, 5.4 mm; Phase 8), and a tool drawn there circles the axis as the spindle turns.
    The table's top is the highest level, under the face, where the work part's upward faces
    have at least half the area of its largest such level: a line straight down from the nose
    can fall into a T-slot, and a stand-in built of overlapping boxes (the TM-1's: a slab with
    rails between the slots) has a hidden face below its top with more area. A chip guard's rim
    above the top has little area."""
    points = _points(_part_prim(stage, binding.tool_part))
    if not points:
        raise ProgramError(f"the tool part '{binding.tool_part}' has no mesh")
    levels: dict[float, list[tuple[float, float, float]]] = {}
    for p in points:
        levels.setdefault(round(p[2], 4), []).append(p)
    face = next((levels[z] for z in sorted(levels) if len(levels[z]) >= NOSE_MIN_POINTS), None)
    if face is None:
        raise ProgramError(f"no level of '{binding.tool_part}' holds {NOSE_MIN_POINTS} points")
    nx = sum(p[0] for p in face) / len(face)
    ny = sum(p[1] for p in face) / len(face)
    nz = face[0][2]
    on_axis = _vertical_axis_xy(stage, binding.spindle) if binding.spindle else None
    if on_axis is not None:  # the tool turns about the spindle's joint, so its tip is on it
        nx, ny = on_axis
    areas: dict[float, float] = {}  # by height to the millimetre
    heights: dict[float, float] = {}  # the faces' own height, area-weighted
    for tri in _triangles(_part_prim(stage, binding.work_part)):
        up, area = _upward(tri)
        z = sum(v[2] for v in tri) / 3
        if up and z < nz:
            areas[round(z, 3)] = areas.get(round(z, 3), 0.0) + area
            heights[round(z, 3)] = heights.get(round(z, 3), 0.0) + area * z
    if not areas:
        raise ProgramError(f"the work part '{binding.work_part}' has no top under the spindle")
    largest = max(areas.values())
    top = max(z for z, area in areas.items() if area >= TOP_AREA_SHARE * largest)
    return MillGeometry(nose_m=(nx, ny, nz), table_top_m=heights[top] / areas[top])


def _vertical_axis_xy(stage: Usd.Stage, joint_id: str) -> tuple[float, float] | None:
    """Where the revolute joint ``joint_id``'s axis stands, (x, y) on the twin at its 0, if the
    axis is vertical (within about 2.5 degrees); else None."""
    joint = UsdPhysics.Joint(_joint_prim(stage, joint_id))
    targets = joint.GetBody1Rel().GetTargets()
    if not targets:
        return None
    body = stage.GetPrimAtPath(targets[0])
    xf = UsdGeom.XformCache().GetLocalToWorldTransform(body)
    anchor = xf.Transform(Gf.Vec3d(joint.GetLocalPos1Attr().Get() or Gf.Vec3f(0.0)))
    token = UsdPhysics.RevoluteJoint(joint.GetPrim()).GetAxisAttr().Get() or "X"
    local = Gf.Vec3d(*(1.0 if token == name else 0.0 for name in "XYZ"))
    rotation = joint.GetLocalRot1Attr().Get() or Gf.Quatf(1.0)
    axis = xf.TransformDir(Gf.Rotation(Gf.Quatd(rotation)).TransformDir(local))
    if axis.GetLength() < 1e-12 or abs(axis[2]) / axis.GetLength() < 0.999:
        return None
    return anchor[0], anchor[1]


def _upward(tri: Sequence[Sequence[float]]) -> tuple[bool, float]:
    """Whether a triangle faces straight up (within about 2.5 degrees), and its area."""
    (x1, y1, z1), (x2, y2, z2), (x3, y3, z3) = tri
    u, v = (x2 - x1, y2 - y1, z2 - z1), (x3 - x1, y3 - y1, z3 - z1)
    n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
    length = math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2)
    if length < 1e-15:
        return False, 0.0
    return n[2] / length > 0.999, length / 2


def _part_prim(stage: Usd.Stage, part_id: str) -> Usd.Prim:
    for prim in stage.Traverse():
        data = prim.GetCustomDataByKey("moonwalkers")
        if prim.HasAPI(UsdPhysics.RigidBodyAPI) and data and data.get("part_id") == part_id:
            return prim
    raise ExportError(f"the exported twin has no part '{part_id}'")


def _meshes(prim: Usd.Prim) -> list[tuple[UsdGeom.Mesh, Gf.Matrix4d]]:
    cache = UsdGeom.XformCache()
    return [
        (UsdGeom.Mesh(p), cache.GetLocalToWorldTransform(p))
        for p in Usd.PrimRange(prim)
        if p.IsA(UsdGeom.Mesh)
    ]


def _points(prim: Usd.Prim) -> list[tuple[float, float, float]]:
    out = []
    for mesh, xf in _meshes(prim):
        for p in mesh.GetPointsAttr().Get() or []:
            q = xf.Transform(Gf.Vec3d(p))
            out.append((q[0], q[1], q[2]))
    return out


def _triangles(prim: Usd.Prim) -> list[tuple[tuple[float, float, float], ...]]:
    out = []
    for mesh, xf in _meshes(prim):
        pts = [xf.Transform(Gf.Vec3d(p)) for p in mesh.GetPointsAttr().Get() or []]
        counts = mesh.GetFaceVertexCountsAttr().Get() or []
        indices = list(mesh.GetFaceVertexIndicesAttr().Get() or [])
        at = 0
        for n in counts:
            face = indices[at : at + n]
            at += n
            for k in range(1, n - 1):
                out.append(tuple(tuple(pts[i]) for i in (face[0], face[k], face[k + 1])))
    return out  # type: ignore[return-value]


# ------------------------------------------------------------------------------- pictures
def _drawn_tool(setup: Setup, trajectory: MillTrajectory) -> tuple[str, float, float] | None:
    """(number, length m, diameter m) of the tool the pictures show: the one in the spindle at
    the end, if the set-up gives its length."""
    if trajectory.tool is None:
        return None
    tool = setup.tools.get(trajectory.tool)
    if tool is None or tool.length is None:
        return None
    unit = setup.unit_m
    diameter = (tool.diameter or 0.25) * unit
    return trajectory.tool, tool.length * unit, diameter


def tip_on_table(
    binding: MillBinding,
    geometry: MillGeometry,
    length_m: float,
    machine_m: Sequence[float],
    rotary_deg: Sequence[float] = (),
) -> tuple[float, float, float]:
    """The tool tip at machine position ``machine_m`` (and A, B at ``rotary_deg``), in the work
    part's frame at the twin's 0 (where its points are drawn): the tip's place, taken back
    through how far the work has moved and turned (decision 0036)."""
    z = next(a for a in binding.axes if a.axis == "Z")
    tip0 = [geometry.nose_m[i] - length_m * z.direction[i] for i in range(3)]
    tool = binding.displacement(machine_m, "tool")
    return binding.to_work([tip0[i] + tool[i] for i in range(3)], machine_m, rotary_deg)


def _add_pictures(
    stage: Usd.Stage,
    binding: MillBinding,
    geometry: MillGeometry,
    setup: Setup,
    trajectory: MillTrajectory,
    tool: tuple[str, float, float] | None,
) -> None:
    if tool is None:
        return
    number, length, diameter = tool
    spindle = _part_prim(stage, binding.tool_part)
    cylinder = UsdGeom.Cylinder.Define(stage, spindle.GetPath().AppendChild("stand_in_tool"))
    cylinder.CreateAxisAttr("Z")
    cylinder.CreateHeightAttr(length)
    cylinder.CreateRadiusAttr(diameter / 2)
    nx, ny, nz = geometry.nose_m
    cylinder.AddTranslateOp().Set(Gf.Vec3d(nx, ny, nz - length / 2))
    cylinder.CreateDisplayColorAttr([(0.75, 0.75, 0.2)])
    _label(
        cylinder.GetPrim(),
        f"Stand-in tool T{number}: {length * 1000:.1f} mm from the nose's face, "
        f"{diameter * 1000:.2f} mm across (decision 0035); a picture, no collision",
    )

    table = _part_prim(stage, binding.work_part)
    cut = _samples(trajectory, [(a, b) for a, b in trajectory.cutting])
    rapids = _samples(
        trajectory,
        [(e.start_s, e.end_s) for e in trajectory.events if e.kind in ("rapid", "power_up")],
    )

    def drawn(times_runs: list[list[int]]) -> list[list[tuple[float, float, float]]]:
        return [
            [
                tip_on_table(binding, geometry, length, _m(trajectory, k), _rot(trajectory, k))
                for k in run
            ]
            for run in times_runs
            if len(run) > 1
        ]

    cut_points, rapid_points = drawn(cut), drawn(rapids)
    for name, runs, color in (
        ("programmed_path_cutting", cut_points, CUTTING_COLOR),
        ("programmed_path_rapid", rapid_points, RAPID_COLOR),
    ):
        if not runs:
            continue
        curves = UsdGeom.BasisCurves.Define(stage, table.GetPath().AppendChild(name))
        curves.CreateTypeAttr(UsdGeom.Tokens.linear)
        curves.CreateCurveVertexCountsAttr(Vt.IntArray([len(r) for r in runs]))
        curves.CreatePointsAttr(Vt.Vec3fArray([Gf.Vec3f(*p) for r in runs for p in r]))
        curves.CreateWidthsAttr(Vt.FloatArray([0.0015]))
        curves.SetWidthsInterpolation(UsdGeom.Tokens.constant)
        curves.CreateDisplayColorAttr([color])
        curves.CreateExtentAttr(
            UsdGeom.Curves.ComputeExtent(curves.GetPointsAttr().Get(), curves.GetWidthsAttr().Get())
        )
        _label(
            curves.GetPrim(),
            f"The programmed tool tip path ({name.rsplit('_', 1)[-1]} moves), drawn on the table "
            f"with T{number}'s stand-in length: the tip should trace it",
        )

    if setup.stock_height is None or not cut_points:
        return
    xs = [p[0] for r in cut_points for p in r]
    ys = [p[1] for r in cut_points for p in r]
    height = setup.stock_height * setup.unit_m
    size = (
        max(xs) - min(xs) + 2 * STOCK_MARGIN_M,
        max(ys) - min(ys) + 2 * STOCK_MARGIN_M,
        height,
    )
    centre = ((max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2, geometry.table_top_m + height / 2)
    cube = UsdGeom.Cube.Define(stage, table.GetPath().AppendChild("stand_in_stock"))
    cube.CreateSizeAttr(1.0)
    cube.AddTranslateOp().Set(Gf.Vec3d(*centre))
    cube.AddScaleOp().Set(Gf.Vec3f(*size))
    cube.CreateDisplayColorAttr([(0.6, 0.62, 0.66)])
    cube.CreateDisplayOpacityAttr([0.45])
    _label(
        cube.GetPrim(),
        f"Stand-in stock: {setup.stock_height:g} {setup.units} tall under the cutting path "
        "(decision 0035); half see-through so the tip shows; a picture, no collision",
    )


def _samples(trajectory: MillTrajectory, spans: list[tuple[float, float]]) -> list[list[int]]:
    """The plan's sample indices in each span."""
    out = []
    times = trajectory.times
    for start, end in spans:
        run = [k for k, t in enumerate(times) if start - 1e-9 <= t <= end + 1e-9]
        if run:
            out.append(run)
    return out


def _m(trajectory: MillTrajectory, k: int) -> list[float]:
    return [v / 1000 for v in trajectory.machine_mm[k]]


def _rot(trajectory: MillTrajectory, k: int) -> list[float]:
    return list(trajectory.machine_deg[k]) if trajectory.machine_deg else []


def _label(prim: Usd.Prim, text: str) -> None:
    prim.SetDocumentation(text)
    prim.SetCustomDataByKey("moonwalkers", {"stand_in": True, "note": text})


# ---------------------------------------------------------------------------- the files
def trajectory_json(
    trajectory: MillTrajectory,
    settings: MillSettings,
    binding: MillBinding,
    geometry: MillGeometry,
    setup: Setup,
    twin: TwinRecord,
    drive: DriveSettings,
    tool: tuple[str, float, float] | None,
) -> str:
    data = {
        "kind": KIND,
        "twin_id": twin.twin_id,
        "settings": settings.model_dump(mode="json"),
        "setup": setup.model_dump(mode="json"),
        "binding": binding.model_dump(mode="json"),
        "geometry": geometry.model_dump(mode="json"),
        "tool_tip": None
        if tool is None
        else {"tool": tool[0], "length_m": tool[1], "diameter_m": tool[2]},
        "hold": {"stiffness": drive.stiffness, "damping": drive.damping},
        "spindle_damping": SPINDLE_DAMPING,
        "duration_s": trajectory.duration_s,
        **trajectory.model_dump(mode="json"),
    }
    return json.dumps(data, indent=1)


def mill_program_notes(
    program: ProgramFile,
    gcode: GcodeProgram,
    twin: TwinRecord,
    binding: MillBinding,
    geometry: MillGeometry,
    setup: Setup,
    trajectory: MillTrajectory,
    settings: MillSettings,
    drive: DriveSettings,
    collide_unjoined: bool | Collisions,
    tool: tuple[str, float, float] | None,
) -> str:
    """``PROGRAM.md``: what the program is, what it should do, and the check to fill in."""
    behavior = program.behavior
    unit = setup.units
    u = setup.unit_m

    def m_to(v: float) -> str:
        return f"{round(v / u, 4) + 0.0:.4f}"

    lines = [
        f"# Program: {program.name} on {twin.twin_id}",
        "",
        f"- Program: {behavior.name} (`program.nc`, as printed; `program.json`)",
        f"- What it is: {behavior.description}",
        "- Cited: " + "; ".join(c.locator for c in behavior.citations if c.locator),
        f"- Twin: {twin.twin_id} ({twin.status.replace('_', ' ')})",
        (
            f"- Duration {trajectory.duration_s:.2f} s, of which "
            f"{sum(b - a for a, b in trajectory.cutting):.2f} s cutting (feeds and arcs); "
            f"{len(trajectory.times)} points"
        ),
        (
            f"- Simulation: the axes and the carousel hold with stiffness {drive.stiffness:g} and "
            f"damping {drive.damping:g} (the twin's hold, decision 0034); the spindle is a "
            f"velocity drive (damping {SPINDLE_DAMPING:g}); unjoined parts "
            + ("collide, as in the twin" if collide_unjoined else "do not collide, as in the twin")
        ),
        (
            f"- Written by moonwalkers {package_version('moonwalkers')} on "
            f"{datetime.now(UTC).isoformat(timespec='seconds')}"
        ),
        "",
        "## Haas's axes on the twin (decision 0035)",
        "",
        "A program's coordinates are the tool tip's against the table. Machine zero is home.",
        "",
        (
            "| Axis | Joint | Moves | + is the tool going (twin frame) | Machine = "
            "| Home: joint at | Travel (machine) |"
        ),
        "|---|---|---|---|---|---|---|",
    ]
    for a in binding.axes:
        ends = sorted((a.machine(a.lower_m), a.machine(a.upper_m)))
        lines.append(
            f"| {a.axis} | `{a.joint_id}` | the {a.side}'s part | {_vec(a.direction)} | "
            f"{'+' if a.sign > 0 else '-'}(joint - home) | {a.home_m:+.4f} m | "
            f"{m_to(ends[0])} to {m_to(ends[1])} {unit} |"
        )
    if binding.rotary:
        lines += [
            "",
            (
                "A and B (decision 0036): always in degrees. Their joints ride the work, so they "
                "turn opposite to Haas's + for the tool (the right hand rule)."
            ),
            "",
            (
                "| Axis | Joint | + turns the tool about (twin frame) | Machine = | Home: joint at "
                "| Range (joint) | Top speed |"
            ),
            "|---|---|---|---|---|---|---|",
        ]
        for r in binding.rotary:
            span = (
                f"{r.lower_deg:+.1f} to {r.upper_deg:+.1f} deg"
                if r.lower_deg is not None and r.upper_deg is not None
                else "no limit (the plan keeps within +-180 deg)"
            )
            lines.append(
                f"| {r.axis} | `{r.joint_id}` | {_vec(r.direction)} | "
                f"{'+' if r.sign > 0 else '-'}(joint - home) | {r.home_deg:+.1f} deg | {span} | "
                f"{r.rapid_deg_s:.1f} deg/s |"
            )
    start = binding.machine({a.joint_id: 0.0 for a in binding.axes})
    rot0 = [r.machine(0.0) for r in binding.rotary]
    lines += [
        "",
        "The twin's 0 (its photographed pose) is machine "
        + ", ".join(f"{a.axis} {m_to(v)}" for a, v in zip(binding.axes, start, strict=True))
        + f" {unit}"
        + "".join(f", {r.axis} {v + 0.0:g} deg" for r, v in zip(binding.rotary, rot0, strict=True))
        + ".",
        "",
        "## The set-up (stand-ins, labelled)",
        "",
        f"- Units (Setting 9): {unit}",
    ]
    for name, diameter in setup.rotary_diameters.items():
        setting = "Setting 34" if name == "A" else "Setting 79"
        lines.append(
            f"- {setting} ({name}'s part diameter, for a rotary feed): {diameter:g} {unit}"
        )
    for name, offset in setup.work_offsets.items():
        lines.append(
            f"- Work offset {name}: "
            + ", ".join(f"{k} {v:g}" for k, v in offset.items())
            + f" {unit} (machine)"
        )
    for t in trajectory.tool_offsets:
        lines.append(f"- Tool length offset H{int(t.tool):02d} = {t.h:.4f} {unit}: {t.how}")
    if tool is not None:
        lines.append(
            f"- **The tool tip:** T{tool[0]}'s tip, on the spindle's axis {tool[1] / u:g} {unit} "
            f"below the nose's face (drawn as `stand_in_tool`, {tool[2] / u:g} {unit} across)"
        )
    lines.append(
        f"- Measured on the twin: the nose's face at ({_vec(geometry.nose_m)}) m, "
        f"{geometry.nose_over_table_at(binding, start[2]) / u:.2f} {unit} over the table's top "
        f"(z {geometry.table_top_m:.4f} m) at the twin's 0, "
        f"{geometry.nose_over_table_at(binding, 0.0) / u:.2f} {unit} at Z home"
    )
    lines += [f"- {why}" for why in setup.why]
    lines += [
        "",
        "## The blocks, and what each did (the plan)",
        "",
        "Positions are the tool tip's machine X, Y, Z, in "
        + unit
        + "".join(f", and {r.axis}" for r in binding.rotary)
        + (" in degrees" if binding.rotary else "")
        + ".",
        "",
        "| Start (s) | End (s) | Line | Block | Kind | To (X, Y, Z"
        + "".join(f", {r.axis}" for r in binding.rotary)
        + ") | What |",
        "|---|---|---|---|---|---|---|",
    ]
    for e in trajectory.events:
        to = ", ".join([f"{v / 1000 / u:.4f}" for v in e.to_mm] + [f"{v:.3f}" for v in e.to_deg])
        block = e.block.replace("|", "\\|")
        lines.append(
            f"| {e.start_s:.3f} | {e.end_s:.3f} | {e.line or ''} | `{block}` | {e.kind} | {to} | "
            f"{e.what} |"
        )
    if trajectory.notes:
        lines += ["", "## Notes", "", *(f"- {n}" for n in trajectory.notes)]
    lines += [
        "",
        "## Check in Isaac Sim (fill in; `docs/setup/isaac-sim-check.md`, sections 12 and 14)",
        "",
        "1. Open `program.usdc` (not the run's `twin.usdc`). The twin opens in its photographed",
        "   pose, with a yellow stand-in tool under the spindle, a grey see-through block on the",
        "   table, and the programmed path drawn on the table: red for cutting, blue for rapids.",
        "2. Window > Script Editor: paste the whole of `run_program.py` and click Run. It prints",
        f"   one line per joint ({len(trajectory.positions)}) and the physics API it uses.",
        "3. In a second Script Editor tab, paste `record_joints.py` from this folder and click",
        "   Run.",
        "4. Press Play. Type nothing: the runner moves every target. The axes go home first (Z",
        "   up, then X and Y), then the program runs: the tip should trace the red path on the",
        f"   block, and the program ends after {trajectory.duration_s:.1f} s. Let it run 2 s more,",
        "   then Stop. The recorder writes `recordings/program_<date>_<time>.csv` here.",
        "",
        "Then: `uv run python -m moonwalkers.control compare <recording.csv> trajectory.json`.",
        "",
        "- Isaac Sim version/build:",
        "- Runner output (API, first physics step):",
        "- Did the tip follow the red path? Did the spindle turn while cutting?",
        "- Did anything sag, jump or shake?",
        "- Where did it stop?",
        "- Success level reached (1-3):",
        "- Reviewer notes:",
    ]
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------------------------ helpers
def _vec(v: Sequence[float]) -> str:
    return ", ".join(f"{round(c, 4) + 0.0:+.4g}" for c in v)


def _joint_prim(stage: Usd.Stage, joint_id: str) -> Usd.Prim:
    for prim in stage.Traverse():
        data = prim.GetCustomDataByKey("moonwalkers")
        if (
            (prim.IsA(UsdPhysics.RevoluteJoint) or prim.IsA(UsdPhysics.PrismaticJoint))
            and data
            and data.get("joint_id") == joint_id
        ):
            return prim
    raise ExportError(f"the exported twin has no driven joint '{joint_id}'")


def _add_program(
    prim: Usd.Prim,
    program: ProgramFile,
    times: Sequence[float],
    values: Sequence[float],
    speed_only: bool,
) -> None:
    prim.CreateAttribute(NAME, Sdf.ValueTypeNames.String, custom=True).Set(program.name)
    doubles = Sdf.ValueTypeNames.DoubleArray
    prim.CreateAttribute(TIMES, doubles, custom=True).Set(Vt.DoubleArray(list(times)))
    prim.CreateAttribute(POSITIONS, doubles, custom=True).Set(Vt.DoubleArray(list(values)))
    if speed_only:
        prim.CreateAttribute(SPEED_ONLY, Sdf.ValueTypeNames.Bool, custom=True).Set(True)
    else:
        planned = prim.CreateAttribute(PLANNED, Sdf.ValueTypeNames.Double, custom=True)
        for t, v in zip(times, values, strict=True):
            planned.Set(v, Usd.TimeCode(t * TIME_CODES_PER_SECOND))
    kind = "linear" if prim.IsA(UsdPhysics.PrismaticJoint) else "angular"
    UsdPhysics.DriveAPI(prim, kind).CreateTargetVelocityAttr(0.0)
    prim.SetDocumentation(
        f"{prim.GetMetadata('documentation') or ''} Runs Haas program '{program.name}' through "
        "run_program.py (decision 0035).".strip()
    )


def _add_provenance(
    prim: Usd.Prim, program: ProgramFile, trajectory: MillTrajectory, settings: MillSettings
) -> None:
    behavior = program.behavior
    prim.SetCustomDataByKey(
        "moonwalkers:program",
        {
            "name": program.name,
            "format": "haas_gcode",
            "behavior_id": behavior.behavior_id,
            "behavior_name": behavior.name,
            "settings": settings.model_dump_json(),
            "duration_s": trajectory.duration_s,
            "citations": json.dumps([c.model_dump(mode="json") for c in behavior.citations]),
            "sources": json.dumps([s.model_dump(mode="json") for s in program.sources]),
        },
    )


def _write_text(path: Path, text: str) -> None:
    path.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8", newline="\n")
