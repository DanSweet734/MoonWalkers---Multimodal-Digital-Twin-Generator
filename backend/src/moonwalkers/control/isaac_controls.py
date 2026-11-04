"""MoonWalkers controls runner for Isaac Sim (decision 0025). Copied next to a twin's controls
file as ``run_controls.py``.

1. Open the twin's ``controls.usdc`` in Isaac Sim.
2. Open Window > Script Editor, paste this whole file into it (open it in a text editor, select
   all, copy), and click Run at the bottom. It prints the controls it found.
3. Choose what plays: select the ``Controls`` prim under the twin and, in the Property panel,
   set "Scenario on Play" to a scenario or to "live".
4. Press Play. A scenario sets the controls one after another, as an operator would, and shows
   each one in the Property panel. When it ends, or from the start with "live", the panel's
   controls are yours: plug in, insert the key, lift the paddle, choose a speed, pull the
   handles. Every refusal prints the manual's page.
5. Stop, then Play, starts again. Running this file again replaces the earlier runner; ``stop()``
   removes it.

On every physics step the runner sets the spindle's target velocity (degrees per second) and the
target position and velocity of the drive that carries the quill's spring: the quill's own, in
metres, or the downfeed handles', in degrees, where the T33901 has its spring (decision 0025).
The rules are the manual's, written into the stage by ``moonwalkers.control`` as JSON on the
``Controls`` prim (``moonwalkers:controls:spec``):

- the motor runs only when the machine is plugged in, the key is in and the paddle is up;
- the speed is one of the cited settings, changed only while unplugged;
- pulling moves the operator's hand down at the pull speed until the depth stop, where it presses
  on the stop; releasing hands the quill back to its spring;
- the spindle comes up to speed over the run-up time and coasts down over the coast-down time.

Physics steps come from Isaac Sim's ``SimulationManager`` (``PHYSICS_PRE_STEP``), or, if that is
not available, from ``omni.physx``'s step events. Set ``API = "omni.physx"`` below to force the
second. The pure parts (``Controller``, ``ScenarioPlayer``) are tested outside Isaac Sim.
"""

import builtins
import json
import sys

API = "auto"  # "auto", "simulation_manager" or "omni.physx"
PREFIX = "moonwalkers:controls:"
SPEC = PREFIX + "spec"
SCENARIO = PREFIX + "scenario"
SPEED = PREFIX + "speedRpm"
PULL = PREFIX + "pullHandles"
PULL_SPEED = PREFIX + "pullSpeedMmS"
MOTOR = PREFIX + "motorOn"
COMMANDED = PREFIX + "spindleRpmCommanded"
STATUS = PREFIX + "status"
LIVE = "live"
HANDLE = "_moonwalkers_controls_runner"
SAY = "MoonWalkers controls: "


class Refused(ValueError):
    """The manual does not allow, or does not describe, what was asked."""


class Controller:
    """The machine's controls and how its joints respond (decision 0025), stepped in time.

    ``spec`` is the JSON the stage carries: ``switch``, ``speed``, ``hand``, ``joints`` and
    ``scenarios`` (written by ``moonwalkers.control.manual``). Positions are in metres along the
    quill's joint axis, speeds in RPM, times in seconds.
    """

    def __init__(self, spec):
        self.spec = spec
        self.switch = spec["switch"]
        self.speed = spec["speed"]
        self.hand_spec = spec["hand"]
        self.quill = spec["joints"]["quill"]
        self.reset()

    def reset(self):
        self.inputs = {name: item["states"][0] for name, item in self.switch["inputs"].items()}
        self.rpm = float(self.speed["initial_rpm"])
        self.commanded_rpm = 0.0
        self.ramp = 0.0  # RPM per second, set when the motor starts or stops
        self.pulling = False
        self.pull_speed = float(self.hand_spec["live_pull_speed_m_s"])
        self.pull_to = None  # None: down to the depth stop
        self.hand = 0.0

    # ------------------------------------------------------------------------------- state
    @property
    def motor_on(self):
        return all(self.inputs[name] == state for name, state in self.switch["on_when"].items())

    def _state(self, name):
        return ("on" if self.motor_on else "off") if name == "motor" else self.inputs[name]

    # ------------------------------------------------------------------------------ commands
    def set_input(self, name, state, strict=True):
        """Move a switch input (power, key, paddle) to ``state``. A change the manual does not
        describe is refused when ``strict`` (a scenario), and done with a note when not (a
        person in the Property panel). Returns the lines to print."""
        if name not in self.inputs:
            raise Refused(f"the switch has no input '{name}'")
        if state not in self.switch["inputs"][name]["states"]:
            raise Refused(f"'{name}' cannot be '{state}'")
        if self.inputs[name] == state:
            return []
        lines = [f"{name} {state}"]
        for case in self.switch.get("not_described", []):
            if (
                case["input"] == name
                and case["to"] == state
                and all(self._state(k) == v for k, v in case["when"].items())
            ):
                if strict:
                    raise Refused(case["why"])
                lines.append(
                    f"not described by the manual: {case['why']}; the twin applies its rule"
                )
        was_on = self.motor_on
        self.inputs[name] = state
        if self.motor_on != was_on:
            self._motor_changed()
            lines.append("motor " + ("starts" if self.motor_on else "stops"))
        elif name == self.switch["start_input"] and state == self.switch["on_when"].get(name):
            failing = [k for k, v in self.switch["on_when"].items() if self.inputs[k] != v]
            why = "; ".join(
                self.switch["off_why"].get(k, f"{k} is {self.inputs[k]}") for k in failing
            )
            lines.append(f"the motor does not start: {why}")
        return lines

    def set_speed(self, rpm, strict=True):
        """Choose a spindle speed from the table; only while its rule allows it."""
        rpm = float(rpm)
        if rpm == self.rpm:
            return []
        if all(abs(rpm - row["rpm"]) > 1e-9 for row in self.speed["rows"]):
            raise Refused(f"{rpm:g} RPM is not one of the settings: {self.speed['table_why']}")
        if not all(self.inputs[k] == v for k, v in self.speed["change_only_when"].items()):
            raise Refused(self.speed["change_refused_why"])
        self.rpm = rpm
        belts = next((r.get("belts") for r in self.speed["rows"] if r["rpm"] == rpm), None)
        return [f"speed set to {rpm:g} RPM" + (f" (belts {belts})" if belts else "")]

    def pull(self, speed_m_s=None, to_m=None):
        """The operator pulls the handles down at ``speed_m_s``, to ``to_m`` or to the stop."""
        speed = float(speed_m_s if speed_m_s is not None else self.pull_speed)
        if speed <= 0:
            raise Refused("the pull speed must be above 0")
        if to_m is not None and not self.hand <= to_m <= self.quill["stop_m"]:
            raise Refused(
                f"a pull to {to_m:g} m must go down from the hand ({self.hand:g} m) and stay "
                f"above the depth stop ({self.quill['stop_m']:g} m)"
            )
        if not self.pulling:
            self.hand = self.quill["rest_m"]  # the hand takes the handles where they rest
        self.pulling, self.pull_speed, self.pull_to = True, speed, to_m
        where = "the depth stop" if to_m is None else f"{to_m * 1000:.1f} mm"
        return [f"pull the handles down to {where} at {speed * 1000:.2f} mm/s"]

    def release(self):
        if not self.pulling:
            return []
        self.pulling, self.pull_to = False, None
        return [f"release the handles: {self.hand_spec['release_why']}"]

    def pull_duration(self, speed_m_s, to_m=None):
        """How long a pull from where the hand is now takes (the hand is ideal)."""
        start = self.hand if self.pulling else self.quill["rest_m"]
        goal = self.quill["stop_m"] if to_m is None else to_m
        return max(goal - start, 0.0) / speed_m_s

    # --------------------------------------------------------------------------------- time
    def _motor_changed(self):
        seconds = self.speed["run_up_s"] if self.motor_on else self.speed["coast_down_s"]
        self.ramp = max(self.rpm, self.commanded_rpm) / seconds

    def step(self, dt):
        """Advance ``dt`` seconds. Returns the joints' targets for this step."""
        goal = self.rpm if self.motor_on else 0.0
        change = self.ramp * dt
        if self.commanded_rpm < goal:
            self.commanded_rpm = min(goal, self.commanded_rpm + change)
        else:
            self.commanded_rpm = max(goal, self.commanded_rpm - change)
        quill = self.quill
        if self.pulling:
            goal_m = quill["stop_m"] if self.pull_to is None else self.pull_to
            moving = self.hand < goal_m
            self.hand = min(goal_m, self.hand + self.pull_speed * dt)
            if self.hand >= goal_m and self.pull_to is None:  # pressing on the depth stop
                target, velocity = quill["stop_m"] + quill["press_past_m"], 0.0
            else:  # gravity holds the quill g/k past the drive's target, so the hand aims short
                target = self.hand - quill["gravity_offset_m"]
                velocity = self.pull_speed if moving and self.hand < goal_m else 0.0
        else:
            target, velocity = quill["spring_target_m"], 0.0
        return {
            "spindle_deg_s": self.commanded_rpm * 6.0 * self.speed["direction"],
            "quill_target_m": target,
            "quill_velocity_m_s": velocity,
            "motor_on": self.motor_on,
            "rpm": self.commanded_rpm,
        }


class ScenarioPlayer:
    """Plays a scenario's steps on a controller, one after another: a step starts when the one
    before it ends. A wait lasts its seconds, a pull lasts its distance over its speed, and the
    other steps take no time."""

    def __init__(self, controller, steps, strict=True):
        self.controller = controller
        self.steps = list(steps)
        self.strict = strict
        self.index = 0
        self.next_t = 0.0

    @property
    def done(self):
        return self.index >= len(self.steps)

    def advance(self, t):
        """Run every step that starts at or before ``t``. Returns (step number, start time,
        step, lines) for each."""
        ran = []
        while not self.done and self.next_t <= t + 1e-9:
            step = self.steps[self.index]
            start = self.next_t
            try:
                lines, seconds = self._run(step)
            except Refused as exc:
                if self.strict:
                    raise Refused(f"step {self.index + 1} ({step['do']}): {exc}") from exc
                lines, seconds = [f"refused: {exc}"], 0.0
            ran.append((self.index + 1, start, step, lines))
            self.index += 1
            self.next_t = start + seconds
        return ran

    def _run(self, step):
        c, do = self.controller, step["do"]
        if do == "wait":
            return [f"wait {step['s']:g} s"], float(step["s"])
        if do == "set_speed":
            return c.set_speed(step["rpm"], self.strict), 0.0
        if do == "set":
            return c.set_input(step["input"], step["state"], self.strict), 0.0
        if do == "pull":
            seconds = c.pull_duration(step["speed_m_s"], step.get("to_m"))
            return c.pull(step["speed_m_s"], step.get("to_m")), seconds
        if do == "release":
            return c.release(), 0.0
        raise Refused(f"unknown step '{do}'")

    def end_time(self):
        """When the last step ends, if the scenario were played from the start."""
        return self.next_t if self.done else None


# ------------------------------------------------------------------------------- Isaac Sim
def find_controls(stage):
    """The prim that carries the controls' JSON."""
    for prim in stage.Traverse():
        attr = prim.GetAttribute(SPEC)
        if attr and attr.HasAuthoredValue():
            return prim
    return None


def panel_inputs(prim, spec):
    """The switch inputs, speed, pull and pull speed as the Property panel holds them."""
    values = {}
    for name, item in spec["switch"]["inputs"].items():
        on = bool(prim.GetAttribute(PREFIX + item["attribute"]).Get())
        values[name] = item["states"][1] if on else item["states"][0]
    return (
        values,
        float(prim.GetAttribute(SPEED).Get() or spec["speed"]["initial_rpm"]),
        bool(prim.GetAttribute(PULL).Get()),
        float(prim.GetAttribute(PULL_SPEED).Get() or 0.0) / 1000.0,
    )


def show_inputs(prim, controller):
    """Write the controller's inputs into the Property panel (scenario mode)."""
    for name, item in controller.switch["inputs"].items():
        on = controller.inputs[name] == item["states"][1]
        _set(prim, PREFIX + item["attribute"], on)
    _set(prim, SPEED, f"{controller.rpm:g}")
    _set(prim, PULL, controller.pulling)


def apply_panel(prim, controller):
    """Bring the controller to what the Property panel says (live mode). A refused speed goes
    back in the panel. Returns the lines to print."""
    inputs, rpm, pulling, pull_speed = panel_inputs(prim, controller.spec)
    lines = []
    for name, state in inputs.items():
        lines += controller.set_input(name, state, strict=False)
    try:
        lines += controller.set_speed(rpm, strict=False)
    except Refused as exc:
        lines.append(f"refused: {exc}")
        _set(prim, SPEED, f"{controller.rpm:g}")
    if pull_speed > 0:
        controller.pull_speed = pull_speed
    if pulling and not controller.pulling:
        lines += controller.pull()
    elif not pulling and controller.pulling:
        lines += controller.release()
    return lines


def to_drive(drive, metres):
    """A position in metres of quill travel as the drive's own target (metres or degrees)."""
    return drive["scale"] * metres + drive["offset"]


def _set(prim, name, value):
    attr = prim.GetAttribute(name)
    if attr and attr.Get() != value:
        attr.Set(value)


def start():
    """Find the controls on the open stage and drive the joints on every physics step."""
    import omni.timeline
    import omni.usd
    from pxr import UsdPhysics

    stop()
    stage = omni.usd.get_context().get_stage()
    prim = find_controls(stage)
    if prim is None:
        print(SAY + "no controls on this stage (open controls.usdc)")
        return
    spec = json.loads(prim.GetAttribute(SPEC).Get())
    joints = spec["joints"]
    spindle = UsdPhysics.DriveAPI(stage.GetPrimAtPath(joints["spindle"]["path"]), "angular")
    hand = joints["quill"]["drive"]  # quill metres -> the drive's units: scale * m + offset
    quill = UsdPhysics.DriveAPI(stage.GetPrimAtPath(hand["path"]), hand["kind"])
    for drive in (spindle, quill):
        drive.CreateTargetPositionAttr()
        drive.CreateTargetVelocityAttr()
    controller = Controller(spec)
    timeline = omni.timeline.get_timeline_interface()
    state = {"last_t": None, "player": None, "run": 0}

    def on_step(*_args):
        t = float(timeline.get_current_time())
        if state["last_t"] is None or t < state["last_t"]:  # Play, or Stop then Play
            state["run"] += 1
            controller.reset()
            name = str(prim.GetAttribute(SCENARIO).Get() or LIVE)
            scenario = spec["scenarios"].get(name)
            state["player"] = (
                ScenarioPlayer(controller, scenario["steps"], False) if scenario else None
            )
            show_inputs(prim, controller)
            _set(prim, PULL_SPEED, controller.pull_speed * 1000.0)
            again = f" (run {state['run']})" if state["run"] > 1 else ""
            what = f"scenario '{name}'" if scenario else "live controls (the Property panel)"
            print(f"{SAY}first physics step at t = {t:.3f} s{again}: {what}")
            state["last_t"] = 0.0
        dt = max(t - state["last_t"], 0.0)
        state["last_t"] = t
        lines = []
        player = state["player"]
        if player is not None:
            for number, start_t, step, said in player.advance(t):
                lines += [f"t = {start_t:.2f} s, step {number} ({step['do']}): {s}" for s in said]
            show_inputs(prim, controller)
            if player.done:
                state["player"] = None
                lines.append(
                    f"t = {t:.2f} s: scenario finished; the Property panel's controls are live"
                )
        else:
            lines += [f"t = {t:.2f} s: {s}" for s in apply_panel(prim, controller)]
        targets = controller.step(dt)
        spindle.GetTargetVelocityAttr().Set(targets["spindle_deg_s"])
        quill.GetTargetPositionAttr().Set(to_drive(hand, targets["quill_target_m"]))
        quill.GetTargetVelocityAttr().Set(hand["scale"] * targets["quill_velocity_m_s"])
        _set(prim, MOTOR, targets["motor_on"])
        _set(prim, COMMANDED, round(targets["rpm"], 1))
        for line in lines:
            print(SAY + line)
        if lines:
            _set(prim, STATUS, lines[-1])

    api, handle = _subscribe(on_step)
    setattr(builtins, HANDLE, (api, handle))
    names = ", ".join([*spec["scenarios"], LIVE])
    paths = (
        f"spindle {joints['spindle']['path']}, quill {joints['quill']['path']} "
        f"(moved through {hand['path']})"
    )
    print(f"{SAY}{spec.get('machine', 'twin')}: scenarios {names}; {paths}")
    print(f"{SAY}driving the joints on each physics step through {api}; press Play")


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
    print(SAY + "stopped the earlier runner")


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
            print(f"{SAY}SimulationManager not usable ({exc}); using omni.physx")
    import omni.physx

    return "omni.physx", omni.physx.get_physx_interface().subscribe_physics_step_events(callback)


if __name__ == "__main__" or "omni.usd" in sys.modules:  # the Script Editor, not a test
    start()
