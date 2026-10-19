"""MoonWalkers program runner for Isaac Sim (decision 0016). Copied next to a program file as
``run_program.py``.

1. Open the program's ``program.usdc`` in Isaac Sim.
2. Open Window > Script Editor, paste this whole file into it (open it in a text editor, select
   all, copy), and click Run at the bottom. It prints what it found.
3. Press Play. On every physics step the runner sets the joint's drive target to the program's
   planned angle at that moment, and its target velocity to the planned speed, so the drive does
   not trail behind.
4. Press Stop, then Play, to run the program again from the start. Running this file again
   replaces the earlier runner; ``stop()`` removes it.

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
HANDLE = "_moonwalkers_program_runner"


class Program:
    """One joint's planned motion."""

    def __init__(self, joint_path, name, times, angles):
        if len(times) != len(angles) or len(times) < 1:
            raise ValueError(f"{joint_path}: the program needs as many times as angles")
        if any(b < a for a, b in itertools.pairwise(times)):
            raise ValueError(f"{joint_path}: the program's times must not go backwards")
        self.joint_path = joint_path
        self.name = name
        self.times = list(times)
        self.angles = list(angles)

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


def find_programs(stage):
    """Every joint on the stage that carries a program."""
    programs = []
    for prim in stage.Traverse():
        times, angles = prim.GetAttribute(TIMES), prim.GetAttribute(ANGLES)
        if not (times and angles and times.HasAuthoredValue() and angles.HasAuthoredValue()):
            continue
        name = prim.GetAttribute(NAME)
        programs.append(
            Program(
                str(prim.GetPath()),
                name.Get() if name and name.HasAuthoredValue() else "program",
                [float(v) for v in times.Get()],
                [float(v) for v in angles.Get()],
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
        drive = UsdPhysics.DriveAPI(stage.GetPrimAtPath(program.joint_path), "angular")
        drive.CreateTargetPositionAttr()
        drive.CreateTargetVelocityAttr()
        drives.append((drive, program))
    state = {"first": True, "finished": set()}

    def on_step(*_args):
        t = float(timeline.get_current_time())
        if state["first"]:
            print(f"MoonWalkers runner: first physics step at t = {t:.3f} s")
            state["first"] = False
        for drive, program in drives:
            angle, speed = program.target_at(t)
            drive.GetTargetPositionAttr().Set(angle)
            drive.GetTargetVelocityAttr().Set(speed)
            if t >= program.duration and program.joint_path not in state["finished"]:
                state["finished"].add(program.joint_path)
                print(
                    f"MoonWalkers runner: '{program.name}' finished at {program.duration:.3f} s, "
                    f"target {program.angles[-1]:.3f} deg"
                )

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
