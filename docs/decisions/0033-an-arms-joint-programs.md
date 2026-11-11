# 0033 - An arm's joint programs: iRC's own XML, run as synchronised joint moves

- **Status:** proposed (the lab's machines plan, Phase 3), for Daniel's review with the phase's
  pull request.
- **Date:** 2026-11-10
- **Decided by:** team (Daniel), proposed by Claude Code
- **Applies:** decisions 0016 and 0026 (programs, the runner), 0031 (the arm's zero pose), 0032
  (its hold and collisions)

## Context
Level 3 for the ReBeL arm (`igus/rebel6dof02@v3`) is "a program of joint moves at no more than
the cited 45°/s, as a `program_interpreter` behaviour" (the plan's Phase 3). What we had:
- decision 0016's program folders, its runner and its interpreter, which read the HA5C's step
  table and drive one joint;
- an arm whose joint positions are not igus's angles: the twin's 0 is its photographed pose
  (decision 0031);
- program exports that held joints with the exporter's default drive and let unjoined parts pass
  through each other, unlike the arm's twin (decision 0032; the hand-off's two gaps).

The research is `docs/research/2026-11-10-irc-programs-and-cri.md`: igus's iRC command reference
(V902-11-005, 06/2020), Commonplace Robotics' iRC user guide (V14.5, 2025), the CPR wiki's
example program, Commonplace's CRI library, iRC_ROS and RoboDK's CPR post-processor. The lab has
shared no program.

## Options considered
1. **How the program is written.**
   - (a) **iRC's own XML,** in `spec["program"]` as `{"format": "irc_xml", "xml": <the file's
     text>, "axes": {"A1": joint id, ..., "A6": joint id}}`. It is what the arm's control stores
     ("Robot programs are .xml files", command reference p. 2), so the lab's program, when it
     comes, can be dropped in as it is, and a test program can be checked against the sources line
     by line. As decision 0016 chose for the HA5C, the machine's own language.
   - (b) Our own list of moves. Simpler, but no longer the machine's language, and the lab's
     program would need translating by hand.
   - (c) CRI commands (`CMD Move Joint A1..A6 E1..E3 vel`). They carry the same move, but they
     are how another program drives the arm live, not a program the arm keeps.
2. **What is read.** (a) **Joint moves; Wait and Output in RoboDK's form; the wiki's endless
   Loop** (`Condition="False"`), run for a set number of passes; everything else refused with the
   reason. (b) All of iRC's commands. Linear, circular and Cartesian moves need the arm's inverse
   kinematics in a convention (Euler order, tool and user frames) the sources do not give;
   conditions, variables, inputs and sub-programs need a simulated cell. The plan leaves linear
   moves out "unless a source makes them simple", and none does.
3. **How a joint move of several joints is timed.** No source states it. (a) **Synchronised:**
   the joint with the farthest to go runs at Vel % of the top speed, and the others keep pace so
   all start and stop together [INFERENCE from "The joint velocities during the motion are
   constant" (command reference, 6.1) and "The robot moves as fast as the slowest joint allows"
   (user guide, PDF p. 47, printed p. 45)]. (b) Each joint at Vel % on its own, ending at
   different times. (a) matches both passages; (b) would make a joint's speed change when another
   stops.
4. **What 100 % is.** (a) **Vel 100 % = 45°/s**, igus's "Max. speed 45 [°/s]", which iRC_ROS's
   URDF gives every joint (`velocity="${pi*45/180}"`) [INFERENCE: iRC's robot file is not
   public]. **Acc 100 % = 300.2°/s², a labelled stand-in:** iRC_ROS's MoveIt limit
   (`max_acceleration: 5.240` rad/s²); igus publishes none. (b) No acceleration (decision 0016's
   motion), kept as `--acceleration 0`.
5. **Angles.** iRC's angles are igus's documented ones, from the arm straight up (iRC_ROS:
   "Position limit difference with iRC files due to 30 degree offset in joint 2 and 3"; the
   limits' arithmetic, decision 0031). The twin's position is iRC's minus the joint's angle in the
   photographed pose. Where that angle comes from:
   - (a) **From the twin itself:** igus's cited range (the facts `jointN_lower`, `jointN_upper`)
     minus the twin's own limits, which decision 0031 shifted by exactly that angle. Both ends
     must give the same angle (within 0.05°), and it is rounded to 0.01° as decision 0031 gives
     it. A twin rebuilt with new angles carries them with no change to the program. A twin
     without those facts needs the angles given (`pose_deg`).
   - (b) Written into each program. A program would then be tied to one twin version.
   - (c) A `zero_offset` on the contract's `Joint` (decision 0031, option 3(c)). Not needed:
     (a) reads the same number from what the twin already carries.
6. **The hold and the collisions in program folders.** (a) **The twin's own:** the program
   folder is built with the run's `hold_drive` and `self_collision` (decision 0032), for the HA5C
   and the T33901 as well (their specs give neither, so nothing changes for them). (b) Keep the
   exporter's default: an arm's program would sag 1.1 to 1.5 degrees (the box arm's recordings)
   and pass through itself.

## Decision
1(a), 2(a), 3(a), 4(a), 5(a), 6(a). Claude Code's proposals.
- **`moonwalkers.control.irc`:** `IrcProgram.from_xml` reads the XML; `bind_arm` finds each
  axis's joint, its pose angle (5a), its limits and its cited top speed; `run_irc_program` plans
  the moves from the twin's 0 and refuses a target outside the twin's range, naming it in both
  iRC's and the twin's degrees. Smoothing is noted and not modelled: each move ends at rest.
  `ArmSettings`: the override (the Play tab's "override for the robot velocity", user guide PDF
  p. 37), the acceleration stand-in, the loop's passes.
- **`moonwalkers.control.arm_export`:** a program folder as decision 0016's, plus `program.xml`
  (the iRC file as it is). Every joint carries its planned angles for the same runner
  (`isaac_runner.py`, unchanged), which already drives every joint that carries a program.
  `trajectory.json` has `"kind": "irc_joint_program"`.
- **`control compare`** measures an arm's recording: each joint's largest distance from the plan,
  where it ended, its top speed against the plan's and the cited 45°/s, and when each move's
  joints were all within 0.5° of its target.
- **`python -m moonwalkers.control run rebel-test-joint-moves --twin igus/rebel6dof02@v3`**
  (`--override`, `--acceleration`, `--loop-passes`). `run` and `controls` read the stored twin's
  run spec for its hold and collisions (6a). Builds pass them too. The MCP tool `add_control`
  checks an iRC program as it checks an HA5C one.
- **The test program** (`control/programs/rebel-test-joint-moves.json`), labelled as Claude Code's,
  not the lab's: from the photographed pose, each joint alone out and back at Vel 100 % (and
  joint 1 back at 50 %), then all six together at 50 % and home at 100 %, Acc 40 % (the wiki's
  and RoboDK's value), 24.36 s. Its targets keep away from the pose where v3's spin check jammed
  (joint 2 at +78.9° on the twin), and stay within every range. Not tried on the real arm, and
  iRC would refuse it as it is: it has no Header, which iRC compares "to avoid executing an
  incompatible program" (user guide, PDF p. 44).

## Consequences
- **Level 3 is reachable for the arm** by the same steps as the HA5C's: open `program.usdc`,
  paste `run_program.py`, press Play; record with the run's `record_joints.py`, then `control
  compare`. Folder:
  `data/machines/igus-rebel6dof02/programs/2026-11-10_rebel-test-joint-moves_v3/`.
- **The lab's own program** can be read once it is shared, if it keeps to joint moves; any linear
  move in it is refused with the reason, and would need inverse kinematics (a later decision).
- **Not iRC's timing, exactly.** The speed's shape (a trapezoid here), the brief stop between
  unsmoothed moves, iRC's own top speeds and accelerations and the synchronisation are inferred
  or stand-ins, listed in each `PROGRAM.md`. Comparing with the real arm's motion needs it moving
  (the video trip).
- **Joints 4 and 6** keep decision 0031's assumed 0 in the photographed pose, so a program's
  angles for them may be off by up to 180° on the real arm.
- **Program folders now hold and collide as their twin does,** for every machine. The HA5C's and
  the T33901's specs give no `hold_drive` or `self_collision`, so their folders are unchanged.
- **Reversing it:** `moonwalkers.control` dispatches on `"format": "irc_xml"`; removing `irc.py`
  and `arm_export.py` leaves decision 0016's programs as they were. The hold and collisions are
  two optional arguments.
