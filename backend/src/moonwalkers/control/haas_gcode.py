"""A Haas mill program (G and M codes) run into a mill twin's axes (decision 0035).

The sources are in ``docs/research/2026-11-16-haas-mill-programs.md``: the Classic Haas Control's
"Mill Operator's Manual 96-8000 Rev Y December 2009" (PDF pages below; printed = PDF - 8) and the
"2023 Mill Operator's Manual", whose example programs O40001 and O40006 are packaged.

What the reader takes (everything else is refused with the reason):

- G00, G01, G02, G03 (G17 only, I/J or R, full circles, helices), G04, G17, G20, G21, G28, G40,
  G41 and G42 with a zero diameter offset, G43, G49, G53, G54-G59, G80, G90, G91, G94;
- M01 (skipped: Optional Stop off), M02, M03, M04, M05, M06 with T, M08, M09, M30;
- N, O, F, S, T, H, D, P; comments in parentheses; ``%``; ``;`` (end of block).

How it plans, with the manual's words:

- **A program's coordinates are the tool's position against the table:** "G17 Defined - ...
  This defines the motion of the tool relative to the table" (PDF p. 148). Each axis (X, Y, Z)
  maps onto one sliding joint of the twin, which moves the tool's part or the work's part; its
  sign follows from Haas's direction of the axis in the twin's frame and the joint's own axis.
  Machine zero (home) is a stated end of the joint's travel (decision 0035).
- **G00:** "Each axis specified is moved at the same speed, but all axes will not necessarily
  complete their motions at the same time" (PDF p. 139): each axis at its cited rapid, on its own.
- **G01:** "all programmed axes will move and reach the destination at the same time"; an axis
  asked for more than it can do raises "an alarm (max feedrate exceeded)" (PDF p. 139), so the
  move is refused. F is taken as the feed along the path [INFERENCE].
- **G02/G03** in the XY plane, clockwise or not as seen from above (PDF pp. 140-141, 148).
- **M codes "take effect at the end of the block"; "Only one M code may be programmed per line"**
  (PDF p. 207).
- **M06** stops the spindle (PDF p. 207), brings Z "up to the machine zero position" (PDF p. 53),
  and turns the umbrella carousel to the tool's pocket, tool n in pocket n [INFERENCE from the
  loading steps, PDF p. 60] at a stand-in time per pocket.
- **Accelerations are stand-ins** (none is cited): every move speeds up and slows down at
  ``acceleration_mm_s2`` and ends at rest, with no blending between blocks.
- The plan starts from the twin's 0 (its photographed pose, decision 0031) and first returns to
  machine zero, Z then X and Y, as POWER UP does before a program runs ("the axes will return to
  the machine zero position", PDF p. 24; the order of HOME G28 on the Tool Room Mill, its 2002
  addendum p. 14).
"""

from __future__ import annotations

import bisect
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from moonwalkers.contracts.pipeline_result import ControlBehavior, PipelineResult

from .interpreter import move_profile
from .program import PROGRAM_KEY, ProgramError

FORMAT = "haas_gcode"
AXES = ("X", "Y", "Z")
INCH_M = 0.0254
MM_M = 0.001
ACCELERATION_STAND_IN_MM_S2 = 1000.0  # no source read gives the axes' acceleration
POCKET_SECONDS_STAND_IN = 1.0  # no tool-change time is cited (Phase 4's hand-off)
ARC_STEP_DEG = 2.0  # the plan's points along an arc, at most this far apart
ARC_TOLERANCE_M = 0.001 * INCH_M  # an arc's end must lie on its circle to 0.001 in
LIMIT_TOLERANCE_M = 1e-7
ALIGNED = 0.999  # Haas's axis and the joint's axis must be parallel to within 2.6 degrees

# The codes the reader takes, by modal group (2009 manual, the G code list, PDF pp. 137-138).
G_GROUPS: dict[int, str] = {
    0: "motion",
    1: "motion",
    2: "motion",
    3: "motion",
    4: "non-modal",
    17: "plane",
    20: "units",
    21: "units",
    28: "non-modal",
    40: "cutter",
    41: "cutter",
    42: "cutter",
    43: "length",
    49: "length",
    53: "non-modal",
    54: "work",
    55: "work",
    56: "work",
    57: "work",
    58: "work",
    59: "work",
    80: "canned",
    90: "distance",
    91: "distance",
    94: "feed mode",
}
G_REFUSED: dict[int, str] = {
    **dict.fromkeys(
        (73, 74, 76, 77, 81, 82, 83, 84, 85, 86, 87, 88, 89),
        "canned cycles are not read (no program read uses one)",
    ),
    12: "circular pocket milling is not read",
    13: "circular pocket milling is not read",
    18: "only the XY plane (G17) is read",
    19: "only the XY plane (G17) is read",
    29: "a return from the reference point is not read",
    31: "feed until skip needs a probe, which is not simulated",
    44: "negative tool length compensation is not read",
    47: "engraving is not read",
    50: "scaling is not read",
    51: "scaling is not read",
    52: "a global work offset shift is not read",
    61: "exact stop mode is not read (every block ends at rest anyway)",
    64: "exact stop cancel is not read",
    68: "rotation is not read",
    69: "rotation is not read",
    92: "a work coordinate shift is not read",
    93: "inverse time feed is not read",
    95: "feed per revolution is not read",
    98: "canned cycles are not read (no program read uses one)",
    99: "canned cycles are not read (no program read uses one)",
}
M_TAKEN = frozenset({1, 2, 3, 4, 5, 6, 8, 9, 30})
M_REFUSED: dict[int, str] = {
    0: "M00 stops the program until a person presses Cycle Start, which is not simulated",
    97: "sub-programs are not read",
    98: "sub-programs are not read",
    99: "sub-programs are not read",
}
LETTERS = frozenset("GMXYZIJKRFSTHDPNO")
NEEDS_DECIMAL = frozenset("XYZIJKRF")  # Setting 77 (PDF p. 229): no decimal point is scaled
WORD = re.compile(r"(,?[A-Z#])\s*([+-]?(?:\d+\.?\d*|\.\d+))?")


# ------------------------------------------------------------------------------- reading
@dataclass(frozen=True)
class Word:
    letter: str
    value: float
    decimal: bool


@dataclass(frozen=True)
class Block:
    line: int  # 1-based, in the program's text
    text: str  # as written, comments included
    words: tuple[Word, ...]

    def codes(self, letter: str) -> list[int]:
        return [int(w.value) for w in self.words if w.letter == letter]

    def get(self, letter: str) -> Word | None:
        return next((w for w in self.words if w.letter == letter), None)

    def has(self, letter: str) -> bool:
        return any(w.letter == letter for w in self.words)


@dataclass(frozen=True)
class GcodeProgram:
    number: str | None  # the O number, as written
    blocks: tuple[Block, ...]

    @classmethod
    def from_text(cls, text: str) -> GcodeProgram:
        number, blocks, ended = None, [], False
        for index, raw in enumerate(text.splitlines(), start=1):
            line = raw.strip()
            body = re.sub(r"\([^)]*\)", " ", line)  # comments
            if "(" in body or ")" in body:
                raise ProgramError(f"line {index}: a comment's parentheses do not match: {line}")
            body = body.replace(";", " ").strip().upper()  # ";" ends a block as printed
            if not body or body == "%":
                continue
            where = f"line {index} ({line})"
            if body.startswith("/"):
                raise ProgramError(f"{where}: block delete (/) is not read")
            words = _words(body, where)
            if ended:
                raise ProgramError(f"{where}: a block after the program's end (M30 or M02)")
            if [w.letter for w in words] == ["O"]:
                number = f"O{int(words[0].value):05d}"
                continue
            block = Block(index, line, tuple(words))
            _check_block(block, where)
            blocks.append(block)
            ended = bool(set(block.codes("M")) & {2, 30})
        if not blocks:
            raise ProgramError("the program has no blocks")
        if not ended:
            raise ProgramError("the program has no end (M30 or M02)")
        return cls(number, tuple(blocks))

    @classmethod
    def from_behavior(cls, behavior: ControlBehavior) -> GcodeProgram:
        if not is_gcode(behavior):
            raise ProgramError(f"behaviour {behavior.behavior_id} holds no Haas program")
        spec = behavior.spec[PROGRAM_KEY]
        text = spec.get("text")
        if not isinstance(text, str):
            raise ProgramError(f"spec['{PROGRAM_KEY}']['text'] must hold the program's text")
        program = cls.from_text(text)
        machine_map(behavior)  # refuses a missing or partial axis map
        setup_of(behavior)
        return program


def _words(body: str, where: str) -> list[Word]:
    words, at = [], 0
    for match in WORD.finditer(body):
        gap = body[at : match.start()].strip()
        if gap:
            raise ProgramError(f"{where}: cannot read {gap!r}")
        at = match.end()
        letter, number = match.group(1), match.group(2)
        if letter == "#":
            raise ProgramError(f"{where}: macros (#) are not read")
        if letter.startswith(","):
            raise ProgramError(
                f"{where}: corner rounding and chamfers ({letter}) are not read (2009 manual, "
                "PDF p. 140)"
            )
        if number is None:
            raise ProgramError(f"{where}: {letter} has no number")
        if letter not in LETTERS:
            raise ProgramError(f"{where}: the address {letter} is not read")
        words.append(Word(letter, float(number), "." in number))
    if body[at:].strip():
        raise ProgramError(f"{where}: cannot read {body[at:].strip()!r}")
    return words


def _check_block(block: Block, where: str) -> None:
    for w in block.words:
        if w.letter in NEEDS_DECIMAL and w.value != 0 and not w.decimal:
            raise ProgramError(
                f'{where}: {w.letter} has no decimal point; Setting 77 would scale it ("F12 '
                'becomes: 0.0012units/minute with Setting 77 Off", 2009 manual, PDF p. 229), '
                "so the reader does not guess it"
            )
    singles = [w.letter for w in block.words if w.letter not in "GM"]
    for letter in set(singles):
        if singles.count(letter) > 1:
            raise ProgramError(f"{where}: {letter} is given twice")
    ms = block.codes("M")
    if len(ms) > 1:
        raise ProgramError(
            f'{where}: "Only one M code may be programmed per line of code" (2009 manual, '
            "PDF p. 207)"
        )
    for m in ms:
        if m in M_REFUSED:
            raise ProgramError(f"{where}: M{m:02d}: {M_REFUSED[m]}")
        if m not in M_TAKEN:
            raise ProgramError(f"{where}: M{m:02d} is not read")
    groups: dict[str, int] = {}
    for g in block.codes("G"):
        if g in G_REFUSED:
            raise ProgramError(f"{where}: G{g:02d}: {G_REFUSED[g]}")
        if g not in G_GROUPS:
            raise ProgramError(f"{where}: G{g:02d} is not read")
        group = G_GROUPS[g]
        if group != "non-modal" and group in groups:
            raise ProgramError(
                f'{where}: G{groups[group]:02d} and G{g:02d} are in the same group; "You cannot '
                'place two G-codes from the same group in a program block" (2023 manual, '
                "p. 102)"
            )
        groups[group] = g


def is_gcode(behavior: ControlBehavior) -> bool:
    """Whether the behaviour's program is a Haas mill program."""
    program = behavior.spec.get(PROGRAM_KEY)
    return isinstance(program, dict) and program.get("format") == FORMAT


# ------------------------------------------------------------------- the machine and set-up
class AxisMap(BaseModel):
    """One of Haas's axes on the twin: its joint, which way + is, and where home is."""

    model_config = ConfigDict(extra="forbid")

    joint_id: str
    direction: tuple[float, float, float] = Field(
        description="Haas's +, the tool's motion against the work, in the twin's frame"
    )
    home: Literal["plus_end", "minus_end"] = Field(
        description="machine zero at the + or the - end of the axis's travel"
    )


class MachineMap(BaseModel):
    model_config = ConfigDict(extra="forbid")

    axes: dict[Literal["X", "Y", "Z"], AxisMap]
    tool_part: str = Field(description="the part that carries the tool (the spindle)")
    work_part: str = Field(description="the part that carries the work (the table)")
    spindle: str | None = Field(default=None, description="the spindle's turning joint")
    carousel: str | None = Field(default=None, description="the tool carousel's turning joint")
    pockets: int | None = Field(default=None, ge=1)


class Tool(BaseModel):
    """A tool in the set-up: a stand-in, an operator's choice, not the machine's."""

    model_config = ConfigDict(extra="forbid")

    length: float | None = Field(
        default=None, gt=0, description="from the spindle nose's face to the tip, set-up units"
    )
    length_offset: float | None = Field(
        default=None, description="H, the machine Z of the tip's touch-off, set-up units"
    )
    diameter: float | None = Field(default=None, gt=0, description="drawn only")
    diameter_offset: float = Field(default=0.0, description="D; only 0 is read")


class Setup(BaseModel):
    """What an operator sets before running the program: units, offsets, tools and stock."""

    model_config = ConfigDict(extra="forbid")

    units: Literal["inch", "mm"] = Field(default="inch", description="Setting 9")
    work_offsets: dict[str, dict[Literal["X", "Y", "Z"], float]] = Field(default_factory=dict)
    tools: dict[str, Tool] = Field(default_factory=dict)
    stock_height: float | None = Field(
        default=None, gt=0, description="a block on the table under the path; set-up units"
    )
    start_pocket: int = Field(default=1, ge=1, description="the pocket at the spindle at the start")
    optional_stop: bool = Field(default=False, description="M01 stops only when this is on")
    why: list[str] = Field(default_factory=list, description="why each stand-in is what it is")

    @property
    def unit_m(self) -> float:
        return INCH_M if self.units == "inch" else MM_M


def machine_map(behavior: ControlBehavior) -> MachineMap:
    raw = behavior.spec.get(PROGRAM_KEY, {}).get("machine")
    try:
        machine = MachineMap.model_validate(raw)
    except ValidationError as exc:
        raise ProgramError(f"spec['{PROGRAM_KEY}']['machine']: {_first(exc)}") from exc
    if sorted(machine.axes) != list(AXES):
        raise ProgramError(f"spec['{PROGRAM_KEY}']['machine']['axes'] must map X, Y and Z")
    if len({a.joint_id for a in machine.axes.values()}) != len(AXES):
        raise ProgramError("two of Haas's axes map to the same joint")
    return machine


def setup_of(behavior: ControlBehavior) -> Setup:
    raw = behavior.spec.get(PROGRAM_KEY, {}).get("setup", {})
    try:
        return Setup.model_validate(raw)
    except ValidationError as exc:
        raise ProgramError(f"spec['{PROGRAM_KEY}']['setup']: {_first(exc)}") from exc


# ------------------------------------------------------------------------------- the twin
class MillAxis(BaseModel):
    axis: str
    joint_id: str
    side: Literal["tool", "work"]
    joint_axis: tuple[float, float, float]
    direction: tuple[float, float, float]
    sign: int = Field(description="Haas's coordinate = sign x (joint position - home)")
    home_m: float = Field(description="the joint's position at machine zero")
    lower_m: float
    upper_m: float
    rapid_m_s: float

    def machine(self, q: float) -> float:
        return self.sign * (q - self.home_m)

    def joint(self, m: float) -> float:
        return self.home_m + self.sign * m


class MillBinding(BaseModel):
    """Haas's axes on the twin, with its spindle and carousel."""

    axes: list[MillAxis]
    tool_part: str
    work_part: str
    spindle: str | None
    spindle_max_rpm: float | None
    carousel: str | None
    pockets: int | None
    max_feed_m_s: float | None = Field(description="the cited maximum cutting feed, if given")

    def machine(self, q: Mapping[str, float]) -> list[float]:
        return [a.machine(q[a.joint_id]) for a in self.axes]

    def joints(self, m: Sequence[float]) -> dict[str, float]:
        return {a.joint_id: a.joint(v) for a, v in zip(self.axes, m, strict=True)}

    def displacement(self, m: Sequence[float], side: str) -> tuple[float, float, float]:
        """How far the ``side``'s part has moved from the twin's 0 at machine position ``m``."""
        out = [0.0, 0.0, 0.0]
        for axis, q in zip(self.axes, self.joints(m).values(), strict=True):
            if axis.side == side:
                for i in range(3):
                    out[i] += q * axis.joint_axis[i]
        return out[0], out[1], out[2]


def bind_mill(behavior: ControlBehavior, results: Sequence[PipelineResult]) -> MillBinding:
    """Find each of Haas's axes on the twin: its sliding joint, which side it moves, its sign
    and its home. A joint's sign: + when the joint moves the tool along Haas's +, or the work
    against it."""
    machine = machine_map(behavior)
    joints = {j.joint_id: j for r in results for j in r.joints}
    parts = {p.part_id for r in results for p in r.parts}
    facts = {f.key: f.value for r in results for f in r.facts}
    for name, part in (("tool_part", machine.tool_part), ("work_part", machine.work_part)):
        if part not in parts:
            raise ProgramError(f"{name} '{part}' is not a part of this twin")
    children: dict[str, list[str]] = {}
    for j in joints.values():
        children.setdefault(j.parent_part, []).append(j.child_part)

    def carried(part: str) -> set[str]:
        out, todo = {part}, [part]
        while todo:
            for child in children.get(todo.pop(), []):
                if child not in out:
                    out.add(child)
                    todo.append(child)
        return out

    axes = []
    for name in AXES:
        mapping = machine.axes[name]  # type: ignore[index]
        joint = joints.get(mapping.joint_id)
        if joint is None or joint.joint_type != "prismatic":
            raise ProgramError(f"{name} moves '{mapping.joint_id}', not a sliding joint here")
        if joint.lower_limit is None or joint.upper_limit is None:
            raise ProgramError(f"{joint.joint_id} has no limits")
        if joint.max_velocity is None:
            raise ProgramError(f"{joint.joint_id} has no cited top speed (its rapid)")
        moved = carried(joint.child_part)
        if machine.tool_part in moved:
            side = "tool"
        elif machine.work_part in moved:
            side = "work"
        else:
            raise ProgramError(f"{joint.joint_id} moves neither the tool nor the work")
        direction = _unit(mapping.direction, f"{name}'s direction")
        joint_axis = _unit(joint.axis, f"{joint.joint_id}'s axis")
        dot = sum(a * b for a, b in zip(direction, joint_axis, strict=True))
        if abs(dot) < ALIGNED:
            raise ProgramError(
                f"{name}'s direction {direction} is not along {joint.joint_id}'s axis {joint_axis}"
            )
        sign = (1 if dot > 0 else -1) * (1 if side == "tool" else -1)
        plus_end = joint.upper_limit if sign > 0 else joint.lower_limit
        minus_end = joint.lower_limit if sign > 0 else joint.upper_limit
        axes.append(
            MillAxis(
                axis=name,
                joint_id=joint.joint_id,
                side=side,
                joint_axis=joint_axis,
                direction=direction,
                sign=sign,
                home_m=plus_end if mapping.home == "plus_end" else minus_end,
                lower_m=joint.lower_limit,
                upper_m=joint.upper_limit,
                rapid_m_s=joint.max_velocity,
            )
        )
    spindle_rpm = None
    for name, joint_id in (("spindle", machine.spindle), ("carousel", machine.carousel)):
        if joint_id is None:
            continue
        joint = joints.get(joint_id)
        if joint is None or joint.joint_type != "revolute":
            raise ProgramError(f"the {name} '{joint_id}' is not a turning joint here")
        if name == "spindle" and joint.max_velocity is not None:
            spindle_rpm = joint.max_velocity * 60 / (2 * math.pi)
    if machine.carousel is not None and machine.pockets is None:
        raise ProgramError("a carousel needs its number of pockets")
    feed = facts.get("max_cutting_feed")
    return MillBinding(
        axes=axes,
        tool_part=machine.tool_part,
        work_part=machine.work_part,
        spindle=machine.spindle,
        spindle_max_rpm=spindle_rpm,
        carousel=machine.carousel,
        pockets=machine.pockets,
        max_feed_m_s=float(feed) if isinstance(feed, int | float) else None,
    )


class MillGeometry(BaseModel):
    """Measured on the twin's stage, for the touch-off and the pictures (decision 0035)."""

    nose_m: tuple[float, float, float] = Field(description="the spindle nose's face, twin's 0")
    table_top_m: float = Field(description="the table's top under the spindle, twin's 0")

    def nose_over_table_at(self, binding: MillBinding, z_machine_m: float) -> float:
        """The nose's height over the table's top with Z at ``z_machine_m`` (X and Y do not
        change it: they move along the table)."""
        z = next(a for a in binding.axes if a.axis == "Z")
        moved = z.joint(z_machine_m) * z.joint_axis[2] * (1 if z.side == "tool" else -1)
        return self.nose_m[2] + moved - self.table_top_m


class MillSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    acceleration_mm_s2: float | None = Field(
        default=ACCELERATION_STAND_IN_MM_S2, gt=0, description="a stand-in; None: none"
    )
    seconds_per_pocket: float = Field(default=POCKET_SECONDS_STAND_IN, gt=0)
    power_up: bool = Field(default=True, description="return to machine zero before the program")
    max_blocks: int = Field(default=10_000, ge=1)


# ------------------------------------------------------------------------------- the plan
class MillEvent(BaseModel):
    line: int = Field(description="0: the operator's POWER UP, before the program")
    block: str
    kind: str
    start_s: float
    end_s: float
    from_mm: list[float] = Field(description="the tool against the table: machine X, Y, Z")
    to_mm: list[float]
    what: str


class ToolOffset(BaseModel):
    tool: str
    h: float = Field(description="set-up units")
    how: str


class MillTrajectory(BaseModel):
    """The program's targets over time: the joints' positions (m on a slide, degrees on a turning
    joint) at each time, the tool tip's machine position, and what each block did."""

    times: list[float]
    positions: dict[str, list[float]]
    machine_mm: list[list[float]]
    axes: list[MillAxis]
    spindle: str | None
    carousel: str | None
    events: list[MillEvent]
    cutting: list[list[float]] = Field(description="[start, end] of each feed or arc move")
    spindle_rpm: list[list[float]] = Field(description="[time, rpm] at each change")
    tool_offsets: list[ToolOffset]
    tool: str | None = Field(description="the tool in the spindle at the end")
    units: str
    notes: list[str]

    @property
    def duration_s(self) -> float:
        return self.times[-1]


def run_gcode_program(
    program: GcodeProgram,
    binding: MillBinding,
    setup: Setup,
    settings: MillSettings | None = None,
    geometry: MillGeometry | None = None,
) -> MillTrajectory:
    """The plan of ``program`` from the twin's 0."""
    runner = _MillRunner(binding, setup, settings or MillSettings(), geometry)
    runner.run(program)
    return runner.trajectory()


@dataclass
class _State:
    units_m: float
    absolute: bool = True
    motion: int | None = None
    work: str = "G54"
    length_m: float = 0.0
    length_h: int | None = None
    cutter: int = 40
    feed_m_s: float | None = None
    speed_rpm: float = 0.0
    next_tool: int | None = None


class _MillRunner:
    def __init__(
        self,
        binding: MillBinding,
        setup: Setup,
        settings: MillSettings,
        geometry: MillGeometry | None,
    ) -> None:
        self.b = binding
        self.setup = setup
        self.settings = settings
        self.geometry = geometry
        self.acc = (
            None if settings.acceleration_mm_s2 is None else settings.acceleration_mm_s2 / 1e3
        )
        self.state = _State(units_m=setup.unit_m)
        self.pos = binding.machine({a.joint_id: 0.0 for a in binding.axes})
        self.t = 0.0
        self.times = [0.0]
        self.machine = [list(self.pos)]
        self.spindle_deg = [0.0]
        self.spindle_rate = 0.0  # deg/s
        self.spindle_rpm: list[list[float]] = [[0.0, 0.0]]
        self.carousel_deg = [0.0]
        self.pocket = setup.start_pocket
        self.tool: str | None = None
        self.events: list[MillEvent] = []
        self.cutting: list[list[float]] = []
        self.notes: list[str] = []
        self.offsets: dict[str, ToolOffset] = {}
        self._check_start()

    # ------------------------------------------------------------------------- the run
    def run(self, program: GcodeProgram) -> None:
        if self.settings.power_up:
            self._power_up()
        if len(program.blocks) > self.settings.max_blocks:
            raise ProgramError(f"the program has more than {self.settings.max_blocks} blocks")
        for block in program.blocks:
            self._block(block)

    def _power_up(self) -> None:
        start, from_mm = self.t, self._mm()
        z = [self.pos[0], self.pos[1], 0.0]
        self._rapid(z)
        self._rapid([0.0, 0.0, 0.0])
        self._note(
            "The plan starts at the twin's 0 (its photographed pose) and returns to machine zero "
            "first, Z then X and Y at the rapids, as POWER UP does before a program runs (2009 "
            "manual, PDF p. 24; the order of the Tool Room Mill's HOME G28, its 2002 addendum, "
            "p. 14). The homing speed is a stand-in: the manuals give none"
        )
        self._event(0, "POWER UP", "power_up", start, from_mm, "zero return: Z, then X and Y")

    def _block(self, block: Block) -> None:
        where = f"line {block.line} ({block.text})"
        s = self.state
        start, from_mm = self.t, self._mm()
        gs = block.codes("G")
        did: list[str] = []
        kind = "modal"
        # units first: the block's numbers are read in them
        if 20 in gs or 21 in gs:
            s.units_m = INCH_M if 20 in gs else MM_M
            did.append("inch" if 20 in gs else "mm")
        if 90 in gs or 91 in gs:
            s.absolute = 90 in gs
            did.append("absolute" if s.absolute else "incremental")
        for g in gs:
            if G_GROUPS[g] == "work":
                s.work = f"G{g}"
                if s.work not in self.setup.work_offsets:
                    raise ProgramError(f"{where}: {s.work} has no offset in the set-up")
                did.append(f"work offset {s.work}")
            elif g in (17, 80, 94):
                pass
            elif g in (0, 1, 2, 3):
                s.motion = g
        self._cutter(block, gs, where, did)
        self._length(block, gs, where, did)
        if (f := block.get("F")) is not None:
            if f.value <= 0:
                raise ProgramError(f"{where}: a feed must be above 0")
            s.feed_m_s = f.value * s.units_m / 60
        if (sw := block.get("S")) is not None:
            if sw.value < 0:
                raise ProgramError(f"{where}: a spindle speed cannot be negative")
            if self.b.spindle_max_rpm is not None and sw.value > self.b.spindle_max_rpm + 1e-6:
                raise ProgramError(
                    f"{where}: S{sw.value:g} is over the spindle's cited "
                    f"{self.b.spindle_max_rpm:.0f} rpm"
                )
            s.speed_rpm = sw.value
        if (tw := block.get("T")) is not None:
            s.next_tool = int(tw.value)

        moved = [block.has(a) for a in AXES]
        if 4 in gs:
            kind = "dwell"
            did.append(self._dwell(block, where))
        elif 28 in gs:
            kind = "rapid"
            did.append(self._return(block, gs, where))
        elif any(moved) or (s.motion in (2, 3) and (block.has("I") or block.has("J"))):
            if s.motion is None:
                raise ProgramError(f"{where}: a move before any G00, G01, G02 or G03")
            kind = {0: "rapid", 1: "feed", 2: "arc", 3: "arc"}[s.motion]
            did.append(self._move(block, gs, where))
        for m in block.codes("M"):
            kind, what = self._m(m, block, where, kind)
            did.append(what)
        what = "; ".join(d for d in did if d) or "nothing to do"
        self._event(block.line, block.text, kind, start, from_mm, what)

    # --------------------------------------------------------------------- modal codes
    def _cutter(self, block: Block, gs: list[int], where: str, did: list[str]) -> None:
        s = self.state
        for g in gs:
            if g not in (40, 41, 42):
                continue
            s.cutter = g
            if g == 40:
                did.append("cutter compensation off")
                continue
            d = block.get("D")
            if d is None:
                raise ProgramError(f'{where}: "A D address must be programmed" (PDF p. 153)')
            tool = self.setup.tools.get(str(int(d.value)))
            offset = 0.0 if tool is None else tool.diameter_offset
            if int(d.value) != 0 and tool is None:
                raise ProgramError(f"{where}: D{int(d.value):02d} has no tool in the set-up")
            if offset != 0:
                raise ProgramError(
                    f"{where}: cutter compensation with a diameter offset of {offset:g} is not "
                    "read: the offset path is not modelled (decision 0035); only D = 0 is"
                )
            did.append(f"cutter compensation G{g} with D{int(d.value):02d} = 0: on the path")
            self._note(
                f"G{g} with a diameter offset of 0 (a stand-in): the tool's centre follows the "
                "programmed path. With the offset an operator would set, the cut would lie half "
                "the tool's diameter to one side of it"
            )

    def _length(self, block: Block, gs: list[int], where: str, did: list[str]) -> None:
        s = self.state
        if 49 in gs:
            s.length_m, s.length_h = 0.0, None
            did.append("tool length compensation off")
        h = block.get("H")
        if 43 in gs:
            if h is None:
                raise ProgramError(f"{where}: G43 needs an H")
            if int(h.value) == 0:
                s.length_m, s.length_h = 0.0, None
            else:
                s.length_m, s.length_h = self._offset(int(h.value), where), int(h.value)
                did.append(f"tool length offset H{int(h.value):02d} on")
        elif h is not None and int(h.value) == 0:
            s.length_m, s.length_h = 0.0, None  # "An H0 ... will also cancel" (PDF p. 158)

    def _offset(self, number: int, where: str) -> float:
        key = str(number)
        if key in self.offsets:
            return self.offsets[key].h * self.setup.unit_m
        tool = self.setup.tools.get(key)
        if tool is None:
            raise ProgramError(f"{where}: H{number:02d} has no tool in the set-up")
        if tool.length_offset is not None:
            h = tool.length_offset
            how = "given in the set-up"
        else:
            h = self._touch_off(tool, number, where)
            how = (
                f"touched off on the twin: the machine Z where a {tool.length:g} "
                f"{self.setup.units} tool's tip meets the top of {self.setup.stock_height:g} "
                f"{self.setup.units} of stock (2009 manual, PDF p. 67)"
            )
        self.offsets[key] = ToolOffset(tool=key, h=h, how=how)
        return h * self.setup.unit_m

    def _touch_off(self, tool: Tool, number: int, where: str) -> float:
        if tool.length is None or self.setup.stock_height is None or self.geometry is None:
            raise ProgramError(
                f"{where}: H{number:02d}: give the tool's length_offset, or its length, the "
                "stock's height and the twin's geometry, to touch it off"
            )
        z = next(a for a in self.b.axes if a.axis == "Z")
        if z.side != "tool" or abs(z.joint_axis[2]) < ALIGNED:
            raise ProgramError(f"{where}: a touch-off needs Z to move the tool up and down")
        unit = self.setup.unit_m
        home_gap = self.geometry.nose_over_table_at(self.b, 0.0)
        tip_at_stock_top = (self.setup.stock_height + tool.length) * unit
        return -(home_gap - tip_at_stock_top) / unit

    # ------------------------------------------------------------------------- moves
    def _target(self, block: Block, gs: list[int], where: str) -> list[float]:
        s = self.state
        target = list(self.pos)
        machine = 53 in gs
        absolute = s.absolute
        if machine and not absolute:
            raise ProgramError(f"{where}: G53 with G91 is not read; G53 takes machine positions")
        offsets = self.setup.work_offsets.get(s.work, {})
        for i, axis in enumerate(AXES):
            w = block.get(axis)
            if w is None:
                continue
            value = w.value * s.units_m
            if machine:
                target[i] = value
            elif absolute:
                target[i] = value + offsets.get(axis, 0.0) * self.setup.unit_m  # type: ignore[call-overload]
                if axis == "Z":
                    target[i] += s.length_m
            else:
                target[i] = self.pos[i] + value
        self._check_reach(target, where)
        return target

    def _move(self, block: Block, gs: list[int], where: str) -> str:
        s = self.state
        target = self._target(block, gs, where)
        if s.motion == 0:
            moved = self._rapid(target)
            return f"rapid, {moved:.3f} s" if moved else "rapid: already there"
        if s.feed_m_s is None:
            raise ProgramError(f"{where}: a feed move before any F")
        start = self.t
        if s.motion == 1:
            length = self._line(target, s.feed_m_s, where)
            what = f"feed {length / s.units_m:.4f} {self._unit()} at F{self._f():g}"
        else:
            length = self._arc(block, target, s.motion == 2, s.feed_m_s, where)
            way = "CW" if s.motion == 2 else "CCW"
            what = f"{way} arc, {length / s.units_m:.4f} {self._unit()} at F{self._f():g}"
        if self.t > start:
            self.cutting.append([start, self.t])
        return what

    def _rapid(self, target: Sequence[float]) -> float:
        start, origin = self.t, list(self.pos)
        profiles = []
        for i, axis in enumerate(self.b.axes):
            profiles.append(move_profile(target[i] - origin[i], axis.rapid_m_s, self.acc))
        duration = max(p[-1][0] for p in profiles)
        if duration <= 0:
            return 0.0
        times = sorted({round(t, 9) for p in profiles for t, _ in p})
        for t in times[1:]:
            point = [origin[i] + _along(p, t) for i, p in enumerate(profiles)]
            self._sample(start + t, point)
        self._settle(target)
        return self.t - start

    def _line(self, target: Sequence[float], feed: float, where: str) -> float:
        origin = list(self.pos)
        delta = [b - a for a, b in zip(origin, target, strict=True)]
        length = math.sqrt(sum(d * d for d in delta))
        if length == 0:
            return 0.0
        self._check_feed(feed, [abs(d) / length for d in delta], where)
        start = self.t
        for t, s in move_profile(length, feed, self.acc)[1:]:
            self._sample(
                start + t, [a + d * s / length for a, d in zip(origin, delta, strict=True)]
            )
        self._settle(target)
        return length

    def _arc(self, block: Block, target: list[float], cw: bool, feed: float, where: str) -> float:
        s = self.state
        x0, y0, z0 = self.pos
        x1, y1, z1 = target
        i, j, r = block.get("I"), block.get("J"), block.get("R")
        if block.has("K"):
            raise ProgramError(f"{where}: K belongs to the XZ or YZ plane, which are not read")
        if r is not None and (i is not None or j is not None):
            raise ProgramError(f"{where}: an arc takes I and J, or R, not both")
        if r is not None:
            if (x0, y0) == (x1, y1):
                raise ProgramError(
                    f'{where}: "To cut a full circle ... using an R address will '
                    'not work" (PDF p. 141)'
                )
            cx, cy, sweep, radius = _arc_by_radius(x0, y0, x1, y1, r.value * s.units_m, cw, where)
        elif i is not None or j is not None:
            cx = x0 + (i.value if i else 0.0) * s.units_m
            cy = y0 + (j.value if j else 0.0) * s.units_m
            radius = math.hypot(x0 - cx, y0 - cy)
            if radius == 0:
                raise ProgramError(f"{where}: the arc's centre is its start")
            end_radius = math.hypot(x1 - cx, y1 - cy)
            if abs(end_radius - radius) > ARC_TOLERANCE_M:
                raise ProgramError(
                    f"{where}: the arc's end is {abs(end_radius - radius) / s.units_m:.4f} "
                    f"{self._unit()} off its circle"
                )
            a0 = math.atan2(y0 - cy, x0 - cx)
            a1 = math.atan2(y1 - cy, x1 - cx)
            sweep = _sweep(a0, a1, cw)
        else:
            raise ProgramError(f"{where}: an arc needs I and J, or R")
        a0 = math.atan2(y0 - cy, x0 - cx)
        flat = radius * abs(sweep)
        length = math.hypot(flat, z1 - z0)
        self._check_feed(feed, [flat / length, flat / length, abs(z1 - z0) / length], where)
        start = self.t
        profile = move_profile(length, feed, self.acc)
        times = [t for t, _ in profile]
        step = math.radians(ARC_STEP_DEG) * radius / feed * length / max(flat, 1e-12)
        extra = [k * step for k in range(1, math.ceil(times[-1] / step))]
        for t in sorted({round(t, 9) for t in [*times[1:], *extra]}):
            share = _along(profile, t) / length
            angle = a0 + sweep * share
            point = [
                cx + radius * math.cos(angle),
                cy + radius * math.sin(angle),
                z0 + (z1 - z0) * share,
            ]
            self._check_reach(point, where)
            self._sample(start + t, point)
        self._settle(target)
        return length

    def _return(self, block: Block, gs: list[int], where: str) -> str:
        """G28: through the given point (with G90), then the named axes, or all, to zero."""
        s = self.state
        named = [a for a in AXES if block.has(a)] or list(AXES)
        via = "directly"  # with G91 the given point is where the axes stand (PDF p. 150)
        if s.absolute and any(block.has(a) for a in AXES):
            middle = self._target(block, [g for g in gs if g != 28], where)
            if self._rapid(middle):
                via = "through the given point"
        home = [0.0 if a in named else self.pos[i] for i, a in enumerate(AXES)]
        self._rapid(home)
        s.length_m, s.length_h = 0.0, None  # "G28 cancels tool length offsets" (PDF p. 149)
        return f"G28: {', '.join(named)} to machine zero {via}; tool length offset off"

    def _dwell(self, block: Block, where: str) -> str:
        p = block.get("P")
        if p is None:
            raise ProgramError(f"{where}: G04 needs a P")
        seconds = p.value if p.decimal else p.value / 1000  # "G04 P10 is ... 10 milliseconds"
        if seconds < 0:
            raise ProgramError(f"{where}: a dwell cannot be negative")
        if seconds:
            self._sample(self.t + seconds, list(self.pos))
        return f"dwell {seconds:g} s"

    # ------------------------------------------------------------------------- M codes
    def _m(self, m: int, block: Block, where: str, kind: str) -> tuple[str, str]:
        s = self.state
        if m in (3, 4):
            if self.b.spindle is None:
                raise ProgramError(f"{where}: M{m:02d}: the twin has no spindle joint")
            if s.speed_rpm <= 0:
                raise ProgramError(f"{where}: M{m:02d} before any S")
            self._spin(s.speed_rpm if m == 3 else -s.speed_rpm)
            way = "forward" if m == 3 else "reverse"
            self._note(
                "The spindle reaches its speed at once and stops at once: no run-up is cited"
            )
            return kind, f"spindle {way} at {s.speed_rpm:g} rpm"
        if m == 5:
            self._spin(0.0)
            return kind, "spindle stop"
        if m in (8, 9):
            self._note("Coolant (M08, M09) is logged only: the twin has none")
            return kind, "coolant on (logged)" if m == 8 else "coolant off (logged)"
        if m == 1:
            if self.setup.optional_stop:
                raise ProgramError(f"{where}: M01 with Optional Stop on waits for Cycle Start")
            self._note("M01 is skipped: the Optional Stop is off (a stand-in)")
            return kind, "optional stop skipped (Optional Stop off)"
        if m == 6:
            return "tool_change", self._tool_change(block, where)
        # M02 and M30: the end
        self._spin(0.0)
        s.length_m, s.length_h = 0.0, None  # "M30 cancels tool length offsets" (PDF p. 209)
        return "end", f"M{m:02d}: the program's end; spindle stop"

    def _tool_change(self, block: Block, where: str) -> str:
        s = self.state
        tool = s.next_tool
        if tool is None:
            raise ProgramError(f"{where}: M06 without a T")
        self._spin(0.0)  # "the spindle and coolant ... will be stopped by the M06 command"
        self._rapid([self.pos[0], self.pos[1], 0.0])  # "bring the Z axis up to ... machine zero"
        what = f"tool change to T{tool}: spindle stop, Z to machine zero"
        if self.b.carousel is not None and self.b.pockets is not None:
            pockets = self.b.pockets
            if not 1 <= tool <= pockets:
                raise ProgramError(f"{where}: T{tool} is not one of the {pockets} pockets")
            steps = (tool - self.pocket) % pockets
            if steps > pockets / 2:
                steps -= pockets
            if steps:
                seconds = abs(steps) * self.settings.seconds_per_pocket
                self._sample(self.t + seconds, list(self.pos), turn=steps * 360 / pockets)
            what += (
                f", carousel {steps:+d} pocket(s) to pocket {tool}"
                if steps
                else f", pocket {tool} already at the spindle"
            )
            self.pocket = tool
            self._note(
                "A tool change turns the carousel the shorter way at "
                f"{self.settings.seconds_per_pocket:g} s a pocket (a stand-in: no time is "
                "cited); tool n is in pocket n [INFERENCE, 2009 "
                f"manual, PDF p. 60]; pocket {self.setup.start_pocket} is at the spindle at the "
                "start (a stand-in); the carousel's slide to the spindle and Z's lift above "
                "machine zero are not modelled"
            )
        self.tool = str(tool)
        return what

    # ------------------------------------------------------------------------- helpers
    def _spin(self, rpm: float) -> None:
        self.spindle_rate = rpm * 6.0  # deg/s
        if self.spindle_rpm[-1][1] != rpm:
            if self.spindle_rpm[-1][0] == self.t:
                self.spindle_rpm[-1][1] = rpm
            else:
                self.spindle_rpm.append([self.t, rpm])

    def _sample(self, t: float, point: Sequence[float], turn: float = 0.0) -> None:
        if t < self.times[-1] - 1e-12:
            raise AssertionError("the plan's times went backwards")
        dt = t - self.times[-1]
        if dt <= 1e-12:
            self.machine[-1] = list(point)
            self.carousel_deg[-1] += turn
        else:
            self.times.append(t)
            self.machine.append(list(point))
            self.spindle_deg.append(self.spindle_deg[-1] + self.spindle_rate * dt)
            self.carousel_deg.append(self.carousel_deg[-1] + turn)
        self.t = t
        self.pos = list(point)

    def _settle(self, target: Sequence[float]) -> None:
        self.pos = list(target)
        self.machine[-1] = list(target)

    def _check_start(self) -> None:
        for axis, m in zip(self.b.axes, self.pos, strict=True):
            if (
                not axis.lower_m - LIMIT_TOLERANCE_M
                <= axis.joint(m)
                <= axis.upper_m + LIMIT_TOLERANCE_M
            ):
                raise ProgramError(f"{axis.joint_id}: the twin's 0 is outside its own range")

    def _check_reach(self, point: Sequence[float], where: str) -> None:
        for axis, m in zip(self.b.axes, point, strict=True):
            q = axis.joint(m)
            if not axis.lower_m - LIMIT_TOLERANCE_M <= q <= axis.upper_m + LIMIT_TOLERANCE_M:
                unit = self.state.units_m
                travel = (axis.machine(axis.lower_m), axis.machine(axis.upper_m))
                raise ProgramError(
                    f"{where}: {axis.axis} to machine {m / unit:.4f} {self._unit()} is outside "
                    f"the travel {min(travel) / unit:.4f} to {max(travel) / unit:.4f} "
                    f"({axis.joint_id} {q:.4f} m, range {axis.lower_m:.4f} to {axis.upper_m:.4f})"
                )

    def _check_feed(self, feed: float, shares: Sequence[float], where: str) -> None:
        if self.b.max_feed_m_s is not None and feed > self.b.max_feed_m_s * (1 + 1e-6):
            raise ProgramError(
                f"{where}: F{self._f():g} is over the cited maximum cutting feed "
                f"({self.b.max_feed_m_s / self.state.units_m * 60:.1f} {self._unit()}/min)"
            )
        for axis, share in zip(self.b.axes, shares, strict=True):
            if feed * share > axis.rapid_m_s * (1 + 1e-6):
                raise ProgramError(
                    f"{where}: {axis.axis} would move at {feed * share * 1000:.1f} mm/s, over its "
                    f'cited {axis.rapid_m_s * 1000:.1f}: "an alarm (max feedrate exceeded)" '
                    "(2009 manual, PDF p. 139)"
                )

    def _mm(self) -> list[float]:
        return [v * 1000 for v in self.pos]

    def _unit(self) -> str:
        return "in" if self.state.units_m == INCH_M else "mm"

    def _f(self) -> float:
        assert self.state.feed_m_s is not None
        return round(self.state.feed_m_s * 60 / self.state.units_m, 6)

    def _event(
        self, line: int, block: str, kind: str, start: float, from_mm: list[float], what: str
    ) -> None:
        self.events.append(
            MillEvent(
                line=line,
                block=block,
                kind=kind,
                start_s=start,
                end_s=self.t,
                from_mm=from_mm,
                to_mm=self._mm(),
                what=what,
            )
        )

    def _note(self, note: str) -> None:
        if note not in self.notes:
            self.notes.append(note)

    def trajectory(self) -> MillTrajectory:
        positions: dict[str, list[float]] = {}
        for k, axis in enumerate(self.b.axes):
            positions[axis.joint_id] = [axis.joint(m[k]) for m in self.machine]
        if self.b.spindle is not None:
            positions[self.b.spindle] = list(self.spindle_deg)
        if self.b.carousel is not None:
            positions[self.b.carousel] = list(self.carousel_deg)
        if self.acc is None:
            self._note("No acceleration: every move starts and stops at full speed")
        else:
            self._note(
                f"Every move speeds up and slows down at {self.acc * 1000:g} mm/s^2 (a stand-in: "
                "no source read gives the axes' acceleration) and ends at rest: blending between "
                "blocks is not modelled"
            )
        return MillTrajectory(
            times=list(self.times),
            positions=positions,
            machine_mm=[[v * 1000 for v in m] for m in self.machine],
            axes=self.b.axes,
            spindle=self.b.spindle,
            carousel=self.b.carousel,
            events=self.events,
            cutting=self.cutting,
            spindle_rpm=self.spindle_rpm,
            tool_offsets=list(self.offsets.values()),
            tool=self.tool,
            units=self.setup.units,
            notes=self.notes,
        )


# ------------------------------------------------------------------------------- geometry
def _arc_by_radius(
    x0: float, y0: float, x1: float, y1: float, r: float, cw: bool, where: str
) -> tuple[float, float, float, float]:
    """The centre and sweep of an R arc: "a positive R-value for radii of 180° or less, and a
    negative R-value for radii more than 180°" (PDF p. 141)."""
    chord = math.hypot(x1 - x0, y1 - y0)
    radius = abs(r)
    if radius < chord / 2 - ARC_TOLERANCE_M:
        raise ProgramError(f"{where}: R {radius:.6f} m is shorter than half the chord")
    h = math.sqrt(max(radius * radius - chord * chord / 4, 0.0))
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    ux, uy = (x1 - x0) / chord, (y1 - y0) / chord
    # left of the chord for a CCW arc of 180 degrees or less; right for CW; R < 0 flips it
    side = (1.0 if not cw else -1.0) * (1.0 if r > 0 else -1.0)
    cx, cy = mx - uy * h * side, my + ux * h * side
    a0 = math.atan2(y0 - cy, x0 - cx)
    a1 = math.atan2(y1 - cy, x1 - cx)
    return cx, cy, _sweep(a0, a1, cw), radius


def _sweep(a0: float, a1: float, cw: bool) -> float:
    """The signed angle from ``a0`` to ``a1``, clockwise (negative) or not; a full turn when
    they meet, as "To cut a full circle, do not specify an ending point" (PDF p. 141)."""
    turn = 2 * math.pi
    ccw = (a1 - a0) % turn  # in [0, 2 pi)
    if ccw < 1e-12 or ccw > turn - 1e-12:
        return -turn if cw else turn
    return ccw - turn if cw else ccw


def _along(profile: list[tuple[float, float]], t: float) -> float:
    """The distance moved at ``t`` along a ``move_profile``: exact on its straight pieces, and its
    ramps are sampled every 0.01 s."""
    times = [p[0] for p in profile]
    if t >= times[-1]:
        return profile[-1][1]
    k = bisect.bisect_right(times, t)
    (t0, s0), (t1, s1) = profile[k - 1], profile[k]
    return s0 + (s1 - s0) * (t - t0) / (t1 - t0) if t1 > t0 else s1


def _unit(v: Sequence[float], what: str) -> tuple[float, float, float]:
    n = math.sqrt(sum(c * c for c in v))
    if len(v) != 3 or n == 0:
        raise ProgramError(f"{what} must be a non-zero 3-vector")
    return v[0] / n, v[1] / n, v[2] / n


def _first(exc: ValidationError) -> str:
    error = exc.errors()[0]
    field = ".".join(str(p) for p in error["loc"])
    return f"{field}: {error['msg']}" if field else str(error["msg"])


def describe_blocks(program: GcodeProgram) -> list[str]:
    """One line per block, for ``control show``."""
    head = [f"{program.number}" if program.number else "(no O number)"]
    return head + [f"  line {b.line:>3}  {b.text}" for b in program.blocks]


def plan_summary(trajectory: MillTrajectory) -> dict[str, Any]:
    """The numbers ``PROGRAM.md`` and the command line print."""
    cutting = sum(b - a for a, b in trajectory.cutting)
    return {
        "duration_s": trajectory.duration_s,
        "cutting_s": cutting,
        "points": len(trajectory.times),
        "end_mm": trajectory.machine_mm[-1],
    }
