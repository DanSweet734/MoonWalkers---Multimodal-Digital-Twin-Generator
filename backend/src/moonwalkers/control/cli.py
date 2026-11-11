"""Command line for indexing programs (decision 0016). Run from ``backend/``::

    uv run python -m moonwalkers.control list
    uv run python -m moonwalkers.control show PROGRAM [settings]
    uv run python -m moonwalkers.control run PROGRAM --twin haas/ha5c[@v3] [settings]

Manual machines (decision 0025)::

    uv run python -m moonwalkers.control controls --twin grizzly/t33901[@v7] [--file controls.json]
    uv run python -m moonwalkers.control compare RECORDING.csv TRAJECTORY.json

``controls`` writes a controls folder for a stored twin whose result carries an operator's command
set (or from a ``controls.json``), under ``data/machines/<machine>/programs/``; open its
``PROGRAM.md``. ``compare`` measures a joint recording from Isaac Sim against a scenario's plan.

``PROGRAM`` is a packaged program's name (``list`` shows them: the HA5C manual's examples) or a
program file. ``show`` prints what the program does. ``run`` writes a program folder for a stored
twin: by default the version a request would reuse, under
``data/machines/<machine>/programs/<date>_<program>_v<version>/``. Open its ``PROGRAM.md``.
Settings: ``--dwell`` (seconds paused after each step, Parameter 16), ``--absolute`` (``direct``
or ``shortest``), ``--max-feed`` (degrees per second for steps without F), and, from decision
0026, ``--acceleration`` (deg/s^2; 0 for none), ``--relay`` (Parameter 1), ``--step-mode``
(Parameter 10 = 0) and ``--mill-answer`` (seconds the simulated mill takes to send cycle start).

An arm's program in igus Robot Control's XML (decision 0033), such as ``rebel-test-joint-moves``:
``show`` lists its commands, and ``run`` plans it on the twin's joints, with ``--override``
(percent of the robot velocity), ``--acceleration`` (deg/s^2 at Acc 100 %; default the stand-in,
300.2; 0 for none) and ``--loop-passes`` (passes of an endless loop). ``run`` and ``controls``
hold the joints and collide as the stored twin does (its run's spec, decision 0032).
"""

from __future__ import annotations

import argparse
import itertools
import json
import re
import sys
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from moonwalkers.contracts.pipeline_result import TwinRecord
from moonwalkers.kb import JsonKnowledgeBase, KnowledgeBase, validate_machine_key
from moonwalkers.orchestrator import Orchestrator
from moonwalkers.pipelines import default_pipelines
from moonwalkers.usd.exporter import DriveSettings, ExportError
from moonwalkers.workspace import default_data_dir

from .compare import compare, format_measures, read_recording
from .controls_export import controls_files, write_controls_folder
from .export import write_program_folder
from .interpreter import ACCELERATION_STAND_IN, RunSettings, Trajectory, run_program
from .irc import ArmSettings, ArmTrajectory, IrcProgram, JointMove, Loop, Output, Wait
from .manual import ControlsFile
from .program import ProgramError, ProgramFile, packaged_programs

TWIN = re.compile(r"(?P<key>[a-z0-9-]+/[a-z0-9]+)(?:@v(?P<version>[1-9][0-9]*))?")


class UsageError(Exception):
    """The command was given arguments it cannot use."""


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return args.command(args)
    except (UsageError, ProgramError, ExportError, FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m moonwalkers.control", description=__doc__)
    commands = parser.add_subparsers(required=True)
    listing = commands.add_parser("list", help="the packaged programs")
    listing.set_defaults(command=_list)

    for name, func, text in (
        ("show", _show, "print what a program does"),
        ("run", _run, "write a program folder for a stored twin"),
    ):
        command = commands.add_parser(name, help=text)
        command.add_argument("program", help="a packaged program's name, or a program file")
        command.add_argument("--dwell", type=float, default=1.0, help="pause after each step (s)")
        command.add_argument("--absolute", choices=("direct", "shortest"), default="direct")
        command.add_argument("--max-feed", type=float, help="feed rate for steps without F")
        command.add_argument(
            "--acceleration",
            type=float,
            help="HA5C: Parameter 18 as deg/s^2 (default: the stand-in, 540); an iRC program: "
            "deg/s^2 at Acc 100 %% (default: the stand-in, 300.2); 0 for none",
        )
        command.add_argument("--relay", type=int, choices=(0, 1, 2), help="Parameter 1")
        command.add_argument(
            "--step-mode", action="store_true", help="Parameter 10 = 0: wait for cycle start"
        )
        command.add_argument(
            "--mill-answer", type=float, default=1.0, help="seconds the simulated mill takes"
        )
        command.add_argument(
            "--override", type=float, default=100.0, help="iRC: the robot velocity override, %%"
        )
        command.add_argument(
            "--loop-passes", type=int, default=1, help="iRC: passes of an endless loop"
        )
        if name == "run":
            command.add_argument("--twin", required=True, help="machine key[@vN], e.g. haas/ha5c")
            command.add_argument("--data", type=Path, help="the data folder")
            command.add_argument("--out", type=Path, help="the program folder to write")
        command.set_defaults(command=func)

    controls = commands.add_parser("controls", help="write a controls folder for a stored twin")
    controls.add_argument("--twin", required=True, help="machine key[@vN], e.g. grizzly/t33901")
    controls.add_argument("--file", type=Path, help="a controls.json, if the twin has none")
    controls.add_argument("--data", type=Path, help="the data folder")
    controls.add_argument("--out", type=Path, help="the controls folder to write")
    controls.set_defaults(command=_controls)
    measure = commands.add_parser("compare", help="measure a recording against a plan")
    measure.add_argument("recording", type=Path, help="a joint recorder CSV")
    measure.add_argument("trajectory", type=Path, help="a controls folder's trajectory_*.json")
    measure.set_defaults(command=_compare)
    return parser


def _list(args: argparse.Namespace) -> int:
    for name, path in packaged_programs().items():
        print(f"{name}: {ProgramFile.load(path).behavior.name}")
    return 0


def _show(args: argparse.Namespace) -> int:
    program = load_program(args.program)
    if program.is_irc:
        print(format_irc_commands(program))
        print("\nthe timeline needs the twin's joints: run it with --twin")
        return 0
    print(format_trajectory(program, run_program(program.program(), _settings(args))))
    return 0


def _run(args: argparse.Namespace) -> int:
    program = load_program(args.program)
    data_dir = (args.data or default_data_dir()).resolve()
    kb = JsonKnowledgeBase(data_dir / "kb")
    key, twin = _stored_twin(kb, args.twin)
    results = [r for rid in twin.built_from if (r := kb.get_result(rid)) is not None]
    out = args.out or _new_folder(data_dir, key, program.name, twin.version)
    hold, collide = twin_simulation(twin, data_dir)
    output = write_program_folder(
        out,
        program,
        twin,
        results,
        data_dir,
        None if program.is_irc else _settings(args),
        arm_settings=_arm_settings(args) if program.is_irc else None,
        hold=hold,
        collide_unjoined=collide,
    )
    trajectory = output.trajectory
    if isinstance(trajectory, ArmTrajectory):
        print(format_arm_trajectory(program, trajectory))
    else:
        print(format_trajectory(program, trajectory))
    print(f"\nwrote {output.folder} for {twin.twin_id}, joint {output.joint_id}")
    print("next: follow its PROGRAM.md in Isaac Sim (open program.usdc, run run_program.py)")
    return 0


def _controls(args: argparse.Namespace) -> int:
    data_dir = (args.data or default_data_dir()).resolve()
    kb = JsonKnowledgeBase(data_dir / "kb")
    key, twin = _stored_twin(kb, args.twin)
    results = [r for rid in twin.built_from if (r := kb.get_result(rid)) is not None]
    if args.file is not None:
        controls = ControlsFile.load(args.file)
    else:
        found = controls_files(results)
        if len(found) != 1:
            raise UsageError(
                f"{twin.twin_id} carries {len(found)} operator command sets; give --file"
            )
        controls = found[0]
    out = args.out or _new_folder(data_dir, key, controls.name, twin.version)
    hold, collide = twin_simulation(twin, data_dir)
    output = write_controls_folder(out, controls, twin, results, data_dir, hold, collide)
    for name, plan in output.plans.items():
        print(f"{name}: {plan.duration_s:.2f} s, {len(plan.events)} steps; {plan.milestones}")
    print(f"\nwrote {output.folder} for {twin.twin_id}")
    print("next: follow its PROGRAM.md in Isaac Sim (open controls.usdc, run run_controls.py)")
    return 0


def _compare(args: argparse.Namespace) -> int:
    plan = json.loads(Path(args.trajectory).read_text(encoding="utf-8"))
    measures = compare(read_recording(args.recording), plan)
    what = plan.get("scenario") or f"the plan in {args.trajectory.parent.name}"
    print(f"{args.recording.name} against {what} on {plan['twin_id']}")
    print(format_measures(measures))
    return 0


def load_program(name_or_path: str) -> ProgramFile:
    packaged = packaged_programs()
    if name_or_path in packaged:
        return ProgramFile.load(packaged[name_or_path])
    path = Path(name_or_path)
    if not path.is_file():
        raise UsageError(
            f"{name_or_path!r} is neither a packaged program ({', '.join(packaged)}) nor a file"
        )
    return ProgramFile.load(path)


def format_trajectory(program: ProgramFile, trajectory: Trajectory) -> str:
    lines = [f"{program.name}: {program.behavior.name}"]
    for e in trajectory.events:
        lines.append(
            f"  {e.start_s:7.3f}-{e.end_s:7.3f} s  step {e.step:02d} G{e.g}  "
            f"{e.start_deg:8.3f} -> {e.end_deg:8.3f} deg  {e.what}"
        )
    lines.append(
        f"duration {trajectory.duration_s:.3f} s, final target {trajectory.final_deg:.3f} deg"
    )
    lines += [f"note: {n}" for n in trajectory.notes]
    return "\n".join(lines)


def format_irc_commands(program: ProgramFile) -> str:
    irc = IrcProgram.from_behavior(program.behavior)
    lines = [f"{program.name}: {program.behavior.name} (iRC XML)"]

    def add(commands: Sequence[object], pad: str) -> None:
        for c in commands:
            if isinstance(c, JointMove):
                to = ", ".join(f"{v:g}" for v in c.target_deg)
                lines.append(
                    f"{pad}Nr {c.nr:>3}  Joint to [{to}] deg, Vel {c.vel_percent:g} %, "
                    f"Acc {c.acc_percent:g} %  {c.descr}"
                )
            elif isinstance(c, Wait):
                lines.append(f"{pad}Nr {c.nr:>3}  Wait {c.seconds:g} s  {c.descr}")
            elif isinstance(c, Output):
                lines.append(f"{pad}Nr {c.nr:>3}  Output {c.dio} = {c.state}  {c.descr}")
            elif isinstance(c, Loop):
                lines.append(f"{pad}Nr {c.nr:>3}  Loop (endless)  {c.descr}")
                add(c.body, pad + "  ")
                lines.append(f"{pad}       EndLoop")

    add(irc.commands, "  ")
    return "\n".join(lines)


def format_arm_trajectory(program: ProgramFile, trajectory: ArmTrajectory) -> str:
    lines = [f"{program.name}: {program.behavior.name}"]
    for e in trajectory.events:
        to = ", ".join(f"{v:.2f}" for v in e.to_deg)
        lines.append(f"  {e.start_s:7.3f}-{e.end_s:7.3f} s  Nr {e.nr:>3}  to [{to}]  {e.what}")
    pose = ", ".join(f"{a} {p:g}" for a, p in zip(trajectory.axes, trajectory.pose_deg))
    lines.append(f"duration {trajectory.duration_s:.3f} s; the twin's 0 is iRC {pose} deg")
    lines += [f"note: {n}" for n in trajectory.notes]
    return "\n".join(lines)


def twin_simulation(twin: TwinRecord, data_dir: Path) -> tuple[DriveSettings | None, bool]:
    """How the stored twin holds its joints and whether its unjoined parts collide: its run's
    spec (decisions 0032 and 0033), or the defaults when the run has none."""
    from moonwalkers.pipelines.b.build import SPEC_FILE, hold_drive, self_collision

    if twin.usd_path is None:
        return None, False
    run_dir = (data_dir / twin.usd_path).parent
    if not (run_dir / SPEC_FILE).is_file():
        return None, False
    return hold_drive(run_dir), self_collision(run_dir) == "on"


def _arm_settings(args: argparse.Namespace) -> ArmSettings:
    values: dict[str, object] = {
        "override_percent": args.override,
        "loop_passes": args.loop_passes,
    }
    if args.acceleration is not None:
        values["acceleration_deg_s2"] = args.acceleration or None
    try:
        return ArmSettings(**values)  # type: ignore[arg-type]
    except ValueError as exc:
        raise UsageError(str(exc).splitlines()[0]) from exc


def _settings(args: argparse.Namespace) -> RunSettings:
    acceleration = ACCELERATION_STAND_IN if args.acceleration is None else args.acceleration
    values = {
        "step_dwell_s": args.dwell,
        "absolute": args.absolute,
        "acceleration_deg_s2": acceleration or None,
        "relay": args.relay,
        "continue_mode": "step" if args.step_mode else "auto",
        "mill_answer_s": args.mill_answer,
    }
    if args.max_feed is not None:
        values["max_feed_deg_s"] = args.max_feed
    try:
        return RunSettings(**values)
    except ValueError as exc:
        raise UsageError(str(exc).splitlines()[0]) from exc


def _stored_twin(kb: KnowledgeBase, text: str):
    match = TWIN.fullmatch(text)
    if match is None:
        raise UsageError(f"--twin {text!r}: expected a machine key, e.g. haas/ha5c@v3")
    key = validate_machine_key(match["key"])
    return key, _twin(kb, key, int(match["version"]) if match["version"] else None)


def _twin(kb: KnowledgeBase, key: str, version: int | None):
    if version is not None:
        twin = kb.get_twin(key, version)
        if twin is None:
            raise UsageError(f"no twin {key}@v{version} is stored")
        return twin
    twin = Orchestrator(kb, default_pipelines()).reusable_twin(key)
    if twin is None:
        raise UsageError(f"no reusable twin for {key}; give a version (@vN)")
    return twin


def _new_folder(data_dir: Path, key: str, name: str, version: int) -> Path:
    programs = data_dir / "machines" / key.replace("/", "-") / "programs"
    base = f"{datetime.now().astimezone().date().isoformat()}_{name}_v{version}"
    for n in itertools.count(1):
        folder = programs / (base if n == 1 else f"{base}-{n}")
        if not folder.exists():
            return folder
    raise AssertionError("unreachable")
