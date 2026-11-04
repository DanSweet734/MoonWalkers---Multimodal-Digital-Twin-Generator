"""MoonWalkers program runner for Isaac Sim (decision 0016). Copied next to a program file as
``run_program.py``.

1. Open the program's ``program.usdc`` in Isaac Sim.
2. Open Window > Script Editor, paste this whole file into it (open it in a text editor, select
   all, copy), and click Run at the bottom. It prints what it found.
3. Press Play. On every physics step the runner sets the joint's drive target to the program's
   planned angle at that moment, and its target velocity to the planned speed, so the drive does
   not trail behind.
4. Press Stop, then Play, to run the program again from the start; the runner prints its lines
   again. Running this file again replaces the earlier runner; ``stop()`` removes it.
5. The mill's signals (decision 0026): the runner prints when the CNC relay closes and opens, and
   shows it in the joint's "CNC relay (to the mill)" attribute. Where the controller waits for
   the mill's cycle start, a simulated mill answers after its planned time. To press Cycle Start
   yourself instead, select the joint and, in the Property panel, tick "Hold for Cycle Start"
   before Play; at each wait, tick "Cycle Start" to go on.

The program's motion is stored in the stage itself: every joint with the attributes
``moonwalkers:program:times`` (seconds) and ``moonwalkers:program:anglesDeg`` (degrees), written by
``moonwalkers.control``. Between those points the target moves in a straight line.

Physics steps come from Isaac Sim's ``SimulationManager`` (``PHYSICS_PRE_STEP``), or, if that is
not available, from ``omni.physx``'s step events. Set ``API = "omni.physx"`` below to force the
second, for example if Play prints no "first physics step" line.
"""

import bisect
import builtins
import itertools
import sys

API = "auto"  # "auto", "simulation_manager" or "omni.physx"
TIMES = "moonwalkers:program:times"
ANGLES = "moonwalkers:program:anglesDeg"
NAME = "moonwalkers:program:name"
RELAY_TIMES = "moonwalkers:program:relayTimes"  # start, end, start, end, ... (seconds)
WAIT_STARTS = "moonwalkers:program:waitStarts"  # where the controller waits for cycle start
WAIT_HOLDS = "moonwalkers:program:waitHolds"  # how long the simulated mill takes to answer
HOLD = "moonwalkers:program:holdForCycleStart"  # the panel: wait for a person's press
CYCLE_START = "moonwalkers:program:cycleStart"  # the panel: the press, reset by the runner
RELAY = "moonwalkers:program:cncRelay"  # the panel: the relay's state, set by the runner
HANDLE = "_moonwalkers_program_runner"


class Program:
    """One joint's planned motion."""

    def __init__(self, joint_path, name, times, angles, relay=(), waits=()):
        if len(times) != len(angles) or len(times) < 1:
            raise ValueError(f"{joint_path}: the program needs as many times as angles")
        if any(b < a for a, b in itertools.pairwise(times)):
            raise ValueError(f"{joint_path}: the program's times must not go backwards")
        if len(relay) % 2:
            raise ValueError(f"{joint_path}: the relay's times come in pairs (closed, open)")
        self.joint_path = joint_path
        self.name = name
        self.times = list(times)
        self.angles = list(angles)
        self.relay = [(relay[i], relay[i + 1]) for i in range(0, len(relay), 2)]
        self.waits = list(waits)  # (start, hold) pairs

    def relay_at(self, t):
        """Whether the CNC relay is closed at plan time ``t``."""
        return any(start <= t < end for start, end in self.relay)

    @property
    def duration(self):
        return self.times[-1]

    def target_at(self, t):
        """(angle in degrees, speed in degrees per second) of the target at ``t`` seconds."""
        times, angles = self.times, self.angles
        if t <= times[0]:
            return angles[0], 0.0
        if t >= times[-1]:
            return angles[-1], 0.0
        i = bisect.bisect_right(times, t)
        t0, t1, a0, a1 = times[i - 1], times[i], angles[i - 1], angles[i]
        if t1 == t0:
            return a1, 0.0
        speed = (a1 - a0) / (t1 - t0)
        return a0 + speed * (t - t0), speed


class Progress:
    """What the runner prints as the timeline runs. A run starts on the first physics step, and
    again whenever the timeline's time goes back, as it does on Stop, then Play."""

    def __init__(self, programs):
        self.programs = programs
        self.runs = 0
        self.last_t = None
        self.finished = set()

    def lines(self, t):
        """The lines to print on the physics step at timeline time ``t`` (seconds)."""
        lines = []
        if self.last_t is None or t < self.last_t:
            self.runs += 1
            self.finished = set()
            again = f" (run {self.runs})" if self.runs > 1 else ""
            lines.append(f"MoonWalkers runner: first physics step at t = {t:.3f} s{again}")
        self.last_t = t
        for program in self.programs:
            if t >= program.duration and program.joint_path not in self.finished:
                self.finished.add(program.joint_path)
                lines.append(
                    f"MoonWalkers runner: '{program.name}' finished at {program.duration:.3f} s, "
                    f"target {program.angles[-1]:.3f} deg"
                )
        return lines


class PlanClock:
    """The program's own time. It runs with the timeline, except that with ``hold`` it stops
    at each wait for cycle start until a press, then goes on from the end of that wait, as the
    controller does when the mill (or a person) sends cycle start."""

    def __init__(self, waits):
        self.waits = sorted(waits)
        self.reset()

    def reset(self):
        self.offset = 0.0
        self.next = 0
        self.holding = False

    def advance(self, t, hold, pressed):
        """The plan time at timeline time ``t``, and whether a press was used."""
        plan = t - self.offset
        if not hold or self.next >= len(self.waits):
            if self.next < len(self.waits) and plan >= sum(self.waits[self.next]):
                self.next += 1  # the simulated mill answered this wait
            return plan, False
        start, wait = self.waits[self.next]
        if plan < start:
            return plan, False
        if pressed:
            self.offset = t - (start + wait)
            self.next += 1
            self.holding = False
            return start + wait, True
        self.holding = True
        self.offset = t - start
        return start, False


def find_programs(stage):
    """Every joint on the stage that carries a program."""
    programs = []
    for prim in stage.Traverse():
        times, angles = prim.GetAttribute(TIMES), prim.GetAttribute(ANGLES)
        if not (times and angles and times.HasAuthoredValue() and angles.HasAuthoredValue()):
            continue
        name = prim.GetAttribute(NAME)
        relay = _floats(prim.GetAttribute(RELAY_TIMES))
        starts = _floats(prim.GetAttribute(WAIT_STARTS))
        holds = _floats(prim.GetAttribute(WAIT_HOLDS))
        programs.append(
            Program(
                str(prim.GetPath()),
                name.Get() if name and name.HasAuthoredValue() else "program",
                [float(v) for v in times.Get()],
                [float(v) for v in angles.Get()],
                relay,
                list(zip(starts, holds, strict=True)),
            )
        )
    return programs


def start():
    """Find the programs on the open stage and drive their joints on every physics step."""
    import omni.timeline
    import omni.usd
    from pxr import UsdPhysics

    stop()
    stage = omni.usd.get_context().get_stage()
    programs = find_programs(stage)
    if not programs:
        print("MoonWalkers runner: no joint with a program on this stage (open program.usdc)")
        return
    timeline = omni.timeline.get_timeline_interface()
    drives = []
    for program in programs:
        prim = stage.GetPrimAtPath(program.joint_path)
        drive = UsdPhysics.DriveAPI(prim, "angular")
        drive.CreateTargetPositionAttr()
        drive.CreateTargetVelocityAttr()
        drives.append((drive, program, prim, PlanClock(program.waits), {"relay": None}))
    progress = Progress(programs)
    say = "MoonWalkers runner: "

    def on_step(*_args):
        t = float(timeline.get_current_time())
        restart = progress.last_t is None or t < progress.last_t
        for drive, program, prim, clock, seen in drives:
            if restart:
                clock.reset()
                seen["relay"] = None
            hold = bool(_get(prim, HOLD, False))
            pressed = hold and clock.holding and bool(_get(prim, CYCLE_START, False))
            was_holding = clock.holding
            plan_t, used = clock.advance(t, hold, pressed)
            if used:
                _put(prim, CYCLE_START, False)
                print(f"{say}Cycle Start at t = {t:.2f} s: plan time {plan_t:.2f} s")
            elif clock.holding and not was_holding:
                print(f"{say}waiting for Cycle Start at plan time {plan_t:.2f} s")
            angle, speed = program.target_at(plan_t)
            drive.GetTargetPositionAttr().Set(angle)
            drive.GetTargetVelocityAttr().Set(0.0 if clock.holding else speed)
            relay = program.relay_at(plan_t)
            if relay != seen["relay"]:
                if seen["relay"] is not None:
                    state = "closes (a signal to the mill)" if relay else "opens"
                    print(f"{say}CNC relay {state} at plan time {plan_t:.2f} s")
                seen["relay"] = relay
                _put(prim, RELAY, relay)
        for line in progress.lines(t):
            print(line)

    api, handle = _subscribe(on_step)
    setattr(builtins, HANDLE, (api, handle))
    for program in programs:
        print(
            f"MoonWalkers runner: '{program.name}' on {program.joint_path}: "
            f"{len(program.times)} points over {program.duration:.3f} s"
        )
    print(
        f"MoonWalkers runner: driving the joint(s) on each physics step through {api}; press Play"
    )


def _floats(attr):
    return [float(v) for v in attr.Get()] if attr and attr.HasAuthoredValue() else []


def _get(prim, name, default):
    attr = prim.GetAttribute(name)
    value = attr.Get() if attr else None
    return default if value is None else value


def _put(prim, name, value):
    attr = prim.GetAttribute(name)
    if attr and attr.Get() != value:
        attr.Set(value)


def stop():
    """Remove a runner started earlier in this Isaac Sim session."""
    previous = getattr(builtins, HANDLE, None)
    if previous is None:
        return
    api, handle = previous
    if api == "simulation_manager":
        from isaacsim.core.simulation_manager import SimulationManager

        SimulationManager.deregister_callback(handle)
    elif hasattr(handle, "unsubscribe"):
        handle.unsubscribe()
    setattr(builtins, HANDLE, None)
    print("MoonWalkers runner: stopped the earlier runner")


def _subscribe(callback):
    if API in ("auto", "simulation_manager"):
        try:
            from isaacsim.core.simulation_manager import SimulationEvent, SimulationManager

            uid = SimulationManager.register_callback(
                callback, event=SimulationEvent.PHYSICS_PRE_STEP
            )
            return "simulation_manager", uid
        except (ImportError, AttributeError, ValueError) as exc:
            if API == "simulation_manager":
                raise
            print(f"MoonWalkers runner: SimulationManager not usable ({exc}); using omni.physx")
    import omni.physx

    return "omni.physx", omni.physx.get_physx_interface().subscribe_physics_step_events(callback)


if __name__ == "__main__" or "omni.usd" in sys.modules:  # the Script Editor, not a test
    start()
