# Haas mill programs: the TM-1's axes, its home, the tool tip, and the G and M codes (2026-11-16)

**Question.** Phase 5 of `docs/lab-machines-plan.md` runs a Haas program on `haas/tm1@v3`,
measured by the tool tip's path. Before any code, Daniel asked (2026-11-16) for three answers from
Haas's filed manuals, with pages, and stand-ins, labelled and logged, where the manuals give none:
1. which way +X, +Y and +Z move on the TM-1;
2. where machine home is;
3. what "the tool tip" is in the twin.

Then: which G and M codes Haas's example programs use, what each does, and which example programs
to run.

**Dates and method.** Read on 2026-11-16 by Claude Code. The manuals were filed in Phase 1 and
Phase 4 (`data/machines/haas-tm1/inputs/SOURCES.md`, with their SHA-256); their text was read with
pypdfium2, and the figures quoted below were rendered to PNG and looked at. Page numbers are the
PDF's; the 2009 manual's printed page is the PDF's minus 8, the 2023 manual's is the PDF's.

## Sources
| Source | What it is | Used for |
|---|---|---|
| **Mill Operator's Manual 96-8000 Rev Y, December 2009** (`haas_mill-operators-manual_96-8000-rev-y_2009.pdf`, from https://haascnc.com/content/dam/haascnc/en/service/manual/operator/english---mill-operator's-manual---2009.pdf) | The Classic Haas Control's manual, 264 pages; the edition nearest this 2006 TM-1, whose pendant matches it [INFERENCE, Phase 4] | Every code's meaning, the home, +Z, the tool change |
| **2023 Mill Operator's Manual** (`haas_mill-operators-manual_ngc_2023.pdf`, from https://haascnc.com/content/dam/haascnc/en/service/manual/operator/english_mill_interactive_manual_print_version_2023.pdf) | The Next Generation Control's manual, 187 pages | Its two example programs, O40001 and O40006, and +X and +Y |
| **Tool Room Mill addendum 96-0041 rev B, 2/02** (`haas_toolroom-mill-operators-addendum_96-0041-rev-b_2002.pdf`) | The TM-1's own addendum (Phase 4) | The rapids, the travels, HOME G28 on the Tool Room Mill |

The two manuals are for different controls. Every code the two example programs use is defined in
the 2009 (Classic) manual too, with the same meaning (the table below), so the programs are read
by the 2009 manual's rules.

## 1. Which way +X, +Y and +Z move
**A program's coordinates are the tool's position relative to the table.** The 2009 manual, PDF
p. 148 (printed 140), defines the XY plane: "G17 Defined - Circular motion with the operator
looking down on the XY table from above. This defines the motion of the tool relative to the
table."

- **+X: the tool to the operator's right of the part, so the table moves to the operator's
  left.** The 2023 manual's basic program O40001 (PDF p. 102) says "(G54 X0 Y0 is top right
  corner of part)" and cuts "from X = 0.0, Y = 0.0 to X = - 4.0, Y = - 4.0": from the part's
  right edge, -X goes into the part, to its left. Its O40002 (PDF p. 107) starts at "(G54 X0 Y0
  is center left of part)" and drills five holes at X1.25 steps (`G99 G91 G81 F8.15 X1.25 Z-0.3
  L5`), which its figure (PDF p. 106) draws to the right of point 1. [INFERENCE: "right" and
  "left" in these comments and the figure are as the operator sees the part from the front.]
- **+Y: the tool towards the back of the part, so the table moves towards the operator.** O40001's
  X0 Y0 is the part's "top right corner", and -Y goes into the part. Seen "from above" (G17), the
  top of the part is the side away from the operator [INFERENCE].
- **+Z: up.** The 2009 manual's work offset set-up, PDF p. 65 (printed 57): "5. Press +Z (C). 6.
  Handle jog (D) the Z-axis approximately. 1” above the part." On the TM-1 the head carries Z
  (Phase 4: `axes_layout`), so +Z raises the head.

**In the twin's frame** (decision 0012: +x towards the operator, +z up, so +y is the operator's
right): Haas +X is +y, +Y is -x and +Z is +z, as the tool moves against the table. The twin's
joints move parts, not the tool: `x_axis` moves the table along +y, `y_axis` the saddle (with the
table) along +x, `z_axis` the head along +z. So **Haas X = -`x_axis`, Haas Y = +`y_axis`, Haas Z =
+`z_axis`**, each from its home. The reader works these signs out from the directions above and
the joints' axes, rather than taking them as typed numbers.

Not seen on the lab's machine: the visit list's item 1 (which way the table goes on +X) checks it.

## 2. Where machine home is
- **Home is machine zero, where a zero return goes.** 2009 manual, PDF p. 161 (printed 153), G53:
  "In the machine coordinate system, the zero point for each axis is the position where the machine
  goes when a Zero Return is performed." Power-up does one: "Power Up / Restart - On most machines,
  when this key is pressed, the axes will return to the machine zero position and a tool change
  may occur" (PDF p. 24, printed 16). The 2023 manual (PDF p. 95): "the axes move toward their home
  positions. The axes then move slowly until the machine finds the home switch for each axis."
- **Z home is at the top of Z's travel.** 2009 manual, PDF p. 67 (printed 59): "Tool Length is
  measured from the tip of the tool to the top of the part with the Z axis at its home position";
  PDF p. 53 (printed 45): "The control will bring the Z axis up to the machine zero position. The
  control will move the Z axis to a position above machine zero during a tool change but will never
  move below machine zero." So every program move is at or below Z0, and only a tool change goes
  above it. **Stand-in:** Z home is the top of the twin's cited 16 in of Z; the tool change's lift
  above zero is not modelled (the twin's Z stops at its home).
- **Y home: the table towards the operator.** O40001's completion blocks "move the table to a
  position from where the part can be unloaded and inspected" (2023 manual, PDF p. 102), by
  `G53 Y0 (Y home)` (PDF p. 105). So Y0 brings the table to the operator [INFERENCE], which is the
  + end of Y (the tool at the back of the table, from 1.). **Labelled [INFERENCE]**, not a stated
  position.
- **X home: not given by any source read.** No page says where X0 is in the travel. **Stand-in:**
  the + end of X (the table at its operator-left end), as Y and Z are at their + ends, so every
  machine position is 0 or below [INFERENCE]. The twin's photographed pose has the table 4.6 in
  from that end (decision 0034), which a homed machine left standing would explain, but nothing
  confirms it. The visit list's item 2 (the position display in machine coordinates, with a photo
  of the machine at that moment) settles it.
- **The zero return's order:** the Tool Room Mill's HOME G28 "will first move Z to Machine zero,
  then it will move X and Y" (2002 addendum, p. 14), and the Second Home button does the same
  (2009 manual, PDF p. 24). The plan's power-up zero return does likewise, at the cited 200 ipm
  rapids [stand-in: the manuals give no homing speed; the 2023 manual says the axes "move slowly"
  only while finding the switch].

So the machine coordinates of the twin's 0 (its photographed pose) are X -4.6 in, Y -6.0 in
(Y's middle, not measured) and Z -10.0 in.

## 3. What "the tool tip" is in the twin
Haas's programs give the **tool tip's** position: with G43 "the tool length in the offsets page is
added to the commanded axis position" (2009 manual, PDF p. 154, printed 146), and the length is
"measured from the tip of the tool to the top of the part with the Z axis at its home position"
(PDF p. 67). `haas/tm1@v3` has a spindle nose stand-in and no tool (Phase 4).

- **The tool tip is a point on the spindle's axis, a stand-in tool length below the nose's face,**
  carried by the head. Moving only with X, Y and Z, its path against the table is the axes'
  motion; the length shifts it in Z only, so it does not change any distance measured between the
  plan and a recording.
- **Stand-ins, labelled in each program file and in `PROGRAM.md`:**
  - a tool **3.0 in** long from the nose's face, of the diameter the program's comment gives
    (O40001: "T1 is a 1/2” end mill"; O40006: "T1 is a .250 dia endmill");
  - a **2.0 in** block of stock on the table's top, under the program's path;
  - the work offset G54 X and Y, chosen so the program's path is centred on the table;
  - G54 Z = 0, and the tool's length offset H found as the manual's touch-off finds it: the
    machine Z where the tip meets the top of the stock (2009 manual, PDF p. 67: "Press Tool Ofset
    Mesur (J). This will take the Z position located in the bottom left of the screen and put it
    at the tool number position"), measured on the twin's own geometry;
  - cutter compensation's diameter offset D = 0 (below).
- **On the twin:** the nose's face is 9.81 in over the table top at the twin's 0 (the front
  photo's 10 in) and 19.81 in at Z home (the cited "Spindle Nose To Table: 4 inches to 20
  inches"). With the stand-ins, H01 = -14.81 in.
- The program folder draws the stand-in tool and stock, and the programmed path on the table, so
  a reviewer sees the tip follow it in Isaac Sim. They are pictures only: no collision, no mass.

## 4. The G and M codes the programs use
From the 2009 manual (PDF pages; printed = PDF - 8) unless noted.

| Code | What the manual says | How the reader takes it |
|---|---|---|
| G00 | "Generally, rapid motion will not be in a straight line. Each axis specified is moved at the same speed, but all axes will not necessarily complete their motions at the same time" (p. 139) | Each axis at its cited rapid, 200 ipm, on its own |
| G01 | "Once a G01 is started all programmed axes will move and reach the destination at the same time. If an axis is not capable of the programmed feedrate the control will not proceed with the G01 command and an alarm (max feedrate exceeded) will be generated." (p. 139) | A straight line at F along the path [INFERENCE: F is the path's feed]; an axis asked for more than its cited speed is refused, as the alarm |
| G02 / G03 | CW / CCW; "I, J and K addresses are the distances from the starting point to the center of the circle"; "Use a positive R-value for radii of 180° or less, and a negative R-value for radii more than 180°"; "To cut a full circle, do not specify an ending point" (pp. 140-141); a Z move on the same block makes a helix (p. 142) | XY plane only (G17); I/J or R; full circles; helices |
| G04 | "G04 P10. is a dwell of 10 seconds; G04 P10 is a dwell of 10 milliseconds" (p. 145) | As stated |
| G17 | (above, p. 148) | The plane; G18 and G19 are refused (no program read uses them) |
| G20 / G21 | Inch / metric; "Selection between inch and metric programming should be done using Setting 9" (p. 149) | Setting 9 is a stand-in: inch, the unit both programs are written in ("F20. specifies that the feed rate for the motion is 20” (508 mm) / min", 2023 manual, p. 104) |
| G28 | "used to return all axes to machine zero, unless an axis (or axes) is specified"; with G90 it moves through the given point first, with G91 "directly to machine coordinate Z = 0"; "G28 cancels tool length offsets" (pp. 149-150) | As stated, at rapid |
| G40 / G41 / G42 | Cutter compensation; "A D address must be programmed to select the correct tool radius or diameter offset" (p. 153) | Taken only with a diameter offset of 0 (a stand-in), when the tool's centre follows the programmed path; any other offset is refused, since the offset path is not modelled |
| G43 / G49 | "the tool length in the offsets page is added to the commanded axis position" (p. 154); G49 cancels it, as do "H0, G28, M30" (p. 158) | As stated |
| G53 | Non-modal machine coordinates (p. 161) | As stated |
| G54-G59 | "select one of the six user coordinate systems" (p. 161) | Offsets from the program file's set-up |
| G80, G94 | Canned cycle cancel; feed per minute (p. 181) | Accepted; G80 has nothing to cancel, since canned cycles are refused |
| G90 / G91 | Absolute / incremental (p. 180) | As stated |
| M00 / M01 | Stop; "M01 works the same as M00, except the Optional Stop feature must be on" (p. 207) | M00 refused (it waits for a person's Cycle Start); M01 skipped, the Optional Stop being off (a stand-in), and logged |
| M03 / M04 / M05 | Spindle forward, reverse, stop; "S5000 will command a spindle speed of 5000RPM" (p. 207) | The spindle turns at S, up to the cited 4000 rpm, with no run-up (none is cited) |
| M06 | "M06 T12 this will put tool 12 into the spindle. If the spindle is running, the spindle and coolant (including TSC) will be stopped by the M06 command." (p. 207); Z goes to machine zero first (p. 53); an umbrella changer is loaded tool 1, ATC FWD, tool 2, ... (p. 60), so tool n sits in pocket n [INFERENCE] | Spindle stops; Z to home at rapid; the carousel turns to pocket n at a stand-in second per pocket |
| M08 / M09 | Coolant on / off (p. 207) | Logged; no coolant in the twin |
| M02 / M30 | Program end; M30 "stops the spindle and turns off the coolant ... M30 cancels tool length offsets" (pp. 207, 209) | The end |

And the block's rules:
- "Only one M code may be programmed per line of code. All M codes take effect at the end of the
  block." (p. 207) The reader refuses two, and runs the M code after the block's motion.
- Numbers without a decimal point: Setting 77 (p. 229): "F12 becomes: 0.0012units/minute with
  Setting 77 Off" and "It is recommended that programmers always use a decimal point". The reader
  refuses a non-zero X, Y, Z, I, J, K, R or F without one, rather than guess Setting 77; `X0` is 0
  either way.

**Refused, with the reason:** canned cycles (G73-G89), cutter compensation with an offset,
corner rounding and chamfers (`,R` and `,C`), G12/G13 pocket milling, sub-programs (M97, M98),
macros (`#`), block delete (`/`), feed per revolution and inverse time (G93, G95), other planes,
scaling and rotation. None is in the programs below.

## 5. The programs
- **O40001, "Basic program"** (2023 manual, PDF p. 102): a tool change, a rapid to X0 Y0, the
  spindle at 1000 rpm, a feed 0.1 in down at 20 in/min, a straight cut to X-4. Y-4., and the
  return: Z home (`G53 G49 Z0 M05`) and Y home (`G53 Y0`). Lines only.
- **O40006, "Cutter comp ex-prog"** (2023 manual, PDF p. 172): a contour round a 4 by 4.5 in
  part, 1 in deep at 50 in/min, with six arcs (`G02`/`G03` with R) and lines, under G41 with D01.
  "This program uses cutter compensation. The tool path is programmed to the centerline of the
  cutter." With D01 = 0 (the stand-in) the tool's centre follows the printed path. On a real
  machine with D01 set to the .250 in tool, the cut would lie 0.125 in to the left of it.
- **The 2009 manual's own examples** use what the reader refuses: O1234 (p. 140) corner rounding
  and chamfers, O02300 and O02400 (pp. 143-144) cutter compensation with an offset on thread
  milling. They stay for later.
- **The lab's own program:** none has been shared for the TM-1.

## 6. What is not cited, and stays a stand-in
| What | Stand-in | Why |
|---|---|---|
| The axes' acceleration | 1000 mm/s², each axis and each path | No source read gives one; `--acceleration 0` plans without it |
| Corner blending | none: each block ends at rest | Not read; the plan stops at every block's end |
| Spindle run-up and stop | none: at S at once | No time is cited |
| The tool change's time | 1 s per pocket the carousel turns; its slide to the spindle and Z's lift above home not modelled | No time is cited (Phase 4's hand-off) |
| Which pocket faces the spindle at the start | pocket 1 | Not photographed |
| Which way ATC FWD turns the carousel | the twin's + direction | Not cited |
| Setting 9 (units) | inch | Both programs are in inches |
| Work offsets, tool length, stock | above (3.) | An operator's set-up, not the machine's |
| X home | the + end of X | Not cited (2.) |
