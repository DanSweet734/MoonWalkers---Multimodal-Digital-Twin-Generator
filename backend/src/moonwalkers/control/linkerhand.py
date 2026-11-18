"""LinkerBot's SDK commands for the L20 hand, run into joint targets (decision 0038).

The sources are in ``docs/research/2026-11-17-l20-hand-sdk-and-models.md``; the SDK files are
filed under ``data/machines/igus-rebel6dof02/inputs/documents/sdk/`` (LinkerBot's ROS 2 SDK,
Apache-2.0, commit 0035f23). This module is our own code; it copies none of LinkerBot's.

- **A position command** is a list of 20 values, each "0~255" (``finger_move``'s docstring,
  ``linker_hand_api.py``). The L20's order is the README's: "Thumb Base", "Index Base", "Middle
  Base", "Ring Base", "Little Base", "Thumb Abduction", four more abductions, "Thumb Roll", four
  "Reserved", "Thumb Tip" and four more tips. The driver sends them as four CAN frames
  (``set_joint_positions``: pitch, yaw, roll and tip frames).
- **Its angles:** ``mapping.py`` turns a right L20's values into radians with a minimum, a maximum
  and a direction per slot (``l20_r_min``, ``l20_r_max``, ``l20_r_derict``): direction -1 maps
  255 to the minimum and 0 to the maximum, else 0 to the minimum; the reserved slots 11 to 14
  are skipped. Those ranges are the limits of LinkerBot's own L20 model (linker_hand_sim,
  l20/right), joint by joint, which is why the twin uses that model (decision 0037).
- **Which joint each slot turns** is matched by those ranges: each slot's range is the limits of
  exactly one joint of the model [INFERENCE, decision 0038]. ``bind_hand`` checks every slot's
  range against its joint's cited limits and refuses a binding that does not match.
- **Presets:** the SDK's GUI keeps each hand's "init_pos" and preset actions, among them
  "张开" (open) and "握拳" (fist), in ``constants.py``.
- **Speed:** ``set_speed`` takes five values "0~255" (the driver sends them in one CAN frame,
  0x05, "motor running speed control"). What a value means in rad/s is not published; the plan
  moves a joint at ``value / 255`` of a top speed, the maker's model's ``velocity="1"`` (rad/s),
  a stand-in [INFERENCE]. The five values are taken per finger, thumb first, as the driver's
  other five-value frames are ordered (the pitch frame carries slots 0 to 4) [INFERENCE].

How a command is timed is inferred, not stated [INFERENCE, decision 0038]: each joint runs from
where it is to its new target at its finger's speed, on its own, so a joint with less to go
arrives first; a later command, or a new speed, takes over from wherever each joint is. The
program waits with ``sleep`` between commands, as a Python script using the SDK would.

Angles: the SDK's are the model's (URDF) angles. The twin's 0 is the photographed pose, so the
twin's angle is the SDK's minus the joint's angle in that pose (decision 0031, as for the arm).
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from moonwalkers.contracts.pipeline_result import ControlBehavior, PipelineResult

from .program import PROGRAM_KEY, ProgramError

FORMAT = "linkerhand_sdk"
SLOTS = 20
RESERVED = (11, 12, 13, 14)
# LinkerBot's ROS 2 SDK README (V3.0.1), "L20:" in its joint correspondence table
SLOT_NAMES = (
    "Thumb Base",
    "Index Base",
    "Middle Base",
    "Ring Base",
    "Little Base",
    "Thumb Abduction",
    "Index Abduction",
    "Middle Abduction",
    "Ring Abduction",
    "Little Abduction",
    "Thumb Roll",
    "Reserved",
    "Reserved",
    "Reserved",
    "Reserved",
    "Thumb Tip",
    "Index Tip",
    "Middle Tip",
    "Ring Tip",
    "Little Tip",
)
# mapping.py, "# L20 R OK": l20_r_min, l20_r_max, l20_r_derict (lines 43-45 at commit 0035f23)
L20_RIGHT_MIN = (0, 0, 0, 0, 0, -0.297, -0.26, -0.26, -0.26, -0.26, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
L20_RIGHT_MAX = (
    0.87, 1.4, 1.4, 1.4, 1.4, 0.683, 0.26, 0.26, 0.26, 0.26,
    1.78, 0, 0, 0, 0, 1.29, 1.08, 1.08, 1.08, 1.08,
)  # fmt: skip
L20_RIGHT_DIRECTION = (-1, -1, -1, -1, -1, -1, 0, 0, 0, 0, -1, 0, 0, 0, 0, -1, -1, -1, -1, -1)
# Each slot's joint in LinkerBot's right L20 model, matched by the ranges above [INFERENCE]
L20_RIGHT_SLOTS = {
    0: "thumb_joint2",
    1: "index_joint1",
    2: "middle_joint1",
    3: "ring_joint1",
    4: "little_joint1",
    5: "thumb_joint0",
    6: "index_joint0",
    7: "middle_joint0",
    8: "ring_joint0",
    9: "little_joint0",
    10: "thumb_joint1",
    15: "thumb_joint3",
    16: "index_joint2",
    17: "middle_joint2",
    18: "ring_joint2",
    19: "little_joint2",
}
FINGERS = ("thumb", "index", "middle", "ring", "little")
# the finger whose speed (set_speed's five values, thumb first) a slot moves at [INFERENCE]
SLOT_FINGER = {s: (0 if s in (0, 5, 10, 15) else (s % 5 if s < 10 else s - 15)) for s in range(20)}
FULL = 255
# set_speed with no values sends [100] * 5 (linker_hand_api.py); a stand-in for the speed the
# hand runs at before a program's first set_speed [INFERENCE]
DEFAULT_SPEED = 100
RANGE_TOLERANCE = 1e-6


def slot_radians(slot: int, value: float) -> float:
    """The model's angle (rad) for ``value`` (0-255, clamped as mapping.py does) in ``slot``."""
    if slot in RESERVED:
        raise ProgramError(f"slot {slot} is reserved; it turns no joint")
    v = min(FULL, max(0.0, float(value)))
    low, high = L20_RIGHT_MIN[slot], L20_RIGHT_MAX[slot]
    if L20_RIGHT_DIRECTION[slot] == -1:
        return high + (low - high) * v / FULL
    return low + (high - low) * v / FULL


def slot_value(slot: int, radians: float) -> float:
    """The 0-255 value that gives ``radians`` in ``slot`` (the inverse, clamped to the range)."""
    if slot in RESERVED:
        raise ProgramError(f"slot {slot} is reserved; it turns no joint")
    low, high = L20_RIGHT_MIN[slot], L20_RIGHT_MAX[slot]
    r = min(high, max(low, radians))
    share = (r - low) / (high - low)
    return FULL * (1 - share) if L20_RIGHT_DIRECTION[slot] == -1 else FULL * share


def pose_radians(values: Sequence[float]) -> dict[str, float]:
    """A 20-value position command as the model's joint angles, by joint name."""
    if len(values) != SLOTS:
        raise ProgramError(f"an L20 position command has {SLOTS} values, not {len(values)}")
    return {joint: slot_radians(slot, values[slot]) for slot, joint in L20_RIGHT_SLOTS.items()}


# ------------------------------------------------------------------------------- program
@dataclass(frozen=True)
class SetSpeed:
    nr: int
    speed: tuple[float, ...]  # five values, 0-255, thumb first
    descr: str


@dataclass(frozen=True)
class FingerMove:
    nr: int
    pose: tuple[float, ...]  # twenty values, 0-255
    descr: str


@dataclass(frozen=True)
class Sleep:
    nr: int
    seconds: float
    descr: str


Call = SetSpeed | FingerMove | Sleep


class _CallModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    call: Literal["set_speed", "finger_move", "sleep"]
    speed: list[float] | None = None
    pose: list[float] | None = None
    seconds: float | None = None
    descr: str = ""


@dataclass(frozen=True)
class HandProgram:
    hand_joint: str  # "L20"
    hand_type: str  # "right"
    calls: tuple[Call, ...]

    @classmethod
    def from_behavior(cls, behavior: ControlBehavior) -> HandProgram:
        program = behavior.spec.get(PROGRAM_KEY)
        if not is_linkerhand(behavior):
            raise ProgramError(f"behaviour {behavior.behavior_id} holds no LinkerHand program")
        assert isinstance(program, dict)
        if program.get("hand_joint") != "L20" or program.get("hand_type") != "right":
            raise ProgramError(
                "only the L20 right hand's commands are read (hand_joint 'L20', hand_type "
                f"'right'); got {program.get('hand_joint')!r}, {program.get('hand_type')!r}"
            )
        raw = program.get("calls")
        if not isinstance(raw, list) or not raw:
            raise ProgramError(f"spec['{PROGRAM_KEY}']['calls'] must list the SDK calls")
        calls: list[Call] = []
        for nr, item in enumerate(raw, start=1):
            try:
                c = _CallModel.model_validate(item)
            except ValueError as exc:
                raise ProgramError(f"call {nr}: {exc}") from exc
            calls.append(_call(nr, c))
        if not any(isinstance(c, FingerMove) for c in calls):
            raise ProgramError("the program has no finger_move")
        return cls("L20", "right", tuple(calls))


def _call(nr: int, c: _CallModel) -> Call:
    where = f"call {nr} ({c.call})"
    if c.call == "set_speed":
        if c.speed is None or len(c.speed) != len(FINGERS):
            raise ProgramError(f"{where}: set_speed takes five values, thumb first")
        _check_values(c.speed, where)
        return SetSpeed(nr, tuple(c.speed), c.descr)
    if c.call == "finger_move":
        if c.pose is None or len(c.pose) != SLOTS:
            raise ProgramError(f"{where}: an L20 finger_move takes {SLOTS} values")
        _check_values(c.pose, where)
        return FingerMove(nr, tuple(c.pose), c.descr)
    if c.seconds is None or not math.isfinite(c.seconds) or c.seconds < 0:
        raise ProgramError(f"{where}: sleep needs seconds, 0 or more")
    return Sleep(nr, c.seconds, c.descr)


def _check_values(values: Sequence[float], where: str) -> None:
    # finger_move refuses "less than 0 or greater than 255" (linker_hand_api.py)
    bad = [v for v in values if not math.isfinite(v) or v < 0 or v > FULL]
    if bad:
        raise ProgramError(f"{where}: values must be 0 to 255; got {bad}")


def is_linkerhand(behavior: ControlBehavior) -> bool:
    program = behavior.spec.get(PROGRAM_KEY)
    return isinstance(program, dict) and program.get("format") == FORMAT


# ------------------------------------------------------------------------------- binding
class HandSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    top_speed_rad_s: float | None = Field(
        default=None, gt=0, description="speed 255's rad/s; None: the twin's cited hand speed"
    )
    pose_rad: dict[str, float] | None = Field(
        default=None, description="each joint's SDK angle in the twin's 0 pose; None: the twin's"
    )
    start_speed: float = Field(
        default=DEFAULT_SPEED,
        ge=0,
        le=FULL,
        description="each finger's speed before any set_speed: set_speed's own default",
    )


class HandJoint(BaseModel):
    slot: int | None = Field(description="the SDK's position slot; None for a follower")
    name: str = Field(description="the slot's name in the SDK's README, or 'follows <leader>'")
    joint_id: str
    pose_rad: float = Field(description="the SDK's angle at the twin's 0")
    lower_rad: float = Field(description="the twin's limit")
    upper_rad: float
    top_speed_rad_s: float
    leader: str | None = None
    ratio: float = 1.0
    offset: float = 0.0


class HandBinding(BaseModel):
    joints: list[HandJoint]
    pose_from: str

    def driven(self) -> list[HandJoint]:
        return [j for j in self.joints if j.slot is not None]


def bind_hand(
    behavior: ControlBehavior, results: Sequence[PipelineResult], settings: HandSettings
) -> HandBinding:
    """Each slot's joint on the twin, checked against the SDK's range: the twin's facts
    ``<joint>_lower`` and ``<joint>_upper`` must be the slot's minimum and maximum. A joint's
    pose angle is the cited lower limit minus the twin's (decision 0031). The followers come
    with their leader, ratio and offset, so the plan can show where they should be."""
    program = behavior.spec.get(PROGRAM_KEY, {})
    slots = {int(k): str(v) for k, v in (program.get("slots") or {}).items()}
    if slots != L20_RIGHT_SLOTS:
        raise ProgramError(
            f"spec['{PROGRAM_KEY}']['slots'] must map the L20's 16 slots to the joints of "
            "LinkerBot's right L20 model (decision 0038)"
        )
    joints = {j.joint_id: j for r in results for j in r.joints}
    facts = {f.key: f.value for r in results for f in r.facts}
    speed = settings.top_speed_rad_s
    if speed is None:
        cited = facts.get("hand_joint_speed")
        if not isinstance(cited, int | float):
            raise ProgramError("the twin's facts give no hand_joint_speed; give top_speed_rad_s")
        speed = float(cited)
    out, sources = [], set()

    def pose_of(joint_id: str, lower: float, upper: float) -> float:
        if settings.pose_rad is not None and joint_id in settings.pose_rad:
            sources.add("given")
            return settings.pose_rad[joint_id]
        cited = facts.get(f"{joint_id}_lower"), facts.get(f"{joint_id}_upper")
        if not all(isinstance(v, int | float) for v in cited):
            raise ProgramError(f"the twin's facts give no {joint_id}_lower and _upper")
        low, high = (float(c) - t for c, t in zip(cited, (lower, upper)))  # type: ignore[arg-type]
        if abs(low - high) > 1e-3:
            raise ProgramError(f"{joint_id}: the cited range is not the twin's moved by one angle")
        sources.add("the model's limits in the twin's facts minus the twin's (decision 0031)")
        return round((low + high) / 2, 4)

    for slot, joint_id in sorted(slots.items()):
        joint = joints.get(joint_id)
        if joint is None or joint.joint_type != "revolute":
            raise ProgramError(f"slot {slot} turns '{joint_id}', not a revolute joint here")
        if joint.lower_limit is None or joint.upper_limit is None:
            raise ProgramError(f"{joint_id} has no limits")
        cited = facts.get(f"{joint_id}_lower"), facts.get(f"{joint_id}_upper")
        want = L20_RIGHT_MIN[slot], L20_RIGHT_MAX[slot]
        if not all(isinstance(v, int | float) for v in cited) or any(
            abs(float(c) - w) > RANGE_TOLERANCE  # type: ignore[arg-type]
            for c, w in zip(cited, want)
        ):
            raise ProgramError(
                f"slot {slot} ({SLOT_NAMES[slot]}) ranges {want[0]:g} to {want[1]:g} rad in the "
                f"SDK, but {joint_id}'s cited limits are {cited}: not the joint it turns"
            )
        out.append(
            HandJoint(
                slot=slot,
                name=SLOT_NAMES[slot],
                joint_id=joint_id,
                pose_rad=pose_of(joint_id, joint.lower_limit, joint.upper_limit),
                lower_rad=joint.lower_limit,
                upper_rad=joint.upper_limit,
                top_speed_rad_s=speed,
            )
        )
    driven = {j.joint_id for j in out}
    for joint in joints.values():
        link = joint.follows
        if link is None or link.leader not in driven:
            continue
        if joint.lower_limit is None or joint.upper_limit is None:
            raise ProgramError(f"{joint.joint_id} has no limits")
        out.append(
            HandJoint(
                slot=None,
                name=f"follows {link.leader}",
                joint_id=joint.joint_id,
                pose_rad=pose_of(joint.joint_id, joint.lower_limit, joint.upper_limit),
                lower_rad=joint.lower_limit,
                upper_rad=joint.upper_limit,
                top_speed_rad_s=speed * abs(link.ratio),
                leader=link.leader,
                ratio=link.ratio,
                offset=link.offset,
            )
        )
    return HandBinding(joints=out, pose_from="; ".join(sorted(sources)))


# ------------------------------------------------------------------------------- the plan
class HandEvent(BaseModel):
    nr: int
    command: str  # "set_speed", "finger_move" or "sleep"
    start_s: float
    end_s: float = Field(description="a finger_move: when its last joint arrives, as planned")
    from_deg: list[float] = Field(description="the SDK's (model's) angles, every bound joint")
    to_deg: list[float] = Field(description="a finger_move: its targets; else as from_deg")
    reached: bool = Field(default=True, description="False: a later call took over first")
    what: str


class HandTrajectory(BaseModel):
    """The program's targets over time, in the SDK's (the model's) angles: straight lines
    between waypoints. ``joint_ids`` lists the driven joints, then the followers."""

    joint_ids: list[str]
    slots: list[int | None]
    pose_deg: list[float] = Field(description="each joint's SDK angle at the twin's 0")
    times: list[float]
    sdk_deg: list[list[float]] = Field(description="per joint, one angle per waypoint")
    events: list[HandEvent]
    notes: list[str] = Field(default_factory=list)

    @property
    def duration_s(self) -> float:
        return self.times[-1]

    def twin_deg(self) -> list[list[float]]:
        return [[v - p for v in series] for series, p in zip(self.sdk_deg, self.pose_deg)]


Waypoints = list[tuple[float, float]]  # a joint's (time s, SDK angle rad), in time order


def _angle_at(path: Waypoints, time: float) -> float:
    for (t0, a0), (t1, a1) in itertools.pairwise(path):
        if time < t1:
            return a0 if time <= t0 else a0 + (a1 - a0) * (time - t0) / (t1 - t0)
    return path[-1][1]


def _replan(path: Waypoints, time: float, goal: float, rate: float) -> float:
    """Cut ``path`` at ``time`` and head for ``goal`` at ``rate`` (rad/s) from there; returns
    when it arrives (``time`` when it is there already or cannot move)."""
    here = _angle_at(path, time)
    path[:] = [p for p in path if p[0] < time] + [(time, here)]
    distance = abs(goal - here)
    if distance <= 1e-12 or rate <= 0:
        return time
    path.append((time + distance / rate, goal))
    return time + distance / rate


def run_hand_program(
    program: HandProgram, binding: HandBinding, settings: HandSettings | None = None
) -> HandTrajectory:
    """The trajectory of ``program`` from the twin's 0 pose."""
    settings = settings or HandSettings()
    driven = binding.driven()
    paths: dict[str, Waypoints] = {j.joint_id: [(0.0, j.pose_rad)] for j in driven}
    goals = {j.joint_id: j.pose_rad for j in driven}
    speeds = [float(settings.start_speed)] * len(FINGERS)
    events: list[HandEvent] = []
    notes: list[str] = []
    t = 0.0

    def rate(j: HandJoint) -> float:
        return j.top_speed_rad_s * speeds[SLOT_FINGER[j.slot or 0]] / FULL

    def now() -> dict[str, float]:
        return {jid: _angle_at(path, t) for jid, path in paths.items()}

    def take_over(nr: int) -> None:
        for e in events:
            if e.command == "finger_move" and e.reached and e.end_s > t + 1e-9:
                e.reached = False
                notes.append(f"call {nr} at {t:.3f} s takes over before call {e.nr} arrives")

    for call in program.calls:
        here = now()
        if isinstance(call, Sleep):
            events.append(_event(call, t, t + call.seconds, driven, here, here))
            events[-1].what = f"wait {call.seconds:g} s"
            t += call.seconds
            continue
        if isinstance(call, SetSpeed):
            speeds = list(call.speed)
            moving = [j for j in driven if abs(goals[j.joint_id] - here[j.joint_id]) > 1e-12]
            if moving:
                take_over(call.nr)
            for j in moving:
                _replan(paths[j.joint_id], t, goals[j.joint_id], rate(j))
            stopped = [FINGERS[k] for k, v in enumerate(speeds) if v == 0]
            if stopped:
                notes.append(f"call {call.nr}: speed 0 holds the {', '.join(stopped)} joints")
            events.append(_event(call, t, t, driven, here, here))
            pairs = ", ".join(f"{f} {v:g}" for f, v in zip(FINGERS, speeds))
            events[-1].what = f"set_speed: {pairs} (of 255)"
            continue
        targets = pose_radians(call.pose)
        for j in driven:
            _check_limit(call, j, targets[j.joint_id])
        take_over(call.nr)
        end = t
        stuck = False
        for j in driven:
            jid = j.joint_id
            goals[jid] = targets[jid]
            arrive = _replan(paths[jid], t, targets[jid], rate(j))
            stuck |= arrive == t and abs(targets[jid] - here[jid]) > 1e-12
            end = max(end, arrive)
        moved = sum(1 for j in driven if abs(targets[j.joint_id] - here[j.joint_id]) > 1e-9)
        events.append(_event(call, t, end, driven, here, targets))
        events[-1].reached = not stuck
        label = f" ({call.descr})" if call.descr else ""
        took = end - t
        events[-1].what = f"finger_move{label}: {moved} joints move; the last after {took:.3f} s"

    final = max([t] + [path[-1][0] for path in paths.values()])
    stamps = {0.0, final, *(p[0] for path in paths.values() for p in path)}
    stamps |= {e.start_s for e in events} | {e.end_s for e in events}
    times = sorted(x for x in stamps if x <= final)
    series = [[math.degrees(_angle_at(paths[j.joint_id], x)) for x in times] for j in driven]
    followers = [j for j in binding.joints if j.slot is None]
    index = {j.joint_id: k for k, j in enumerate(driven)}
    for f in followers:
        k = index[f.leader or ""]
        series.append([math.degrees(_follow(f, driven[k], math.radians(v))) for v in series[k]])
    for e in events:
        e.from_deg = _with_followers(e.from_deg, driven, followers)
        e.to_deg = _with_followers(e.to_deg, driven, followers)
    return HandTrajectory(
        joint_ids=[j.joint_id for j in [*driven, *followers]],
        slots=[j.slot for j in [*driven, *followers]],
        pose_deg=[math.degrees(j.pose_rad) for j in [*driven, *followers]],
        times=times,
        sdk_deg=series,
        events=events,
        notes=notes,
    )


def _follow(follower: HandJoint, leader: HandJoint, leader_sdk: float) -> float:
    """A follower's SDK angle: its link holds in the twin's angles (twin = ratio * the leader's
    twin + offset), and each twin angle is the SDK's minus the joint's pose."""
    twin = follower.ratio * (leader_sdk - leader.pose_rad) + follower.offset
    return twin + follower.pose_rad


def _with_followers(
    driven_deg: list[float], driven: Sequence[HandJoint], followers: Sequence[HandJoint]
) -> list[float]:
    by_id = {j.joint_id: (j, v) for j, v in zip(driven, driven_deg)}
    extra = []
    for f in followers:
        lead, deg = by_id[f.leader or ""]
        extra.append(math.degrees(_follow(f, lead, math.radians(deg))))
    return list(driven_deg) + extra


def _event(
    call: Call,
    start: float,
    end: float,
    driven: Sequence[HandJoint],
    before: Mapping[str, float],
    after: Mapping[str, float],
) -> HandEvent:
    command = {SetSpeed: "set_speed", FingerMove: "finger_move", Sleep: "sleep"}[type(call)]
    return HandEvent(
        nr=call.nr,
        command=command,
        start_s=start,
        end_s=end,
        from_deg=[math.degrees(before[j.joint_id]) for j in driven],
        to_deg=[math.degrees(after[j.joint_id]) for j in driven],
        what=command,
    )


def _check_limit(call: FingerMove, joint: HandJoint, target: float) -> None:
    twin = target - joint.pose_rad
    if not joint.lower_rad - 1e-9 <= twin <= joint.upper_rad + 1e-9:
        raise ProgramError(
            f"call {call.nr}: {joint.joint_id} to {target:.4f} rad (SDK) is the twin's "
            f"{twin:.4f}, outside its range {joint.lower_rad:.4f} to {joint.upper_rad:.4f}"
        )


def format_values(values: Sequence[Any]) -> str:
    return ", ".join(f"{v:g}" for v in values)
