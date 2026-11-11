"""An igus Robot Control (iRC) program for the ReBeL arm, run into joint targets (decision 0033).

The sources are in ``docs/research/2026-11-10-irc-programs-and-cri.md``:

- "Robot programs are .xml files" (igus's iRC command reference, V902-11-005, 06/2020, p. 2). The
  CPR wiki's example ("Transferring Robot Programs via CRI") gives the form: ``<Program>``, an
  optional ``<Header>``, then commands with ``Nr`` and ``Descr``, among them::

      <Joint AbortCondition="False" Nr="2" Source="Numerical" velPercent="100" acc="40"
             smooth="0" a1="10" a2="0" a3="0" a4="0" a5="0" a6="0" e1="0" e2="0" e3="0" Descr="" />

- A Joint move: "A1 to A6: Joint values of the target position in degree", "Vel: Velocity in
  percent of the max joint velocities", "Acc: Acceleration in % of the max joint acceleration",
  and "The joint velocities during the motion are constant" (command reference, section 6.1).

What the reader takes:

- **Joint** with numbers (``Source="Numerical"``), no abort condition, and no external axes;
- **Wait** (``Seconds``) and **Output** (``DIO``, ``State``, logged, no motion), in the form
  RoboDK's post-processor for CPR robots writes them: second-hand, not confirmed for iRC;
- **Loop** ... **EndLoop** with ``Condition="False"``, the wiki's endless loop, run for a set
  number of passes;
- a ``Header``, kept as written. Comments in the XML are skipped.

Everything else is refused with the reason: linear and circular moves need the arm's inverse
kinematics (left out, as the plan allows); variables, conditions, inputs and sub-programs are not
simulated; RelativeJoint's XML is not confirmed.

How a move is timed is inferred, not stated [INFERENCE, decision 0033]: the joint with the
farthest to go runs at Vel % of the top speed (times the override), speeding up and slowing down
at Acc % of the maximum acceleration, and the other joints follow in proportion, so all start and
stop together ("The robot moves as fast as the slowest joint allows", user guide V14.5, p. 45).
The ReBeL's top speed is the cited 45 deg/s; its maximum acceleration is a stand-in, iRC_ROS's
MoveIt limit of 5.240 rad/s^2. Smoothing is not modelled: each move ends at rest.

Angles: a program's are iRC's, which are igus's documented angles, measured from the arm straight
up. The twin's joint position is the iRC angle minus the joint's angle in the twin's pose
(decision 0031), its ``pose_deg``.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from xml.etree import ElementTree

from pydantic import BaseModel, ConfigDict, Field

from moonwalkers.contracts.pipeline_result import ControlBehavior, PipelineResult

from .interpreter import move_profile
from .program import PROGRAM_KEY, ProgramError

FORMAT = "irc_xml"
AXES = ("A1", "A2", "A3", "A4", "A5", "A6")
EXTERNAL = ("e1", "e2", "e3")
# iRC_ROS's irc_ros_moveit_config/config/joint_limits.yaml (commit 41701e6): "max_acceleration:
# 5.240" (rad/s^2) for every ReBeL joint; a stand-in for iRC's own "max joint acceleration".
ACCELERATION_STAND_IN_DEG_S2 = math.degrees(5.240)
POSE_TOLERANCE_DEG = 0.05  # the two ends of a joint's range must give the same pose angle
LIMIT_TOLERANCE_DEG = 1e-6

REFUSED = {
    "Linear": "a linear move needs the arm's inverse kinematics, which is not modelled",
    "LinearByVariable": "a linear move needs the arm's inverse kinematics, which is not modelled",
    "Circular": "a circular move needs the arm's inverse kinematics, which is not modelled",
    "RelativeBase": "a Cartesian move needs the arm's inverse kinematics, which is not modelled",
    "RelativeTool": "a Cartesian move needs the arm's inverse kinematics, which is not modelled",
    "Path": "a path from a file needs the arm's inverse kinematics, which is not modelled",
    "RelativeJoint": "its XML form is not confirmed by any source read (decision 0033)",
    "JointByVariable": "variables are not simulated",
    "WaitInput": "inputs are not simulated",
    "WaitConditional": "conditions and inputs are not simulated",
    "If": "conditions are not simulated",
    "Sub": "sub-programs are not read",
}


@dataclass(frozen=True)
class JointMove:
    nr: int
    target_deg: tuple[float, ...]  # A1 to A6, iRC's angles
    vel_percent: float
    acc_percent: float
    smooth: float
    descr: str


@dataclass(frozen=True)
class Wait:
    nr: int
    seconds: float
    descr: str


@dataclass(frozen=True)
class Output:
    nr: int
    dio: str
    state: str
    descr: str


@dataclass(frozen=True)
class Loop:
    nr: int
    body: tuple[Command, ...]
    descr: str


Command = JointMove | Wait | Output | Loop


@dataclass(frozen=True)
class IrcProgram:
    commands: tuple[Command, ...]
    header: Mapping[str, str]

    @classmethod
    def from_xml(cls, text: str) -> IrcProgram:
        try:
            root = ElementTree.fromstring(text)
        except ElementTree.ParseError as exc:
            raise ProgramError(f"the iRC program is not well-formed XML: {exc}") from exc
        if root.tag != "Program":
            raise ProgramError(f"an iRC program's root element is <Program>, not <{root.tag}>")
        header: dict[str, str] = {}
        stack: list[tuple[Loop | None, list[Command]]] = [(None, [])]
        for index, element in enumerate(root, start=1):
            tag, a = element.tag, element.attrib
            nr = _int(a.get("Nr", index), tag, "Nr")
            where = f"<{tag} Nr={nr}>"
            descr = a.get("Descr", "")
            if tag == "Header":
                header = dict(a)
            elif tag == "Joint":
                stack[-1][1].append(_joint(a, nr, where, descr))
            elif tag == "Wait":
                seconds = _float(a.get("Seconds"), where, "Seconds")
                if seconds < 0:
                    raise ProgramError(f"{where}: a wait cannot be negative ({seconds:g} s)")
                stack[-1][1].append(Wait(nr, seconds, descr))
            elif tag == "Output":
                dio, state = a.get("DIO"), a.get("State")
                if dio is None or state is None:
                    raise ProgramError(f"{where}: an output needs DIO and State")
                stack[-1][1].append(Output(nr, dio, state, descr))
            elif tag == "Loop":
                if a.get("Condition", "").strip().lower() != "false":
                    raise ProgramError(
                        f'{where}: only the endless loop (Condition="False") is read; its '
                        "condition would need inputs or variables, which are not simulated"
                    )
                stack.append((Loop(nr, (), descr), []))
            elif tag == "EndLoop":
                if len(stack) == 1:
                    raise ProgramError(f"{where}: an EndLoop without its Loop")
                loop, body = stack.pop()
                assert loop is not None
                stack[-1][1].append(Loop(loop.nr, tuple(body), loop.descr))
            elif tag in REFUSED:
                raise ProgramError(f"{where}: not supported: {REFUSED[tag]}")
            else:
                raise ProgramError(
                    f"{where}: not read; the reader takes Joint, Wait, Output and the endless "
                    "Loop (decision 0033)"
                )
        if len(stack) != 1:
            raise ProgramError(f"<Loop Nr={stack[-1][0].nr}> has no EndLoop")  # type: ignore[union-attr]
        commands = tuple(stack[0][1])
        if not any(isinstance(c, JointMove) for c in _flat(commands)):
            raise ProgramError("the iRC program has no Joint move")
        return cls(commands, header)

    @classmethod
    def from_behavior(cls, behavior: ControlBehavior) -> IrcProgram:
        program = behavior.spec.get(PROGRAM_KEY)
        if not is_irc(behavior):
            raise ProgramError(f"behaviour {behavior.behavior_id} holds no iRC program")
        xml = program.get("xml") if isinstance(program, dict) else None
        if not isinstance(xml, str):
            raise ProgramError(f"spec['{PROGRAM_KEY}']['xml'] must hold the program's XML text")
        result = cls.from_xml(xml)
        program_axes(behavior)  # refuses a missing or partial axis map
        return result


def is_irc(behavior: ControlBehavior) -> bool:
    """Whether the behaviour's program is iRC's XML (else the HA5C's step table)."""
    program = behavior.spec.get(PROGRAM_KEY)
    return isinstance(program, dict) and program.get("format") == FORMAT


def program_axes(behavior: ControlBehavior) -> dict[str, str]:
    """iRC's axes A1 to A6 and the twin's joints they turn: ``spec["program"]["axes"]``."""
    axes = behavior.spec.get(PROGRAM_KEY, {}).get("axes")
    if not isinstance(axes, dict) or sorted(axes) != list(AXES):
        raise ProgramError(
            f"spec['{PROGRAM_KEY}']['axes'] must map each of {', '.join(AXES)} to a joint"
        )
    if len(set(axes.values())) != len(AXES):
        raise ProgramError("two of iRC's axes map to the same joint")
    return {axis: str(axes[axis]) for axis in AXES}


# ------------------------------------------------------------------------------- the arm
class ArmSettings(BaseModel):
    """What the program leaves to the control and the simulation (decision 0033)."""

    model_config = ConfigDict(extra="forbid")

    override_percent: float = Field(
        default=100.0, gt=0, le=100, description="the Play tab's override of the robot velocity"
    )
    acceleration_deg_s2: float | None = Field(
        default=ACCELERATION_STAND_IN_DEG_S2,
        gt=0,
        description="Acc 100 %: a stand-in (iRC_ROS's MoveIt limit); None: full speed at once",
    )
    loop_passes: int = Field(
        default=1, ge=1, le=100, description="passes of an endless loop in the plan"
    )
    pose_deg: dict[str, float] | None = Field(
        default=None,
        description="each joint's iRC angle in the twin's 0 pose; None: from the twin (0031)",
    )
    max_moves: int = Field(default=10_000, ge=1, description="a guard against runaway programs")


class ArmJoint(BaseModel):
    axis: str
    joint_id: str
    pose_deg: float = Field(description="iRC's angle at the twin's 0")
    lower_deg: float = Field(description="the twin's limit")
    upper_deg: float
    top_speed_deg_s: float


class ArmBinding(BaseModel):
    """The program's axes on the twin: which joint, its pose angle, limits and top speed."""

    joints: list[ArmJoint]
    pose_from: str

    @property
    def top_speed_deg_s(self) -> float:
        return min(j.top_speed_deg_s for j in self.joints)

    @property
    def pose(self) -> tuple[float, ...]:
        return tuple(j.pose_deg for j in self.joints)


def bind_arm(
    behavior: ControlBehavior, results: Sequence[PipelineResult], settings: ArmSettings
) -> ArmBinding:
    """Find each axis's joint on the twin. A joint's pose angle is given in ``settings``, or
    read from the twin: igus's cited range (facts ``<joint>_lower`` and ``<joint>_upper``) minus
    the twin's own, which decision 0031 shifted by that angle. Both ends must agree."""
    joints = {j.joint_id: j for r in results for j in r.joints}
    facts = {f.key: f.value for r in results for f in r.facts}
    out, sources = [], set()
    for axis, joint_id in program_axes(behavior).items():
        joint = joints.get(joint_id)
        if joint is None or joint.joint_type != "revolute":
            raise ProgramError(f"{axis} turns '{joint_id}', which is not a revolute joint here")
        if joint.lower_limit is None or joint.upper_limit is None:
            raise ProgramError(f"{joint_id} has no limits")
        if joint.max_velocity is None:
            raise ProgramError(f"{joint_id} has no cited top speed (max_velocity)")
        lower, upper = math.degrees(joint.lower_limit), math.degrees(joint.upper_limit)
        if settings.pose_deg is not None and joint_id in settings.pose_deg:
            pose = settings.pose_deg[joint_id]
            sources.add("given")
        else:
            pose = _pose_from_facts(joint_id, facts, lower, upper)
            sources.add("igus's ranges in the twin's facts minus its limits (decision 0031)")
        out.append(
            ArmJoint(
                axis=axis,
                joint_id=joint_id,
                pose_deg=pose,
                lower_deg=lower,
                upper_deg=upper,
                top_speed_deg_s=math.degrees(joint.max_velocity),
            )
        )
    return ArmBinding(joints=out, pose_from="; ".join(sorted(sources)))


def _pose_from_facts(joint_id: str, facts: Mapping[str, Any], lower: float, upper: float) -> float:
    cited = facts.get(f"{joint_id}_lower"), facts.get(f"{joint_id}_upper")
    if not all(isinstance(v, int | float) for v in cited):
        raise ProgramError(
            f"the twin's facts give no {joint_id}_lower and {joint_id}_upper (igus's range), so "
            f"{joint_id}'s angle in the twin's pose is unknown; give it (pose_deg)"
        )
    low, high = (math.degrees(float(v)) - twin for v, twin in zip(cited, (lower, upper)))  # type: ignore[arg-type]
    if abs(low - high) > POSE_TOLERANCE_DEG:
        raise ProgramError(
            f"{joint_id}: igus's range is shifted by {low:.3f} at one end and {high:.3f} at the "
            "other, so it is not the twin's range moved by one pose angle; give it (pose_deg)"
        )
    # to 0.01 deg, as decision 0031 gives the angles: a spec's limits in radians to 4 decimals
    # carry 0.006 deg of rounding (v3's joint 5 reads 10.459 at one end, 10.460 at the other)
    return round((low + high) / 2, 2)


class ArmEvent(BaseModel):
    nr: int
    command: str
    start_s: float
    end_s: float
    from_deg: list[float] = Field(description="iRC's angles A1 to A6")
    to_deg: list[float]
    what: str


class ArmTrajectory(BaseModel):
    """The program's targets over time: straight lines between waypoints, in iRC's angles."""

    axes: list[str]
    joint_ids: list[str]
    pose_deg: list[float]
    times: list[float]
    irc_deg: list[list[float]] = Field(description="per axis, one angle per waypoint")
    events: list[ArmEvent]
    notes: list[str] = Field(default_factory=list)
    top_speed_deg_s: float
    acceleration_deg_s2: float | None

    @property
    def duration_s(self) -> float:
        return self.times[-1]

    def twin_deg(self) -> list[list[float]]:
        """Per joint, the twin's target angle at each waypoint."""
        return [[v - p for v in series] for series, p in zip(self.irc_deg, self.pose_deg)]

    def final_irc(self) -> list[float]:
        return [series[-1] for series in self.irc_deg]


def run_irc_program(
    program: IrcProgram, binding: ArmBinding, settings: ArmSettings | None = None
) -> ArmTrajectory:
    """The trajectory of ``program`` from the twin's 0 pose."""
    settings = settings or ArmSettings()
    runner = _ArmRunner(binding, settings)
    runner.run(program.commands)
    return ArmTrajectory(
        axes=[j.axis for j in binding.joints],
        joint_ids=[j.joint_id for j in binding.joints],
        pose_deg=list(binding.pose),
        times=runner.times,
        irc_deg=[list(s) for s in runner.series],
        events=runner.events,
        notes=runner.notes,
        top_speed_deg_s=binding.top_speed_deg_s,
        acceleration_deg_s2=settings.acceleration_deg_s2,
    )


class _ArmRunner:
    def __init__(self, binding: ArmBinding, settings: ArmSettings) -> None:
        self.binding = binding
        self.settings = settings
        self.now = list(binding.pose)  # the twin starts at its 0: the photographed pose
        self.t = 0.0
        self.times = [0.0]
        self.series = [[v] for v in self.now]
        self.events: list[ArmEvent] = []
        self.notes: list[str] = []
        self.moves = 0

    def run(self, commands: Sequence[Command]) -> None:
        for command in commands:
            if isinstance(command, JointMove):
                self._move(command)
            elif isinstance(command, Wait):
                start = self.t
                self._hold(command.seconds)
                self._event(command.nr, "Wait", start, self.now, f"wait {command.seconds:g} s")
            elif isinstance(command, Output):
                what = f"set output {command.dio} to {command.state} (logged; no motion)"
                self._event(command.nr, "Output", self.t, self.now, what)
            else:
                passes = self.settings.loop_passes
                self._note(
                    f"Loop Nr={command.nr} repeats until its condition is true, which is never "
                    f'(Condition="False"): the plan runs {passes} pass(es)'
                )
                for _ in range(passes):
                    self.run(command.body)

    def _move(self, move: JointMove) -> None:
        self.moves += 1
        if self.moves > self.settings.max_moves:
            raise ProgramError(f"the program makes more than {self.settings.max_moves} moves")
        self._check_limits(move)
        if move.smooth:
            self._note(
                f"Joint Nr={move.nr}: smoothing ({move.smooth:g} %) is not modelled; the twin "
                "stops at the end of each move"
            )
        start, start_deg = self.t, list(self.now)
        deltas = [b - a for a, b in zip(self.now, move.target_deg)]
        distance = max(abs(d) for d in deltas)
        speed = self.binding.top_speed_deg_s * move.vel_percent / 100
        speed *= self.settings.override_percent / 100
        acceleration = self.settings.acceleration_deg_s2
        if acceleration is not None:
            acceleration *= move.acc_percent / 100
        if distance > 0:
            for dt, moved in move_profile(distance, speed, acceleration)[1:]:
                share = moved / distance
                self.times.append(start + dt)
                for series, a, d in zip(self.series, start_deg, deltas):
                    series.append(a + d * share)
            self.t = self.times[-1]
            self.now = list(move.target_deg)
            for series, v in zip(self.series, self.now):
                series[-1] = v
        lead = self.binding.joints[max(range(len(deltas)), key=lambda i: abs(deltas[i]))].axis
        what = (
            f"joint move at {move.vel_percent:g} % ({speed:g} deg/s for {lead}, "
            f"{distance:.2f} deg), Acc {move.acc_percent:g} %"
            if distance > 0
            else "joint move: already there"
        )
        self._event(move.nr, "Joint", start, start_deg, what)

    def _check_limits(self, move: JointMove) -> None:
        for joint, angle in zip(self.binding.joints, move.target_deg):
            twin = angle - joint.pose_deg
            low, high = joint.lower_deg - LIMIT_TOLERANCE_DEG, joint.upper_deg + LIMIT_TOLERANCE_DEG
            if not low <= twin <= high:
                raise ProgramError(
                    f"Joint Nr={move.nr}: {joint.axis} to {angle:g} deg (iRC) is the twin's "
                    f"{twin:.2f} deg, outside {joint.joint_id}'s range {joint.lower_deg:.2f} to "
                    f"{joint.upper_deg:.2f} (iRC {joint.lower_deg + joint.pose_deg:.2f} to "
                    f"{joint.upper_deg + joint.pose_deg:.2f})"
                )

    def _hold(self, seconds: float) -> None:
        if seconds > 0:
            self.t += seconds
            self.times.append(self.t)
            for series in self.series:
                series.append(series[-1])

    def _event(self, nr: int, command: str, start: float, from_deg: list[float], what: str) -> None:
        self.events.append(
            ArmEvent(
                nr=nr,
                command=command,
                start_s=start,
                end_s=self.t,
                from_deg=list(from_deg),
                to_deg=list(self.now),
                what=what,
            )
        )

    def _note(self, note: str) -> None:
        if note not in self.notes:
            self.notes.append(note)


# ------------------------------------------------------------------------------- helpers
def _joint(a: Mapping[str, str], nr: int, where: str, descr: str) -> JointMove:
    if a.get("Source", "Numerical") != "Numerical":
        raise ProgramError(f"{where}: Source={a['Source']!r}: variables are not simulated")
    if a.get("AbortCondition", "False").strip().lower() != "false":
        raise ProgramError(f"{where}: an abort condition needs inputs, which are not simulated")
    target = tuple(_float(a.get(axis.lower()), where, axis.lower()) for axis in AXES)
    for name in EXTERNAL:
        if name in a and _float(a[name], where, name) != 0:
            raise ProgramError(f"{where}: {name}: the ReBeL twin has no external axes")
    vel = _float(a.get("velPercent"), where, "velPercent")
    acc = _float(a.get("acc"), where, "acc")
    smooth = _float(a.get("smooth", "0"), where, "smooth")
    if not 0 < vel <= 100:
        raise ProgramError(f"{where}: velPercent {vel:g} is outside 0-100 % (above 0)")
    if not 0 < acc <= 100:
        raise ProgramError(f"{where}: acc {acc:g} is outside 0-100 % (above 0)")
    if not 0 <= smooth <= 100:
        raise ProgramError(f"{where}: smooth {smooth:g} is outside 0-100 %")
    return JointMove(nr, target, vel, acc, smooth, descr)


def _float(value: Any, where: str, name: str) -> float:
    if value is None:
        raise ProgramError(f"{where}: {name} is missing")
    try:
        number = float(value)
    except ValueError as exc:
        raise ProgramError(f"{where}: {name}={value!r} is not a number") from exc
    if not math.isfinite(number):
        raise ProgramError(f"{where}: {name}={value!r} is not a finite number")
    return number


def _int(value: Any, tag: str, name: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise ProgramError(f"<{tag}>: {name}={value!r} is not a whole number") from exc


def _flat(commands: Sequence[Command]) -> list[Command]:
    out: list[Command] = []
    for command in commands:
        out += _flat(command.body) if isinstance(command, Loop) else [command]
    return out
