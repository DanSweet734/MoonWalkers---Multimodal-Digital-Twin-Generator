# Checking an exported twin in Isaac Sim 6.2.0

Purpose: confirm by eye that an exported twin opens in Isaac Sim at the right size and that its
joint moves. Phase 2 does this with the synthetic box-and-cylinder test twin. Phase 3 repeats it
with the HA5C. The files have already passed both validators (our own and NVIDIA's asset
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

One warning *is* about our files: the stage "has no usable time-code range". It does not affect
these checks. The exporter will set a time range in Phase 3, before controllers need it.

Isaac Sim lit the stage with a directional light that is not in the file, so the files do not need
their own lights.

## If something looks wrong
- **Nothing moves on Play:** copy any console errors. Check that the joint shows an angular drive in
  the Property panel.
- **The spindle drops or flies away:** the joint is not holding it. Copy the console messages.
- **The spindle turns about the wrong axis, or wobbles:** the joint frame or axis is wrong.
- **The view is black:** Isaac Sim normally adds a light (see above). If it does not, add a dome
  light from the Create menu (not confirmed for 6.2).
