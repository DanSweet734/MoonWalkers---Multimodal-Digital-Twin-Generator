"""Write the files that let a person operate a manual machine's twin in Isaac Sim (decision 0025).

A controls folder holds::

    controls.usdc                the twin, its spindle on a velocity drive, with a ``Controls``
                                 prim whose attributes the Property panel shows
    run_controls.py              the runner to load in Isaac Sim's Script Editor (isaac_controls.py)
    record_joints.py             the joint recorder (usd/isaac_recorder.py)
    controls.json                the three behaviours and the sources they cite
    trajectory_<scenario>.json   each scenario planned at the physics step, with the quill's
                                 reference response and the numbers ``compare`` measures against
    PROGRAM.md                   the rules, the stand-ins, each scenario's timeline, and the check

Every scenario is planned before any file is written, so one the manual does not allow writes
nothing. A folder is never overwritten.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.metadata import version as package_version
from pathlib import Path
from typing import Any

from pxr import Sdf, Usd, UsdGeom, UsdPhysics, Vt

from moonwalkers.contracts.pipeline_result import Joint, PipelineResult, TwinRecord
from moonwalkers.usd.exporter import (
    DriveSettings,
    ExportError,
    JointSettings,
    build_stage,
    write_stage,
)
from moonwalkers.usd.validate import validate_file

from . import isaac_controls as runner
from .manual import (
    ControlPlan,
    ControlsFile,
    ManualControls,
    controller_spec,
    manual_controls,
    plan_scenario,
)
from .program import ProgramError

CONTROLS_PRIM = "Controls"
CONTROLS_FILE = "controls.usdc"
RUNNER = Path(runner.__file__)
RECORDER = Path(__file__).parents[1] / "usd" / "isaac_recorder.py"
GROUP = "MoonWalkers controls"


@dataclass(frozen=True)
class ControlsOutput:
    folder: Path
    spec: dict[str, Any]
    plans: dict[str, ControlPlan]


def controls_files(results: Sequence[PipelineResult]) -> list[ControlsFile]:
    """A controls file for each operator command set in the results, with the sources its
    behaviours cite (decision 0025)."""
    files = []
    for result in results:
        for controls in manual_controls(result.control):
            cited = {c.source_id for b in controls.behaviors for c in b.citations}
            files.append(
                ControlsFile(
                    name=controls.name,
                    sources=[s for s in result.sources if s.source_id in cited],
                    behaviors=controls.behaviors,
                )
            )
    return files


def write_controls_folder(
    out_dir: Path,
    controls_file: ControlsFile,
    twin: TwinRecord,
    results: Sequence[PipelineResult],
    data_dir: Path,
) -> ControlsOutput:
    """Write the controls folder ``out_dir`` for ``twin``."""
    out_dir = Path(out_dir)
    if out_dir.exists():
        raise ExportError(f"{out_dir} exists; controls folders are never overwritten")
    controls = controls_file.controls()
    joints = {j.joint_id: j for r in results for j in r.joints}
    spindle = controls.speed_spec.joint
    if spindle not in joints:
        raise ProgramError(f"the speed table drives '{spindle}', which the twin does not have")
    settings = {
        spindle: JointSettings(
            drive=DriveSettings.spin(0.0),
            note="a velocity drive that run_controls.py sets on every physics step (decision 0025)",
        )
    }
    stage = build_stage(twin, results, DriveSettings.hold(0.0), data_dir, joint_settings=settings)
    spec = controller_spec(controls, joints, _joint_paths(stage), twin.twin_id)
    plans = {name: plan_scenario(spec, name) for name in spec["scenarios"]}
    _add_controls_prim(stage, controls, controls_file, spec)

    tmp = out_dir.with_name(f".{out_dir.name}.tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    try:
        path = write_stage(stage, tmp / CONTROLS_FILE)
        errors = [i for i in validate_file(path) if i.severity == "error"]
        if errors:
            raise ExportError(f"{CONTROLS_FILE} failed validation: {errors[0].message}")
        shutil.copyfile(RUNNER, tmp / "run_controls.py")
        shutil.copyfile(RECORDER, tmp / "record_joints.py")
        _write_text(tmp / "controls.json", controls_file.model_dump_json(indent=2))
        for name, plan in plans.items():
            data = {
                "twin_id": twin.twin_id,
                "quill": spec["joints"]["quill"],
                "spindle": spec["joints"]["spindle"],
                "followers": _followers(joints, controls.operator_spec.quill),
                **plan.model_dump(mode="json"),
            }
            _write_text(tmp / f"trajectory_{name}.json", json.dumps(data, indent=1))
        _write_text(tmp / "PROGRAM.md", controls_notes(controls, twin, spec, plans))
        tmp.rename(out_dir)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return ControlsOutput(out_dir, spec, plans)


def _joint_paths(stage: Usd.Stage) -> dict[str, str]:
    paths = {}
    for prim in stage.Traverse():
        data = prim.GetCustomDataByKey("moonwalkers")
        if data and "joint_id" in data and prim.IsA(UsdPhysics.Joint):
            paths[data["joint_id"]] = str(prim.GetPath())
    return paths


def _followers(joints: dict[str, Joint], leader: str) -> list[dict[str, Any]]:
    return [
        {"joint_id": j.joint_id, "ratio": j.follows.ratio, "stand_in": j.follows.stand_in}
        for j in joints.values()
        if j.follows is not None and j.follows.leader == leader
    ]


def _add_controls_prim(
    stage: Usd.Stage, controls: ManualControls, controls_file: ControlsFile, spec: dict[str, Any]
) -> None:
    """The ``Controls`` prim: its inputs and outputs in the Property panel, and the runner's
    JSON (hidden there)."""
    root = stage.GetDefaultPrim()
    prim = UsdGeom.Scope.Define(stage, root.GetPath().AppendChild(CONTROLS_PRIM)).GetPrim()
    prim.SetDocumentation(
        "The machine's controls (decision 0025). Select this prim and use the Property panel: "
        "run_controls.py reads the inputs on every physics step and writes the outputs."
    )

    def attr(name: str, kind: Sdf.ValueTypeName, value: Any, label: str, **extra: Any) -> None:
        a = prim.CreateAttribute(runner.PREFIX + name, kind, custom=True)
        a.Set(value)
        a.SetDisplayName(label)
        a.SetDisplayGroup(extra.get("group", GROUP))
        if "tokens" in extra:
            a.SetMetadata("allowedTokens", Vt.TokenArray(extra["tokens"]))
        if "doc" in extra:
            a.SetDocumentation(extra["doc"])
        if extra.get("hidden"):
            a.SetHidden(True)

    tokens = Sdf.ValueTypeNames.Token
    for item in controls.switch_spec.inputs.values():
        attr(item.attribute, Sdf.ValueTypeNames.Bool, False, item.label)
    speeds = [f"{row.rpm:g}" for row in controls.speed_spec.rows]
    attr(
        "speedRpm", tokens, f"{controls.speed_spec.initial_rpm:g}", "Spindle speed (RPM)",
        tokens=speeds, doc=controls.speed_spec.table_why,
    )  # fmt: skip
    attr("pullHandles", Sdf.ValueTypeNames.Bool, False, "Pull the downfeed handles")
    attr(
        "pullSpeedMmS", Sdf.ValueTypeNames.Double,
        controls.operator_spec.live_pull_speed_m_s * 1000.0, "Pull speed (mm/s)",
    )  # fmt: skip
    scenarios = [*controls.operator_spec.scenarios, runner.LIVE]
    attr(
        "scenario", tokens, controls.operator_spec.default_scenario, "Scenario on Play",
        tokens=scenarios, doc="what plays when Play is pressed; 'live' starts with the panel",
    )  # fmt: skip
    out = f"{GROUP}: set by run_controls.py"
    attr("motorOn", Sdf.ValueTypeNames.Bool, False, "Motor running", group=out)
    attr("spindleRpmCommanded", Sdf.ValueTypeNames.Double, 0.0, "Spindle RPM commanded", group=out)
    attr("status", Sdf.ValueTypeNames.String, "", "Last message", group=out)
    attr("spec", Sdf.ValueTypeNames.String, json.dumps(spec), "Controls (JSON)", hidden=True)
    prim.SetCustomDataByKey(
        "moonwalkers",
        {
            "behavior_ids": json.dumps([b.behavior_id for b in controls.behaviors]),
            "citations": json.dumps(
                {
                    b.behavior_id: [c.model_dump(mode="json") for c in b.citations]
                    for b in controls.behaviors
                }
            ),
            "sources": json.dumps([s.model_dump(mode="json") for s in controls_file.sources]),
        },
    )


def controls_notes(
    controls: ManualControls,
    twin: TwinRecord,
    spec: dict[str, Any],
    plans: dict[str, ControlPlan],
) -> str:
    """``PROGRAM.md``: the rules, the stand-ins, each scenario's timeline, and the check."""
    quill, spindle = spec["joints"]["quill"], spec["joints"]["spindle"]
    switch, speed, op = controls.switch_spec, controls.speed_spec, controls.operator_spec
    lines = [
        f"# Controls: {controls.name} on {twin.twin_id}",
        "",
        (
            f"- Twin: {twin.twin_id} ({twin.status.replace('_', ' ')}); the operator's hand "
            f"drives `{quill['joint_id']}`, the speed table `{spindle['joint_id']}` "
            "(decision 0025)"
        ),
        *(
            f"- `{b.behavior_id}` ({b.kind}): {b.name}. Cited: "
            + "; ".join(c.locator or c.source_id for c in b.citations)
            for b in controls.behaviors
        ),
        (
            f"- Written by moonwalkers {package_version('moonwalkers')} on "
            f"{datetime.now(UTC).isoformat(timespec='seconds')}"
        ),
        "",
        "## The rules",
        "",
        "- The motor runs only when "
        + ", ".join(f"{name} is {state}" for name, state in switch.on_when.items())
        + ". Otherwise: "
        + "; ".join(switch.off_why.values()),
        (
            f"- Speeds (RPM): {', '.join(f'{r.rpm:g}' for r in speed.rows)}: {speed.table_why}. "
            f"Changed only when {_states(speed.change_only_when)}: {speed.change_refused_why}"
        ),
        f"- Pulling the handles: {op.commands.get('pull', '')}. Releasing: {op.release_why}",
        f"- The depth stop: {quill['stop_m'] * 1000:.1f} mm of quill travel.",
        "- Not described by the manual, so refused in a scenario and done with a note in live use:",
        *(f"  - {case.why}" for case in switch.not_described),
        "",
        "## Stand-ins and simulation choices",
        "",
        *(f"- `{k}`: {v}" for k, v in {**speed.stand_ins, **op.stand_ins}.items()),
        (
            f"- The spindle comes up to speed over {speed.run_up_s:g} s and coasts down over "
            f"{speed.coast_down_s:g} s, in straight lines."
        ),
        (
            f"- The quill keeps its spring drive (stiffness {quill['stiffness']:g}, damping "
            f"{quill['damping']:g}, aimed {abs(quill['spring_target_m']) * 1000:.0f} mm above "
            "the top; decision 0018). The hand moves that drive's target: it aims "
            f"{quill['gravity_offset_m'] * 1000:.1f} mm short of where it holds the quill, the "
            "sag under gravity (9.81 / stiffness), and presses "
            f"{quill['press_past_m'] * 1000:.0f} mm past the depth stop when it reaches it."
        ),
        "- The hand is ideal: it follows its path whatever the spring and the handles push back.",
    ]
    for name, plan in plans.items():
        scenario = op.scenarios[name]
        m = plan.milestones
        lines += [
            "",
            f"## Scenario `{name}` (`trajectory_{name}.json`)",
            "",
            scenario.description,
            "",
            "| t (s) | Step | Does | Says | Why |",
            "|---|---|---|---|---|",
        ]
        for e in plan.events:
            said = "; ".join(e.said).replace("|", "/")
            lines.append(
                f"| {e.t:.2f} | {e.step} | {e.do} | {said} | {(e.note or '').replace('|', '/')} |"
            )
        lines += [
            "",
            f"Planned: {plan.duration_s:.2f} s; spindle up to {m.get('top_rpm') or 0:g} RPM"
            + (f" from t = {m['motor_on_s']:.2f} s" if m.get("motor_on_s") is not None else "")
            + (f", off at t = {m['motor_off_s']:.2f} s" if m.get("motor_off_s") is not None else "")
            + "."
            + _quill_line(m),
        ]
    lines += [
        "",
        "## Check in Isaac Sim (fill in)",
        "",
        f"1. Open `{CONTROLS_FILE}`.",
        "2. Window > Script Editor: paste the whole of `record_joints.py` and click Run, then",
        "   paste the whole of `run_controls.py` and click Run. Each prints what it found.",
        "3. Select the `Controls` prim under the twin (Stage window). In the Property panel, under",
        f'   "{GROUP}", set "Scenario on Play" (default `{op.default_scenario}`).',
        "4. Press Play. The scenario's steps print in the console and show in the panel. When it",
        '   ends, the panel\'s controls are live: tick "Plugged in", "Disabling key in" and',
        '   "ON/OFF paddle up"; choose a speed (only while unplugged); tick "Pull the downfeed',
        '   handles" and untick it to release. Stop, then Play, starts again.',
        (
            "5. Measure a recording: `uv run python -m moonwalkers.control compare "
            "<recordings/...csv> <this folder>/trajectory_<scenario>.json`."
        ),
        "",
        "- Isaac Sim version/build:",
        "- Runner and recorder output:",
        *(f"- `{name}`: what happened, and the recording:" for name in plans),
        "- Live controls in the Property panel (check boxes, the speed list, refusals):",
        "- Success level reached (1-3):",
        "- Reviewer notes:",
    ]
    return "\n".join(lines) + "\n"


def _states(states: dict[str, str]) -> str:
    return ", ".join(f"{name} is {state}" for name, state in states.items())


def _quill_line(m: dict[str, Any]) -> str:
    if m.get("quill_at_stop_s") is None:
        return ""
    line = f" The quill reaches the stop at t = {m['quill_at_stop_s']:.2f} s"
    if m.get("released_s") is not None:
        line += f", is released at {m['released_s']:.2f} s"
    if m.get("quill_home_s") is not None:
        line += (
            f" and is home by {m['quill_home_s']:.2f} s in the reference response, which leaves "
            "out the handles' inertia (v3-v6 bounced for 3.4-5.7 s, decision 0024)"
        )
    return line + "."


def _write_text(path: Path, text: str) -> None:
    path.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8", newline="\n")
