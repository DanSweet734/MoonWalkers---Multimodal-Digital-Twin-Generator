# Control logic: the T33901's switch, speeds and stroke, and the HA5C's acceleration (2026-10-30)

**Question.** Phase 6 of `docs/drill-press-plan.md` (level 3) needs, before any code:
- what the T33901's manual says about its keyed switch, its speeds and an operator's stroke, and
  what it leaves out;
- where the depth stop is set in the photos (Daniel, 2026-10-30: "let's move the nut
  accordingly");
- whether Isaac Sim 6.2.0 can turn the spindle at its cited speed, record it, and let a person
  operate the controls from the Property panel;
- the HA5C's Parameters 18 and 44 beyond the 2006 and 2012 manuals (the advisors, 2026-10-22).

**Dates.** Read on 2026-10-30. Files fetched are logged with SHA-256 in their machine's
`inputs/SOURCES.md`. PDF text was read with pypdf, and page numbers are the PDF's.

## Sources
- **The T33901 manual,** `data/machines/grizzly-t33901/inputs/documents/grizzly-t33901-t33902-manual-2023.pdf`
  (https://cdn0.grizzly.com/manuals/t33901_m.pdf, "REVISED DECEMBER, 2023"). Page 29 was also
  rendered with pypdfium2, since its chart is an image.
- **Two drilling-feed references,** fetched today into the same folder:
  - University of Toronto, Mechanical & Industrial Engineering, "MODULE 1 The Drill Press"
    (https://www.mie.utoronto.ca/wp-content/uploads/2016/10/MODULE-1-The-Drill-Press.pdf; PDF
    created 2010-07-26);
  - University of Florida, EML2322L, "Drilling and Milling Speeds and Feeds"
    (https://web.mae.ufl.edu/designlab/Lab%20Assignments/EML2322L-Drilling%20and%20Milling%20Speeds%20and%20Feeds.pdf;
    PDF created 2018-10-23).
- **Isaac Sim 6.2.0's own files** on Daniel's machine (`C:\isaacsim`, Kit 110.4.0 build 386251):
  - `extscache/omni.usd.schema.physx-110.4.4+110.4.0.wx64.r.cp312.u7f4/plugins/PhysxSchema/resources/generatedSchema.usda`;
  - `extscache/omni.physics.tensors-110.4.4+110.4.0.wx64.r.cp312.u7f4/omni/physics/tensors/api.py`;
  - `exts/isaacsim.core.experimental.prims/isaacsim/core/experimental/prims/impl/articulation.py`;
  - `exts/isaacsim.asset.validation/pip_prebundle/simready/foundation/tier_core/capabilities/physics_bodies/physics_driven_joints/requirements/physics-joint-max-velocity.md`;
  - `extscache/omni.kit.property.usd-4.9.18+187cf21b/omni/kit/property/usd/` (the Property panel).
- **Three Haas manuals for the HA5C:** the 2006 HA5C manual and the 2012 rotary manual (already
  in `data/machines/haas-ha5c/inputs/documents/`), and the 2017 rotary manual, fetched today
  (https://www.haascnc.com/content/dam/haascnc/en/service/manual/operator/english---rotary-tailstock-operator's-manual---2017.pdf;
  its pages are printed "96-8960A" and "Tuesday, July 28, 2015", and the PDF was modified
  2024-03-05).
- **Searches** (WebSearch, standard and extended) for HA5C parameter values and for drill-press
  stroke times. haascnc.com's HTML pages and practicalmachinist.com answered WebFetch with HTTP
  403, so only search snippets of them were seen.

## 1. What the T33901's manual says about its control
| What | Quote | Page |
|---|---|---|
| The keyed switch | "ON/OFF Switch w/Disabling Key: Turns motor ON when moved up; turns motor OFF when moved down. Removal of yellow key disables switch so motor cannot start." | 6 |
| Its test | "Remove switch disabling key" ... "Try to start machine with ON/OFF switch. Machine should not start." | 24 |
| The operator's order of work | "Selects appropriate spindle speed according to drill bit speed chart located on Page 27, and adjusts belts to required pulley sheaves." "Connects machine to power, and turns machine ON." "Performs drilling operation." "When finished, turns machine OFF and disconnects it from power." | 26 |
| Changing speed | "To change spindle speed: 1. DISCONNECT MACHINE FROM POWER!" | 30 |
| The twelve speeds | "12 Speed Settings: 340, 500, 530, 660, 740, 790, 1380, 1420, 1680, 1860, 2200, 2860 RPM" | 9 |
| The one cited belt | "a belt combination of B-3 creates 790 RPM" | 30 |
| The stroke | "Downfeed Handle (1 of 3): Moves spindle down when pulled down. Spindle automatically returns to top position when released." | 7 |
| The depth stop | "Stops spindle travel at predetermined drilling depth. Top of depth stop nut indicates depth on scale." | 7 |
| Stopping | "Always allow spindle to stop on its own. DO NOT stop spindle using your hand or any other object." | 14 |
| The motor | "Speed ... 1720 RPM", "Type ... TEFC Capacitor-Start Induction" | 8 |

**The speed chart** ("Figure 30. Drill bit speed chart (RPMs).", p. 29; the text above it calls it
"Figure 28"). Its "Twist/Brad Point Drill Bits" rows, read from the rendered page:

| Bit | Soft wood | Hard wood | Plastic | Brass | Aluminum | Mild steel |
|---|---|---|---|---|---|---|
| 1/16" - 3/16" | 3000 | 2500 | 2500 | 2500 | 3000 | 2500 |
| 13/64" - 3/8" | 2000 | 1500 | 2000 | 1250 | 2500 | 1250 |
| 25/64" - 5/8" | 1500 | 750 | 1500 | 750 | 1500 | 600 |
| 11/16" - 1" | 750 | 500 | 1000 | 400 | 1000 | 350 |

The page warns: "Exceeding the recommended speeds may be dangerous to the operator."

**Not in the manual:** how fast an operator pulls the handles or feeds, how long they hold at
depth, how long the motor takes to reach speed or to stop, and what removing the key does while
the motor runs (p. 6 says only that the motor then "cannot start").

**[INFERENCE] A scenario that ties these together:** a 1/4 in twist bit in mild steel. The chart
gives 1250 RPM for 13/64" - 3/8". The fastest of the twelve settings that does not exceed it is
790 RPM (the next is 1380), and 790 RPM is also the one setting whose belts the manual names
(B-3). Which bit and material are drilled is our choice for the scenario; the speed then follows
from the manual.

## 2. The depth stop's setting in the photos
p. 42 calibrates the scale so that, with the "depth stop nut all the way down so it sits against
stop bracket", it reads 0". So the stop's setting is the gap between the nut and the bracket.
The rod's thread is taken as M12, the thread of its "DEPTH STOP NUT M12-1.75" (p. 49, part 48)
[INFERENCE], so its 12 mm width scales each photo. Measured on intensity profiles across and
along the rod, beside it where the bracket shows (Pillow, read-only in the generator's
environment):

| Image | Rod across | Nut's bottom to bracket's top | Gap |
|---|---|---|---|
| Fig. 35 (`photos/manual/manual_p31_fig35_depth-stop.jpg`, 451 x 338 px) | 12 px (x 209.5-221.5) | y 129.5 to 172.5, 43 px | 43 mm |
| `photos/front_operator_left.jpeg` | 6.5 px (x 371.5-378) | y 158 to 180.5, 22.5 px | 41.5 mm |
| The mesh (run `2026-10-24_run-001`): the generated nut's bottom (z 0.555) to the bracket stand-in's top (z 0.467), at the twin's scale | | 0.088 units | 43.6 mm |

The three agree on **about 43 mm (1.7 in)**, within the rod's ±1 px (8% in Fig. 35, 15% in the
colour photo). Foreshortening along the rod would make the true gap slightly larger, not smaller
[INFERENCE]. Phase 5's spec said "about 2 in" by eye (decision 0027, v5); this measurement
replaces it.

## 3. A drilling stroke's timing
**No published stroke time was found.** A search for drill-press time studies found none. The
closest material is feeds for cutting:
- UofT, Table 1.1.2 "HSS Feed Rates [in/rev]": "1/8 - 1/4 .002 - .006", "1/4 - ½ .004 - .010"
  (p. 10). Its example: "For a selected spindle speed of 500 [rpm] this would produce a vertical
  displacement of ~3 inches in one minute", and "it is recommended that, when drilling a hole,
  the drill bit is only moved approximately 0.2" into the work-piece and is then 'pulled back'"
  (pecking, p. 11).
- UF, "Table 2: Recommended Average Feed Rates for 2 Flute HSS Drills": "1/4″ to 1/2″ 0.004 to
  0.008" (p. 4); for a 1/4 in drill, "fr ≈ 0.004 in/rev" and "f [in/min] = N [rpm] × fr
  [in/rev]" (p. 5). It adds: "When applying oil manually (as in the lab), scale the feed and
  speed back to 60%" (p. 5).

**For the scenario above:** 790 RPM × 0.004 in/rev = 3.16 in/min = 1.34 mm/s while the bit cuts.
How long the pull to the work, the hold, the motor's start and stop take is not in any source.

**Daniel's direction (2026-10-30):** time a stroke on any benchtop drill press, and keep the
information for stand-ins ready if that is not possible. What to time is in decision 0025.

## 4. Isaac Sim 6.2.0
- **No speed cap by default.** `physxJoint:maxJointVelocity` defaults to `inf` in the PhysX
  schema ("Maximum joint velocity."). Isaac Sim's articulation code writes it in degrees per
  second for a rotation: `if self.dof_types[dof_index] == omni.physics.tensors.DofType.Rotation:
  max_velocity = np.rad2deg(max_velocity)` (`articulation.py`, `set_dof_max_velocities`). So
  2860 RPM is 17,160 deg/s. NVIDIA's SimReady rule DJ.005 asks driven joints with
  `PhysxJointAPI` for "a positive maximum velocity". This settles the attribute name and units
  left open since decision 0010.
- **Velocities can be recorded.** The tensor API's `get_dof_velocities` "returns the positions
  in radians/second for rotational DOFs" (sic: velocities), beside `get_dof_positions`, which
  the joint recorder already uses (`api.py`).
- **Why the recorder needs them.** "The joint position of a revolute joint that does not have
  limits applied will wrap on a 360° boundary"
  (`docs/research/2026-10-17-usd-physics-for-isaac-sim.md`). At 790 RPM the spindle turns 79°
  per 60 Hz step, and at 2860 RPM 286°, so positions alone cannot tell the speed at high
  settings [arithmetic].
- **The Property panel offers a choice list.** A token attribute with `allowedTokens` metadata
  is shown with `TfTokenAttributeModel` as a drop-down (`usd_property_widget_builder.py`); the
  panel's own test makes such an attribute on a plain prim (`tests/test_widget.py`,
  `token_attr_allowedTokens`). So the twelve speeds can be a drop-down, and booleans (key,
  paddle, power) check boxes. Whether a custom attribute shows under "Raw USD Properties" while
  Play runs is to be seen in Daniel's check.
- **No drive gains need changing mid-run** for the stroke: the operator's hand can move the
  quill spring drive's target and hand it back, as the HA5C runner moves its drive's target on
  every step (decision 0016). So whether PhysX takes stiffness changes during a run is not
  needed.

## 5. The HA5C's acceleration (Parameters 18, 19 and 44)
**No HA5C value was found** in the 2006, 2012 or 2017 manuals, or in any page we could read.
What the manuals do give:
- **Parameter 18 (Acceleration):**
  - 2006: "The value used is (Par 18)*100 in encoder steps/second/second ... It must be greater
    than or equal to Parameter 19, usually 2X" (p. 43).
  - 2012: "(Par 18)*10 in encoder steps/second/second ... It must be greater than or equal to
    twice Parameter 19, usually 2X" (p. 61).
  - 2017: "The value used is units * 10 in encoder steps/second/second ... It must be greater
    than or equal to twice Parameter 19, usually 2X" (p. 70).
- **Parameter 19 (Maximum Speed)** uses the same factor as Parameter 18 in each manual (2006:
  "(Par 19)*100 in encoder steps/second", p. 43; 2012: "(Par 19)*10", p. 61).
- **[INFERENCE] So, "usually", the acceleration in steps/s² is twice the top speed in steps/s:**
  a move reaches full speed in half a second. That is the manuals' usual setting, not the
  HA5C's.
- **Parameter 44:** "Exponential acceleration time constant. Units are 1/10000 seconds" (2012,
  p. 65; 2017, p. 78: range 0 to 999). No value.
- **Encoder steps per degree** (Parameter 9), the manuals' own HA5C example: "An HA5C with a 2000
  pulse per revolution encoder (with four pulses per line, or quadrature) and a 60:1 gear ratio
  would be (8000 x 60)/360° = 1333.333 encoder steps ... Set Parameter 20 to 3, therefore:
  1333.333 x 3 = 4000 (entered in Parameter 9)" (2006, p. 42; 2012, p. 59).
- **A forum value, not verified:** a search snippet of a Practical Machinist thread
  (https://www.practicalmachinist.com/forum/threads/parameterhelp-on-haase-ha5c-indexer.319887/,
  HTTP 403 to WebFetch) lists, for an HA5C control "series #933449 and software version 34",
  P9 = 4000, P18 = 1000, P19 = 3600 and P20 = 3.
  - With the 2006 factor, P19 gives 3600 × 100 / (4000 / 3) = 270 °/s, the manual's top feed rate
    ("The feed rate display ranges between 00.001 and 270.000", decision 0016) [arithmetic].
  - But P18 = 1000 is below P19, against every manual's rule, and the poster was asking for
    default values because something was wrong. So it is not used.
- **Not found:** a Haas parameter table for the HA5C. Haas's online "Rotary - Parameters" page
  answers 403.

## What this settles
- The T33901's control can be described from the manual, except the stroke's timings and the
  motor's start and stop times: these come from Daniel's timing, or are labelled stand-ins.
- The depth stop is set at about 43 mm in the photos; v7's stop and nut go there.
- Isaac Sim needs no new tools: write the cited top speed in deg/s, record velocities, and offer
  the controls as attributes.
- The HA5C's acceleration has no cited value. Its stand-in can rest on the manuals' "usually 2X"
  (full speed in 0.5 s), labelled and brought back to the stakeholders (plan, Phase 6, item 4).
