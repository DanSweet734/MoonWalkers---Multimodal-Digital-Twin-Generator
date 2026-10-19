# HA5C indexing programs, and driving a joint from a program in Isaac Sim (Phase 6)

**Question.** What exactly does an HA5C indexing program do, step by step? How can such a program
drive the twin's joint in Isaac Sim 6.2, success level 3?

**Dates.** Read on 2026-10-18 (local time, PDT). Decision 0016 uses this note.

## 1. The 2006 operator's manual
The source is `data/machines/haas-ha5c/inputs/documents/ha5c-operators-manual-2006.pdf`
("96-4039 rev N June 2006", SHA-256 `f99f3492...`, `SOURCES.md`). Its text was read with pypdf,
and page numbers are the PDF's.

### What a step holds (p. 33)
- "Up to 7 programs can be stored, numbered 0-6." "Every one of the possible 99 steps in a
  program may contain the following":
  1. "a step size or position command shown as a number with possible minus sign with a preceding
     S";
  2. "a feed rate shown with a preceding F";
  3. "a loop count shown with a preceding L";
  4. "a G code shown with a preceding G";
  5. "a jump destination with a preceding Step#".
- "Every step contains at least one G code."
- "Enter your step size in degrees to three decimal places." "Enter a minus sign (-) for opposite
  rotation."
- "The step will automatically be set to the fastest feed rate and a loop count of one."
- "When the last step has been entered, an end code must be present at the following step."

### The codes (p. 34)
The manual lists G28, G73, G85, G86, G87, G88, G89, G90, G91, G92, G93, G94, G95, G96, G97, G98
and G99, for example:
- "G28 Return to Home Position return to home position (same as G90 with step 0)"
- "G90 absolute position command", "G91 incremental command"
- "G96 Jump To Step# subroutine call/jump (destination is a step number)"
- "G97 Delay By 1/10 Sec delay by L count/10 seconds (down to 0.1 second)"
- "G98 360/Loop circle division (circular operation only)"
- "G99 End 99 end of program/return and end of steps"
- "G73 peck cycle (linear operation only)", "G85 fractional circle division"

### Feed rates, loops and subroutines (p. 34)
- **Feed rates:** "The feed rate display ranges between 00.001 and 270.000 preceded by an F."
  "The feed rate corresponds to degrees rotated per second. A feed rate of 270.000 means the
  spindle will rotate 270 degrees (270o) in one second." The "o" is a degree sign that pypdf
  cannot decode.
- **Loops:** "Loop Counts allow you to repeat a step up to 999 times before going on to the next
  step."
- **Subroutines:** "After executing a G96 step, the control will jump to the step called out in
  the Step# register, execute that step and the ones following until it reaches G code 95 or 99,
  the end of subroutine call. The program then jumps back to the step following G96."
  - "The Step# register replaces the feed rate register and is only present on G96 steps."
  - "Nesting of subroutine calls is not permitted."

### Dwell, circle division, auto continue, defaults (p. 35)
- **Dwell:** "programming a G97 and setting L = 10 will produce a 1 second dwell."
- **Circle division:** "The L count defines how many equal sized parts a circle is to be divided
  into. After the L count steps, the servo will be in the same position as it started."
- **Auto continue:** "If Parameter 10 is set to 2, the controller can be run like a single axis
  CNC. The entire program will be executed until the last step is encountered."
  - "the step preceding the G99 is the last one to be executed".
  - "Step 99 may also be the last step if all of memory is used."
- **Defaults:** "000.000 (step size zero)", "F (maximum feed rate defined by parameters)",
  "L 001", "G 91 (incremental)".

### Timing details (pp. 36-37)
- "G94 can be used to perform simultaneous milling. The CNC relay is pulsed at the beginning of
  the step so that your NC machine will proceed to the next block."
- "When the HA5C executes a G94, a 250 millisecond delay is required before executing the
  following step."

### Parameters (pp. 42-46)
- **Parameter 10:**
  - "0: Stop after each step";
  - "1: Continue all looped steps and stop before next step";
  - "2: Continue all programs until end code 99 or 95";
  - "3: Repeat all steps until stopped manually".
- **Parameter 16:** "This parameter causes a pause at the end of a step when the automatic
  continuation option is used. The delay is in multiples of 1/10 second." Its range is 0 to 99.
- **Parameter 18 (acceleration):** "The value used is (Par 18)*100 in encoder steps/second/second."
  Parameter 44 is an "Exponential acceleration time constant".
  - The manual gives no HA5C values for either, so acceleration is **not confirmed**.
- **Parameter 27:** home options include "+8: home to zero position in negative direction", "+16:
  home to zero position in positive direction" and "+24: home to zero position in shortest
  direction".
  - Its HA5C setting is not given. Whether a G90, G28 or G88 move takes the shortest way is
    **not confirmed**.
- **Parameter 11** can reverse the motor's direction. So which way a positive step turns the real
  spindle is **not confirmed** either.

### The programming examples (pp. 38-40)
| Example | What the manual says | Steps (step, S, F, L, G) |
|---|---|---|
| #2 | "you want the indexing head to index 90 degrees (Step 1)", feed "in the opposite direction for 10.25 degrees (Step2), then return home (Step 3)." | entered on the keypad: 90.000 G91; -10.250 F5 G91; G88 |
| #3 | "We want to drill a four-hole pattern and then drill a five-hole pattern on the same part." | 01 90.000 270.000 4 91; 02 72.000 270.000 5 91; 03 0 270.000 1 99 |
| #3 with circle division | "Example #3 could have also been done using Circle Division." | 01 0 270.000 4 98; 02 0 270.000 5 98; 03 0 270.000 1 99 |
| #4 | "We want to index 90.12 degrees (90.12°), start a seven-hole bolt pattern and then return back to our zero position." | 01 90.120 270.000 1 91; 02 0 270.000 7 98; 03 0 270.000 1 88; 04 ... 99 |
| #5 | "We want to index 90 degrees (90°), slow feed for 15 degrees (15°), repeat this pattern three times and return home." | 90/80 and 15/25, three times; 07 0 080.000 1 88; 08 ... 99 |
| #5 with a subroutine | "This is the same program (#5) using subroutines." | 01 0 Step# 4 3 96; 02 ... 88; 03 ... 95; 04 90.00 080.000 1 91; 05 15.00 25.000 1 91; 06 ... 99 |
| #6 | "You wish to index 15, 20, 25, 30° in sequence four times and then drill a five-hole bolt pattern." | 01 0 Step# 4 4 96; 02 0 080.000 5 98; 03 ... 95; 04-07 15, 20, 25, 30 at 80; 08 ... 99 |

All 28 quotes in the packaged program files were checked against these pages with a script
(pypdf, whitespace ignored): none missing.

## 2. Driving a joint from a program in Isaac Sim
- **Per-step callbacks, not time samples.** From the Robot Simulation Tips page
  (https://docs.isaacsim.omniverse.nvidia.com/latest/robot_simulation/robot_simulation_tips.html;
  the page shows no version):
  - "USD scenes that drive motion through time-sampled (`timeSample`) keyframes will appear to play
    back slower than real time" under fixed time stepping.
  - "Replace the time-sampled attributes on the moving prims with a per-step callback."
  - "The current API is `SimulationManager.register_callback(fn,
    event=SimulationEvent.PHYSICS_POST_STEP)`."
  - "Joint targets and kinematic bodies are advanced by the physics step".

  Whether PhysX follows time-sampled drive targets at all is **not stated**, so
  `program_native.usdc` tests it.
- **The API.** From the SimulationManager reference
  (https://docs.isaacsim.omniverse.nvidia.com/latest/py/source/extensions/isaacsim.core.simulation_manager/docs/api.html):
  - `register_callback(callback, event, *, order=0, **kwargs) -> int`, "Register/subscribe a
    callback to be triggered when a specific simulation event occurs."
  - `PHYSICS_PRE_STEP`: "Event triggered before a physics step is performed."
  - The example imports `from isaacsim.core.simulation_manager import SimulationEvent,
    SimulationManager`, and its callback is `def callback(dt, context):`.
  - `deregister_callback(uid)`. `IsaacEvents` is "Deprecated since version 1.7.0: Use
    SimulationEvent enum instead."
  - The page shows no Isaac Sim version, so the runner falls back to `omni.physx`'s
    `subscribe_physics_step_events`. That call is known only from community examples (a forum
    thread and a tutorial); its official reference page was not found. The runner prints which
    one it used.
- **The drive.** From OpenUSD's `UsdPhysicsDriveAPI`
  (https://openusd.org/release/api/class_usd_physics_drive_a_p_i.html):
  - "Force or acceleration = stiffness * (targetPosition - position) + damping * (targetVelocity -
    velocity)".
  - targetPosition is in "degrees", and targetVelocity in "degrees/second", for an angular drive.

  So setting both targets every step gives the spring a velocity feed-forward. With our drive
  (acceleration type, stiffness 100, damping 20, decision 0010), a target moving at v with
  targetVelocity left at 0 would trail by damping / stiffness × v = 0.2 s × v [INFERENCE:
  steady-state error of a second-order spring tracking a ramp].
- **The Script Editor.** From the Isaac Sim 6.2.0 Basic Usage Tutorial
  (https://docs.isaacsim.omniverse.nvidia.com/6.2.0/introduction/quickstart_isaacsim.html; the
  page shows no version, but the URL is 6.2.0's):
  - "The Script Editor allows the users to interact with the stage using Python."
  - "go the top Menu Bar and click Window > Script Editor"
  - "copy paste the following snippet in the Script Editor", then "run it by clicking the Run
    button on the bottom."

## 3. Measurements (2026-10-18)
- **Each example's duration** by the interpreter, with 1 s after each step:
  - #2: 5.679 s;
  - #3 (both forms): 11.667 s;
  - #4: 12.334 s;
  - #5 (both forms): 16.112 s;
  - #6: 30.000 s.
- **The manual's equivalences hold exactly:** the waypoints of #3 and its circle-division form
  are equal, and so are #5 and its subroutine form.
- **On HA5C v3,** the Example #5 program folder's `program.usdc` and `program_native.usdc` both
  pass `moonwalkers.usd.validate` and NVIDIA's `omni_asset_validate` ("No issues found.").
  - Read outside Isaac Sim, the runner finds the program on `/haas_ha5c/joints/spindle_rotation`
    and gives (40°, 80 °/s) at 0.5 s, (90°, 0) at 1.5 s and (169°, -80 °/s) at 13.0 s.

## Open questions
- Does `SimulationEvent.PHYSICS_PRE_STEP` fire on Play in the Isaac Sim GUI? This is to be seen
  in Daniel's check: the runner prints a line on the first physics step.
- Does PhysX follow time-sampled drive targets without a script? `program_native.usdc` tests
  this.
- The HA5C's real acceleration, home direction and positive direction (Parameters 18, 44, 27 and
  11): not in the manual.
