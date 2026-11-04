"""Run an indexing program into joint targets over time, as the HA5C control would (decisions 0016,
0026).

The control runs one step per Cycle Start, or the whole program with Parameter 10 = 2, "Continue
all programs until end code 99 or 95" (manual PDF p. 42). The interpreter records the spindle's
target angle over time as straight-line pieces: the drive moves at the step's feed rate, in
degrees per second ("A feed rate of 270.000 means the spindle will rotate 270 degrees (270°) in
one second", p. 34), and, from decision 0026, speeds up and slows down at the acceleration.

What each code does (manual pp. 33-37):

- G91 moves by S, L times; G90 moves to S; G28 and G88 return home (G90 to 0).
- G98 divides the circle into L equal steps; G97 waits L/10 s; G96 calls the subroutine at Step#,
  L times, which runs until G95 or G99; G95 or G99 in the main program ends it.
- The mill's two signals (p. 10: "Your equipment tells the Haas control to index (an input), it
  indexes, then sends a signal back to your equipment that the index (an output) has been
  completed"):
  - **the relay** (the output), set by Parameter 1 ("0: relay active during indexer motion; 1:
    relay pulsed for ¼ second at end of motion; 2: no relay action", p. 42) and by G86 (on), G87
    (off), G93 (pulse), G92 (pulse, then wait) and G94 (pulse at the beginning of the step, p. 36);
  - **the remote input** (cycle start): G89 and G92 wait for it, and with Parameter 10 = 0, "Stop
    after each step", every step does, except the L steps after a G94, which run "without waiting
    for start commands" (p. 36). G94 adds the manual's 250 ms.

Choices the manual does not settle are settings, all [INFERENCE] (decisions 0016 and 0026):

- **Acceleration** (Parameter 18): no HA5C value is published. The manuals say it "must be greater
  than or equal to Parameter 19, usually 2X" (2006, p. 43), so the stand-in is twice the top feed
  per second: 2 x 270 = 540 deg/s^2, a trapezoid (a triangle when a move is too short to reach its
  feed). Parameter 44's exponential smoothing has no value and is left out. ``None`` gives decision
  0016's motion, at full feed from start to end.
- **The relay:** Parameter 1 is not given for the HA5C either. By default it is 2 when the program
  uses G86, G87, G89, G92 or G93, as p. 33 asks, and 1 otherwise, the pulse that tells the mill
  the index is done. G93's pulse lasts ¼ s, like Parameter 1's.
- **The mill's answer:** a simulated mill sends the remote input ``mill_answer_s`` after the
  controller starts waiting, standing in for its own work (default 1 s). In Isaac Sim a person can
  press Cycle Start instead.
- **Absolute moves** (G90, G28, G88) go straight to the programmed angle by default ("direct",
  so 450° back to home turns -450°). "shortest" takes the shorter way around instead, like the
  home options in Parameter 27.
- **The pause after each step** is Parameter 16, "Auto Continue Dwell" (0 to 9.9 s), used only
  with auto continue; its HA5C value is not given. The default 1 s stands in for the machining.
"""

from __future__ import annotations

import bisect
import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .program import MAX_FEED_DEG_S, IndexProgram, IndexStep, ProgramError

AbsoluteMode = Literal["direct", "shortest"]
G94_DELAY_S = 0.25  # "a 250 millisecond delay is required before executing the following step"
RELAY_PULSE_S = 0.25  # Parameter 1 = 1: "relay pulsed for ¼ second at end of motion"
ACCELERATION_STAND_IN = 2 * MAX_FEED_DEG_S  # deg/s^2: Parameter 18 "usually 2X" (decision 0026)
RAMP_SAMPLE_S = 0.01  # waypoints along a speeding-up or slowing-down move
RELAY_CODES = frozenset({86, 87, 89, 92, 93})  # "used with the CNC relay function disabled"


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
    acceleration_deg_s2: float | None = Field(
        default=ACCELERATION_STAND_IN,
        gt=0,
        description="Parameter 18 as degrees per second squared (a stand-in); None: none",
    )
    relay: Literal[0, 1, 2] | None = Field(
        default=None, description="Parameter 1; None: 2 if the program uses relay codes, else 1"
    )
    continue_mode: Literal["auto", "step"] = Field(
        default="auto", description="Parameter 10: 2 (auto) or 0, 'Stop after each step' (step)"
    )
    mill_answer_s: float = Field(
        default=1.0, ge=0, description="how long the simulated mill takes to send cycle start"
    )


class Waypoint(BaseModel):
    t: float = Field(description="seconds from the program's start")
    deg: float = Field(description="the joint's target angle")


class ProgramEvent(BaseModel):
    """One thing the program did: a move, a pause, or a signal to or from the mill."""

    step: int
    g: int
    loop: int
    start_s: float
    end_s: float
    start_deg: float
    end_deg: float
    what: str


class RelaySpan(BaseModel):
    """The CNC relay closed from ``start_s`` to ``end_s``: the signal to the mill."""

    start_s: float
    end_s: float
    why: str


class Wait(BaseModel):
    """The controller waits for the remote input (cycle start) from ``start_s``; the simulated
    mill answers ``hold_s`` later."""

    start_s: float
    hold_s: float
    step: int
    why: str


class Trajectory(BaseModel):
    """The program's targets over time: straight lines between waypoints."""

    waypoints: list[Waypoint]
    events: list[ProgramEvent]
    notes: list[str] = Field(default_factory=list)
    relay: list[RelaySpan] = Field(default_factory=list)
    waits: list[Wait] = Field(default_factory=list)
    relay_parameter: int = 1

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

    def relay_at(self, t: float) -> bool:
        return any(span.start_s <= t < span.end_s for span in self.relay)


def move_profile(
    distance: float, feed: float, acceleration: float | None
) -> list[tuple[float, float]]:
    """A move of ``distance`` degrees (signed) at ``feed``: (seconds, degrees moved) from its
    start to its end. Without acceleration it is one straight piece; with it, a trapezoid of speed,
    or a triangle when the move is too short to reach its feed, sampled every 0.01 s on the
    ramps."""
    d = abs(distance)
    sign = math.copysign(1.0, distance)
    if d == 0:
        return [(0.0, 0.0)]
    if acceleration is None:
        return [(0.0, 0.0), (d / feed, distance)]
    if feed * feed / acceleration >= d:  # a triangle: it never reaches its feed
        ramp = math.sqrt(d / acceleration)
        peak = acceleration * ramp
    else:
        ramp, peak = feed / acceleration, feed
    cruise = (d - peak * ramp) / peak  # the time at full feed (0 for a triangle)
    total = 2 * ramp + cruise

    def moved(t: float) -> float:
        if t <= ramp:
            return 0.5 * acceleration * t * t
        if t <= ramp + cruise:
            return 0.5 * peak * ramp + peak * (t - ramp)
        left = total - t
        return d - 0.5 * acceleration * left * left

    times = [k * RAMP_SAMPLE_S for k in range(math.ceil(ramp / RAMP_SAMPLE_S))]
    times += [ramp, ramp + cruise]
    times += [ramp + cruise + k * RAMP_SAMPLE_S for k in range(1, math.ceil(ramp / RAMP_SAMPLE_S))]
    times.append(total)
    points = sorted({round(t, 12) for t in times if 0 <= t <= total})
    return [(t, sign * moved(t)) for t in points]


def run_program(program: IndexProgram, settings: RunSettings | None = None) -> Trajectory:
    """The trajectory of ``program`` run from ``settings.start_deg``."""
    settings = settings or RunSettings()
    runner = _Runner(program, settings)
    runner.run()
    return Trajectory(
        waypoints=runner.waypoints,
        events=runner.events,
        notes=runner.notes,
        relay=runner.relay,
        waits=runner.waits,
        relay_parameter=runner.relay_parameter,
    )


class _Runner:
    def __init__(self, program: IndexProgram, settings: RunSettings) -> None:
        self.steps = program.steps
        self.settings = settings
        self.t = 0.0
        self.deg = settings.start_deg
        self.waypoints = [Waypoint(t=0.0, deg=self.deg)]
        self.events: list[ProgramEvent] = []
        self.notes: list[str] = []
        self.relay: list[RelaySpan] = []
        self.waits: list[Wait] = []
        self.moves = 0
        uses_codes = any(s.g in RELAY_CODES for s in self.steps)
        self.relay_parameter = (
            settings.relay if settings.relay is not None else (2 if uses_codes else 1)
        )
        if uses_codes and self.relay_parameter != 2:
            self.notes.append(
                "the program uses G86, G87, G89, G92 or G93, which 'should be used with the CNC "
                f"relay function disabled (Parameter 1 = 2)' (p. 33); Parameter 1 is "
                f"{self.relay_parameter}"
            )
        self.relay_on_since: float | None = None
        self.free_steps = 0  # steps a G94 runs without waiting for start commands

    def run(self) -> None:
        for step in self.steps:
            if step.g in (95, 99):  # "the step preceding the G99 is the last one to be executed"
                break
            if step.g == 96:
                for loop in range(1, step.loops + 1):
                    self._subroutine(step, loop)
            else:
                self._execute(step)
        self._drop_last_wait()
        if self.relay_on_since is not None:  # G86 with no G87: closed to the end
            self.relay.append(RelaySpan(start_s=self.relay_on_since, end_s=self.t, why="G86"))

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
            self._step_done(step)
        elif g == 94:
            self._pulse(step, "G94: pulse at the beginning of the step")
            what = f"pulse the CNC relay; run the next {loops} step(s) at once{suffix}"
            self._wait(step, 1, G94_DELAY_S, what)
            self.free_steps = loops
        elif g == 86:
            if self.relay_on_since is None:
                self.relay_on_since = self.t
            self._wait(step, 1, 0.0, f"CNC relay on (a signal to the mill){suffix}")
        elif g == 87:
            if self.relay_on_since is not None:
                self.relay.append(
                    RelaySpan(start_s=self.relay_on_since, end_s=self.t, why="G86-G87")
                )
                self.relay_on_since = None
            self._wait(step, 1, 0.0, f"CNC relay off{suffix}")
        elif g == 93:
            self._pulse(step, "G93")
            self._wait(step, 1, 0.0, f"pulse the CNC relay (a signal to the mill){suffix}")
        elif g in (89, 92):
            if g == 92:
                self._pulse(step, "G92")
            what = "pulse the CNC relay and wait" if g == 92 else "wait"
            self._remote_input(step, f"{what} for the mill's remote input{suffix}")
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
            for dt, moved in move_profile(delta, feed, self.settings.acceleration_deg_s2)[1:]:
                self.waypoints.append(Waypoint(t=start_t + dt, deg=start_deg + moved))
            self.t, self.deg = self.waypoints[-1].t, start_deg + delta
            self.waypoints[-1] = Waypoint(t=self.t, deg=self.deg)
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
        if self.relay_parameter == 0 and self.t > start_t:
            self.relay.append(RelaySpan(start_s=start_t, end_s=self.t, why="Parameter 1 = 0"))
        if self.relay_parameter == 1:
            self.relay.append(
                RelaySpan(start_s=self.t, end_s=self.t + RELAY_PULSE_S, why="Parameter 1 = 1")
            )
        self._step_done(step)

    def _step_done(self, step: IndexStep) -> None:
        """After a step: Parameter 16's pause (auto continue), or a wait for cycle start."""
        if self.settings.continue_mode == "step":
            if self.free_steps > 0:
                self.free_steps -= 1
            else:
                self._remote_input(step, "stopped after the step: wait for cycle start")
        elif self.settings.step_dwell_s > 0:  # Parameter 16: a pause at the end of each step
            self.t += self.settings.step_dwell_s
            self.waypoints.append(Waypoint(t=self.t, deg=self.deg))

    def _remote_input(self, step: IndexStep, why: str) -> None:
        hold = self.settings.mill_answer_s
        self.waits.append(Wait(start_s=self.t, hold_s=hold, step=step.number, why=why))
        self._wait(step, 1, hold, f"{why}; the simulated mill answers after {hold:g} s")

    def _pulse(self, step: IndexStep, why: str) -> None:
        self.relay.append(RelaySpan(start_s=self.t, end_s=self.t + RELAY_PULSE_S, why=why))

    def _drop_last_wait(self) -> None:
        """The program ends after its last step: a stop-after-step wait there is not needed."""
        if self.waits and self.waits[-1].start_s + self.waits[-1].hold_s == self.t:
            last = self.waits[-1]
            if last.why.startswith("stopped after the step"):
                self.waits.pop()
                self.t = last.start_s
                while self.waypoints[-1].t > self.t:
                    self.waypoints.pop()
                self.events.pop()

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
