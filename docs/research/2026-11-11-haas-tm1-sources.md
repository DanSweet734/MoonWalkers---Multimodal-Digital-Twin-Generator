# The Haas TM-1's sources: what each says, and where they disagree

**Question:** which facts about the lab's TM-1 (made 11/06, nameplate photo `134411`) do the
sources give, which part carries which axis, which control it runs, and where the sources
disagree. The lab's machines plan, Phase 4, first checklist item. Written by Claude Code on
2026-11-11.

**Answer, in short:**
- Haas's own **Tool Room Mill addendum of 2/02** (96-0041 rev B) has a specifications table for
  the TM-1 of that time: travels **30 x 12 x 16 in**, a 47.75 x 10.5 in table, 4 to 20 in from
  the spindle nose to the table, 4000 RPM, 200 ipm rapids, and operating dimensions of 90 x 64 x
  109 in. It is the nearest source to this unit, and the twin uses it.
- **The Y travel is 12 in** on that addendum, the 2018 sheet and dealers' listings of 2006-07
  units, and **16 in** on today's product page, pre-install guide and layout drawing. 12 in is
  used: today's pages describe today's enclosed TM-1.
- **The table carries X, the saddle Y, the head Z** (today's layout drawing, p. 4; the 2009
  addendum's TM-1 figure, p. 12).
- **The tool changer is an umbrella carousel of 10 pockets**: the umbrella type from the 2009
  mill manual and the photos, the 10 from dealers' listings and the 2018 sheet's TM-P, consistent
  with the photos' pocket spacing [INFERENCE].
- **The control is likely the Classic Haas Control** [INFERENCE from the pendant's keys], not
  confirmed.

## Sources
All accessed 2026-11-09 to 2026-11-11; Haas's PDFs are filed under
`data/machines/haas-tm1/inputs/documents/` with their SHA-256 in `inputs/SOURCES.md` (gitignored:
the folder also holds the nameplate photo).

| Source | What it is | Describes |
|---|---|---|
| [96-0041 rev B, 2/02](https://www.haascnc.com/content/dam/haascnc/en/service/manual/supplement/96-0041B-Toolroom-Mill.pdf) | The Tool Room Mill's operator's addendum, 16 pages, with a specifications table (p. 5) | The TM-1 of 2002 (named "Tool Room Mill") |
| [96-0041 Rev T, January 2009](https://www.haascnc.com/content/dam/haascnc/en/service/manual/supplement/english---toolroom-mill-operator%27s-manual-supplement---2009.pdf) | The same addendum, later edition; no specifications; a TM-1 figure of the axes' ballnuts and guides (p. 12) | TM-1, TM-2, TM-1P of 2009 |
| [96-8000 Rev Y, December 2009](https://haascnc.com/content/dam/haascnc/en/service/manual/operator/english---mill-operator's-manual---2009.pdf) | The mill operator's manual for the Classic Haas Control (filed in Phase 1) | Every Haas mill of 2009 |
| [Toolroom Series sheet, V20180208](https://haascnc.com/content/dam/haascnc/machines/vertical-mills/toolroom/assets/Vertical_ToolroomSeries.pdf) | 2 pages (filed in Phase 1) | Today's TM models, 2018 |
| [Machine Layout Drawing TM-1/TM-1P, 3/6/2023](https://pub-aem.haascnc.com/content/dam/haascnc/pdp_feed/mld/tm-1_1p_mld_03_2023.PDF) | 5 pages, linked from the pre-install guide; fetched by script on 2026-11-11 | Today's enclosed TM-1/TM-1P |
| Product page and pre-install guide ([tm-1](https://haascnc.com/machines/vertical-mills/toolroom-mills/models/tm-1), [pre-install](https://haascnc.com/pre-install-guide/tm-1)) | Saved by Daniel in a browser on 2026-11-10 (haascnc.com's HTML pages answer scripts 403) | Today's TM-1 |
| [A dealer's listing of a 2007 TM-1](https://surplusrecord.com/listing/haas-tm-1-cnc-toolroom-mill-47-5-x-10-5-table-30-x-12-y-16-z-7-5-hp-4000-rpm-10-automatic-tool-changer-cat-40-4th-axis-enabled-rigid-tapping-2007-1141865/) | Second-hand; the page answered a script 403 on 2026-11-11, so its title is quoted from its URL | A used 2007 TM-1 |
| The lab's photos (2026-11-05) | `134300`, `134314`, `134337`, `134346`, `134355` show the head, the carousel, the saddle and the pendant | This unit |

## The facts, and where the sources disagree
| Fact | 2002 addendum (p. 5) | Today's pages | Others | Used |
|---|---|---|---|---|
| X travel | "X - 30 inches" | "30.00 in" | 2018 sheet: 30 in | 30 in |
| **Y travel** | **"Y - 12 inches"**; p. 13: "(X=30, Y=12, Z=16)" | **"16.00 in"**, also the layout drawing's "16in [406mm] Y-Axis Travel" (p. 4) | 2018 sheet: "30” x 12" x 16"" for the TM-1; the 2007 listing's title: "30-x-12-y-16-z" | **12 in** (below) |
| Z travel | "Z - 16 inches" | "16.00 in" | | 16 in |
| Spindle nose to table | "4 inches to 20 inches" | "4.0 in" to "20.0 in" | | 4 to 20 in |
| Table | "Length - 47.75 inches", "Width - 10.5 inches", 3 T-slots 0.625 in, 4.00 in apart | 47.8 x 10.5 in; T-slots 0.626-0.630 in | Listings: 47.5 or 47.75 in | 47.75 x 10.5 in |
| Table capacity | "Capacity: 300 lbs." | 350 lb | | 300 lb |
| Spindle | "#40 Taper", "0-4000 RPM", "Direct-Speed Belt Drive", "7.5HP peak" | 4000 rpm, 7.5 hp | 2018: "4000-rpm, Belt Drive (TM)" | 4000 RPM |
| Rapids, X Y Z | "200 ipm" each; cutting feed 200 ipm | 200 ipm each | | 200 ipm |
| Overall size | "Operating Dimensions Width - 90 inches, Depth - 64 inches, Height - 109 inches." | An enclosed machine, 106.6 in to its top (layout drawing, p. 3): a different build | | 90 x 64 x 109 in, size checks |
| Weight | "Weight - 3300 lb" | 4440 lb (shipping) | | 3300 lb (not used: masses are placeholders) |
| Tool changer | none named | The 2018 sheet: "No Tool Changer (TM)" as standard, "10-Station Carousel (TM-P)" | The 2009 mill manual: "Tool Changer (Umbrella Type)" (p. 19); the 2007 listing: "10-automatic-tool-changer"; the photos: an umbrella carousel | Umbrella, 10 pockets |

### Why 12 in of Y travel
- The 2002 addendum is Haas's own document of the Tool Room Mill, from four years before this
  unit, and states 12 in twice (p. 5 and p. 13). The 2018 sheet still gives 12 in for the TM-1,
  and the listings of 2006-07 units say the same.
- The 16 in is on pages that describe today's TM-1, which is enclosed (layout drawing, p. 3) and
  has no tool changer as standard (2018 sheet): a different build from the lab's open-framed unit
  with its umbrella carousel.
- So 12 in fits this 11/06 unit best [INFERENCE]. A tape measure at the lab would settle it
  (plan, "A planned visit to the lab").

### Which part carries which axis
- **Today's layout drawing, p. 4 ("X&Y-AXIS TRAVEL", "Z-AXIS TRAVEL"):** the table is drawn at
  both ends of its X travel and of its Y travel, from above; the head's spindle at both ends of
  Z, from the front.
- **The 2009 addendum, p. 12** ("TM-1 pictured."): the Z ballnut and Z linear guide on the head's
  column side; the X and Y ballnuts and linear guides on the saddle, under the table.
- So the table slides in X on the saddle, the saddle in Y on the base, and the head in Z on the
  column. The order of the table and the saddle (the saddle under the table) is what the photos
  show: the saddle, with two red handles, under the table in `134337`.
- **At the middle of X and Y the table's centre is under the spindle** [INFERENCE, measured on
  the drawing: the two drawn tables' centres are 641 and 1165 px across a 2754 px render, the
  spindle at 900; front to back 655 and 370 px, the spindle at 510]. The twin places its X and Y
  ranges by this.
- **The red handwheels** on the saddle are the "Manual handles" of the 2002 addendum (p. 4;
  "Manual jogging on the X and Y-axis", p. 12, which releases the servos) [INFERENCE]. They are
  modelled as part of the saddle; they do not turn in the twin.
- **The chip guard** in front of the table moves with the table [INFERENCE]: the 2009 addendum
  (p. 12) says its height is adjustable "to gain additional clearance from the operator pendant",
  which only matters if it travels in X towards the pendant.

### The tool changer
- **Umbrella type:** the 2009 mill manual names the "Tool Changer (Umbrella Type)" (p. 19); "ATC
  FWD / REV - Rotates the tool turret to the next / previous tool" (p. 30). The photos show a
  round carousel beside the head, its pockets numbered underneath (`134300`: 9, 8, 7, 6;
  `134337`: 6, 5, 4), a motor and rollers on a rail behind it (`134346`, `134355`).
- **10 pockets:** the 2007 listing and the 2018 sheet's TM-P. On `134337` the numbers 6, 5 and 4
  lie about 31 to 32 degrees apart round the pocket ring (measured from the ring's centre and
  half-width on the photo), close to the 36 degrees of 10 pockets; the numbers sit inside the
  ring's edge, which makes the measured angle small [INFERENCE]. An 18 or 20-pocket carousel
  would give 18 to 20 degrees. The highest number was not photographed.
- **Its place:** today's drawing gives "15.6in [395mm]" from the carousel's centre to the
  spindle's (p. 4), on the operator's left, and draws it about 18 in across [INFERENCE, measured
  against the drawing's 30 in X travel].
- **Not modelled:** the carousel's slide towards the spindle (the rail and rollers in `134355`).
  No source read gives its travel; the plan's level 2 asks only that the carousel index. Logged.

### The control's generation
The pendant (`134314`) has POWER ON and POWER OFF buttons, an analogue SPINDLE LOAD meter,
EMERGENCY STOP, HANDLE JOG, CYCLE START and FEED HOLD, and keys grouped as F1-F4, DISPLAY, CURSOR
and OVERRIDES, beside a small screen. These are the Classic control's pendant features in the
2009 manual ("PENDANT KEYBOARD INTRODUCTION", p. 23-24), and unlike the 2023 manual's Next
Generation Control. So the Classic Haas Control [INFERENCE]; to read off its screen at a visit
(plan, visit list item 5). It matters for Phase 5's G-code reader, not for this phase.

## What the twin uses
`backend/src/moonwalkers/pipelines/b/haas_tm1.reference.json`: 34 facts, 5 issues; 43 of 48
quotes found on their cited pages by `pipelines.b.quotes`, the other 5 being readings of photos
and the listing's URL.
