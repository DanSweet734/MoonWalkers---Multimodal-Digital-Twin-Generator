# 0038 - A hand's SDK commands as a program: LinkerBot's calls, mapped by the SDK's own angle table

- **Status:** accepted by Daniel on 2026-11-17 ("decision 0037 and 0038 seem good, let's accept
  them"), after his Isaac Sim check of the test grasp (the lab's machines plan, Phase 7; PR #34)
- **Date:** 2026-11-17
- **Decided by:** team (Daniel), proposed by Claude Code
- **Applies:** decisions 0016 (program folders and the runner), 0031 (the photographed pose as
  0), 0033 (an arm's programs, whose folder and measures this follows), 0037 (the hand's joints)

## Context
Phase 7's checklist asks for "a grasp: the hand closes and opens on the SDK's commands in
Isaac Sim". The lab has shared no hand program. LinkerBot's ROS 2 SDK (Apache-2.0, commit
`0035f23`; `docs/research/2026-11-17-l20-hand-sdk-and-models.md`) commands an L20 with
`finger_move` (20 values, 0-255), `set_speed` (five values, 0-255) and waits between calls; its
`mapping.py` turns a right L20's values into angles. What it does not say: which joint each
slot turns (only names such as "Thumb Base"), what a speed value is in rad/s, and how the hand
moves between two commands.

## Options considered
**What a program is**
1. A Python script using the SDK, run or parsed: running needs the SDK and its CAN libraries
   (an install); parsing arbitrary Python is fragile.
2. Joint angles in radians: loses the SDK's own units and presets.
3. **The SDK's calls as data** (`set_speed`, `finger_move`, `sleep`) in the behaviour's
   `spec["program"]`, with values exactly as the SDK takes them; the folder also writes them
   back as the script a user would run (`sdk_calls.py`, to read).

**Which joint a slot turns**
1. By the README's names ("Thumb Base" is the thumb's first joint ...): the names do not match
   the model's (the thumb's base is its third joint, `thumb_joint2`, by range).
2. **By range:** each of the 16 slots' (minimum, maximum) in `mapping.py` is exactly one
   joint's limits in LinkerBot's model, and no two agree [INFERENCE]. The binding checks every
   slot against its joint's cited limits and refuses a twin where they differ.

**Timing**
1. All joints of a command start and stop together, as an iRC joint move (decision 0033): no
   source says the hand does this.
2. **Each joint alone:** from where it is, straight to its target at its finger's speed, so a
   joint with less to go arrives first; a later call, or a new speed, takes over from where each
   joint is [INFERENCE]. Each joint has its own motor and the SDK sends targets, not paths.

## Decision
- **A hand program** is a `program_interpreter` behaviour whose `spec["program"]` says
  `"format": "linkerhand_sdk"`, `"hand_joint": "L20"`, `"hand_type": "right"`, the 16
  `"slots"` (SDK slot to joint), and `"calls"`. Only the right L20 is read (`control/linkerhand.py`).
- **Values to angles** by `mapping.py`'s right-L20 range and direction for each slot; reserved
  slots 11-14 turn nothing. The twin's angle is the SDK's minus the joint's angle in the
  photographed pose (decision 0031), taken from the cited limits minus the twin's.
- **Speed:** a joint moves at `value / 255` of a top speed, the model's `velocity="1"` (rad/s), a
  stand-in [INFERENCE]; the five values are per finger, thumb first, as the driver's other
  five-value frames [INFERENCE]. Before the first `set_speed`: 100, `set_speed`'s own default.
  `--hand-top-speed` replaces the stand-in.
- **The followers** are planned through their link, and left to their mimic coupling in the
  program's stage: only the 16 driven joints carry the runner's attributes.
- **The folder** (`control/hand_export.py`) is an arm program's (decision 0033) with
  `sdk_calls.py` in place of `program.xml`; its `trajectory.json` (kind
  `linkerhand_sdk_program`) is measured by `control compare` as an arm's, with "call N"
  arrivals, a call another took over before it arrived skipped.
- **The packaged test program** `linkerhand-l20-test-grasp` is labelled, not the lab's:
  `set_speed` 100 for each finger, the SDK GUI's preset "open" (张开), sleep 3 s, its "fist"
  (握拳), sleep 5 s, "open", sleep 5 s (13 s).

## Consequences
- **Level 3 met for the hand** (Daniel's check of
  `data/machines/igus-rebel6dof02/programs/2026-11-17_linkerhand-l20-test-grasp_v5/`,
  2026-11-17): "all was as you described" in two runs of `program.usdc` and in
  `program_native.usdc`; open, fist and open arrived within 0.5° at 0.70, 7.02 and 12.02 s
  (planned 0.71, 7.02, 12.02); every joint, followers included, within 0.86° of the plan.
- **Logged inaccuracies:** the speed scale and the joint-by-joint timing are stand-ins; the
  slot-to-joint match is inferred from the ranges; the thumb passes through the fingers in the
  fist (decision 0037), where the real one stops on them; the hand's real force and contact are
  not modelled (`set_torque` is "not supported for L20").
- A left L20, or another LinkerBot hand, needs its own table from `mapping.py` and a check of
  its slots; the reader refuses them until then.
- An agent can add a hand program through `add_control` (its description names the format).
- **When the lab shares a hand program**, or a recording of the real hand, the timing and the
  speed scale are checked against it and this decision is revisited.
