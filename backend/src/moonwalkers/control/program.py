"""An HA5C indexing program, as the 2006 operator's manual's step table holds it (decision 0016).

Each step has a step size or position (S, degrees, minus for the opposite direction), a feed rate
(F, degrees per second), a loop count (L) and a G code; for a G96 subroutine call the feed column
holds the step to jump to ("The Step# register replaces the feed rate register", manual PDF p. 34).
A program is written the way the manual prints it, one row per step::

    [step, step_size_deg, feed_deg_s_or_jump_step, loop_count, g_code]

and lives in a ``ControlBehavior`` of kind ``program_interpreter``, under ``spec["program"]``.
Limits and codes are the manual's (PDF pp. 33-35, cited in ``docs/decisions/0016``).
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from moonwalkers.contracts.pipeline_result import ControlBehavior, Source

MAX_STEPS = 99  # "There can be 99 different steps stored in memory."
MAX_STEP_DEG = 999.999  # "step sizes from .001 to 999.999°"
MAX_FEED_DEG_S = 270.0  # "The feed rate display ranges between 00.001 and 270.000"
MIN_FEED_DEG_S = 0.001
MAX_LOOPS = 999  # "three digits between 1 and 999"

MOTION_CODES = frozenset({28, 88, 90, 91, 98})  # moves the spindle
FLOW_CODES = frozenset({95, 96, 97, 99})  # subroutines, dwell, end
SIGNAL_CODES = frozenset({86, 87, 89, 92, 93, 94})  # CNC relay and remote input: no motion
UNSUPPORTED_CODES = {
    73: "G73 is a peck cycle for linear operation only; the HA5C is circular",
    85: "G85 fractional circle division: the manual does not say how its values are entered",
}
KNOWN_CODES = MOTION_CODES | FLOW_CODES | SIGNAL_CODES | frozenset(UNSUPPORTED_CODES)
PROGRAM_KEY = "program"


class ProgramError(ValueError):
    """The program cannot be run as the manual describes."""


class IndexStep(BaseModel):
    """One row of the step table."""

    model_config = ConfigDict(extra="forbid")

    number: int = Field(ge=1, le=MAX_STEPS)
    step_deg: float = Field(default=0.0, ge=-MAX_STEP_DEG, le=MAX_STEP_DEG)
    feed_deg_s: float | None = Field(
        default=None, description="None: the maximum feed rate (the manual's default)"
    )
    loops: int = Field(default=1, ge=1, le=MAX_LOOPS)
    g: int = 91
    jump_to: int | None = Field(default=None, description="G96 only: the subroutine's first step")

    @model_validator(mode="after")
    def _check(self) -> IndexStep:
        where = f"step {self.number:02d} (G{self.g})"
        if self.g not in KNOWN_CODES:
            raise ValueError(f"{where}: G{self.g} is not one of the manual's G codes")
        if self.g in UNSUPPORTED_CODES:
            raise ValueError(f"{where}: not supported: {UNSUPPORTED_CODES[self.g]}")
        if self.g == 96:
            if self.jump_to is None:
                raise ValueError(f"{where}: a subroutine call needs a jump destination (Step#)")
        elif self.jump_to is not None:
            raise ValueError(f"{where}: only G96 has a jump destination")
        if self.feed_deg_s is not None and not MIN_FEED_DEG_S <= self.feed_deg_s <= MAX_FEED_DEG_S:
            raise ValueError(
                f"{where}: feed rate {self.feed_deg_s} is outside {MIN_FEED_DEG_S}-{MAX_FEED_DEG_S}"
                " degrees per second"
            )
        if self.g == 98 and self.loops < 2:
            raise ValueError(f"{where}: circle division needs L from 2 to 999 divisions")
        return self

    @classmethod
    def from_row(cls, row: Sequence[Any]) -> IndexStep:
        """A row as the manual prints it: step, step size, feed rate (or Step# for G96), loop
        count, G code. An empty or zero feed means the default, the maximum feed rate."""
        if len(row) != 5:
            raise ValueError(f"a step row has 5 columns, not {len(row)}: {list(row)}")
        number, step, third, loops, g = row
        g = int(g)
        common = {"number": int(number), "step_deg": float(step), "loops": int(loops), "g": g}
        if g == 96:
            return cls(**common, jump_to=int(third))
        feed = float(third) if third not in (None, "", 0, 0.0) else None
        return cls(**common, feed_deg_s=feed)

    def row(self) -> list[Any]:
        third = self.jump_to if self.g == 96 else self.feed_deg_s
        return [self.number, self.step_deg, third, self.loops, self.g]


class IndexProgram(BaseModel):
    """The step table of one program (the control stores seven: Prog 0-6)."""

    model_config = ConfigDict(extra="forbid")

    steps: list[IndexStep] = Field(min_length=1, max_length=MAX_STEPS)

    @model_validator(mode="after")
    def _check(self) -> IndexProgram:
        numbers = [s.number for s in self.steps]
        if numbers != list(range(1, len(numbers) + 1)):
            raise ValueError(f"steps must be numbered 1, 2, 3, ... without gaps; got {numbers}")
        by_number = {s.number: s for s in self.steps}
        for step in self.steps:
            if step.g != 96:
                continue
            target = by_number.get(step.jump_to or 0)
            if target is None:
                raise ValueError(
                    f"step {step.number:02d}: G96 jumps to missing step {step.jump_to}"
                )
            for inner in self.steps[target.number - 1 :]:
                if inner.g in (95, 99):
                    break
                if inner.g == 96:
                    raise ValueError(
                        f"step {inner.number:02d}: a subroutine calls another one; "
                        "nesting of subroutine calls is not permitted"
                    )
        if not any(s.g in (95, 99) for s in self.steps) and len(self.steps) < MAX_STEPS:
            raise ValueError("the program has no end code (G99) after its last step")
        return self

    @classmethod
    def from_rows(cls, rows: Sequence[Sequence[Any]]) -> IndexProgram:
        steps = []
        for index, row in enumerate(rows, start=1):
            try:
                steps.append(IndexStep.from_row(row))
            except (TypeError, ValueError) as exc:
                raise ProgramError(f"row {index}: {_first_error(exc)}") from exc
        try:
            return cls(steps=steps)
        except ValueError as exc:
            raise ProgramError(_first_error(exc)) from exc

    @classmethod
    def from_behavior(cls, behavior: ControlBehavior) -> IndexProgram:
        """The program in a ``program_interpreter`` behaviour's ``spec["program"]``: a list of
        rows, or ``{"rows": [...]}`` (with optional ``columns``)."""
        if behavior.kind != "program_interpreter":
            raise ProgramError(
                f"behaviour {behavior.behavior_id} is a {behavior.kind}, not a program"
            )
        program = behavior.spec.get(PROGRAM_KEY)
        if program is None:
            raise ProgramError(f"behaviour {behavior.behavior_id} has no spec['{PROGRAM_KEY}']")
        rows = program.get("rows") if isinstance(program, dict) else program
        if not isinstance(rows, list):
            raise ProgramError(f"spec['{PROGRAM_KEY}'] must be a list of step rows")
        return cls.from_rows(rows)

    def rows(self) -> list[list[Any]]:
        return [s.row() for s in self.steps]


def runnable_behaviors(control: Sequence[ControlBehavior]) -> list[ControlBehavior]:
    """The behaviours that carry a program to run."""
    return [b for b in control if b.kind == "program_interpreter" and PROGRAM_KEY in b.spec]


class ProgramFile(BaseModel):
    """A program kept as a file: the behaviour that holds it and the sources it cites."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", description="for folder names")
    sources: list[Source] = Field(min_length=1)
    behavior: ControlBehavior

    @model_validator(mode="after")
    def _check(self) -> ProgramFile:
        known = {s.source_id for s in self.sources}
        unknown = sorted({c.source_id for c in self.behavior.citations} - known)
        if unknown:
            raise ValueError(f"the behaviour cites unknown sources: {unknown}")
        self.program()  # refuses a program that cannot be run
        return self

    def program(self) -> IndexProgram:
        return IndexProgram.from_behavior(self.behavior)

    @classmethod
    def load(cls, path: Path) -> ProgramFile:
        try:
            return cls.model_validate_json(Path(path).read_text(encoding="utf-8"))
        except ValidationError as exc:
            raise ProgramError(f"{Path(path).name}: {_first_error(exc)}") from exc


PROGRAMS_DIR = Path(__file__).with_name("programs")


def packaged_programs() -> dict[str, Path]:
    """The programs that ship with the package (the manual's examples), by name."""
    return {path.stem: path for path in sorted(PROGRAMS_DIR.glob("*.json"))}


def _first_error(exc: Exception) -> str:
    """A one-line reason: the first of pydantic's errors, with the field it concerns."""
    if isinstance(exc, ValidationError):
        error = exc.errors()[0]
        field = ".".join(str(part) for part in error["loc"])
        message = str(error["msg"]).removeprefix("Value error, ")
        return f"{field}: {message}" if field else message
    return str(exc)
