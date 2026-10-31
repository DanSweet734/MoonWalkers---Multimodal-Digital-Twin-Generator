# Checking an exported twin in Isaac Sim 6.2.0

Purpose: confirm by eye that an exported twin opens in Isaac Sim at the right size and that its
joint moves. Phase 2 does this with the synthetic box-and-cylinder test twin. Phase 3 repeats it
with the HA5C (section 6), and Phase 6 runs an indexing program on it (section 7). The files have
already passed both validators (our own and NVIDIA's asset validator), so this step checks what
only the simulator can show.

## 1. Install Isaac Sim 6.2.0 (once)
Steps quoted from the install page
(https://docs.isaacsim.omniverse.nvidia.com/6.2.0/installation/install_workstation.html) and the
download page (https://docs.isaacsim.omniverse.nvidia.com/6.2.0/installation/download.html), both
read 2026-10-17:

1. Download `isaac-sim-standalone-6.2.0-windows-x86_64.zip` from the download page's "Windows" link.
   It is 10.53 GB (the server's reported size on 2026-10-17).
2. Optional integrity check in PowerShell. The download page lists the MD5
   `86dabd127e9e8c225c239b41a8e3909b`:
   ```powershell
   Get-FileHash -Algorithm MD5 .\isaac-sim-standalone-6.2.0-windows-x86_64.zip
   ```
3. Unzip into `C:\isaacsim`, the folder the install page uses:
   ```powershell
   mkdir C:\isaacsim
   tar -xvzf "isaac-sim-standalone-6.2.0-windows-x86_64.zip" -C C:\isaacsim
   ```
4. "On Windows, double click `post_install.bat`."
5. "On Windows, run `isaac-sim.bat`." "The first run of the Isaac Sim app takes some time to warm up
   the shader cache", and the window "can take 5-10 minutes to complete."

## 2. Make the test files
From `backend/` (run `2026-10-17_run-001` already exists):

```powershell
uv run python -m moonwalkers.usd.primitive_twin ../data/machines/moonwalkers-testindexer/runs/<run>
```

This writes `spin.usda`, `quarter_turn.usda` and `RUN.md` into the run folder.

## 3. Check `spin.usda`
1. Open the file in Isaac Sim with **File > Open**. This is the usual Omniverse menu; the 6.2 install
   page does not describe opening files, so it is not confirmed there.
2. Before pressing Play you should see:
   - a grey box (the body), 0.20 m along X, 0.16 m wide and 0.16 m tall;
   - an orange 8-sided cylinder (the spindle) sticking out of the box's +X face: 0.06 m across and
     0.06 m long, with its axis 0.10 m above the bottom of the box.

   If everything looks about 100 times too big or too small, the units are wrong; please report it.
3. Press **Play**. Expected:
   - the spindle turns about the X axis at 30 degrees per second, one full turn every 12 seconds;
   - the box stays still (it is fixed to the world);
   - nothing falls.
4. Press **Stop**.
5. Optional: select `/moonwalkers_testindexer/joints/spindle_rotation`. In the Property panel, the
   angular drive's target velocity should read 30. USD shows angles in degrees (Isaac Sim
   conventions page). Set it to -90 and press Play: the spindle should turn the other way, three
   times faster.

## 4. Check `quarter_turn.usda`
Open it and press **Play**. Expected: the spindle turns 90 degrees and then holds still. With the
current drive tuning this took about two seconds on 2026-10-17 (Daniel's estimate).

## 5. Record what you saw
In the run folder's `RUN.md`, under "Isaac Sim check", note:
- the Isaac Sim version;
- what each file did;
- any errors or warnings shown in Isaac Sim's console (copy the text);
- the success level reached by the test twin: 1 = opens at the right size, 2 = the joint rotates.

Screenshots stay in the run folder (not in git); describe them in the worklog.

## 6. Phase 3: check the HA5C twin
Files in `data/machines/haas-ha5c/runs/2026-10-17_run-003/`. All three are the stored twin
`haas/ha5c@v2`; they differ only in the spindle's drive:
- `twin.usdc`: the spindle holds at 0 degrees;
- `checks/spin.usdc`: the spindle turns at 30 degrees per second;
- `checks/quarter_turn.usdc`: the spindle turns to 90 degrees and holds.

They are binary USD (decision 0012). Open them with **File > Open**, as before.

1. **Before Play (success level 1).** Open `twin.usdc`. You should see:
   - a grey HA5C body with the motor housing on one side, the handle on top and a lever sticking
     out sideways, as in the Haas UK photo;
   - a short orange cylinder with a bore (the spindle nose) at the front, pointing along +X. The
     black six-screw disc around it is part of the grey body (decision 0012, Daniel's choice).

   Expected sizes (from `RUN.md`):
   - about 0.22 m along X, 0.38 m along Y and 0.20 m tall;
   - the base at height 0 and the spindle axis 0.1016 m (4 in) above it;
   - the nose about 0.065 m across.

   For comparison, the Haas drawing gives 15.32 in (0.389 m) for the width and 8.3 in (0.211 m) for
   the height including the handle. If the model looks 100 times too big or too small, the units
   are wrong.

   Measuring by hand is approximate. The measuring tool snaps to vertices, edges or surfaces, and
   its lines are not axis-aligned. On 2026-10-18 Daniel's width and height came within 0.02 in of
   the computed sizes, but a depth line stopped short of the back. The exact sizes are in `RUN.md`.
2. **Play `twin.usdc`.** Nothing should move or fall. The console should no longer warn that the
   stage "has no usable time-code range" (decision 0010, Phase 3 update). Please copy any warning
   that mentions `/haas_ha5c`.
3. **Play `checks/spin.usdc` (success level 2).** The spindle should turn about X at 30 degrees per
   second, one turn every 12 seconds, while the body stays still. The nose is nearly round, so the
   turning can be hard to see. Watch the bore's rim and any small bumps on the nose. A wireframe
   view also shows the triangles moving, though the menu for it in 6.2 is not confirmed. The joint
   is `/haas_ha5c/joints/spindle_rotation`; its angular drive's target velocity should read 30.
4. **Play `checks/quarter_turn.usdc`.** The spindle should turn 90 degrees and hold. It settled in
   under a second on 2026-10-18 (Daniel's estimate). The drive's target position should read 90.
   Once the nose has turned, small black gaps show around it. They are expected: the cut edges no
   longer meet once the slightly out-of-round nose turns, about 1 mm apart and up to 2.8 mm after
   90 degrees (decision 0012).
5. **Look for collisions between the parts.** The body's convex collider overlaps the back of the
   spindle. Jointed parts should not collide (decision 0010, Phase 3 update). If the spindle
   shakes, drifts or is pushed out of place, please report it.
6. **Record** what you saw in `2026-10-17_run-003/RUN.md` under "Isaac Sim check": the version,
   what each file did, any console warnings about our files, and the success level (1 or 2). The
   file is at `data/machines/haas-ha5c/runs/2026-10-17_run-003/RUN.md`. `data/` is gitignored, so
   VS Code's search may skip it: open it from the Explorer, or send your notes to Claude Code to
   add.

**Result on 2026-10-18 (Daniel):** level 2, with no errors, no time-code warning and no collisions.
The seam gaps from step 4 were seen. Details: `docs/worklog/2026-10-18.md`.

**Since Phase 5:** after a check, a person can record the decision as a review of that twin version
in the dashboard: approve or reject, with what was seen as the reason (`docs/setup/dashboard.md`,
decision 0015). A rejected version is no longer reused.

## 7. Phase 6: an indexing program drives the spindle (success level 3)
The program is the manual's Example #5, in its subroutine form:
- index 90° at 80 °/s and slow-feed 15° at 25 °/s, three times;
- then return home.

It runs on HA5C v3, with a 1 s pause after each move. The folder is
`C:\Users\Daniel Sweet\Desktop\MoonWalkers---Multimodal-Digital-Twin-Agent-Platform\data\machines\haas-ha5c\programs\2026-10-18_ha5c-manual-example-5-subroutine_v3\`.
Its `PROGRAM.md` lists every move with its start and end times. The method is decision 0016.

1. **Open the file.** In Isaac Sim 6.2.0, File > Open that folder's `program.usdc`. The orange
   part is the spindle.
2. **Start the runner.** Open `run_program.py` from the same folder in a text editor (VS Code or
   Notepad), select all and copy. In Isaac Sim, go to Window > Script Editor, paste it, and click
   **Run** at the bottom. The editor's output should show:
   - `'ha5c-manual-example-5-subroutine' on /haas_ha5c/joints/spindle_rotation: 15 points over
     16.112 s`;
   - `driving the joint(s) on each physics step through simulation_manager; press Play` (or
     `omni.physx`).
3. **Press Play.** The output prints `first physics step at t = ...`. The spindle should then:
   - turn a quarter turn quickly;
   - pause about 1 s;
   - turn slowly by 15° (0.6 s);
   - pause, and do both twice more;
   - at about 11 s, turn back 315° to where it started, and stop at about 15 s.

   The output prints `finished at 16.112 s, target 0.000 deg`.
4. **Run it again.** Stop, then Play, runs it again from the start, and the runner prints its lines
   again, marked `(run 2)` and so on. Running the pasted script again replaces the earlier runner.
   (Folders written before 2026-10-19 hold a runner that prints only on the first run; the joint
   still moves on every run.)
5. **Optional: no script.** Open `program_native.usdc` from the same folder in a new Isaac Sim
   session, so that no runner from step 2 is still registered, and press Play without running the
   script. The spindle should make the same moves: Isaac Sim 6.2.0 follows time-sampled drive
   targets by itself (checked on 2026-10-19).
6. **Optional: Example #3** (a four-hole, then a five-hole pattern: four 90° and five 72° indexes
   at 270 °/s, 11.7 s). The folder is `...\programs\2026-10-18_ha5c-manual-example-3_v3\`; repeat
   steps 1 to 4 there.
7. **Record what you saw** in the folder's `PROGRAM.md`, under "Check in Isaac Sim (fill in)", or
   send it to Claude Code to add:
   - the runner's output lines;
   - whether the moves and pauses matched the timeline;
   - where it stopped;
   - the native file's result.

**Result on 2026-10-19 (Daniel):** level 3, with no errors.
- The runner used `simulation_manager`, printed its first physics step at t = 0.017 s and finished
  at 16.112 s, target 0.000°. The spindle followed the timeline, and Stop, then Play, ran it again.
- `program_native.usdc` (step 5, in a new session) made the same moves with no script and
  stopped where it started.
- Example #3 (step 6) was not checked.
- In a third session the native file was played again, with no errors. By eye, the two files play
  identically.

**To try the changed runner** (it prints its lines on every run), use the folders written on
2026-10-19: `...\programs\2026-10-19_ha5c-manual-example-5-subroutine_v3\` and
`...\programs\2026-10-19_ha5c-manual-example-3_v3\`. Follow steps 1 to 4 in each. On the second
Play the output should print `first physics step at t = ... (run 2)`.

Details: decision 0016, "Isaac Sim check", and the folder's `PROGRAM.md`.

**If nothing moves on Play:**
- If no `first physics step` line was printed, the callback did not fire. In the pasted script,
  change `API = "auto"` near the top to `API = "omni.physx"`, run it again, and press Play.
- If the line was printed but the spindle still does not move, copy the output, plus any red
  errors in the console.

## 8. Drill-press plan, Phases 1 and 2: the box-and-cylinder drill press
A stand-in for the Grizzly T33901 made of boxes and cylinders (`docs/drill-press-plan.md`,
Phase 1). It has eight parts on seven joints, and its sizes come from the manual where it gives
them. Since Phase 2 its joints state their behaviour in contract v0.2.0 (decision 0020). The
current files are in
`C:\Users\Daniel Sweet\Desktop\MoonWalkers---Multimodal-Digital-Twin-Agent-Platform\data\machines\moonwalkers-testdrillpress\runs\2026-10-23_run-003\`.
Its `RUN.md` repeats what to look for in each file and has room for your notes. Earlier runs, both
checked on 2026-10-23: `...\runs\2026-10-23_run-002\` (the first check's fixes) and
`...\runs\2026-10-22_run-001\` (the first check).

**What changed in run-003** (Phase 2). The physics was compared with run-002's, written at the
same time: `all_motions` is the same, and every other difference is one of these three.
- **The handles follow the quill in every file,** as on the machine. Before, they were linked only
  in files 5 and 6. So in files 3 and 4 the handles now turn as the quill moves.
- **The table is locked at its drawn pose in files 1 to 6,** by its lock handles, as in the
  contract. Before, soft default drives held it, and the height could sag.
- **In `table_free` the table drops** once its locks are loosened (your direction, 2026-10-23:
  a similar drill press's table fell). Before, its height was held.

To make them again (from `backend/`):
`uv run python -m moonwalkers.usd.primitive_drill_press ../data/machines/moonwalkers-testdrillpress/runs/<run>`.

**What you will see.**
- The grey part is the frame: base, column, and one box standing in for the head and motor.
- The orange parts move:
  - the quill, with the 8-sided chuck below it;
  - the hub on the right of the head, with its three handles;
  - the column rack and collar;
  - the bracket with its crank;
  - the table arm and the table.
- The front faces +X, and the operator's right is +Y.
- On Play, parts with a stored start, such as the quill at full depth or the raised table, jump
  there on the first physics step. Before Play the file can only show them where they are drawn.

**Two tools for every file.**
- **Pushing a part:** while the simulation runs, hold **Shift** and drag a part with the left mouse
  button. The Physics settings' "Mouse Interaction" section turns it on or off.
- **Measuring:** before Play, open `record_joints.py` from the folder in a text editor, copy it
  all, and paste it into Window > Script Editor, then click **Run**.
  - It prints `will record /moonwalkers_testdrillpress ...`.
  - After Play it prints `recording ... to ...\recordings\<file>_<time>.csv`. The file holds every
    joint's position over time, in radians or metres.
  - Run it again for each file you open. Please send the CSV files, or note their names.
  - In run-001 it printed `cannot read the joints` instead and wrote nothing (fixed in run-002).

**The files, one at a time** (File > Open, then Play):
1. `spindle_spin.usdc`: the spindle turns at 340 RPM, the lowest cited speed. At 60 frames a second
   it may look slow or even backwards, because each frame is close to its 8-sided symmetry. Nothing
   else moves.
2. `spindle_spin_slow.usdc`: the spindle turns slowly (30°/s), clockwise seen from above, without
   a push.
3. `quill_spring_return.usdc`: the quill jumps to 3-1/4 in down, and the spring returns it to the
   top, where it stays. Since run-003 the handles turn back with it.
4. `depth_stop.usdc`: the quill is fed down and stops at a depth stop 1-1/2 in (38 mm) down, short
   of its full travel. At the top it already sticks 1.38 in out of the head, so it ends 2.88 in out.
   Since run-003 the handles turn about 124° as it goes down.
5. `handles_follow_mimic.usdc`: as file 3, and the handles turn back 270° as the quill rises.
   Shift+drag a handle: the quill moves too. A push on the quill itself barely moves it, because
   through the coupling the handles' lever is about 10 times stronger.
6. `handles_follow_rack_pinion.usdc`: the same coupling, written another way. The handles should
   turn back with the quill, the same way as in file 5.
7. `table_free.usdc`: since run-003, the table starts 0.15 m up and drops to the bottom of its
   travel on Play. Then Shift+drag the table:
   - it slides up and down (run-002 held the height instead);
   - it swings around the column;
   - it tilts up to 45° each way;
   - it turns about its centre.
8. `table_locked_drive.usdc`: the table starts raised 0.15 m, swung 30°, tilted 30° and turned 45°,
   and holds there. Shift+drag it hard, and note whether it gives.
9. `table_locked_limits.usdc`: the same pose, held by limits instead. It should not move at all.
10. `all_motions.usdc`: all of it at once. The spindle turns, the quill rises with the handles
    turning, and the table holds its pose.

**What to send back** (or write in `RUN.md`):
- for each file, what moved and how, and anything that shook, drifted or flew apart;
- which coupling worked: the mimic (file 5), the rack and pinion (file 6), both or neither;
- which lock held better (files 8 and 9);
- any errors or warnings in the log, or the log's file name, so Claude Code can read it;
- the CSV recordings.

**Result of the first check (run-001, Daniel, 2026-10-23).** Isaac Sim 6.2.0, Kit 110.4.0 build
386251. Nothing shook, drifted or flew apart.
- **As expected:** files 1, 3, 4, 5, 8, 9 and 10's table.
  - The depth stop ended at the 2.88 in expected.
  - The mimic moved the quill when a handle was pushed.
  - The equal-limit lock held completely; the drive lock gave a little.
- **Three problems, fixed in run-002:**
  - **Files 2 and 10's slow spindle** turned only while pushed. [INFERENCE] PhysX put the
    articulation to sleep. The files are now written with sleep turned off.
  - **File 6's rack and pinion** jammed. The quill did not rise, and the handles moved only a
    little. [INFERENCE] Its ratio's sign was reversed; it is written with the other sign now.
  - **File 7's table height** sagged on Play and could be pushed. It was held by a soft drive, and
    is now held by equal limits.
- **The recorder** wrote nothing: "Failed to get a valid attached USD stage id from PhysX
  simulation". It now uses Isaac Sim's own physics view.

**Result of the re-check (run-002, Daniel, 2026-10-23).** All three fixes work:
- the slow spindle turns on its own (files 2 and 10);
- the rack and pinion follows the quill like the mimic (file 6);
- the free table's height holds while it swings, tilts and turns (file 7).

**The fixed recorder works** (Daniel, 2026-10-23, `all_motions.usdc`). Run-001's old copy cannot read
the joints, so use the copy in `2026-10-23_run-002` or later:
1. Open any file from that folder, for example `all_motions.usdc`.
2. Paste that folder's `record_joints.py` into Window > Script Editor and click **Run**.
3. Press Play for a few seconds, then Stop.
4. The output should print `recording ... to ...\recordings\all_motions_<time>.csv`, and the folder
   should hold that file.

**Re-check for run-003** (Phase 2, about ten minutes):
- file 7 (`table_free`): the table drops on Play, then slides, swings, tilts and turns when pushed;
- files 3 and 4: the handles turn with the quill;
- file 10 (`all_motions`): the same as in run-002;
- one recording of file 7, if you can, to measure the drop.

**Result of the run-003 re-check (Daniel, 2026-10-24).** Isaac Sim 6.2.0, Kit 110.4.0 build 386251;
two sessions, 0 errors (`kit_20261024_010941.log`, `kit_20261024_011630.log`).
- **File 7:** "upon hitting play the table does indeed drop".
- **Files 3 and 4:** the handles turn with the quill.
  - `quill_spring_return` "acted like always, the quill retracts up when the handles are not being
    pulled down".
  - `depth_stop`: "it extended the quill down and the handles pulled it back up, but when released
    it went back down". That is as designed: its feed drive takes the quill to the stop in place of
    the spring, and a handle lifts it through the two-way link.
- **File 10:** "the same as before". File 2 turned as before.
- Files 5 and 6 were opened too. Files 1, 8 and 9 were not, and no recording was made. Run-003's
  `RUN.md` holds the full record.

## 9. Drill-press plan, Phase 6: the T33901's controls (success level 3)
`grizzly/t33901@v7` (run `2026-10-30_run-001`) carries the manual's controls (decision 0025):
- the keyed switch;
- the twelve speeds;
- the operator's downfeed handles, in two scenarios and live from the Property panel.

Its depth stop and nut are set at 43 mm, where the photos show them. The folder is
`C:\Users\Daniel Sweet\Desktop\MoonWalkers---Multimodal-Digital-Twin-Agent-Platform\data\machines\grizzly-t33901\runs\2026-10-30_run-001\programs\operator-controls\`.
Its `PROGRAM.md` lists the rules, the stand-ins and every step's time.

1. **Open** that folder's `controls.usdc` (File > Open).
2. **Start the recorder, then the runner.** Window > Script Editor:
   - paste the whole of `record_joints.py` from the folder and click **Run**;
   - then paste the whole of `run_controls.py` and click **Run**. It prints `grizzly/t33901@v7:
     scenarios drilling-stroke, no-key-no-start, live; ...` and `driving the joints on each
     physics step through simulation_manager; press Play`.
3. **Find the controls.** In the Stage window, select `Controls` under `grizzly_t33901`. The
   Property panel shows the group "MoonWalkers controls" with:
   - "Plugged in", "Disabling key in", "ON/OFF paddle up" and "Pull the downfeed handles";
   - "Spindle speed (RPM)" (a list of the twelve), "Pull speed (mm/s)" and "Scenario on Play";
   - a second group "set by run_controls.py": "Motor running", "Spindle RPM commanded" and "Last
     message".

   They may sit under "Raw USD Properties". Where Isaac Sim shows custom attributes is not
   confirmed yet. Leave "Scenario on Play" at `drilling-stroke`.
4. **Press Play.** The console prints each step, and the panel's boxes tick as the scenario goes:
   - **t = 0:** speed 790 RPM, power connected, key in, paddle up, "motor starts". The chuck comes
     up to 790 RPM in 1 s, a stand-in. At 13 turns a second it may blur, or seem to turn slowly
     backwards, as fast wheels do on video.
   - **t = 2:** the quill goes down 30 mm in about 1 s, and the handles turn with it.
   - **t = 3 to 12.5:** the cut, 1.34 mm/s. The quill reaches the depth stop at about 12.1 s,
     where the nut meets the bracket.
   - **t = 13.5:** "release the handles", and the spring returns the quill. It may bounce, as v3-v6
     did.
   - **t = 18.5:** paddle down, "motor stops". The spindle coasts to a stop by about 23.5 s.
   - **t = 24.5:** key out, unplugged, then "scenario finished; the Property panel's controls are
     live".
5. **Then use the panel yourself:**
   - tick "Plugged in", then "ON/OFF paddle up" without the key. The console says "the motor does
     not start", quoting p. 6;
   - untick the paddle, tick the key, tick the paddle: "motor starts";
   - pick another speed while plugged in. It is refused, quoting p. 30, and the list goes back to
     790;
   - unplug, pick 340, plug in and start: the chuck turns more slowly;
   - tick "Pull the downfeed handles": the quill goes down at the pull speed to the stop. Untick
     it, and the spring returns the quill.
6. **The other scenario.** Stop, set "Scenario on Play" to `no-key-no-start`, and press Play. The
   paddle goes up at t = 0, but the spindle stays still. At t = 4, with the key in, it starts; it
   stops at t = 7 and coasts down. Stop, then Play, always starts over.
7. **Recordings** go to the folder's `recordings/`, named after the scenario, for example
   `controls_drilling-stroke_<date>_<time>.csv`. They now hold each joint's velocity too. Claude
   Code measures one with `uv run python -m moonwalkers.control compare <csv>
   <folder>/trajectory_drilling-stroke.json`.
8. **Report** what each scenario and the panel did, and which recordings to read.

**Result on 2026-10-31 (Daniel, v7):** the switch, the speeds (790, 1420 and 2860 RPM held
exactly) and both scenarios ran as planned. The live controls work under "Raw USD Properties". The
quill swung about the hand (±12 mm, about every 2.8 s) and bounced on release: the stand-in hub's
placeholder inertia, reflected through the link (decision 0025, "Isaac Sim check").

**Re-check of v8** (run `2026-10-31_run-001`): the quill's spring is now simulated on the downfeed
handles, where the T33901 has its spring (decision 0025, update of 2026-10-31). Use
`...\runs\2026-10-31_run-001\programs\operator-controls\` and repeat steps 1 to 4 with
`drilling-stroke`, with the recorder running. The quill should:
- follow the hand: down 30 mm by t = 3 s, then slowly to the stop by t = 12.5 s, with no swing;
- rest on the stop until t = 13.5 s;
- return to the top in a fraction of a second when released, without bouncing.

Then open `...\runs\2026-10-31_run-001\checks\spring_return.usdc` with that run's
`record_joints.py`, press Play, and stop after a few seconds. The quill jumps to the stop and the
spring brings it home, now without the bounces v3-v7 had.

**If the panel shows no "MoonWalkers controls":** the scenarios still play from the console, so
report that. **If nothing moves on Play:** as in section 7, set `API = "omni.physx"` near the top
of the pasted runner.

## Warnings you can ignore
The first check (2026-10-17, Isaac Sim 6.2.0) showed no errors. It showed these warnings, which are
not about the twin files:
- "Skipping unsupported non-NVIDIA GPU" (the integrated Intel GPU);
- "No material configuration file";
- "Unexpected reference count ... while being closed in UsdContext" (also appears for Isaac Sim's own
  startup stage);
- `pxr.Semantics is deprecated`;
- an `omni.anim.graph.core` node-registration message ("Python import process in
  omni.anim.graph.core failed - 'NoneType' object is not subscriptable. Aborting Python node
  registration"), printed while extensions start, before any file is opened (seen again on
  2026-10-19);
- an omniclient "rejecting empty URL";
- "Snippet folder doesn't exist", when the Script Editor opens (seen on 2026-10-19).

One warning *was* about our files: the stage "has no usable time-code range". Since Phase 3 the
exporter sets a time range (0 to 1,000,000 at 60 per second), so files exported now should not show
it. The Phase 2 test files were made before that change.

Isaac Sim lit the stage with a directional light that is not in the file, so the files do not need
their own lights.

## If something looks wrong
- **Nothing moves on Play:** copy any console errors. Check that the joint shows an angular drive in
  the Property panel.
- **The spindle drops or flies away:** the joint is not holding it. Copy the console messages.
- **The spindle turns about the wrong axis, or wobbles:** the joint frame or axis is wrong.
- **The view is black:** Isaac Sim normally adds a light (see above). If it does not, add a dome
  light from the Create menu (not confirmed for 6.2).
