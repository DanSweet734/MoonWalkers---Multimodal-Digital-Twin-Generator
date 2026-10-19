"""Write the files that run an indexing program on a twin in Isaac Sim (decision 0016).

A program folder holds::

    program.json         the program that was run: its behaviour and the sources it cites
    trajectory.json      the interpreter's output: settings, waypoints, events and notes
    program.usdc         the twin, holding its start angle, with the program on the driven joint
    run_program.py       the runner to load in Isaac Sim's Script Editor (isaac_runner.py)
    program_native.usdc  the same motion as time samples on the drive's own target: a test of
                         whether Isaac Sim follows them with no runner
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

from .interpreter import RunSettings, Trajectory, run_program
from .isaac_runner import ANGLES, NAME, TIMES
from .program import ProgramError, ProgramFile

PLANNED = "moonwalkers:program:plannedAngleDeg"
RUNNER = Path(__file__).with_name("isaac_runner.py")


@dataclass(frozen=True)
class ProgramOutput:
    folder: Path
    joint_id: str
    trajectory: Trajectory
    settings: RunSettings


def write_program_folder(
    out_dir: Path,
    program: ProgramFile,
    twin: TwinRecord,
    results: Sequence[PipelineResult],
    data_dir: Path,
    settings: RunSettings | None = None,
) -> ProgramOutput:
    """Run ``program`` on ``twin``'s driven joint and write the folder ``out_dir``."""
    out_dir = Path(out_dir)
    if out_dir.exists():
        raise ExportError(f"{out_dir} exists; program folders are never overwritten")
    joint = driven_joint(program, results)
    settings = settings or RunSettings()
    if joint.max_velocity is not None:  # the cited top speed caps the feed rates
        settings = settings.model_copy(update={"joint_max_deg_s": math.degrees(joint.max_velocity)})
    trajectory = run_program(program.program(), settings)

    hold = DriveSettings.hold(math.radians(settings.start_deg))
    stage = build_stage(twin, results, hold, data_dir)
    _add_program(_joint_prim(stage, joint.joint_id), program, trajectory, settings)
    native = build_stage(twin, results, hold, data_dir)
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
    if trajectory.notes:
        lines += ["", "## Notes", "", *(f"- {n}" for n in trajectory.notes)]
    lines += [
        "",
        "## Check in Isaac Sim (fill in)",
        "",
        "1. Open `program.usdc`. The orange part is the spindle.",
        "2. Window > Script Editor: open `run_program.py` and press Run. It prints the program it",
        "   found and the physics API it uses.",
        "3. Press Play. The spindle should follow the timeline above, and the runner prints a",
        "   line when the program finishes. Stop, then Play, runs it again.",
        "4. Optional: open `program_native.usdc` and press Play with no runner. Does it move?",
        "",
        "- Isaac Sim version/build:",
        "- Runner output (API, first physics step):",
        "- Did the spindle follow the timeline (moves, pauses, return home)?",
        "- Where did it stop?",
        "- `program_native.usdc` without the runner: moves or not:",
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


def _num(value: float | None, default: str) -> str:
    return default if value is None else f"{value:g}"


def _write_text(path: Path, text: str) -> None:
    path.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8", newline="\n")
