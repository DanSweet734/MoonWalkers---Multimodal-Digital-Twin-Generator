"""Write the files that run an iRC program on an arm's twin in Isaac Sim (decision 0033).

A program folder holds, as decision 0016's do::

    program.json         the program that was run: its behaviour and the sources it cites
    program.xml          the iRC program itself, as iRC stores it ("Robot programs are .xml files")
    trajectory.json      the plan: settings, each joint's targets over time, events and notes
    program.usdc         the twin at its 0 pose, with each joint's planned motion for the runner
    run_program.py       the runner for Isaac Sim's Script Editor (isaac_runner.py, unchanged)
    record_joints.py     the joint recorder (usd/isaac_recorder.py), for ``control compare``
    program_native.usdc  the same motion as time samples on each drive's own target
    PROGRAM.md           the commands, the timeline, what to check, and room for the result

Every arm joint carries ``moonwalkers:program:times`` and ``moonwalkers:program:anglesDeg`` (the
twin's angles, so iRC's minus the pose's), which the runner reads, and a time-sampled
``moonwalkers:program:plannedAngleDeg`` to scrub. The twin's own hold (``hold_drive``) and its
collisions (``self_collision``, decision 0032) are passed in, so the program's stage holds and
collides as the twin does. A folder is never overwritten.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Sequence
from datetime import UTC, datetime
from importlib.metadata import version as package_version
from pathlib import Path

from pxr import Sdf, Usd, UsdPhysics, Vt

from moonwalkers.contracts.pipeline_result import PipelineResult, TwinRecord
from moonwalkers.usd.exporter import (
    TIME_CODES_PER_SECOND,
    DriveSettings,
    ExportError,
    build_stage,
    write_stage,
)
from moonwalkers.usd.validate import validate_file

from .irc import (
    ArmBinding,
    ArmSettings,
    ArmTrajectory,
    IrcProgram,
    JointMove,
    Loop,
    Output,
    Wait,
    bind_arm,
    run_irc_program,
)
from .isaac_runner import ANGLES, NAME, TIMES
from .program import PROGRAM_KEY, ProgramFile

PLANNED = "moonwalkers:program:plannedAngleDeg"
RUNNER = Path(__file__).with_name("isaac_runner.py")
RECORDER = Path(__file__).parents[1] / "usd" / "isaac_recorder.py"
KIND = "irc_joint_program"  # trajectory.json's kind, which ``control compare`` reads


def write_arm_program_folder(
    out_dir: Path,
    program: ProgramFile,
    twin: TwinRecord,
    results: Sequence[PipelineResult],
    data_dir: Path,
    settings: ArmSettings | None = None,
    hold: DriveSettings | None = None,
    collide_unjoined: bool = False,
) -> tuple[Path, ArmBinding, ArmTrajectory, ArmSettings]:
    """Run the iRC ``program`` on ``twin``'s arm joints and write the folder ``out_dir``."""
    out_dir = Path(out_dir)
    if out_dir.exists():
        raise ExportError(f"{out_dir} exists; program folders are never overwritten")
    settings = settings or ArmSettings()
    irc = IrcProgram.from_behavior(program.behavior)
    binding = bind_arm(program.behavior, results, settings)
    trajectory = run_irc_program(irc, binding, settings)

    base = hold or DriveSettings.hold(0.0)
    drive = DriveSettings(  # the twin's 0 is where the program starts
        mode="position", target=0.0, stiffness=base.stiffness, damping=base.damping
    )
    stage = build_stage(twin, results, drive, data_dir, collide_unjoined=collide_unjoined)
    native = build_stage(twin, results, drive, data_dir, collide_unjoined=collide_unjoined)
    twin_deg = trajectory.twin_deg()
    for joint_id, angles in zip(trajectory.joint_ids, twin_deg):
        _add_program(_joint_prim(stage, joint_id), program, trajectory.times, angles)
        _add_native(_joint_prim(native, joint_id), trajectory.times, angles)
    _add_provenance(_joint_prim(stage, trajectory.joint_ids[0]), program, trajectory, settings)

    tmp = out_dir.with_name(f".{out_dir.name}.tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    try:
        for name, built in (("program.usdc", stage), ("program_native.usdc", native)):
            path = write_stage(built, tmp / name)
            errors = [i for i in validate_file(path) if i.severity == "error"]
            if errors:
                raise ExportError(f"{name} failed validation: {errors[0].message}")
        shutil.copyfile(RUNNER, tmp / "run_program.py")
        shutil.copyfile(RECORDER, tmp / "record_joints.py")
        _write_text(tmp / "program.json", program.model_dump_json(indent=2))
        _write_text(tmp / "program.xml", program.behavior.spec[PROGRAM_KEY]["xml"])
        _write_text(
            tmp / "trajectory.json",
            trajectory_json(trajectory, settings, binding, twin, drive, collide_unjoined),
        )
        _write_text(
            tmp / "PROGRAM.md",
            arm_program_notes(
                program, irc, twin, binding, trajectory, settings, drive, collide_unjoined
            ),
        )
        tmp.rename(out_dir)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return out_dir, binding, trajectory, settings


def trajectory_json(
    trajectory: ArmTrajectory,
    settings: ArmSettings,
    binding: ArmBinding,
    twin: TwinRecord,
    drive: DriveSettings,
    collide_unjoined: bool,
) -> str:
    twin_deg = trajectory.twin_deg()
    data = {
        "kind": KIND,
        "twin_id": twin.twin_id,
        "settings": settings.model_dump(mode="json"),
        "pose_from": binding.pose_from,
        "joints": [j.model_dump(mode="json") for j in binding.joints],
        "hold": {"stiffness": drive.stiffness, "damping": drive.damping},
        "collide_unjoined": collide_unjoined,
        "duration_s": trajectory.duration_s,
        "twin_deg": dict(zip(trajectory.joint_ids, twin_deg)),
        **trajectory.model_dump(mode="json"),
    }
    return json.dumps(data, indent=2)


def arm_program_notes(
    program: ProgramFile,
    irc: IrcProgram,
    twin: TwinRecord,
    binding: ArmBinding,
    trajectory: ArmTrajectory,
    settings: ArmSettings,
    drive: DriveSettings,
    collide_unjoined: bool,
) -> str:
    """``PROGRAM.md``: what the program is, what it should do, and the check to fill in."""
    behavior = program.behavior
    axes = ", ".join(f"{j.axis} = `{j.joint_id}`" for j in binding.joints)
    poses = ", ".join(f"{j.axis} {j.pose_deg:g}" for j in binding.joints)
    acc = (
        f"{settings.acceleration_deg_s2:.1f} deg/s^2 at Acc 100 %, a stand-in (iRC_ROS's MoveIt "
        "limit, 5.240 rad/s^2; igus publishes none)"
        if settings.acceleration_deg_s2
        else "none: each move starts and stops at full speed"
    )
    lines = [
        f"# Program: {program.name} on {twin.twin_id}",
        "",
        f"- Program: {behavior.name} (`program.xml`, iRC's own format; `program.json`)",
        f"- What it is: {behavior.description}",
        "- Cited: " + "; ".join(c.locator for c in behavior.citations if c.locator),
        f"- Twin: {twin.twin_id} ({twin.status.replace('_', ' ')}); axes {axes}",
        (
            f"- Angles: the program's are iRC's (igus's, from the arm straight up). The twin's 0 "
            f"is its photographed pose, iRC {poses} deg ({binding.pose_from}); the twin's "
            "angle is iRC's minus that (decision 0031)"
        ),
        (
            f"- Speeds: Vel 100 % is {binding.top_speed_deg_s:g} deg/s, the joints' cited top "
            f"speed; override {settings.override_percent:g} %. Acceleration: {acc}. The joint "
            "with the farthest to go sets the time and the others keep pace, so all start and "
            "stop together [INFERENCE, decision 0033]"
        ),
        (
            f"- Simulation: each joint holds with stiffness {drive.stiffness:g} and damping "
            f"{drive.damping:g} (the twin's hold, decision 0032); unjoined parts "
            + ("collide, as in the twin" if collide_unjoined else "do not collide")
        ),
        f"- Duration {trajectory.duration_s:.3f} s; it ends at iRC "
        + ", ".join(f"{v:g}" for v in trajectory.final_irc()),
        (
            f"- Written by moonwalkers {package_version('moonwalkers')} on "
            f"{datetime.now(UTC).isoformat(timespec='seconds')}"
        ),
        "",
        "## Commands, as `program.xml` holds them",
        "",
        "| Nr | Command | "
        + " | ".join(f"{a} (deg)" for a in trajectory.axes)
        + " | Vel % | Acc % | Smooth | Descr |",
        "|---|---|" + "---|" * len(trajectory.axes) + "---|---|---|---|",
    ]
    lines += _command_rows(irc.commands, len(trajectory.axes))
    lines += [
        "",
        "## What it does (the plan)",
        "",
        "| Start (s) | End (s) | Nr | From (iRC deg) | To (iRC deg) | To (twin deg) | What |",
        "|---|---|---|---|---|---|---|",
    ]
    for e in trajectory.events:
        twin_to = [v - p for v, p in zip(e.to_deg, trajectory.pose_deg)]
        lines.append(
            f"| {e.start_s:.3f} | {e.end_s:.3f} | {e.nr} | {_angles(e.from_deg)} | "
            f"{_angles(e.to_deg)} | {_angles(twin_to)} | {e.what} |"
        )
    if trajectory.notes:
        lines += ["", "## Notes", "", *(f"- {n}" for n in trajectory.notes)]
    lines += [
        "",
        "## Check in Isaac Sim (fill in)",
        "",
        "1. Open `program.usdc`. The twin opens in its photographed pose.",
        "2. Window > Script Editor: paste the whole of `run_program.py` and click Run. It prints",
        f"   one line per joint ({len(trajectory.joint_ids)}) and the physics API it uses.",
        "3. To measure: in a second Script Editor tab, paste `record_joints.py` from this",
        "   folder and click Run. It writes `recordings/program_<date>_<time>.csv` here.",
        "4. Press Play. The arm should make the moves above, one after another, every joint of a",
        "   move starting and stopping together, and end where it began. The runner prints a line",
        "   per joint when the program finishes. Stop, then Play, runs it again.",
        "5. Optional: in a new Isaac Sim session, open `program_native.usdc` and press Play",
        "   without the script. It should make the same moves, trailing slightly.",
        "",
        "Then: `uv run python -m moonwalkers.control compare <recording.csv> trajectory.json`.",
        "",
        "- Isaac Sim version/build:",
        "- Runner output (API, first physics step):",
        "- Did the arm follow the plan (moves, order, all joints together)?",
        "- Did any part stop against another (a collision), or pass through one?",
        "- Where did it stop?",
        "- `program_native.usdc` without the script: same moves or not:",
        "- Success level reached (1-3):",
        "- Reviewer notes:",
    ]
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------------------------ helpers
def _command_rows(commands: Sequence[object], axes: int, depth: int = 0) -> list[str]:
    rows, pad = [], "&nbsp;&nbsp;" * depth
    blank = " | ".join([""] * axes)
    for c in commands:
        if isinstance(c, JointMove):
            values = " | ".join(f"{v:g}" for v in c.target_deg)
            rows.append(
                f"| {c.nr} | {pad}Joint | {values} | {c.vel_percent:g} | {c.acc_percent:g} | "
                f"{c.smooth:g} | {c.descr} |"
            )
        elif isinstance(c, Wait):
            rows.append(f"| {c.nr} | {pad}Wait {c.seconds:g} s | {blank} |  |  |  | {c.descr} |")
        elif isinstance(c, Output):
            rows.append(
                f"| {c.nr} | {pad}Output {c.dio} = {c.state} | {blank} |  |  |  | {c.descr} |"
            )
        elif isinstance(c, Loop):
            rows.append(f"| {c.nr} | {pad}Loop (endless) | {blank} |  |  |  | {c.descr} |")
            rows += _command_rows(c.body, axes, depth + 1)
            rows.append(f"|  | {pad}EndLoop | {blank} |  |  |  |  |")
    return rows


def _angles(values: Sequence[float]) -> str:
    return ", ".join(f"{v:.2f}" for v in values)


def _joint_prim(stage: Usd.Stage, joint_id: str) -> Usd.Prim:
    for prim in stage.Traverse():
        data = prim.GetCustomDataByKey("moonwalkers")
        if prim.IsA(UsdPhysics.RevoluteJoint) and data and data.get("joint_id") == joint_id:
            return prim
    raise ExportError(f"the exported twin has no revolute joint '{joint_id}'")


def _add_program(
    prim: Usd.Prim, program: ProgramFile, times: Sequence[float], angles: Sequence[float]
) -> None:
    prim.CreateAttribute(NAME, Sdf.ValueTypeNames.String, custom=True).Set(program.name)
    doubles = Sdf.ValueTypeNames.DoubleArray
    prim.CreateAttribute(TIMES, doubles, custom=True).Set(Vt.DoubleArray(list(times)))
    prim.CreateAttribute(ANGLES, doubles, custom=True).Set(Vt.DoubleArray(list(angles)))
    planned = prim.CreateAttribute(PLANNED, Sdf.ValueTypeNames.Double, custom=True)
    for t, deg in zip(times, angles):
        planned.Set(deg, Usd.TimeCode(t * TIME_CODES_PER_SECOND))
    UsdPhysics.DriveAPI(prim, "angular").CreateTargetVelocityAttr(0.0)
    prim.SetDocumentation(
        f"{prim.GetMetadata('documentation') or ''} Runs iRC program '{program.name}' through "
        "run_program.py (decision 0033).".strip()
    )


def _add_native(prim: Usd.Prim, times: Sequence[float], angles: Sequence[float]) -> None:
    target = UsdPhysics.DriveAPI(prim, "angular").GetTargetPositionAttr()
    for t, deg in zip(times, angles):
        target.Set(deg, Usd.TimeCode(t * TIME_CODES_PER_SECOND))


def _add_provenance(
    prim: Usd.Prim, program: ProgramFile, trajectory: ArmTrajectory, settings: ArmSettings
) -> None:
    behavior = program.behavior
    prim.SetCustomDataByKey(
        "moonwalkers:program",
        {
            "name": program.name,
            "format": "irc_xml",
            "behavior_id": behavior.behavior_id,
            "behavior_name": behavior.name,
            "settings": settings.model_dump_json(),
            "duration_s": trajectory.duration_s,
            "pose_deg": json.dumps(dict(zip(trajectory.joint_ids, trajectory.pose_deg))),
            "citations": json.dumps([c.model_dump(mode="json") for c in behavior.citations]),
            "sources": json.dumps([s.model_dump(mode="json") for s in program.sources]),
        },
    )


def _write_text(path: Path, text: str) -> None:
    path.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8", newline="\n")
