# 0025 - Control logic for a manual machine: the T33901's switch, speeds and stroke

- **Status:** proposed (by Claude Code in the drill-press plan's Phase 6, after Daniel's answers
  of 2026-10-30)
- **Date:** 2026-10-30
- **Decided by:** team (Daniel)

## Context
Level 3 of `docs/drill-press-plan.md`: "the keyed switch (no key, no start), a speed chosen from
the twelve cited settings, and an operator's drilling stroke run in Isaac Sim. The stroke feeds
down to the depth stop, then releases, and the spring returns the quill."

The HA5C's control is a program its controller runs (decision 0016). The T33901 has no program.
A person plugs it in, turns the switch, chooses a speed by moving belts, and pulls the handles.
The manual describes each control (all quotes:
`docs/research/2026-10-30-control-logic-research.md`, section 1):
- **the switch:** "Turns motor ON when moved up; turns motor OFF when moved down. Removal of
  yellow key disables switch so motor cannot start" (p. 6);
- **the speeds:** "12 Speed Settings: 340, ... 2860 RPM" (p. 9), changed only after "DISCONNECT
  MACHINE FROM POWER!" (p. 30);
- **the stroke:** the handle "Moves spindle down when pulled down. Spindle automatically returns
  to top position when released" (p. 7);
- **stopping:** "Always allow spindle to stop on its own" (p. 14).

The manual does not give:
- the stroke's speed or how long an operator holds at depth;
- how long the motor takes to reach speed or to stop;
- what removing the key does while the motor runs.

What exists:
- **The contract** has `ControlBehavior` kinds `state_machine`, `command_set`, `lookup_table`,
  `program_interpreter` and `other`, each with a free-form `spec`.
- **The quill's only drive is its spring.** It is a position drive of the acceleration type,
  stiffness 600 and damping 49, aimed 0.03 m above the top (decision 0018).
- **The spindle's drive** is a hold at 0 (`driven` mode, decision 0020).
- **The handles** follow the quill through the mimic, both ways (decision 0019).
- **The HA5C's runner** sets angular drive targets from a plan on every physics step
  (`control/isaac_runner.py`).

**Daniel's answers (2026-10-30):**
1. "It would be nice to time a stroke on any benchtop. Let's attempt it but prepare the
   information for a stand in if necessary."
2. Set the depth stop where the photos show it: "let's move the nut accordingly".
3. Live controls: "That would be great if they could be accessible in the property panel as well!"
4. Isaac Sim checks: "Just the drill press for now".

## Options considered
1. **How the operator's stroke is written.**
   - (a) **A `command_set`:** the operator's commands, each cited (plug in, insert the key, paddle
     up, set the speed, pull, release, wait), and named scenarios that list them in order.
   - (b) A `program_interpreter` with a program format of our own. But the machine interprets
     nothing, and the format would be ours, not the machine's.
   - (c) Only a planned motion, time samples on the quill's target. Then there is no switch, no
     speed rule and no live use.
2. **How the hand meets the spring.**
   - (a) **The hand moves the spring drive's target** along its path, with the target velocity,
     then hands it back to the spring's preloaded target on release. Only targets change, as the
     HA5C runner changes them, which Isaac Sim 6.2.0 followed (decision 0016).
   - (b) Change the drive's stiffness and damping during the run. Whether PhysX takes that while
     playing was not checked.
   - (c) A force from a script. It needs real masses, a contract change that waits for the
     pipeline owners (decision 0024, update).
3. **Where the control logic runs.**
   - (a) **One controller in the runner script,** stepped on every physics step. The backend
     imports the same file to plan and test a scenario outside Isaac Sim, as decision 0016 tests
     the runner's pure parts.
   - (b) Plans written as time samples. This was tested for the HA5C (decision 0016), but it
     cannot answer what a person changes while it plays.
4. **Live controls.**
   - (a) **Attributes on a `Controls` prim,** shown in the Property panel: check boxes for the
     power, key, paddle and the pull; a drop-down of the twelve speeds (`allowedTokens`); a
     number for the pull speed. NVIDIA's Property panel shows a token with `allowedTokens` as a
     drop-down (research note, section 4).
   - (b) A window of its own (`omni.ui`). It needs more code that cannot be tested outside Isaac
     Sim.
5. **What the manual does not describe:** removing the key while the motor runs; inserting it with
   the paddle up; plugging in with the switch on.
   - (a) **A scenario that does any of these is refused,** as decision 0016 refuses G85. In live
     use the twin applies its rule (the motor runs only with all three on) and prints that the
     manual does not describe this.
   - (b) Guess what the real switch does.

## Decision
1a, 2a, 3a, 4a and 5a: Claude Code's proposals. No contract change.

### Three behaviours (in `pipelines/b/grizzly_t33901.reference.json`, `control`)
| Behaviour | Kind | Drives | Spec |
|---|---|---|---|
| `power_switch` | `state_machine` | `spindle_rotation` | `inputs` (power: disconnected or connected; key: out or in; paddle: down or up), `output` "motor", `on_when` all three, `not_described` (the three transitions above) |
| `spindle_speed` | `lookup_table` | `spindle_rotation` | `rows` of the twelve speeds, `belts` only for 790 RPM ("B-3"), `change_only_when` power disconnected, `run_up_s` and `coast_down_s`, the joint and its direction |
| `operator_controls` | `command_set` | `quill_travel` (the handles follow) | `commands`, each cited; the hand; `scenarios` |

The scenarios of `operator_controls`:
- **`drilling-stroke`** is the order of work on p. 26:
  1. set the speed to 790 RPM while unplugged;
  2. plug in, insert the key, paddle up;
  3. wait while the spindle comes up to speed;
  4. pull to the work, then feed at the cutting feed to the depth stop;
  5. hold, then release;
  6. wait while the spring returns the quill;
  7. paddle down, and wait while the spindle coasts to a stop;
  8. remove the key and unplug.
- **`no-key-no-start`** is p. 24's test: plug in, paddle up without the key, and the motor does
  not start. Then paddle down, insert the key, paddle up, and it does.

### The scenario's numbers
| Value | Used | From |
|---|---|---|
| Bit and material | a 1/4 in twist bit, mild steel | the scenario's choice |
| Speed | 790 RPM | p. 29's chart gives 1250 RPM for 13/64"-3/8" bits in mild steel, and 790 is the fastest of the twelve not above it; it is also the one setting with a cited belt (B-3) |
| Cutting feed | 0.004 in/rev × 790 RPM = 1.34 mm/s | UF, "fr ≈ 0.004 in/rev" for a 1/4 in HSS drill; UofT, ".002 - .006" for 1/8"-1/4" and ".004 - .010" for 1/4"-1/2" |
| Hole depth | 1/2 in | the scenario's choice, under UF's "3 drill diameters (0.75″)", so no pecking |
| Depth stop | 43 mm (1.7 in) | measured in Fig. 35 and the colour photo (41.5-43.6 mm, research note, section 2); Daniel, 2026-10-30. v7 sets the nut there too |
| Pull to the work | 30.3 mm at 0.03 m/s | **stand-in**, until Daniel's timing |
| Hold at depth | 1.0 s | **stand-in**, until Daniel's timing |
| Motor run-up | 1.0 s, a straight ramp | **stand-in**, until Daniel's timing |
| Coast-down | 5.0 s, a straight ramp | **stand-in**, until Daniel's timing; p. 14 says only that it stops "on its own" |
| Spindle direction | positive about the twin's -Z: clockwise seen from above | [INFERENCE] the manual does not say; not confirmed |

**Daniel's timing replaces the stand-ins.** To time on any benchtop drill press, three tries
each:
- the switch on to the spindle at steady speed;
- the switch off to the chuck stopped;
- a normal pull from the top to a workpiece about 1-1/4 in below;
- a 1/4 in bit into mild steel, 1/2 in deep (or what is at hand, with the bit, material and
  speed noted);
- a natural hold at the bottom;
- the release to the quill back at the top, which checks the spring's stand-in (decision 0018).

A value timed on another machine is logged as such, as decision 0018 logs the Craftsman's
table. Every stand-in is an issue in the twin.

### What a build writes (`programs/operator-controls/`)
- **`controls.usdc`:** the twin with the spindle on a velocity drive and the cited top speed as
  `physxJoint:maxJointVelocity` (2860 RPM = 17,160 deg/s). Its `Controls` prim carries:
  - the inputs: "Plugged in", "Disabling key in", "ON/OFF paddle up", "Spindle speed (RPM)" (a
    drop-down of the twelve), "Pull the downfeed handles", "Pull speed (mm/s)", and the scenario
    that plays (a drop-down, or "live");
  - the outputs, written by the runner: "Motor running", "Spindle speed commanded (RPM)" and the
    last message;
  - the behaviours as JSON, with their citations.
- **`run_controls.py`,** the runner (`control/isaac_controls.py`):
  - on Play it runs the chosen scenario and writes its inputs into the panel;
  - when the scenario ends, or from the start with "live", it reads the panel;
  - on every physics step it sets the spindle's target velocity and the quill's target position
    and velocity;
  - it prints each event and every refusal with its page.
- **`record_joints.py`** (the joint recorder), **`controls.json`** (the three behaviours and their
  sources), **`trajectory_<scenario>.json`** (the plan at 60 Hz and the quill's reference
  response), and **`PROGRAM.md`** (the rules, the stand-ins, each scenario's timeline, and the
  check to fill in).
- **The reference response** is the quill under its exported drive and gravity, stopped by its
  limits. It leaves out the handles, whose inertia the link adds (decision 0024, update), so it is
  what a recording is measured against, not a prediction of it.

### The rules the controller enforces
- The motor runs only when the power is connected, the key is in and the paddle is up (p. 6).
- A speed outside the twelve is refused, and so is a change while plugged in (p. 30). In the panel
  the setting goes back, and the runner says why.
- Pulling moves the hand down at the pull speed until the quill's depth stop. There it presses
  0.03 m past the stop, as the spring presses past the top (decision 0018), so the quill rests on
  the stop. Releasing hands the drive back to the spring (p. 7).
- **While the hand holds the quill, it aims g/k short of it:** 9.81 / 600 = 16.4 mm. The spring
  drive is an acceleration drive, so gravity holds the quill g/k past its target. Decision 0018
  measured this on a softer drive (0.098 m at stiffness 100). Without the offset, the quill ran
  16 mm ahead of the hand, and the planned approach reached the 43 mm stop before the cut began.
  The offset comes from the joint's axis and the exported drive, so it is a simulation choice,
  not a fact about the machine.
- The spindle's target speed ramps up over `run_up_s` when the motor starts, and down over
  `coast_down_s` when it stops (p. 14).

### Also
- **The joint recorder** writes each joint's velocity beside its position (rad/s or m/s), because
  a spindle at 2860 RPM turns 286° between 60 Hz samples, and its position wraps at 360°. It
  names a recording after the scenario that played.
- **`python -m moonwalkers.control compare <recording.csv> <trajectory.json>`** measures a
  recording against the plan:
  - when the quill reached the stop, and where it rested;
  - how long the spring took to bring it home;
  - the spindle's steady speed against the setting;
  - the handles' ratio.
- **The agent's `add_control`** checks these specs as it checks a program.
- **The exporter writes a cited top speed** (`Joint.max_velocity`) as `physxJoint:maxJointVelocity`
  on every new build, in deg/s or m/s, the item decision 0010 deferred.

## Consequences
- **Level 3 can be checked by hand and in a recording:** open `controls.usdc`, paste
  `run_controls.py`, press Play. The no-key scenario and live use are in the same file.
- **The manual's words are the rules.** Every rule cites its page. What the manual leaves out is
  either refused or labelled as a stand-in.
- **A contract-free description.** The specs live in `spec`, so the pipeline owners' results stay
  valid. A machine with another kind of control (a foot pedal, a power feed) needs new input names
  and commands, not a new field.
- **The hand is ideal.** It follows its path exactly, whatever the spring pushes back. The real
  operator's force, and whether the quill slows in the cut, are not modelled; that needs masses
  and a cutting load (decision 0024).
- **The handles' inertia shows.** The spring bounced on return in v3-v6 (decision 0024, update),
  so the scenario waits 5 s after the release.
- **Belt positions stay out** (Daniel, 2026-10-24). Only 790 RPM names its belts, as data.
- **Reversing it:** remove the three behaviours from the reference facts. Builds without them
  write no `programs/operator-controls/`, and the exporter's speed cap is one attribute.

## The build: `grizzly/t33901@v7` (2026-10-30)
- Run `2026-10-30_run-001`, spec `part_cutting/2026-10-27_spec/geometry_spec_v7.json`: v5's spec,
  with the depth stop and its nut at 43 mm.
- It writes `programs/operator-controls/`. NVIDIA's validator reports "No issues found." for
  `twin.usdc`, the six check files and `controls.usdc`.
- The plans:
  - `drilling-stroke` takes 24.5 s, and the quill reaches the stop at 12.1 s;
  - `no-key-no-start` takes 13.0 s, and the motor starts at 4.0 s, once the key is in.
- Daniel's Isaac Sim check is next (`docs/setup/isaac-sim-check.md`, section 9).

## Isaac Sim check (Daniel, 2026-10-31)
Isaac Sim Full 6.2 (Kit 110.4.0), session log `kit_20261031_000713.log`, 0 errors. Five recordings
in `programs/operator-controls/recordings/`, measured with `compare`; the folder's `PROGRAM.md`
holds the full record.
- **Daniel:** "all seemed to go pretty well!" The controls show in the Property panel under "Raw
  USD Properties".
- **As planned:**
  - every step printed at its planned time, and runs 1 and 2 measure the same to the digit;
  - the motor ran only plugged in, with the key in and the paddle up;
  - the not-described changes printed their notes in live use;
  - the spindle reached 95% of 790 RPM in 0.95 s, held 790.0 RPM, and was below 1% 4.95 s after
    the stop;
  - the handles kept 57.08 rad/m;
  - the quill pressed on the stop at 43.00 mm.
- **Not tried:** the speed list. Its refusal while plugged in is unchecked in Isaac Sim.
- **Not as planned: the quill swings about the hand.**
  - It lags at first, overshoots to the stop at 3.5 s during the approach (planned 12.1 s), then
    swings through the cut. The errors shrink from 12 mm, every 1.33-1.48 s.
  - Each release bounces 4-5 times (first bounce 19-22 mm), as v3-v6 did.
- **Why, computed** from v7's convex hulls at the placeholder 1000 kg/m3, with trimesh in the
  generator's environment (the backend has no scipy):
  - The stand-in hub's hull, 6.4 kg spanning its splayed handles, has 0.073 kg m2 about the
    handles' axis. Through the 57.09 rad/m link it weighs on the quill as 237 kg, against the
    quill's own 1.9 kg: M = 125.
  - [INFERENCE] The acceleration drive scales by the quill's own parts only, so it acts on a
    quill 125 times heavier than it allows for. Predicted: a period of 2.87 s and a damping ratio
    of 1/sqrt(M) = 0.090. Measured: about 2.8 s and 0.10.
  - So "the response does not depend on the placeholder masses" (decision 0018) fails for a joint
    that others follow. Decision 0024's update already suspected this for the bounces.
- **Where the spring is:** "the spring housing is located on the left side of the headstock (see
  Figure 49)" (p. 40), a "FLAT COIL SPRING" under a "RETURN SPRING COVER" (p. 49). Phase 5
  measured that housing on the pinion's axis (decision 0027). So the spring turns the pinion, the
  handles' joint [INFERENCE: coaxial within 1 cm on the mesh].
- **Options, for Daniel:**
  - (a) Simulate the spring and the hand on the handles' joint. The contract stays as it is
    (decision 0020: the exporter decides how to simulate). There the drive's own inertia
    dominates: the quill adds only 0.0006 kg m2, M = 1.01, so it should behave as designed.
    Whether PhysX takes a drive on a mimic follower is not confirmed. The link carried pushes
    both ways in Daniel's checks [INFERENCE].
  - (b) Scale the quill drive's gains by M. That needs the hulls' inertia in the backend (scipy,
    an install), and the spring stays where the machine has none.
  - (c) Keep v7 and log the swing until real masses.

**The speed list, checked the same day** (Daniel's second session, `kit_20261031_003325.log`, 0
errors):
- three changes while plugged in were refused, quoting p. 30;
- unplugged, 1420 RPM and then 2860 RPM were accepted;
- the spindle held each speed exactly (790.0, 1420.0, 2860.0 RPM), reaching 95% of 2860 in 0.95 s.
  So nothing caps the cited top speed;
- removing the key while the motor ran printed the "not described" note.

## Update (2026-10-31): the spring is simulated on the pinion
**Daniel chose option (a):** "For the fix I agree with your recommendation. Let's go with option 1."

- **The rule** (`usd/exporter.py`, `springs_on_pinions`): a spring that returns a sliding joint
  which one turning joint follows by mimic is written on the turning joint. That is a rack and
  pinion, as the quill's rack and the handles' pinion are.
  - **The spring keeps its stand-in values** (stiffness 600, damping 49, acceleration type),
    aimed 0.03 rad past the follower's rest angle, towards the top.
  - **The slide keeps no drive;** the link moves it.
  - **Left as they are:** a check whose own settings name either joint (the `adjustable_stop`
    feed), and the rack-and-pinion coupling.
  - **The contract is unchanged:** the quill's `spring_return` still says what the machine does
    (p. 7), and the exporter decides where to simulate it (decision 0020's rule).
- **This amends** decision 0018 (a spring is a drive on its own joint) and decision 0019 (a
  follower has no drive of its own). `JointSettings` no longer refuses a drive on a follower.
- **The validator** no longer reports "has no drive" for a joint whose follower carries one.
- **The controller** moves the drive that carries the spring. `controller_spec` gives its joint
  and the map from metres of quill travel to its degrees (57.09 rad/m, so 3270.8 deg/m).
  - The hand presses 0.03 rad past the stop, 0.53 mm of travel.
  - It aims at itself. [INFERENCE] The quill's weight turns the pinion by about 0.0075 rad, 0.13 mm
    of travel, on v7's hulls: the quill's 1.9 kg x 9.81 / 57.09 = 0.33 N m against the hub's
    0.073 kg m2 and 600 per second squared.
- **What the twin should do now** [INFERENCE: the hub's own inertia outweighs the quill's
  reflected 0.0006 kg m2, M = 1.01]:
  - the drive acts as designed, about critically damped, with omega = 24.5 rad/s;
  - the quill follows the hand within about 1 mm;
  - the spring returns it in a fraction of a second, without bouncing.

  Whether PhysX takes a drive on a mimic follower is for the Isaac Sim re-check to show.

**Built: `grizzly/t33901@v8`** (run `2026-10-31_run-001`, the v7 spec; a dry run in a scratch copy
first).
- In `twin.usdc`, `checks/spring_return.usdc` and `controls.usdc`, the quill has no drive, and the
  downfeed handles carry the spring: -1.719 deg (0.03 rad past the top), stiffness 600, damping 49.
- `checks/adjustable_stop.usdc` keeps its feed on the quill, and the handles have no drive.
- NVIDIA's validator reports "No issues found." for all eight files. Ours gives its usual five
  infos.
- The plan: the quill is home 0.23 s after the release in the reference response. Daniel's
  re-check is next (`docs/setup/isaac-sim-check.md`, section 9, "Re-check of v8").

