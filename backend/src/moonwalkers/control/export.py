"""Write the files that run an indexing program on a twin in Isaac Sim (decision 0016).

A program folder holds::

    program.json         the program that was run: its behaviour and the sources it cites
    trajectory.json      the interpreter's output: settings, waypoints, events and notes
    program.usdc         the twin, holding its start angle, with the program on the driven joint
    run_program.py       the runner to load in Isaac Sim's Script Editor (isaac_runner.py)
    program_native.usdc  the same motion as time samples on the drive's own target, which Isaac
                         Sim 6.2.0 follows with no runner (checked on 2026-10-19)
    PROGRAM.md           the steps, the timeline, what to check, and room for the result

On the driven joint, ``program.usdc`` carries ``moonwalkers:program:times`` (seconds) and
``moonwalkers:program:anglesDeg`` (degrees): the runner reads them. A time-sampled
``moonwalkers:program:plannedAngleDeg`` lets a person scrub the plan on the timeline, and
``customData["moonwalkers"]["program"]`` holds the program's provenance. A folder is never
overwritten.
"""

from __future__ import annotations

import json
import math
import shutil
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.metadata import version as package_version
from pathlib import Path

from pxr import Sdf, Usd, UsdPhysics, Vt

from moonwalkers.contracts.pipeline_result import Joint, PipelineResult, TwinRecord
from moonwalkers.usd.exporter import (
    TIME_CODES_PER_SECOND,
    DriveSettings,
    ExportError,
    build_stage,
    write_stage,
)
from moonwalkers.usd.validate import validate_file

from .arm_export import write_arm_program_folder
from .interpreter import RunSettings, Trajectory, run_program
from .irc import ArmSettings, ArmTrajectory
from .isaac_runner import (
    ANGLES,
    CYCLE_START,
    HOLD,
    NAME,
    RELAY,
    RELAY_TIMES,
    TIMES,
    WAIT_HOLDS,
    WAIT_STARTS,
)
from .program import ProgramError, ProgramFile

PLANNED = "moonwalkers:program:plannedAngleDeg"
PLANNED_RELAY = "moonwalkers:program:plannedRelay"  # time samples of the relay, to scrub
GROUP = "MoonWalkers program"
RUNNER = Path(__file__).with_name("isaac_runner.py")


@dataclass(frozen=True)
class ProgramOutput:
    folder: Path
    joint_id: str  # for an arm's iRC program: its joints, comma-separated
    trajectory: Trajectory | ArmTrajectory
    settings: RunSettings | ArmSettings


def write_program_folder(
    out_dir: Path,
    program: ProgramFile,
    twin: TwinRecord,
    results: Sequence[PipelineResult],
    data_dir: Path,
    settings: RunSettings | None = None,
    *,
    arm_settings: ArmSettings | None = None,
    hold: DriveSettings | None = None,
    collide_unjoined: bool = False,
) -> ProgramOutput:
    """Run ``program`` on ``twin``'s driven joint and write the folder ``out_dir``. An iRC
    program for an arm (decision 0033) goes to ``write_arm_program_folder`` with
    ``arm_settings``. ``hold`` is the twin's own drive (decision 0032: its stiffness and damping;
    the target is the program's start), and ``collide_unjoined`` its collisions."""
    out_dir = Path(out_dir)
    if program.is_irc:
        folder, _, arm_trajectory, used = write_arm_program_folder(
            out_dir, program, twin, results, data_dir, arm_settings, hold, collide_unjoined
        )
        return ProgramOutput(folder, ", ".join(arm_trajectory.joint_ids), arm_trajectory, used)
    if out_dir.exists():
        raise ExportError(f"{out_dir} exists; program folders are never overwritten")
    joint = driven_joint(program, results)
    settings = settings or RunSettings()
    if joint.max_velocity is not None:  # the cited top speed caps the feed rates
        settings = settings.model_copy(update={"joint_max_deg_s": math.degrees(joint.max_velocity)})
    trajectory = run_program(program.program(), settings)

    start = math.radians(settings.start_deg)
    if hold is None:
        drive = DriveSettings.hold(start)
    else:
        drive = DriveSettings(
            mode="position", target=start, stiffness=hold.stiffness, damping=hold.damping
        )
    stage = build_stage(twin, results, drive, data_dir, collide_unjoined=collide_unjoined)
    _add_program(_joint_prim(stage, joint.joint_id), program, trajectory, settings)
    native = build_stage(twin, results, drive, data_dir, collide_unjoined=collide_unjoined)
    _add_native(_joint_prim(native, joint.joint_id), trajectory)

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
        _write_text(tmp / "program.json", program.model_dump_json(indent=2))
        _write_text(tmp / "trajectory.json", _trajectory_json(trajectory, settings, joint, twin))
        _write_text(tmp / "PROGRAM.md", program_notes(program, twin, joint, trajectory, settings))
        tmp.rename(out_dir)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return ProgramOutput(out_dir, joint.joint_id, trajectory, settings)


def driven_joint(program: ProgramFile, results: Sequence[PipelineResult]) -> Joint:
    """The twin's revolute joint that the program's behaviour drives."""
    joints = {j.joint_id: j for r in results for j in r.joints if j.joint_type == "revolute"}
    for joint_id in program.behavior.drives_joints:
        if joint_id in joints:
            return joints[joint_id]
    raise ProgramError(
        f"the program drives {program.behavior.drives_joints or 'no joint'}, but the twin's "
        f"revolute joints are {sorted(joints) or 'none'}"
    )


def program_notes(
    program: ProgramFile,
    twin: TwinRecord,
    joint: Joint,
    trajectory: Trajectory,
    settings: RunSettings,
) -> str:
    """``PROGRAM.md``: what the program is, what it should do, and the check to fill in."""
    behavior = program.behavior
    cap = f"{settings.joint_max_deg_s:g} deg/s" if settings.joint_max_deg_s else "not cited"
    lines = [
        f"# Program: {program.name} on {twin.twin_id}",
        "",
        f"- Program: {behavior.name} (`program.json`)",
        "- Cited: " + "; ".join(f"{c.locator}" for c in behavior.citations if c.locator),
        f"- Twin: {twin.twin_id} ({twin.status.replace('_', ' ')}), joint `{joint.joint_id}`",
        (
            f"- Settings: maximum feed rate {settings.max_feed_deg_s:g} deg/s; the joint's cited "
            f"top speed {cap}; pause after each step {settings.step_dwell_s:g} s (Parameter 16, a "
            f"simulation choice); absolute moves {settings.absolute}; start at "
            f"{settings.start_deg:g} deg"
        ),
        (
            f"- Acceleration (Parameter 18): {_acceleration(settings)}. Parameter 1 (the CNC "
            f"relay): {trajectory.relay_parameter}. Parameter 10: "
            + (
                "2, auto continue"
                if settings.continue_mode == "auto"
                else "0, stop after each step and wait for cycle start"
            )
            + f". The simulated mill answers {settings.mill_answer_s:g} s after the controller "
            "starts waiting (a stand-in; decision 0026)"
        ),
        (
            f"- Duration {trajectory.duration_s:.3f} s; final target {trajectory.final_deg:.3f} "
            f"deg ({trajectory.final_deg % 360:.3f} on the dial)"
        ),
        (
            f"- Written by moonwalkers {package_version('moonwalkers')} on "
            f"{datetime.now(UTC).isoformat(timespec='seconds')}"
        ),
        "",
        "## Steps, as the manual prints them",
        "",
        "| Step | Step size (deg) | Feed (deg/s), or Step# for G96 | Loops | G code |",
        "|---|---|---|---|---|",
    ]
    for step in program.program().steps:
        third = f"Step# {step.jump_to}" if step.g == 96 else _num(step.feed_deg_s, "max")
        lines.append(
            f"| {step.number:02d} | {step.step_deg:g} | {third} | {step.loops} | {step.g} |"
        )
    lines += [
        "",
        "## What it does (the interpreter's timeline)",
        "",
        "| Start (s) | End (s) | Step | G | Target from (deg) | To (deg) | What |",
        "|---|---|---|---|---|---|---|",
    ]
    for e in trajectory.events:
        lines.append(
            f"| {e.start_s:.3f} | {e.end_s:.3f} | {e.step:02d} | {e.g} | {e.start_deg:.3f} | "
            f"{e.end_deg:.3f} | {e.what} |"
        )
    lines += ["", "## The CNC relay (the signal to the mill)", ""]
    lines += [f"- closed {s.start_s:.3f}-{s.end_s:.3f} s ({s.why})" for s in trajectory.relay] or [
        "- never closed"
    ]
    if trajectory.waits:
        lines += ["", "## Waits for the mill's cycle start", ""]
        lines += [
            f"- from {w.start_s:.3f} s, step {w.step:02d}: {w.why}; the simulated mill answers "
            f"after {w.hold_s:g} s"
            for w in trajectory.waits
        ]
    if trajectory.notes:
        lines += ["", "## Notes", "", *(f"- {n}" for n in trajectory.notes)]
    lines += [
        "",
        "## Check in Isaac Sim (fill in)",
        "",
        "1. Open `program.usdc`. The orange part is the spindle.",
        "2. Window > Script Editor: paste the whole of `run_program.py` into it and click Run at",
        "   the bottom. It prints the program it found and the physics API it uses.",
        "3. Press Play. The spindle should follow the timeline above, and the runner prints a",
        "   line when the program finishes. Stop, then Play, runs it again.",
        "   The runner also prints each time the CNC relay closes and opens, and shows it in the",
        '   joint\'s "CNC relay (to the mill)" attribute (Property panel, "Raw USD Properties").',
        '   To press Cycle Start yourself, tick "Hold for Cycle Start" on the joint before Play,',
        '   then tick "Cycle Start" at each wait.',
        "4. Optional: in a new Isaac Sim session, open `program_native.usdc` and press Play",
        "   without the script. It should make the same moves (Isaac Sim 6.2.0 did on 2026-10-19).",
        "",
        "- Isaac Sim version/build:",
        "- Runner output (API, first physics step):",
        "- Did the spindle follow the timeline (moves, pauses, return home)?",
        "- Did the moves speed up and slow down, and did the relay close where listed?",
        "- Where did it stop?",
        "- `program_native.usdc` without the script: same moves or not:",
        "- Success level reached (1-3):",
        "- Reviewer notes:",
    ]
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------------------------ helpers
def _joint_prim(stage: Usd.Stage, joint_id: str) -> Usd.Prim:
    for prim in stage.Traverse():
        data = prim.GetCustomDataByKey("moonwalkers")
        if prim.IsA(UsdPhysics.RevoluteJoint) and data and data.get("joint_id") == joint_id:
            return prim
    raise ExportError(f"the exported twin has no revolute joint '{joint_id}'")


def _add_program(
    prim: Usd.Prim, program: ProgramFile, trajectory: Trajectory, settings: RunSettings
) -> None:
    times = Vt.DoubleArray([w.t for w in trajectory.waypoints])
    angles = Vt.DoubleArray([w.deg for w in trajectory.waypoints])
    prim.CreateAttribute(NAME, Sdf.ValueTypeNames.String, custom=True).Set(program.name)
    prim.CreateAttribute(TIMES, Sdf.ValueTypeNames.DoubleArray, custom=True).Set(times)
    prim.CreateAttribute(ANGLES, Sdf.ValueTypeNames.DoubleArray, custom=True).Set(angles)
    planned = prim.CreateAttribute(PLANNED, Sdf.ValueTypeNames.Double, custom=True)
    for w in trajectory.waypoints:
        planned.Set(w.deg, Usd.TimeCode(w.t * TIME_CODES_PER_SECOND))
    _add_signals(prim, trajectory)
    UsdPhysics.DriveAPI(prim, "angular").CreateTargetVelocityAttr(0.0)
    behavior = program.behavior
    prim.SetCustomDataByKey(
        "moonwalkers:program",
        {
            "name": program.name,
            "behavior_id": behavior.behavior_id,
            "behavior_name": behavior.name,
            "steps": json.dumps(program.program().rows()),
            "settings": settings.model_dump_json(),
            "duration_s": trajectory.duration_s,
            "final_deg": trajectory.final_deg,
            "citations": json.dumps([c.model_dump(mode="json") for c in behavior.citations]),
            "sources": json.dumps([s.model_dump(mode="json") for s in program.sources]),
        },
    )
    prim.SetDocumentation(
        f"{prim.GetMetadata('documentation') or ''} Runs program '{program.name}' through "
        "run_program.py (decision 0016).".strip()
    )


def _add_native(prim: Usd.Prim, trajectory: Trajectory) -> None:
    target = UsdPhysics.DriveAPI(prim, "angular").GetTargetPositionAttr()
    for w in trajectory.waypoints:
        target.Set(w.deg, Usd.TimeCode(w.t * TIME_CODES_PER_SECOND))
    _relay_samples(prim, trajectory)


def _add_signals(prim: Usd.Prim, trajectory: Trajectory) -> None:
    """The mill's signals (decision 0026): the relay's spans and the waits for the runner, the
    relay as time samples to scrub, and the Property panel's attributes."""
    doubles = Sdf.ValueTypeNames.DoubleArray
    spans = [v for s in trajectory.relay for v in (s.start_s, s.end_s)]
    prim.CreateAttribute(RELAY_TIMES, doubles, custom=True).Set(Vt.DoubleArray(spans))
    starts = [w.start_s for w in trajectory.waits]
    prim.CreateAttribute(WAIT_STARTS, doubles, custom=True).Set(Vt.DoubleArray(starts))
    holds = [w.hold_s for w in trajectory.waits]
    prim.CreateAttribute(WAIT_HOLDS, doubles, custom=True).Set(Vt.DoubleArray(holds))
    for name, label, doc in (
        (
            HOLD,
            "Hold for Cycle Start",
            "tick before Play to press Cycle Start yourself at each wait",
        ),
        (CYCLE_START, "Cycle Start", "tick at a wait to send cycle start; the runner unticks it"),
        (
            RELAY,
            "CNC relay (to the mill)",
            "closed while the relay signals the mill; set by the runner",
        ),
    ):
        attr = prim.CreateAttribute(name, Sdf.ValueTypeNames.Bool, custom=True)
        attr.Set(False)
        attr.SetDisplayName(label)
        attr.SetDisplayGroup(GROUP)
        attr.SetDocumentation(doc)
    _relay_samples(prim, trajectory)


def _relay_samples(prim: Usd.Prim, trajectory: Trajectory) -> None:
    relay = prim.CreateAttribute(PLANNED_RELAY, Sdf.ValueTypeNames.Bool, custom=True)
    relay.Set(False, Usd.TimeCode(0))
    for span in trajectory.relay:
        relay.Set(True, Usd.TimeCode(span.start_s * TIME_CODES_PER_SECOND))
        relay.Set(False, Usd.TimeCode(span.end_s * TIME_CODES_PER_SECOND))


def _trajectory_json(
    trajectory: Trajectory, settings: RunSettings, joint: Joint, twin: TwinRecord
) -> str:
    data = {
        "twin_id": twin.twin_id,
        "joint_id": joint.joint_id,
        "settings": settings.model_dump(mode="json"),
        "duration_s": trajectory.duration_s,
        "final_deg": trajectory.final_deg,
        **trajectory.model_dump(mode="json"),
    }
    return json.dumps(data, indent=2)


def _acceleration(settings: RunSettings) -> str:
    if settings.acceleration_deg_s2 is None:
        return "none, full feed from start to end (decision 0016)"
    return (
        f"{settings.acceleration_deg_s2:g} deg/s^2, a stand-in: no HA5C value is published, and "
        "the manuals say Parameter 18 is 'usually 2X' Parameter 19 (decision 0026)"
    )


def _num(value: float | None, default: str) -> str:
    return default if value is None else f"{value:g}"


def _write_text(path: Path, text: str) -> None:
    path.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8", newline="\n")
