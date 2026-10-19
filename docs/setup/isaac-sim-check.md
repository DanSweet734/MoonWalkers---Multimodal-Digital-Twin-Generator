# Checking an exported twin in Isaac Sim 6.2.0

Purpose: confirm by eye that an exported twin opens in Isaac Sim at the right size and that its
joint moves. Phase 2 does this with the synthetic box-and-cylinder test twin. Phase 3 repeats it
with the HA5C (section 6). The files have already passed both validators (our own and NVIDIA's asset
validator), so this step checks what only the simulator can show.

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

## Warnings you can ignore
The first check (2026-10-17, Isaac Sim 6.2.0) showed no errors. It showed these warnings, which are
not about the twin files:
- "Skipping unsupported non-NVIDIA GPU" (the integrated Intel GPU);
- "No material configuration file";
- "Unexpected reference count ... while being closed in UsdContext" (also appears for Isaac Sim's own
  startup stage);
- `pxr.Semantics is deprecated`;
- an `omni.anim.graph.core` node-registration message;
- an omniclient "rejecting empty URL".

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
