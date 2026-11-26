# The Haas VF-3's and its trunnion's sources: what each says, and where they disagree

**Question:** which facts about the lab's VF-3 (made 12/2014, nameplate photo `134114`) and the
trunnion on its table do the sources give: the mill's sizes and axes, the trunnion's model, how
Haas names its two axes, which way they turn, how fast, and how far. The lab's machines plan,
Phase 6, before generating. Written by Claude Code on 2026-11-16 (the downloads are dated
2026-11-17 UTC).

**Answer, in short:**
- **No source for the 2014 unit itself turned up.** Today's product page and layout drawing (2/2023)
  give the travels, **40 x 20 x 25 in**, the same as a dealer's listing of a 2013 unit; the twin
  uses today's sizes, logged as an issue.
- **The enclosure is 78.8 in tall** to its sheet metal, and the table's top is 37 in from the
  floor (the layout drawing, p. 3). The 78.8 in scales the generated mesh, as the TM-1's 109 in
  operating height did [INFERENCE: read off the drawing's dimension line].
- **The table carries X and Y, the head Z** (the layout drawing, p. 4), as on the TM-1.
- **Haas names the trunnion's axes A (the 4th, the tilt) and B (the 5th, the platter's turn)**
  (the 2012 mill manual, pp. 171-177). They are the mill's own axes: Settings 30 and 78 pick the
  rotary unit, and G00 and G01 take an A address (pp. 175, 181).
- **The trunnion is a Haas TR**, a cradle between two supports (the 2026 guide, p. 8; photo
  `133959`), and **the TR160 by elimination** [INFERENCE]: its plate is not readable. A tilts
  **±120°** and B turns **360°** on every TR (the 2004 TRT manual, p. 7; the 2026 guide, p. 12),
  so the ranges hold whatever the model. The TR160's speed, **80°/s on both axes**, and its
  sizes are labelled stand-ins.
- **Which way +A and +B turn is not settled by a source:** the 2011 rotary manual gives the right
  hand rule for the *tool's* motion and says the table turns the opposite way, then notes that
  table movements "depending on the equipment, parameter settings" differ (pp. 34-35).
- **The 2012 manual disagrees with itself twice** on rotary moves: a feed in degrees per second
  against one in inches per minute through a diameter; and rapids "not allowed" against G00 with an
  A address. Decision 0036 chooses.

## Sources
Haas's PDFs are filed under `data/machines/haas-vf3/inputs/documents/`, with their SHA-256 in
`inputs/SOURCES.md` (gitignored: the folder also holds the nameplate photo). The facts and quotes
are in `backend/src/moonwalkers/pipelines/b/haas_vf3.reference.json`, written by
`data/machines/haas-vf3/part_cutting/2026-11-16_spec/write_vf3_reference.py`; 61 of its 62 quotes
were found on their pages by `pipelines.b.quotes` (the 62nd reads the nameplate photo). Page
numbers are the PDF's (the 2012 manual's printed page is the PDF page less 12).

| Source | What it is | Describes |
|---|---|---|
| [96-8000 Rev AP, December 2012](https://haascnc.com/content/dam/haascnc/en/service/manual/operator/english---mill-operator's-manual---2012.pdf) | The mill operator's manual for the Classic Haas Control, 314 pages (filed in Phase 1); "4TH AND 5TH AXIS PROGRAMMING", pp. 171-177 | Every Haas mill of 2012 |
| [VF-3 product page](https://haascnc.com/machines/vertical-mills/vf-series/models/medium/vf-3) | Saved by Daniel in a browser on 2026-11-10 (Haas's HTML pages answer scripts 403); its JSON-LD carries the specs | Today's VF-3 |
| [Machine Layout Drawing VF-3/SS, 2/23/2023](https://pub-aem.haascnc.com/content/dam/haascnc/pdp_feed/mld/vf-3_ss_mld__2_2023.PDF) | 7 pages, linked from the saved product page; fetched 2026-11-17 | Today's VF-3 and VF-3SS |
| [Rotary Operators Manual 96-0315 Rev H, June 2011](https://www.haascnc.com/content/dam/haascnc/en/service/manual/operator/english---rotary-operator's-manual---2011.pdf) | 92 pages; "Dual axes coordinate system" (pp. 34-35), the TR assembly drawings (p. 89); fetched 2026-11-17 | Haas rotaries and trunnions of 2010-11 |
| [TRT Series Operators Manual 96-5048J Rev J, June 2004](https://www.haascnc.com/content/dam/haascnc/en/service/manual/operator/english---trt-tilting-table-operator%27s-manual---2004.pdf) | 80 pages; "1.7 TR SPECIFICATIONS" for the TR160, TR210 and TR310 with mounting drawings (pp. 7-9); fetched 2026-11-17 | Haas's trunnions of 2004 |
| [Rotaries & Indexers guide, 2026-08](https://www.haascnc.com/content/dam/haascnc/assets/printdocuments/rotary-guide/2026-08-RotariesAndIndexers-Guide.pdf) | 13 pages; trunnions (p. 8), the table of 5th-axis rotaries (p. 12); fetched 2026-11-17 | Today's models |
| [TR160 product page](https://haascnc.com/machines/rotaries-indexers/5-axis-rotaries/models/tr160) | Saved by Daniel in a browser on 2026-11-16 at Claude Code's request (the page answers scripts 403); its specs table and JSON-LD | Today's TR160 |
| The lab's photos (2026-11-05) | `133735` to `133846` the enclosure from five places; `133927`, `133932`, `133938`, `133959` the inside with the trunnion | This unit |

Not used: a dealer's TR210 specification PDF was encrypted.

## The mill

| Fact | Value | Source | Disagreement |
|---|---|---|---|
| Travels X, Y, Z | 40.00, 20.00, 25.00 in | product page; layout drawing p. 4 | none; a 2013 unit's listing agrees |
| Spindle nose to table | 4.1 to 29.1 in | layout drawing p. 4 | the product page says 4.2 to 29.2 in; the drawing is used, being the more detailed |
| Table | 48.0 x 18.0 in, 5 T-slots 80 mm apart | product page | |
| Table height | 37 in | layout drawing p. 3 | |
| Enclosure height | 78.8 in (2002 mm) | layout drawing p. 3 [INFERENCE: which line it is read off the drawing] | |
| Operating height | 121.9 in (the spindle's top 121.8 in) | layout drawing pp. 1, 3 | |
| Rapids | 1000 ipm on X, Y and Z; cutting 650 ipm | product page | today's VF-3; the 2014 unit's not found |
| Spindle | 8100 rpm, 40 taper | product page | the 2014 unit's not confirmed |
| Tool changer | a 20-pocket carousel | product page | not seen in the photos: left out of the twin |

The layout drawing draws the table at both ends of X and Y under a fixed spindle and the head at
both ends of Z on the column (p. 4): **the table carries X on the saddle, the saddle Y on the
base, the head Z on the column**, as on the TM-1 (decision 0034).

## The trunnion

### Its names and the control
The 2012 mill manual, "4TH AND 5TH AXIS PROGRAMMING":
- "A-Axis ±120º" and "B-Axis 360º" on the figure "Axis motion on the VR-11 Mill and the Haas
  TRT 210" (p. 171);
- jogging: the jog keys "will select the A axis for jogging. The B axis can be selected for
  jogging by pressing the Shift button" (p. 173);
- "Jog and command the 5th axis using the B address." (p. 177);
- "the distance between the plane of the B-axis platter and the A-axis centerline on tilting
  rotary products" (p. 177): the platter (B) rides on the cradle (A);
- "Setting 30 (and Setting 78 for the 5th axis) specifies a parameter set for a given rotary
  unit", and "The rotary model highlighted in the control must match the model engraved on the
  rotary unit's identification plate." (p. 175);
- "M10/M11 engages/disengages the A-axis brake", M12/M13 the B brake (p. 172);
- "All Haas indexers home in the clockwise direction as viewed from the front." (p. 176).

So **A is the cradle's tilt and B the platter's turn, and the mill's control drives both** (the
inference of `2026-11-06-lab-machines.md`, now cited).

### Which model
The photos show a cradle between two end housings carrying one round platter with a vise
(`133959`, `133938`). Haas's TR family is built that way ("Dual-axis trunnion construction holds
the part rigidly between two supports", the 2026 guide, p. 8; an "A-axis Drive" and an "A-axis
Slave", one at each end, the 2011 rotary manual, p. 89).

| Model | Platter | A and B speed | Fits a VF-3? |
|---|---|---|---|
| TR160 | 6.3 in (160 mm) | 80°/s and 80°/s | yes (39.1 in long [read off the drawing], on a 48 in table) |
| TR210 | 8.27 in | 60°/s | no [INFERENCE]: its mounting drawing adds to 37.14 + 9.46 + 2.99 = 49.6 in, longer than the 48 in table (p. 9) |
| TR310 | 12.2 in | 50°/s | no: "Smallest compatible Mill ... VF-6" (2026 guide, p. 8) |

The trunnion in `133927` is about 0.6 of its table's length; the TR160's 39.1 in would be 0.81
[INFERENCE: measured on the photo, which the lens stretches at its edges]. **The TR160 is used
as a labelled stand-in until its plate or the control's Setting 78 is read** (the visit list,
item 10). The A and B ranges hold for any TR: "A-axis travel: ±120° across the lineup, except
TRT70 (120° to -95°). B-axis: 360° continuous on all models." (2026 guide, p. 12.)

The TR160's figures (2004 TRT manual, p. 7): "Travels: A - +/- 120° (tilt), B - 360 (rotate)";
"Platter: Diameter 6.3” (160mm)"; "Speed: A-axis 80° per sec / B-axis 80° per sec"; "Max swing
at 90°: 14.4” (366mm) located 0.125” (3.1mm) below centerline of A-axis", read as the platter's
face 3.1 mm below the A axis [INFERENCE]; from its drawing, the A axis 7.00 in above the base
[INFERENCE: read off the drawing; its labels are not in the text].

**Today's TR160 page agrees** on what the twin uses: "Spindle - A (tilt)" and "Spindle - B
(rotary)" each at "Max Speed 80 °/sec"; "Indexing - A (tilt)", "Max Rotation/Step ± 120 °"; a
"Platter Diameter 6.30 in"; and "The unit fits into VF-2 and larger VF Series machines". It
**disagrees on the swing:** "Part Swing Max 17.5 in", against the 2004 manual's "Max swing at
90°: 14.4”". Neither sizes the twin, which takes its sizes from the photos. The page also asks
for "NGC software version 100.21.000.1130 or later", while dealers' listings of the TRT160 and
TRT210 ask for "software version 18.00 or later" (`2026-11-06-lab-machines.md`; a Classic
control's numbering [INFERENCE]), so the trunnion does not tell which control the VF-3 runs.

### Which way they turn
The 2011 rotary manual, "Dual axes coordinate system" (p. 34): "The A-axis is rotary motion about
the X-axis, while the B-axis determines rotary motion about the Y-axis. ... the right hand rule
determines direction of tool movement and not the table movement direction. For the right hand
rule, the fingers will point opposite of the positive rotary table movement." Its note under the
figures (p. 35): "Different table movements are possible, for positive directions, depending on
the equipment, parameter settings, or five-axis programming software being used."

On the lab's trunnion B turns the platter about its own normal, the machine's Z when A is 0, not
about Y [INFERENCE: the photos; the manual's B-about-Y is a tilting rotary's other layout]. So:
- **+A**: the tool turns about +X by the right hand rule, so the cradle turns about -X; a cited
  rule, with the p. 35 caveat;
- **+B**: the same rule carried to the platter's normal, the platter turning about -Z at A = 0;
  a labelled stand-in [INFERENCE].
The lab's control would settle both: jog +A and +B and watch (the visit list).

### Rotary feeds and rapids
The 2012 manual disagrees with itself:
- "G01 A90. F50. will rotate the A-Axis 90 degrees at 50 degrees per second" (p. 173), against
  Setting 34, where the control "must know the diameter of the part being machined in the A-axis
  in order to compute angular feedrate" (p. 271): a feed in inches per minute;
- "Rapid moves are not allowed" in its five-axis notes (p. 173), against G00's "A Optional A-axis
  motion command" (p. 181).
Decision 0036 chooses how the reader takes them.

## What the twin uses
- Scale: the enclosure's 78.8 in height.
- The table, the saddle and the head on X, Y and Z, with today's travels (logged).
- The trunnion as two revolute joints on the table: A (the cradle) ±120°, B (the platter, on the
  cradle) continuous, with the TR160's 80°/s and sizes as labelled stand-ins.
- The tool changer left out (not in the photos), and a program's M06 logged.

## Sources still to come
- **Haas's TR160 page:** saved by Daniel on 2026-11-16 (above).
- **At the next visit** (the plan's visit list, item 10; Daniel raises it at the meeting of
  2026-11-19 when scheduling the visit): the trunnion's plate (lower left of the cradle's base in `133959`), or
  the control's Setting 78 and Setting 30; the control's generation (Classic or Next Generation);
  a jog of +A and +B, watched from the front.

## Update, 2026-11-17: how the 2012 manual programs A and B
Read for decision 0036 (Claude Code, 2026-11-17), from the filed 2012 manual (96-8000 Rev AP,
PDF pages; its text taken with pypdfium2):
- **Units:** "5th-axis programming is not affected by the selection of inch (G20) or metric (G21),
  as A and B axes are always programmed in degrees." (p. 172)
- **Which codes take them:**
  - G00 and G01 list "A Optional A-axis motion command" (p. 181);
  - G28 "returns all axes (X, Y, Z, A and B) simultaneously to the machine zero position when no
    axis is specified on the G28 line" (p. 191);
  - Haas's own examples rapid to "A0 B0" (G141's, p. 233) and end with "G91 G28 B0. A0."
    (G161's and G162's, pp. 244-245). Those examples are for a machine whose head tilts (G143,
    the VR-11), so the reader does not run them.
- **Moving together:** "G93 inverse time must be in effect for simultaneous 5-axis motion."
  (p. 172). "Settings 34 and 79 (4th & 5th axis diameter) are not necessary when using G93."
  (p. 225)
- **A rotary feed, defined:**
  - G01: "F Feedrate in inches (mm) per minute" (p. 181);
  - Setting 34: "This is used to set the diameter of the A-axis (0.0 to 50 inches), which the
    control will use to determine the angular feedrate. The feedrate in a program is always
    inches per minute (or mm per minute), therefore, the control must know the diameter of the
    part being machined in the A-axis in order to compute angular feedrate." (p. 271);
  - Setting 79: the same for the B axis (p. 277).

  Against these, p. 173's example: "G01 A90. F50. will rotate the A-Axis 90 degrees at 50
  degrees per second". Decision 0036 takes the definitions [INFERENCE: three statements against
  one example].
- **Rapids:** "When in the rapid mode, the axes will arrive at the programmed position at
  different times; the axis with shortest distance from target will arrive first" (p. 172).
  "Rapid moves are not allowed; rapid motions, entering and exiting holes (full retract
  peck-drill cycle) are not supported." (p. 173, under "Feed Rates" for 4- and 5-axis code).
  Decision 0036 reads the second as for 5-axis cutting [INFERENCE].
- **Brakes:** "It is highly recommended that the A/B brakes be engaged when doing any non 5-axis
  motion." M10/M11 and M12/M13 (p. 172).
- **Not found:** the trunnion's acceleration and how the control turns an absolute B (the shorter
  way or not). Both stay stand-ins.

The 2011 rotary manual's feeds (pp. 23-49: "The feed rate corresponds to degrees rotated per
second", p. 45) belong to the rotary's own servo control, as on the HA5C, not to the mill's
4th and 5th axes.

## Update, 2026-11-25: the plate is read, and the control's keys
From Daniel's photos of the lab visit of 2026-11-19 (filed in `data/machines/haas-vf3/inputs/`,
`SOURCES.md`; read by Claude Code on 2026-11-25):
- **The trunnion is a TR160.** Its plate, photographed square on (`20261119_133507`), reads
  "MODEL NO. TR160", with an S/N (kept in `data/`) and a "VER" stamped too faintly to read with
  confidence. "The TR160 by elimination [INFERENCE]" above is now the plate's own word, and the
  TR160's figures from the 2004 TRT manual and today's page are the model's, no longer a guess at
  the model. Which way +A and +B turn and where they home are still not read (no jog).
- **The control is the Classic Haas Control,** by its keypad (`20261119_133254`, the screen off):
  its keys read "PARAMETER DIAGNOSTIC", "SETTING GRAPHIC" and "POWER UP RESTART". The 2012 manual
  names these combined keys: "Param / Dgnos (Parameters / Diagnostics)" and "Setng / Graph
  (Settings / Graphics)" (PDF pp. 35-36) and "POWER UP/RESTART" (PDF p. 15). The 2023 NGC manual
  lists separate keys: "Diagnostics DIAGNOSTIC", "Settings SETTING" (PDF p. 35) and "Power up POWER
  UP" (PDF p. 34). So the 2012 manual, used for the reader's A and B (update of 2026-11-17), is
  the right generation; its software version is still to read off the screen.
- **Still to ask** (the advisors, 2026-11-19, for the next visit): Settings 78 and 30, and a jog of
  +A, then +B.
