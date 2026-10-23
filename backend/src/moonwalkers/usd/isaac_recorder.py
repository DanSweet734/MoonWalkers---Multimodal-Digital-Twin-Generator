"""MoonWalkers joint recorder for Isaac Sim (drill-press plan, Phase 1). Copied into a run folder as
``record_joints.py``.

1. Open a twin's file in Isaac Sim.
2. Open Window > Script Editor, paste this whole file into it, and click Run. It prints the
   articulation it will record.
3. Press Play. After every physics step it records the timeline's time and every joint's position:
   radians for joints that turn and metres for joints that slide. It reads them through
   ``omni.physics.tensors``, whose ``get_dof_positions`` "returns the positions in radians for
   rotational DOFs".
4. It writes the recording to ``recordings/<file>_<date>_<time>.csv`` next to the opened file,
   every half second and when a run ends, and prints the path. Stop, then Play, starts a new
   recording. Running this file again replaces the earlier recorder; ``stop()`` removes it.

So a check is measured, not only seen: how fast the spring returns the quill, where the depth stop
ends its travel, and how closely the handles follow. Physics steps come from Isaac Sim's
``SimulationManager`` (``PHYSICS_POST_STEP``), or, if that is not available, from ``omni.physx``'s
step events, as the program runner does (``moonwalkers.control.isaac_runner``).
"""

import builtins
import datetime
import math
import pathlib
import sys

API = "auto"  # "auto", "simulation_manager" or "omni.physx"
HANDLE = "_moonwalkers_joint_recorder"
WRITE_EVERY = 30  # physics steps: half a second at 60 steps per second
UNITS = {0: "rad", 1: "m"}  # omni.physics.tensors DofType: 0 rotation, 1 translation


class Recording:
    """One run's joint positions, written as CSV: ``time_s`` then one column per joint."""

    def __init__(self, names, kinds):
        if len(names) != len(kinds):
            raise ValueError("every joint needs a kind (0 for turning, 1 for sliding)")
        self.columns = ["time_s"] + [f"{n} ({UNITS.get(k, '?')})" for n, k in zip(names, kinds)]
        self.rows = []

    def add(self, t, positions):
        if len(positions) != len(self.columns) - 1:
            raise ValueError(f"expected {len(self.columns) - 1} positions, got {len(positions)}")
        self.rows.append([float(t)] + [float(p) for p in positions])

    def csv_text(self):
        lines = [",".join(self.columns)]
        lines += [",".join(_number(v) for v in row) for row in self.rows]
        return "\n".join(lines) + "\n"


class Recorder:
    """Starts a new recording on the first step, and again whenever the timeline's time goes
    back (Stop, then Play). Says when a recording should be written."""

    def __init__(self, names, kinds, path_for_run):
        self.names, self.kinds = list(names), list(kinds)
        self.path_for_run = path_for_run  # run number -> where to write that run
        self.runs = 0
        self.last_t = None
        self.recording = None
        self.path = None

    def step(self, t, positions):
        """Record one step. Returns the (path, text) pairs to write now: a finished run, and the
        current one every ``WRITE_EVERY`` steps."""
        writes = []
        if self.recording is None or t < self.last_t:
            if self.recording is not None:
                writes.append((self.path, self.recording.csv_text()))
            self.runs += 1
            self.recording = Recording(self.names, self.kinds)
            self.path = self.path_for_run(self.runs)
        self.last_t = t
        self.recording.add(t, positions)
        if len(self.recording.rows) % WRITE_EVERY == 0:
            writes.append((self.path, self.recording.csv_text()))
        return writes

    def flush(self):
        return [] if self.recording is None else [(self.path, self.recording.csv_text())]


def recording_path(stage_path, run, now=None):
    """``recordings/<file>_<date>_<time>[_run<N>].csv`` beside the opened file."""
    stage_path = pathlib.Path(stage_path)
    stamp = (now or datetime.datetime.now()).strftime("%Y-%m-%d_%H%M%S")
    suffix = "" if run == 1 else f"_run{run}"
    return stage_path.parent / "recordings" / f"{stage_path.stem}_{stamp}{suffix}.csv"


def _number(value):
    return repr(value) if math.isfinite(value) else "nan"


def _write(writes):
    for path, text in writes:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")


def dof_row(positions, count):
    """The first articulation's joint positions from a tensor-API array. That is a NumPy array, a
    warp array (``.numpy()``) or a torch tensor (``.cpu().numpy()``), shaped (articulations,
    max_dofs)."""
    if hasattr(positions, "cpu"):
        positions = positions.cpu()
    if hasattr(positions, "numpy"):
        positions = positions.numpy()
    flat = positions.reshape(-1) if hasattr(positions, "reshape") else positions
    return [float(v) for v in list(flat)[:count]]


def _articulation_view(root):
    """A tensor-API view of the articulation at ``root``. It is Isaac Sim's own simulation
    view (``SimulationManager.get_physics_simulation_view``) when there is one. Otherwise it is a
    new view made as ``SimulationManager`` makes its own: with the open stage's id and the
    subspace roots set. The default stage id, -1, failed in Isaac Sim 6.2.0 on 2026-10-23 with
    "Failed to get a valid attached USD stage id from PhysX simulation"."""
    sim_view = None
    try:
        from isaacsim.core.simulation_manager import SimulationManager

        sim_view = SimulationManager.get_physics_simulation_view()
    except (ImportError, AttributeError):
        pass
    if sim_view is None:
        import omni.usd
        from omni.physics import tensors

        stage_id = omni.usd.get_context().get_stage_id()
        sim_view = tensors.create_simulation_view("numpy", stage_id=stage_id)
        sim_view.set_subspace_roots("/")
    return sim_view, sim_view.create_articulation_view(root)


def find_articulation(stage):
    """The path of the first prim with ``PhysicsArticulationRootAPI`` (the twin's top prim)."""
    from pxr import UsdPhysics

    for prim in stage.Traverse():
        if prim.HasAPI(UsdPhysics.ArticulationRootAPI):
            return str(prim.GetPath())
    return None


def start():
    """Record the open stage's articulation on every physics step."""
    import omni.timeline
    import omni.usd

    stop()
    stage = omni.usd.get_context().get_stage()
    root = find_articulation(stage)
    if root is None:
        print("MoonWalkers recorder: no articulation on this stage (open a twin with joints)")
        return
    stage_path = stage.GetRootLayer().realPath or str(pathlib.Path.home() / "twin.usd")
    timeline = omni.timeline.get_timeline_interface()
    state = {"view": None, "recorder": None, "failed": False, "last_t": None}
    started = datetime.datetime.now()

    def on_step(*_args):
        t = float(timeline.get_current_time())
        if state["last_t"] is None or t < state["last_t"]:  # a new Play: Stop ends the old view
            state["view"], state["failed"] = None, False
        state["last_t"] = t
        if state["failed"]:
            return
        if state["view"] is None:  # the physics view exists only once the simulation runs
            try:
                state["view"] = _articulation_view(root)
                meta = state["view"][1].shared_metatype
                if state["recorder"] is None:
                    state["recorder"] = Recorder(
                        meta.dof_names,
                        [int(k) for k in meta.dof_types],
                        lambda run: recording_path(stage_path, run, started),
                    )
            except Exception as exc:  # noqa: BLE001 - report, and try again on the next Play
                state["failed"] = True
                print(f"MoonWalkers recorder: cannot read the joints ({exc})")
                return
        recorder = state["recorder"]
        runs = recorder.runs
        positions = dof_row(state["view"][1].get_dof_positions(), len(recorder.names))
        writes = recorder.step(t, positions)
        _write(writes)
        if recorder.runs != runs:
            print(f"MoonWalkers recorder: recording {', '.join(recorder.names)} to {recorder.path}")
        for path, _ in writes:
            if path != recorder.path:
                print(f"MoonWalkers recorder: wrote {path}")

    api, handle = _subscribe(on_step)
    setattr(builtins, HANDLE, (api, handle, state))
    print(f"MoonWalkers recorder: will record {root} after each physics step through {api}")
    print(f"MoonWalkers recorder: files go to {pathlib.Path(stage_path).parent / 'recordings'}")


def stop():
    """Remove a recorder started earlier in this Isaac Sim session, writing what it holds."""
    previous = getattr(builtins, HANDLE, None)
    if previous is None:
        return
    api, handle, state = previous
    if api == "simulation_manager":
        from isaacsim.core.simulation_manager import SimulationManager

        SimulationManager.deregister_callback(handle)
    elif hasattr(handle, "unsubscribe"):
        handle.unsubscribe()
    setattr(builtins, HANDLE, None)
    if state.get("recorder") is not None:
        writes = state["recorder"].flush()
        _write(writes)
        for path, _ in writes:
            print(f"MoonWalkers recorder: wrote {path}")
    print("MoonWalkers recorder: stopped the earlier recorder")


def _subscribe(callback):
    if API in ("auto", "simulation_manager"):
        try:
            from isaacsim.core.simulation_manager import SimulationEvent, SimulationManager

            uid = SimulationManager.register_callback(
                callback, event=SimulationEvent.PHYSICS_POST_STEP
            )
            return "simulation_manager", uid
        except (ImportError, AttributeError, ValueError) as exc:
            if API == "simulation_manager":
                raise
            print(f"MoonWalkers recorder: SimulationManager not usable ({exc}); using omni.physx")
    import omni.physx

    return "omni.physx", omni.physx.get_physx_interface().subscribe_physics_step_events(callback)


if __name__ == "__main__" or "omni.usd" in sys.modules:  # the Script Editor, not a test
    start()
