# 0016 - Control logic: the manual's indexing program drives the twin's joint

- **Status:** accepted (proposed by Claude Code in Phase 6; Daniel reviewed the Phase 6 PR, #11,
  and checked level 3 in Isaac Sim 6.2.0 on 2026-10-19). Check results and what they change: the
  section at the end.
- **Date:** 2026-10-18
- **Decided by:** team (Daniel)

## Context
Success level 3 of `docs/poc-plan.md`: "An indexing program (absolute/incremental steps, per the
2006 operator's manual) drives the joint." Phase 6 asks for the program as a `ControlBehavior`, a
small interpreter that turns G90/G91 steps into joint drive targets, a demonstration in Isaac Sim,
and limits documented honestly.

What we had:
- the agent's v3 reading notes, which hold the manual's program format, its G codes and Example #3
  as a `program_interpreter` behaviour;
- a twin joint with a position drive (decision 0010).

The manual's semantics and the Isaac Sim sources are quoted in
`docs/research/2026-10-18-ha5c-programs-and-isaac-sim-control.md`.

## Options considered
1. **How a program is written.**
   - (a) The manual's own step table (S, F, L, G, Step#), in the behaviour's
     `spec["program"]["rows"]`. It can be checked line for line against the manual's examples.
   - (b) Our own format, such as a list of moves. It is easier to run, but it would no longer be
     the machine's language.
2. **How the program runs.**
   - (a) As the control's auto-continue mode does (Parameter 10 = 2, "Continue all programs until
     end code 99 or 95"), step after step. A simulation has no mill pressing Cycle Start.
   - (b) One step per simulated Cycle Start: a person or another program would have to press it.
3. **How the program reaches Isaac Sim.**
   - (a) A runner script for the Script Editor. Every physics step, it sets the drive's target
     position and target velocity from the program's planned motion, which is stored in the USD.
     This is NVIDIA's advice: "Replace the time-sampled attributes on the moving prims with a
     per-step callback".
   - (b) Time samples on the drive's target only. There is no script, but whether PhysX follows
     them is not stated, and NVIDIA advises against keyframed motion under fixed stepping.
   - (c) An OmniGraph in the USD (`OnPhysicsStep`). There is no script either, but it cannot be
     built or tested outside Isaac Sim with our tools.
4. **Where program files go.**
   - (a) For a new build, into the run folder (`programs/<behaviour>/`), written with the twin.
   - (b) For a twin already built, into `data/machines/<machine>/programs/<date>_<program>_v<N>/`,
     since run folders never change.

## Decision
1a, 2a, 3a (with 3b written beside it as an experiment), and 4a plus 4b. These are Claude Code's
proposals.
- **Package `moonwalkers.control`.**
  - **`program`:**
    - `IndexProgram` and `IndexStep` take rows as the manual prints them.
    - The manual's limits are checked: 99 steps, S up to 999.999, F from 0.001 to 270, L from 1 to
      999 (G98 from 2), the known G codes, G96 targets that exist, no nesting, an end code.
    - G73 (linear only) and G85 (not described) are refused with the reason.
    - `ProgramFile` keeps a behaviour together with the sources it cites. The manual's Examples #2
      to #6 ship as program files; their 28 quotes were checked against the PDF.
  - **`interpreter`:** `run_program` gives the joint's target angle over time, as straight-line
    pieces, plus a log of events.
    - G91 moves by S, L times. G90 moves to S; G28 and G88 move to 0.
    - G98 moves 360/L, L times. G97 waits L/10 s. G96 runs the subroutine L times.
    - G95 or G99 ends the main program and returns from a subroutine.
    - G86, G87, G89, G92 and G93 signal the mill or wait for it: no motion, no wait. G94 adds the
      manual's 250 ms.
    - Each move runs at its feed rate, or at the maximum (270 °/s) without F. It is capped at the
      joint's cited top speed, with a note.
  - **`export`:** `write_program_folder` writes:
    - `program.usdc`: the twin holding its start angle, with `moonwalkers:program:times` and
      `anglesDeg` on the driven joint, a time-sampled `plannedAngleDeg` to scrub, and provenance in
      customData;
    - `run_program.py`;
    - `program_native.usdc`;
    - `program.json`, `trajectory.json` and `PROGRAM.md`.

    Both USD files must pass `moonwalkers.usd.validate`.
  - **`isaac_runner.py`** (copied as `run_program.py`) is pasted into the Script Editor.
    - It finds the program joints on the open stage, registers on
      `SimulationEvent.PHYSICS_PRE_STEP` (falling back to `omni.physx` step events), and every
      step sets `targetPosition` and `targetVelocity` from the plan at the timeline's time.
    - Stop then Play runs the program again.
    - Its pure parts are tested outside Isaac Sim.
  - **`python -m moonwalkers.control list | show | run PROGRAM --twin key[@vN]`.** Without a
    version, `run` uses the twin a request would reuse.
- **Builds.** When a twin's control behaviour carries a program, `build_run` writes its program
  folder into the run and lists it in `RUN.md`.
  - The program is checked before any file is written, and a failure afterwards removes what was
    written.
  - `add_control` checks a program when the agent records it.
- **Settings for what the manual leaves open [INFERENCE].** All of them are recorded in each
  `PROGRAM.md` and `trajectory.json`:
  - **The pause after each step** is Parameter 16, "Auto Continue Dwell" (0 to 9.9 s). Its HA5C
    value is not given, and the default is 1 s, standing in for the machining that follows each
    index.
  - **Absolute moves:** "direct" by default, going straight to the programmed angle, so 315° back
    home turns -315°. "shortest" is the alternative, like Parameter 27's home option +24.
  - **Acceleration** is not modelled: Parameters 18 and 44 set it, and the manual gives no HA5C
    values.
  - **Direction:** a positive step turns the joint positively about the twin's +X (right-hand
    rule). Parameter 11 can reverse the real motor, so the real direction is not confirmed.

## Consequences
- **Level 3 is reachable by hand.** Open `program.usdc`, paste `run_program.py`, press Play.
  - Program folders for HA5C v3 were written for Examples #5 (subroutine form) and #3, under
    `data/machines/haas-ha5c/programs/`.
  - Daniel's check on 2026-10-19 showed it in the simulator (section below).
- **One manual-click step remains with the runner.** The runner is a script, not part of the USD.
  The check showed that the experiment's file, `program_native.usdc`, needs no script: Isaac Sim
  6.2.0 follows the time samples on the drive's target (section below).
- **Not the controller's timing.** Motion starts and stops at full feed rate, so real moves take
  slightly longer, by their acceleration. The pause after each step is a stand-in.
- **The agent can give a twin control logic** by recording a program from the manual
  (`add_control`). The next build carries it. An existing twin gets a program folder from the
  command line, without a rebuild.
- **Only the HA5C's control** is modelled: rotary indexing in degrees, one joint. Linear mode
  (Parameter 12 = 1-4), the CNC relay and remote inputs are out of scope.
- **Reversing it.** `moonwalkers.control` stands alone, and builds only call it when a behaviour
  carries a program. Removing it leaves twins as they were in Phase 5.

## Isaac Sim check (2026-10-19)
Daniel checked the Example #5 program folder on HA5C v3
(`data/machines/haas-ha5c/programs/2026-10-18_ha5c-manual-example-5-subroutine_v3/`, whose
`PROGRAM.md` holds the full record). Isaac Sim 6.2.0 (Kit 110.4.0, build 386251), in two
sessions, with no errors in either log.
- **`program.usdc` with the runner: level 3 met.**
  - The runner used `SimulationManager` (`PHYSICS_PRE_STEP`), so the `omni.physx` fallback was
    not needed. Its first physics step came at t = 0.017 s (one step at 60 Hz).
  - Daniel: "It did exactly as you said." It printed "finished at 16.112 s, target 0.000 deg"
    16.48 s of wall-clock time after Play (from the log's timestamps).
  - Stop, then Play, ran it again from the start, "exactly as the script said".
- **`program_native.usdc` with no script: it moves.** In a new session it "performed the moves as
  program.usdc with the script", and stopped exactly where it started. So Isaac Sim 6.2.0 follows
  time samples on `drive:angular:physics:targetPosition` by itself. Its timing was not compared
  with a clock. Daniel later opened it again in a third session (log `kit_20261019_202904.log`:
  Play at 73.7 s for 36 s, no errors). By eye, the files with and without the script play
  identically, and the native file "Looked just as fast" (Daniel). Isaac Sim's log does not record
  joint angles, so it cannot confirm the timing.
- **One fix from the check.** On the second Play, the runner printed nothing, because it printed
  its lines once per start of the script. The joint still moved, since the targets are set on
  every step. `isaac_runner.Progress` now starts a new run whenever the timeline's time goes back,
  so the lines print on every run ("(run 2)" from the second). This is tested outside Isaac Sim,
  and the changed runner has not yet been run in Isaac Sim. Folders written earlier keep their
  copy of the runner.
- **The warning Daniel asked about.** "Python import process in omni.anim.graph.core failed -
  'NoneType' object is not subscriptable. Aborting Python node registration" comes while Isaac
  Sim's extensions start, before any file is opened (35.5 s and 7.0 s into the two sessions). It
  is on the guide's list of warnings to ignore (`docs/setup/isaac-sim-check.md`).

**What this changes.** Nothing in the decision yet: the runner stays the default.
- It follows NVIDIA's advice for fixed time stepping.
- It sets the target velocity as well as the position. With only a position target (the native
  file), our drive trails a moving target by about damping / stiffness × speed = 0.2 s × speed,
  which is 16° during an 80 °/s index [INFERENCE: the steady-state error of a second-order spring
  tracking a ramp; not measured].

The native file is now a confirmed way to show a program with no script, for example to someone
without this guide. Whether to make it the default, perhaps with the target velocity time-sampled
too, is a choice for the integration phase. It should come after measuring both files' joint
angle over time against the plan.

## Update (2026-11-02): acceleration and the mill's signals
Decision 0026 amends this record:
- moves now speed up and slow down at a labelled stand-in of 540 deg/s^2 (Parameter 18 is "usually
  2X" Parameter 19);
- the CNC relay is a timeline set by Parameter 1 and the signal codes;
- G89, G92 and, with Parameter 10 = 0, every step wait for the mill's cycle start, answered by a
  simulated mill or by a person in Isaac Sim's Property panel.

`--acceleration 0 --mill-answer 0` gives this record's motion. Folders written before then keep it.
