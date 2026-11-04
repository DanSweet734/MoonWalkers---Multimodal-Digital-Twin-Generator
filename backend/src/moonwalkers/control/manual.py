"""A manual machine's controls: its switch, its speed table and the operator's commands
(decision 0025).

Three ``ControlBehavior``s describe them, each with its own ``spec``:

- a ``state_machine`` (``SwitchSpec``): the switch's inputs, when the motor runs, and the changes
  the manual does not describe;
- a ``lookup_table`` (``SpeedSpec``): the speed settings, when they may change, and how the
  spindle comes up to speed and coasts down;
- a ``command_set`` (``OperatorSpec``): the operator's commands and named scenarios that use them,
  naming the other two behaviours and the joint the hand drives.

The rules run in ``isaac_controls.Controller``, the same code Isaac Sim runs on every physics
step, so a scenario is planned and checked here first (``plan_scenario``). The quill's response is
predicted with the drive the exporter writes (``predict_quill``): a check, not a simulation of
the machine.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from moonwalkers.contracts.pipeline_result import ControlBehavior, Joint, Source
from moonwalkers.usd.exporter import SPRING_PRELOAD, simulated_settings, stopped_limits

from .isaac_controls import LIVE, Controller, Refused, ScenarioPlayer
from .program import ProgramError

SCENARIOS_KEY = "scenarios"
GRAVITY = 9.81  # m/s^2: the stage's default, earth gravity (decision 0018 balances against it)
PLAN_STEP_S = 1 / 60  # Isaac Sim's physics step (decision 0016: first step at t = 0.017 s)
NAME = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
ATTRIBUTE = r"^[a-z][A-Za-z0-9]*$"


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ------------------------------------------------------------------------------------ specs
class SwitchInput(_Model):
    states: tuple[str, str] = Field(description="off, then on: the panel shows a check box")
    attribute: str = Field(pattern=ATTRIBUTE, description="its name in the Property panel")
    label: str


class NotDescribed(_Model):
    """A change the manual does not describe: refused in a scenario."""

    input: str
    to: str
    when: dict[str, str] = Field(default_factory=dict, description="other inputs, or 'motor'")
    why: str


class SwitchSpec(_Model):
    inputs: dict[str, SwitchInput] = Field(min_length=1)
    output: str = "motor"
    on_when: dict[str, str] = Field(min_length=1)
    start_input: str = Field(description="the input a person moves to start the motor")
    off_why: dict[str, str] = Field(description="on_when input -> why the motor stays off")
    not_described: list[NotDescribed] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check(self) -> SwitchSpec:
        def check(name: str, state: str, where: str) -> None:
            if name not in self.inputs:
                raise ValueError(f"{where}: the switch has no input '{name}'")
            if state not in self.inputs[name].states:
                raise ValueError(f"{where}: '{name}' has no state '{state}'")

        for name, state in self.on_when.items():
            check(name, state, "on_when")
        if self.start_input not in self.inputs:
            raise ValueError(f"start_input: the switch has no input '{self.start_input}'")
        if unexplained := sorted(set(self.on_when) - set(self.off_why) - {self.start_input}):
            raise ValueError(f"off_why: say why the motor stays off without {unexplained}")
        for case in self.not_described:
            check(case.input, case.to, "not_described")
            for name, state in case.when.items():
                if name == self.output:
                    if state not in ("on", "off"):
                        raise ValueError(f"not_described: '{self.output}' is 'on' or 'off'")
                else:
                    check(name, state, "not_described")
        return self


class SpeedRow(_Model):
    rpm: float = Field(gt=0)
    belts: str | None = None


class SpeedSpec(_Model):
    joint: str
    switch: str = Field(description="the switch behaviour whose inputs change_only_when names")
    rows: list[SpeedRow] = Field(min_length=1)
    initial_rpm: float
    table_why: str
    change_only_when: dict[str, str] = Field(default_factory=dict)
    change_refused_why: str
    run_up_s: float = Field(gt=0)
    coast_down_s: float = Field(gt=0)
    direction: Literal[1, -1] = 1
    stand_ins: dict[str, str] = Field(default_factory=dict, description="value -> why")

    @model_validator(mode="after")
    def _check(self) -> SpeedSpec:
        speeds = [row.rpm for row in self.rows]
        if len(set(speeds)) != len(speeds):
            raise ValueError("the speed table lists a speed twice")
        if self.initial_rpm not in speeds:
            raise ValueError(f"initial_rpm {self.initial_rpm:g} is not in the table")
        return self


class Step(_Model):
    do: Literal["wait", "set", "set_speed", "pull", "release"]
    s: float | None = Field(default=None, gt=0)
    input: str | None = None
    state: str | None = None
    rpm: float | None = None
    speed_m_s: float | None = Field(default=None, gt=0)
    to_m: float | None = Field(default=None, ge=0)
    note: str | None = None

    @model_validator(mode="after")
    def _check(self) -> Step:
        needs = {
            "wait": {"s"},
            "set": {"input", "state"},
            "set_speed": {"rpm"},
            "pull": {"speed_m_s"},
            "release": set(),
        }[self.do]
        given = {k for k in ("s", "input", "state", "rpm", "speed_m_s", "to_m") if getattr(self, k)}
        if self.to_m == 0.0:
            given.add("to_m")
        missing = needs - given
        extra = given - needs - ({"to_m"} if self.do == "pull" else set())
        if missing or extra:
            raise ValueError(
                f"a '{self.do}' step takes {sorted(needs) or 'nothing'}"
                + (" (and to_m)" if self.do == "pull" else "")
                + f"; got {sorted(given) or 'nothing'}"
            )
        return self

    def as_runner(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)


class Scenario(_Model):
    description: str
    steps: list[Step] = Field(min_length=1)


class OperatorSpec(_Model):
    switch: str = Field(description="the switch behaviour's id")
    speed: str = Field(description="the speed table behaviour's id")
    quill: str = Field(description="the joint the operator's hand drives")
    commands: dict[str, str] = Field(min_length=1, description="step kind -> what the manual says")
    release_why: str
    live_pull_speed_m_s: float = Field(gt=0)
    scenarios: dict[str, Scenario] = Field(min_length=1)
    default_scenario: str
    stand_ins: dict[str, str] = Field(default_factory=dict, description="value -> why")

    @model_validator(mode="after")
    def _check(self) -> OperatorSpec:
        for name, scenario in self.scenarios.items():
            if name == LIVE or not re.fullmatch(NAME, name):
                raise ValueError(
                    f"scenario name '{name}': lowercase words joined by '-', not 'live'"
                )
            for number, step in enumerate(scenario.steps, start=1):
                if step.do != "wait" and step.do not in self.commands:
                    raise ValueError(f"{name}, step {number}: '{step.do}' is not in commands")
        if self.default_scenario not in self.scenarios:
            raise ValueError(f"default_scenario '{self.default_scenario}' is not a scenario")
        return self


# ------------------------------------------------------------------------- the three together
@dataclass(frozen=True)
class ManualControls:
    """An operator's command set with the switch and speed table it names."""

    operator: ControlBehavior
    switch: ControlBehavior
    speed: ControlBehavior
    operator_spec: OperatorSpec
    switch_spec: SwitchSpec
    speed_spec: SpeedSpec

    @property
    def name(self) -> str:
        return self.operator.behavior_id.lower().replace("_", "-")

    @property
    def behaviors(self) -> list[ControlBehavior]:
        return [self.switch, self.speed, self.operator]


def is_operator(behavior: ControlBehavior) -> bool:
    return behavior.kind == "command_set" and SCENARIOS_KEY in behavior.spec


def manual_controls(control: Sequence[ControlBehavior]) -> list[ManualControls]:
    """Every operator command set among ``control``, with its switch and speed table."""
    by_id = {b.behavior_id: b for b in control}
    found = []
    for operator in (b for b in control if is_operator(b)):
        operator_spec = _parse(OperatorSpec, operator)
        switch = _named(by_id, operator_spec.switch, "state_machine", operator)
        speed = _named(by_id, operator_spec.speed, "lookup_table", operator)
        switch_spec = _parse(SwitchSpec, switch)
        speed_spec = _parse(SpeedSpec, speed)
        if speed_spec.switch != switch.behavior_id:
            raise ProgramError(
                f"{speed.behavior_id} names the switch '{speed_spec.switch}', but "
                f"{operator.behavior_id} uses '{switch.behavior_id}'"
            )
        for name, state in speed_spec.change_only_when.items():
            if name not in switch_spec.inputs or state not in switch_spec.inputs[name].states:
                raise ProgramError(
                    f"{speed.behavior_id}: change_only_when {name}={state} is unknown"
                )
        found.append(
            ManualControls(operator, switch, speed, operator_spec, switch_spec, speed_spec)
        )
    return found


def check_behavior(behavior: ControlBehavior, control: Sequence[ControlBehavior] = ()) -> None:
    """Refuse a manual-control spec that cannot be read (the agent's ``add_control``). A switch or
    speed table is checked alone; a command set also with the behaviours it names, if given."""
    if behavior.kind == "state_machine" and "on_when" in behavior.spec:
        _parse(SwitchSpec, behavior)
    elif behavior.kind == "lookup_table" and "rows" in behavior.spec:
        _parse(SpeedSpec, behavior)
    elif is_operator(behavior):
        spec = _parse(OperatorSpec, behavior)
        others = {b.behavior_id for b in control}
        if {spec.switch, spec.speed} <= others:
            manual_controls([*control, behavior])


def _named(
    by_id: Mapping[str, ControlBehavior], behavior_id: str, kind: str, user: ControlBehavior
) -> ControlBehavior:
    behavior = by_id.get(behavior_id)
    if behavior is None or behavior.kind != kind:
        raise ProgramError(f"{user.behavior_id} names '{behavior_id}', which is not a {kind}")
    return behavior


def _parse[M: BaseModel](model: type[M], behavior: ControlBehavior) -> M:
    try:
        return model.model_validate(behavior.spec)
    except ValidationError as exc:
        error = exc.errors()[0]
        field = ".".join(str(part) for part in error["loc"])
        message = str(error["msg"]).removeprefix("Value error, ")
        where = f"{field}: " if field else ""
        raise ProgramError(f"behaviour {behavior.behavior_id}: {where}{message}") from exc


# ------------------------------------------------------------------- the runner's JSON
def controller_spec(
    controls: ManualControls,
    joints: Mapping[str, Joint],
    paths: Mapping[str, str],
    machine: str,
) -> dict[str, Any]:
    """The JSON the stage carries for ``isaac_controls``: the three specs, and the quill and
    spindle joints with what the exporter writes for them (decisions 0018, 0020, 0025).

    The hand moves the drive that carries the quill's spring. That is the quill's own drive, or,
    when a turning joint follows the quill, that joint's (``springs_on_pinions``). The controller
    works in metres of quill travel either way; ``drive`` maps them to the drive's own units
    (metres, or degrees: ``scale`` x metres + ``offset``)."""
    op, speed = controls.operator_spec, controls.speed_spec
    quill = joints.get(op.quill)
    spindle = joints.get(speed.joint)
    if quill is None or quill.joint_type != "prismatic":
        raise ProgramError(
            f"the hand drives '{op.quill}', which is not a sliding joint of the twin"
        )
    if spindle is None or spindle.joint_type != "revolute":
        raise ProgramError(f"the speed table drives '{speed.joint}', not a turning joint")
    if quill.mode is None or quill.mode.kind != "spring_return":
        raise ProgramError(f"'{quill.joint_id}' has no spring to return it when released")
    lower, stop = stopped_limits(quill)
    if stop is None:
        raise ProgramError(f"'{quill.joint_id}' has no stop or limit at the end of its travel")
    hand = _hand_drive(quill, joints, paths)
    switch = controls.switch_spec.model_dump()
    return {
        "machine": machine,
        "switch": switch,
        "speed": {
            **speed.model_dump(exclude={"stand_ins"}),
            "rows": [r.model_dump(exclude_none=True) for r in speed.rows],
        },
        "hand": {
            "live_pull_speed_m_s": op.live_pull_speed_m_s,
            "release_why": op.release_why,
        },
        "joints": {
            "quill": {
                "joint_id": quill.joint_id,
                "path": paths[quill.joint_id],
                "rest_m": quill.mode.position or 0.0,
                "lower_m": lower if lower is not None else 0.0,
                "stop_m": stop,
                **hand,
            },
            "spindle": {"joint_id": spindle.joint_id, "path": paths[spindle.joint_id]},
        },
        "scenarios": {
            name: {
                "description": s.description,
                "steps": [step.as_runner() for step in s.steps],
            }
            for name, s in op.scenarios.items()
        },
        "default_scenario": op.default_scenario,
    }


def _hand_drive(
    quill: Joint, joints: Mapping[str, Joint], paths: Mapping[str, str]
) -> dict[str, Any]:
    """The drive the hand moves, in metres of quill travel: its spring's target, gains, how far
    it presses past the stop and how far short of the hand it aims against gravity."""
    settings = simulated_settings(joints)
    own = settings[quill.joint_id].drive
    if own is not None:  # the spring is on the quill itself
        down = -quill.axis[2] / math.sqrt(sum(c * c for c in quill.axis))
        return {
            "drive": {
                "joint_id": quill.joint_id,
                "path": paths[quill.joint_id],
                "kind": "linear",
                "scale": 1.0,
                "offset": 0.0,
            },
            "spring_target_m": own.target,
            "stiffness": own.stiffness,
            "damping": own.damping,
            "press_past_m": SPRING_PRELOAD,
            "gravity_offset_m": GRAVITY * down / own.stiffness,
        }
    (pinion_id,) = [
        j
        for j, s in settings.items()
        if s.drive is not None and s.coupling is not None and s.coupling.leader == quill.joint_id
    ]
    pinion = settings[pinion_id]
    assert pinion.drive is not None and pinion.coupling is not None
    ratio, offset = pinion.coupling.ratio, pinion.coupling.offset
    return {
        "drive": {
            "joint_id": pinion_id,
            "path": paths[pinion_id],
            "kind": "angular",
            "scale": math.degrees(ratio),
            "offset": math.degrees(offset),
        },
        "spring_target_m": (pinion.drive.target - offset) / ratio,
        "stiffness": pinion.drive.stiffness,
        "damping": pinion.drive.damping,
        "press_past_m": SPRING_PRELOAD / abs(ratio),
        # [INFERENCE] The quill's weight barely turns the pinion: on the T33901's v7 hulls it
        # sags 0.0075 rad, 0.13 mm of travel (decision 0025, update), so the hand aims at itself.
        "gravity_offset_m": 0.0,
    }


# --------------------------------------------------------------------------------- planning
class PlanEvent(BaseModel):
    t: float
    step: int
    do: str
    note: str | None = None
    said: list[str]


class ControlPlan(BaseModel):
    """A scenario run through the controller at the physics step, outside Isaac Sim."""

    scenario: str
    description: str
    dt: float
    times: list[float]
    quill_target_m: list[float]
    quill_velocity_m_s: list[float]
    spindle_deg_s: list[float]
    rpm: list[float]
    motor_on: list[bool]
    predicted_quill_m: list[float] = Field(default_factory=list)
    events: list[PlanEvent]
    milestones: dict[str, float | None] = Field(default_factory=dict)

    @property
    def duration_s(self) -> float:
        return self.times[-1]


def plan_scenario(spec: Mapping[str, Any], name: str, dt: float = PLAN_STEP_S) -> ControlPlan:
    """Play scenario ``name`` of the runner's JSON ``spec`` at steps of ``dt`` seconds. A step the
    manual does not allow is refused (``ProgramError``), with the step's number."""
    scenario = spec["scenarios"][name]
    controller = Controller(dict(spec))
    player = ScenarioPlayer(controller, scenario["steps"], strict=True)
    columns: dict[str, list[Any]] = {
        k: [] for k in ("times", "quill_target_m", "quill_velocity_m_s", "spindle_deg_s", "rpm")
    }
    motor: list[bool] = []
    events: list[PlanEvent] = []
    k = 0
    while True:
        t = k * dt
        try:
            ran = player.advance(t)
        except Refused as exc:
            raise ProgramError(f"scenario '{name}': {exc}") from exc
        for number, start, step, said in ran:
            events.append(
                PlanEvent(t=start, step=number, do=step["do"], note=step.get("note"), said=said)
            )
        targets = controller.step(dt if k else 0.0)
        columns["times"].append(t)
        columns["quill_target_m"].append(targets["quill_target_m"])
        columns["quill_velocity_m_s"].append(targets["quill_velocity_m_s"])
        columns["spindle_deg_s"].append(targets["spindle_deg_s"])
        columns["rpm"].append(targets["rpm"])
        motor.append(targets["motor_on"])
        if player.done and t >= player.next_t - 1e-9:
            break
        k += 1
        if k > 100_000:
            raise ProgramError(f"scenario '{name}' runs longer than {100_000 * dt:.0f} s")
    plan = ControlPlan(
        scenario=name,
        description=scenario["description"],
        dt=dt,
        motor_on=motor,
        events=events,
        **columns,
    )
    plan.predicted_quill_m = predict_quill(plan, spec["joints"]["quill"])
    plan.milestones = milestones(plan, spec)
    return plan


def predict_quill(plan: ControlPlan, quill: Mapping[str, Any], substeps: int = 10) -> list[float]:
    """The quill under its drive, as the exporter writes it: an acceleration drive,
    ``k (target - x) + c (target velocity - v)``, plus gravity along the joint, stopped by its
    limits. It leaves out the handles, whose inertia the link adds (the bounces of decision 0024,
    update), so it is a reference to measure a recording against, not a prediction of it."""
    k, c = quill["stiffness"], quill["damping"]
    g = quill["gravity_offset_m"] * k  # gravity along the joint, m/s^2
    lower, upper = quill["lower_m"], quill["stop_m"]
    x, v = quill["rest_m"], 0.0
    out = []
    h = plan.dt / substeps
    for target, target_v in zip(plan.quill_target_m, plan.quill_velocity_m_s, strict=True):
        out.append(x)
        for _ in range(substeps):
            v += (k * (target - x) + c * (target_v - v) + g) * h
            x += v * h
            if x < lower:
                x, v = lower, max(v, 0.0)
            elif x > upper:
                x, v = upper, min(v, 0.0)
    return out


def milestones(plan: ControlPlan, spec: Mapping[str, Any]) -> dict[str, float | None]:
    """When the predicted quill reaches the stop and returns home, and how fast the spindle runs:
    the numbers ``compare`` measures a recording against."""
    quill = spec["joints"]["quill"]
    stop, rest = quill["stop_m"], quill["rest_m"]
    x, times = plan.predicted_quill_m, plan.times
    released = next((e.t for e in plan.events if e.do == "release"), None)
    at_stop = next((t for t, q in zip(times, x, strict=True) if q >= stop - 0.0005), None)
    home = None
    if released is not None:
        home = next(
            (t for t, q in zip(times, x, strict=True) if t > released and q <= rest + 0.001), None
        )
    on = [r for r, m in zip(plan.rpm, plan.motor_on, strict=True) if m]
    return {
        "stop_m": stop,
        "quill_at_stop_s": at_stop,
        "released_s": released,
        "quill_home_s": home,
        "top_rpm": max(on) if on else 0.0,
        "motor_on_s": next((t for t, m in zip(times, plan.motor_on, strict=True) if m), None),
        "motor_off_s": _motor_off(plan),
    }


def _motor_off(plan: ControlPlan) -> float | None:
    was = False
    for t, on in zip(plan.times, plan.motor_on, strict=True):
        if was and not on:
            return t
        was = on
    return None


# -------------------------------------------------------------------------------- files
class ControlsFile(BaseModel):
    """A machine's manual controls kept as a file: the three behaviours and their sources."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(pattern=NAME)
    sources: list[Source] = Field(min_length=1)
    behaviors: list[ControlBehavior] = Field(min_length=3)

    @model_validator(mode="after")
    def _check(self) -> ControlsFile:
        known = {s.source_id for s in self.sources}
        unknown = sorted({c.source_id for b in self.behaviors for c in b.citations} - known)
        if unknown:
            raise ValueError(f"the behaviours cite unknown sources: {unknown}")
        if len(manual_controls(self.behaviors)) != 1:
            raise ValueError("a controls file holds one operator command set")
        return self

    def controls(self) -> ManualControls:
        return manual_controls(self.behaviors)[0]

    @classmethod
    def load(cls, path: Path) -> ControlsFile:
        return cls.model_validate_json(Path(path).read_text(encoding="utf-8"))
