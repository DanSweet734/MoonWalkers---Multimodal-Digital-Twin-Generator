"""Write the files that run LinkerBot SDK calls on the L20 hand's twin in Isaac Sim (decision
0038), as an arm's program folder does (decision 0033)::

    program.json         the program that was run: its behaviour and the sources it cites
    sdk_calls.py         the calls as a Python script using the SDK would make them (to read;
                         nothing here runs it, and it needs the SDK and the hand)
    trajectory.json      the plan: settings, each joint's targets over time, events and notes
    program.usdc         the twin at its 0 pose, with each driven joint's planned motion
    run_program.py       the runner for Isaac Sim's Script Editor (isaac_runner.py, unchanged)
    record_joints.py     the joint recorder (usd/isaac_recorder.py), for ``control compare``
    program_native.usdc  the same motion as time samples on each drive's own target
    PROGRAM.md           the calls, the timeline, what to check, and room for the result

The 16 driven joints carry the runner's attributes, in the twin's angles (the SDK's minus the
pose's); the 5 followers carry none and move by their mimic coupling, as in the twin. Their
planned angles are in ``trajectory.json``, so ``control compare`` measures them too. The arm's
joints hold where they are. A folder is never overwritten.
"""

from __future__ import annotations

import json
import math
import shutil
from collections.abc import Sequence
from datetime import UTC, datetime
from importlib.metadata import version as package_version
from pathlib import Path

from moonwalkers.contracts.pipeline_result import PipelineResult, TwinRecord
from moonwalkers.usd.exporter import (
    Collisions,
    DriveSettings,
    ExportError,
    build_stage,
    collisions_json,
    write_stage,
)
from moonwalkers.usd.validate import validate_file

from .arm_export import _add_native, _add_program, _joint_prim, _write_text
from .linkerhand import (
    FINGERS,
    FORMAT,
    SLOT_NAMES,
    FingerMove,
    HandBinding,
    HandProgram,
    HandSettings,
    HandTrajectory,
    SetSpeed,
    Sleep,
    bind_hand,
    run_hand_program,
)
from .program import ProgramFile

RUNNER = Path(__file__).with_name("isaac_runner.py")
RECORDER = Path(__file__).parents[1] / "usd" / "isaac_recorder.py"
KIND = "linkerhand_sdk_program"  # trajectory.json's kind, which ``control compare`` reads


def write_hand_program_folder(
    out_dir: Path,
    program: ProgramFile,
    twin: TwinRecord,
    results: Sequence[PipelineResult],
    data_dir: Path,
    settings: HandSettings | None = None,
    hold: DriveSettings | None = None,
    collide_unjoined: bool | Collisions = False,
    hidden_parts: Sequence[str] = (),
) -> tuple[Path, HandBinding, HandTrajectory, HandSettings]:
    """Run the SDK calls of ``program`` on ``twin``'s hand and write the folder ``out_dir``."""
    out_dir = Path(out_dir)
    if out_dir.exists():
        raise ExportError(f"{out_dir} exists; program folders are never overwritten")
    settings = settings or HandSettings()
    calls = HandProgram.from_behavior(program.behavior)
    binding = bind_hand(program.behavior, results, settings)
    trajectory = run_hand_program(calls, binding, settings)

    base = hold or DriveSettings.hold(0.0)
    drive = DriveSettings(  # the twin's 0 is where the program starts
        mode="position", target=0.0, stiffness=base.stiffness, damping=base.damping
    )
    stage = build_stage(
        twin, results, drive, data_dir, collide_unjoined=collide_unjoined, hidden_parts=hidden_parts
    )
    native = build_stage(
        twin, results, drive, data_dir, collide_unjoined=collide_unjoined, hidden_parts=hidden_parts
    )
    for joint, angles in zip(binding.joints, trajectory.twin_deg()):
        if joint.slot is None:
            continue  # a follower: its mimic coupling moves it
        prim = _joint_prim(stage, joint.joint_id)
        _add_program(prim, program, trajectory.times, angles, "LinkerBot SDK calls", "0038")
        _add_native(_joint_prim(native, joint.joint_id), trajectory.times, angles)
    first = _joint_prim(stage, binding.driven()[0].joint_id)
    first.SetCustomDataByKey(
        "moonwalkers:program",
        {
            "name": program.name,
            "format": FORMAT,
            "behavior_id": program.behavior.behavior_id,
            "behavior_name": program.behavior.name,
            "settings": settings.model_dump_json(),
            "duration_s": trajectory.duration_s,
            "pose_deg": json.dumps(dict(zip(trajectory.joint_ids, trajectory.pose_deg))),
            "citations": json.dumps(
                [c.model_dump(mode="json") for c in program.behavior.citations],
                ensure_ascii=False,
            ),
            "sources": json.dumps([s.model_dump(mode="json") for s in program.sources]),
        },
    )

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
        _write_text(tmp / "sdk_calls.py", sdk_calls_script(program, calls))
        _write_text(
            tmp / "trajectory.json",
            trajectory_json(trajectory, settings, binding, twin, drive, collide_unjoined),
        )
        _write_text(
            tmp / "PROGRAM.md",
            hand_program_notes(
                program, calls, twin, binding, trajectory, settings, drive, collide_unjoined
            ),
        )
        tmp.rename(out_dir)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return out_dir, binding, trajectory, settings


def trajectory_json(
    trajectory: HandTrajectory,
    settings: HandSettings,
    binding: HandBinding,
    twin: TwinRecord,
    drive: DriveSettings,
    collide_unjoined: bool | Collisions,
) -> str:
    """The plan, in the keys ``compare_arm`` reads (decision 0033), plus the hand's own."""
    joints = []
    for j in binding.joints:
        joints.append({**j.model_dump(mode="json"), "top_speed_deg_s": _deg(j.top_speed_rad_s)})
    data = {
        "kind": KIND,
        "twin_id": twin.twin_id,
        "settings": settings.model_dump(mode="json"),
        "pose_from": binding.pose_from,
        "joints": joints,
        "hold": {"stiffness": drive.stiffness, "damping": drive.damping},
        "collide_unjoined": collisions_json(collide_unjoined),
        "duration_s": trajectory.duration_s,
        "twin_deg": dict(zip(trajectory.joint_ids, trajectory.twin_deg())),
        **trajectory.model_dump(mode="json"),
    }
    return json.dumps(data, indent=2, ensure_ascii=False)


def sdk_calls_script(program: ProgramFile, calls: HandProgram) -> str:
    """The calls as LinkerBot's Python API takes them (``LinkerHandApi``: ``set_speed``,
    ``finger_move``), with ``time.sleep`` between them. Our own text, for reading."""
    lines = [
        f'"""{program.name}: {program.behavior.name}',
        "",
        "The calls this program folder plans, written as a script using LinkerBot's SDK would",
        "make them (LinkerHandApi in linker_hand_api.py, LinkerBot's ROS 2 SDK, commit 0035f23).",
        "Written by MoonWalkers to be read: nothing here runs it, and it needs the SDK, the hand",
        'and its CAN adapter. Not tried on the real hand."""',
        "",
        "import time",
        "",
        "from LinkerHand.linker_hand_api import LinkerHandApi",
        "",
        f'hand = LinkerHandApi(hand_type="{calls.hand_type}", hand_joint="{calls.hand_joint}")',
    ]
    for call in calls.calls:
        note = f"  # {call.descr}" if call.descr else ""
        if isinstance(call, SetSpeed):
            lines.append(f"hand.set_speed(speed={_ints(call.speed)}){note}")
        elif isinstance(call, FingerMove):
            lines.append(f"hand.finger_move(pose={_ints(call.pose)}){note}")
        elif isinstance(call, Sleep):
            lines.append(f"time.sleep({call.seconds:g}){note}")
    return "\n".join(lines) + "\n"


def hand_program_notes(
    program: ProgramFile,
    calls: HandProgram,
    twin: TwinRecord,
    binding: HandBinding,
    trajectory: HandTrajectory,
    settings: HandSettings,
    drive: DriveSettings,
    collide_unjoined: bool | Collisions,
) -> str:
    """``PROGRAM.md``: what the program is, what it should do, and the check to fill in."""
    behavior = program.behavior
    driven = binding.driven()
    followers = [j for j in binding.joints if j.slot is None]
    posed = [j for j in binding.joints if abs(j.pose_rad) > 1e-9]
    poses = ", ".join(f"`{j.joint_id}` {_deg(j.pose_rad):.2f}" for j in posed) or "none"
    lines = [
        f"# Program: {program.name} on {twin.twin_id}",
        "",
        (
            f"- Program: {behavior.name} (`program.json`; the calls as a script would make "
            "them in `sdk_calls.py`)"
        ),
        f"- What it is: {behavior.description}",
        "- Cited: " + "; ".join(c.locator for c in behavior.citations if c.locator),
        (
            f"- Twin: {twin.twin_id} ({twin.status.replace('_', ' ')}); the hand "
            f"{calls.hand_joint} {calls.hand_type}: {len(driven)} driven joints, "
            f"{len(followers)} following"
        ),
        (
            "- Values: each `finger_move` value (0-255) is an angle in LinkerBot's own L20 model "
            "by `mapping.py`'s range and direction for its slot. The twin's 0 is the "
            f"photographed pose, where the SDK's angle is not 0 for {poses} deg "
            f"({binding.pose_from}); the twin's angle is the SDK's minus that (decision 0031)"
        ),
        (
            f"- Speeds: `set_speed` 255 is {_deg(driven[0].top_speed_rad_s):.2f} deg/s, the "
            "model's joint velocity limit, a stand-in [INFERENCE]; a joint moves at "
            "value / 255 of it, its finger's value (thumb first). Before the first `set_speed`: "
            f"{settings.start_speed:g}. Each joint goes straight to its target on its own, so "
            "a joint with less to go arrives first [INFERENCE, decision 0038]"
        ),
        (
            f"- Simulation: each joint holds with stiffness {drive.stiffness:g} and damping "
            f"{drive.damping:g} (the twin's hold, decision 0032); unjoined parts "
            + ("collide, as in the twin" if collide_unjoined else "do not collide")
            + "; the followers move by their mimic coupling, as in the twin"
        ),
        f"- Duration {trajectory.duration_s:.3f} s",
        (
            f"- Written by moonwalkers {package_version('moonwalkers')} on "
            f"{datetime.now(UTC).isoformat(timespec='seconds')}"
        ),
        "",
        "## The slots and their joints",
        "",
        "| Slot | SDK name | Joint | Twin range (deg) | SDK angle at the twin's 0 (deg) |",
        "|---|---|---|---|---|",
    ]
    for j in binding.joints:
        slot = "" if j.slot is None else str(j.slot)
        name = j.name if j.slot is None else SLOT_NAMES[j.slot]
        lines.append(
            f"| {slot} | {name} | `{j.joint_id}` | {_deg(j.lower_rad):.2f} to "
            f"{_deg(j.upper_rad):.2f} | {_deg(j.pose_rad):.2f} |"
        )
    lines += ["", "## The calls", "", "| Nr | Call | Values | Descr |", "|---|---|---|---|"]
    for call in calls.calls:
        if isinstance(call, SetSpeed):
            pairs = ", ".join(f"{f} {v:g}" for f, v in zip(FINGERS, call.speed))
            lines.append(f"| {call.nr} | set_speed | {pairs} | {call.descr} |")
        elif isinstance(call, FingerMove):
            lines.append(f"| {call.nr} | finger_move | {_ints(call.pose)} | {call.descr} |")
        elif isinstance(call, Sleep):
            lines.append(f"| {call.nr} | sleep | {call.seconds:g} s | {call.descr} |")
    lines += [
        "",
        "## What it does (the plan, the twin's degrees)",
        "",
        "| Start (s) | End (s) | Nr | Call | Moves (twin deg, from > to) | What |",
        "|---|---|---|---|---|---|",
    ]
    for e in trajectory.events:
        moves = [
            f"{jid} {f - p:.1f} > {t - p:.1f}"
            for jid, f, t, p in zip(trajectory.joint_ids, e.from_deg, e.to_deg, trajectory.pose_deg)
            if abs(t - f) > 0.05
        ]
        lines.append(
            f"| {e.start_s:.3f} | {e.end_s:.3f} | {e.nr} | {e.command} | "
            f"{'; '.join(moves) or '-'} | {e.what} |"
        )
    if trajectory.notes:
        lines += ["", "## Notes", "", *(f"- {n}" for n in trajectory.notes)]
    lines += [
        "",
        "## Check in Isaac Sim (fill in)",
        "",
        "1. Open `program.usdc`. The twin opens in its photographed pose.",
        "2. Window > Script Editor: paste the whole of `run_program.py` and click Run. It prints",
        f"   one line per driven joint ({len(driven)}) and the physics API it uses.",
        "3. To measure: in a second Script Editor tab, paste `record_joints.py` from this",
        "   folder and click Run. It writes `recordings/program_<date>_<time>.csv` here.",
        "4. Press Play. The hand should open (the thumb turns out a little and the fingers",
        "   spread), then close into a fist with the thumb across the fingers, hold it, and",
        "   open again; the arm stays still. Stop, then Play, runs it again.",
        "5. Optional: in a new Isaac Sim session, open `program_native.usdc` and press Play",
        "   without the script. It should make the same moves, trailing slightly.",
        "",
        "Then: `uv run python -m moonwalkers.control compare <recording.csv> trajectory.json`.",
        "",
        "- Isaac Sim version/build:",
        "- Runner output (API, first physics step):",
        "- Did the hand open, close into a fist and open again, as planned?",
        "- Did any finger stop against another (a collision), or pass through one?",
        "- Did the followers (each finger's last joint, the thumb's tip) curl with their leader?",
        "- `program_native.usdc` without the script: same moves or not:",
        "- Success level reached (1-3):",
        "- Reviewer notes:",
    ]
    return "\n".join(lines) + "\n"


def _deg(rad: float) -> float:
    return math.degrees(rad)


def _ints(values: Sequence[float]) -> str:
    return "[" + ", ".join(f"{v:g}" for v in values) + "]"
