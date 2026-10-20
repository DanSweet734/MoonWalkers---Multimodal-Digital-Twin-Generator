"""Run an indexing program into joint targets over time, as the HA5C control would (decision 0016).

The control runs one step per Cycle Start, or the whole program with Parameter 10 = 2, "Continue
all programs until end code 99 or 95" (manual PDF p. 42). A simulation has no mill pressing Cycle
Start, so this runs the program that way, step after step, and records the spindle's target angle
over time as straight-line pieces: the drive moves at the step's feed rate, in degrees per second
("A feed rate of 270.000 means the spindle will rotate 270 degrees (270°) in one second", p. 34).

What each code does (manual pp. 33-37):

- G91 moves by S, L times; G90 moves to S; G28 and G88 return home (G90 to 0).
- G98 divides the circle into L equal steps; G97 waits L/10 s; G96 calls the subroutine at Step#,
  L times, which runs until G95 or G99; G95 or G99 in the main program ends it.
- G86, G87, G89, G92 and G93 only signal the mill or wait for it: no motion, and the simulation
  goes on at once. G94 adds the 250 ms delay the manual gives before the following step.

Choices the manual does not settle are settings, all [INFERENCE] (decision 0016):

- **Acceleration** is not modelled: Parameters 18 and 44 set it, and the manual gives no HA5C
  values. A target moves at the feed rate from the start of a step to its end.
- **Absolute moves** (G90, G28, G88) go straight to the programmed angle by default ("direct",
  so 450° back to home turns -450°). "shortest" takes the shorter way around instead, like the
  home options in Parameter 27.
- **The pause after each step** is Parameter 16, "Auto Continue Dwell" (0 to 9.9 s); its HA5C
  value is not given. The default 1 s stands in for the machining that would follow each index.
"""

from __future__ import annotations

import bisect
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .program import MAX_FEED_DEG_S, IndexProgram, IndexStep, ProgramError

AbsoluteMode = Literal["direct", "shortest"]
G94_DELAY_S = 0.25  # "a 250 millisecond delay is required before executing the following step"


class RunSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_feed_deg_s: float = Field(
        default=MAX_FEED_DEG_S,
        gt=0,
        description="the feed rate of a step without F: the manual's 'maximum feed rate'",
    )
    joint_max_deg_s: float | None = Field(
        default=None, gt=0, description="the twin joint's cited top speed; faster feeds are capped"
    )
    step_dwell_s: float = Field(default=1.0, ge=0, le=9.9, description="Parameter 16")
    absolute: AbsoluteMode = "direct"
    start_deg: float = 0.0
    max_moves: int = Field(default=10_000, ge=1, description="a guard against runaway programs")


class Waypoint(BaseModel):
    t: float = Field(description="seconds from the program's start")
    deg: float = Field(description="the joint's target angle")


class ProgramEvent(BaseModel):
    """One thing the program did: a move, a pause, or a signal to the mill."""

    step: int
    g: int
    loop: int
    start_s: float
    end_s: float
    start_deg: float
    end_deg: float
    what: str


class Trajectory(BaseModel):
    """The program's targets over time: straight lines between waypoints."""

    waypoints: list[Waypoint]
    events: list[ProgramEvent]
    notes: list[str] = Field(default_factory=list)

    @property
    def duration_s(self) -> float:
        return self.waypoints[-1].t

    @property
    def final_deg(self) -> float:
        return self.waypoints[-1].deg

    def angle_at(self, t: float) -> float:
        """The target angle at ``t`` seconds (held before the start and after the end)."""
        times = [w.t for w in self.waypoints]
        if t <= times[0]:
            return self.waypoints[0].deg
        if t >= times[-1]:
            return self.waypoints[-1].deg
        i = bisect.bisect_right(times, t)
        a, b = self.waypoints[i - 1], self.waypoints[i]
        return a.deg + (b.deg - a.deg) * (t - a.t) / (b.t - a.t)

    def velocity_at(self, t: float) -> float:
        """The target's speed at ``t`` (degrees per second): the slope of the piece holding it."""
        times = [w.t for w in self.waypoints]
        if t < times[0] or t >= times[-1]:
            return 0.0
        i = bisect.bisect_right(times, t)
        a, b = self.waypoints[i - 1], self.waypoints[i]
        return (b.deg - a.deg) / (b.t - a.t)


def run_program(program: IndexProgram, settings: RunSettings | None = None) -> Trajectory:
    """The trajectory of ``program`` run in auto-continue mode from ``settings.start_deg``."""
    runner = _Runner(program, settings or RunSettings())
    runner.run()
    return Trajectory(waypoints=runner.waypoints, events=runner.events, notes=runner.notes)


class _Runner:
    def __init__(self, program: IndexProgram, settings: RunSettings) -> None:
        self.steps = program.steps
        self.settings = settings
        self.t = 0.0
        self.deg = settings.start_deg
        self.waypoints = [Waypoint(t=0.0, deg=self.deg)]
        self.events: list[ProgramEvent] = []
        self.notes: list[str] = []
        self.moves = 0

    def run(self) -> None:
        for step in self.steps:
            if step.g in (95, 99):  # "the step preceding the G99 is the last one to be executed"
                return
            if step.g == 96:
                for loop in range(1, step.loops + 1):
                    self._subroutine(step, loop)
            else:
                self._execute(step)

    def _subroutine(self, call: IndexStep, loop: int) -> None:
        """Run from the call's Step# until G95 or G99, then return (manual PDF p. 34)."""
        for step in self.steps[(call.jump_to or 1) - 1 :]:
            if step.g in (95, 99):
                return
            self._execute(step, f"subroutine called by step {call.number:02d}, pass {loop}")

    def _execute(self, step: IndexStep, context: str = "") -> None:
        g, loops = step.g, step.loops
        suffix = f" ({context})" if context else ""
        if g == 91:
            for loop in range(1, loops + 1):
                self._move(step, loop, step.step_deg, f"incremental {step.step_deg:+g} deg{suffix}")
        elif g in (90, 28, 88):
            target = step.step_deg if g == 90 else 0.0
            for loop in range(1, loops + 1):
                what = "absolute" if g == 90 else "return home"
                self._move(step, loop, self._absolute(target), f"{what} to {target:g} deg{suffix}")
        elif g == 98:
            for loop in range(1, loops + 1):
                what = f"circle division {loop} of {loops}{suffix}"
                self._move(step, loop, 360.0 / loops, what)
        elif g == 97:
            self._wait(step, 1, loops / 10.0, f"dwell {loops / 10.0:g} s{suffix}")
        elif g == 94:
            what = f"pulse the CNC relay; run the next {loops} step(s) at once{suffix}"
            self._wait(step, 1, G94_DELAY_S, what)
        elif g in (86, 87, 93):
            names = {86: "CNC relay on", 87: "CNC relay off", 93: "pulse the CNC relay"}
            self._wait(step, 1, 0.0, f"{names[g]} (a signal to the mill; no motion){suffix}")
        elif g in (89, 92):
            what = "wait for the mill's remote input; the simulation goes on at once"
            self._wait(step, 1, 0.0, f"{what}{suffix}")
        else:  # unsupported codes are refused when the program is read
            raise ProgramError(f"step {step.number:02d}: G{g} cannot be run")

    def _absolute(self, target: float) -> float:
        delta = target - self.deg
        if self.settings.absolute == "shortest":
            delta = (delta + 180.0) % 360.0 - 180.0
        return delta

    def _feed(self, step: IndexStep) -> float:
        feed = step.feed_deg_s or self.settings.max_feed_deg_s
        limit = self.settings.joint_max_deg_s
        if limit is not None and feed > limit:
            note = (
                f"step {step.number:02d}: feed {feed:g} deg/s is above the joint's cited top speed "
                f"{limit:g} deg/s, so it runs at {limit:g}"
            )
            if note not in self.notes:
                self.notes.append(note)
            return limit
        return feed

    def _move(self, step: IndexStep, loop: int, delta: float, what: str) -> None:
        self.moves += 1
        if self.moves > self.settings.max_moves:
            raise ProgramError(f"the program makes more than {self.settings.max_moves} moves")
        feed = self._feed(step)
        start_t, start_deg = self.t, self.deg
        if delta != 0.0:
            self.t += abs(delta) / feed
            self.deg += delta
            self.waypoints.append(Waypoint(t=self.t, deg=self.deg))
        self.events.append(
            ProgramEvent(
                step=step.number,
                g=step.g,
                loop=loop,
                start_s=start_t,
                end_s=self.t,
                start_deg=start_deg,
                end_deg=self.deg,
                what=f"{what} at {feed:g} deg/s",
            )
        )
        if self.settings.step_dwell_s > 0:  # Parameter 16: a pause at the end of each step
            self.t += self.settings.step_dwell_s
            self.waypoints.append(Waypoint(t=self.t, deg=self.deg))

    def _wait(self, step: IndexStep, loop: int, seconds: float, what: str) -> None:
        start = self.t
        if seconds > 0:
            self.t += seconds
            self.waypoints.append(Waypoint(t=self.t, deg=self.deg))
        self.events.append(
            ProgramEvent(
                step=step.number,
                g=step.g,
                loop=loop,
                start_s=start,
                end_s=self.t,
                start_deg=self.deg,
                end_deg=self.deg,
                what=what,
            )
        )
