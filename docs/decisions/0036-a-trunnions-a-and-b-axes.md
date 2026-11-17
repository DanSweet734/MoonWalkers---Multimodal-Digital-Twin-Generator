# 0036 - A trunnion's A and B axes in the Haas reader, and parts hidden in the checks

- **Status:** proposed (the lab's machines plan, Phase 6), for Daniel's review after his Isaac Sim
  check of the VF-3's programs
- **Date:** 2026-11-17
- **Decided by:** team (Daniel), proposed by Claude Code
- **Applies:** decisions 0023 and 0034 (the spec, a mill's axes), 0026 (the HA5C's acceleration
  rule), 0035 (the Haas reader, which this extends)

## Context
`haas/vf3@v1` (run `2026-11-16_run-001`) carries a Haas trunnion as two turning joints on the
table: `a_axis` tilts the cradle (±120°) and `b_axis` turns the platter on it (no limit), both at
the TR160's 80 °/s, a labelled stand-in model. Daniel's level-2 check of 2026-11-17 reached every
limit within 0.01° and 0.01 mm. Level 3 is "a program that tilts and turns the part" on Phase 5's
reader (the plan, Phase 6), which took X, Y and Z only.

The sources are in `docs/research/2026-11-16-haas-vf3-and-trunnion-sources.md`, with its update
of 2026-11-17 on the 2012 Classic manual (96-8000 Rev AP; PDF pages):
- "A and B axes are always programmed in degrees" (p. 172);
- G00 and G01 take "A Optional A-axis motion command" (p. 181);
- G28 "returns all axes (X, Y, Z, A and B)" (p. 191);
- "G93 inverse time must be in effect for simultaneous 5-axis motion" (p. 172);
- the brakes M10-M13 (p. 172);
- **two feeds disagree:**
  - "G01 A90. F50. will rotate the A-Axis 90 degrees at 50 degrees per second" (p. 173);
  - G01's "F Feedrate in inches (mm) per minute" (p. 181), and Settings 34 and 79: "The feedrate
    in a program is always inches per minute ... the control must know the diameter of the part"
    (pp. 271, 277);
- "Rapid moves are not allowed" (p. 173), in its notes on 4- and 5-axis cutting, against G00's A
  address (p. 181) and the same notes' rapid positioning, where "the axes will arrive at the
  programmed position at different times" (p. 172).

The 2011 rotary manual (p. 34): "the right hand rule determines direction of tool movement and
not the table movement direction. For the right hand rule, the fingers will point opposite of the
positive rotary table movement". It adds a caveat on p. 35: "Different table movements are
possible ... depending on the equipment, parameter settings".

A second question came up in the build: the generator made the VF-3's enclosure one closed shell,
so nothing inside it shows in the twin or its checks.

## Options considered
1. **Where A and B live.**
   - (a) **In the machine map**, as X, Y and Z do: `rotary: {"A": {joint_id, direction,
     home_deg}}`. `direction` is the axis about which + turns the tool against the work (the
     right hand rule). A joint on the work's side turns the other way, so its sign comes from
     the joint's own axis, as `bind_mill` does for slides.
   - (b) A sign written per joint. That is simpler, but it hides the rule the manual gives.
2. **G00 with A or B.**
   - (a) **Allowed:** each axis at its top speed, on its own, as G00 moves X, Y and Z. "Rapid
     moves are not allowed" is read as for 5-axis cutting [INFERENCE: the sentence sits under
     "Feed Rates" for 4- and 5-axis code, while G00 lists the A address and the same notes
     position "to an approach vector" at the rapid].
   - (b) Refused: every turn would need a feed, and Haas's own examples rapid to "A0 B0"
     (p. 233).
3. **G01's F on a rotary axis.**
   - (a) **Units per minute along the part's circumference at Settings 34 and 79's diameter:**
     the control's definition, given three times (G01, both settings). The diameter is a set-up
     stand-in.
   - (b) Degrees per second, as one example says (p. 173): a single sentence against the
     definitions.
4. **A rotary axis moving together with another in G01.**
   - (a) **Refused, with the manual's reason:** it needs G93, which the reader does not read.
   - (b) Read with G94 by our own blend. No source says how the control mixes them.
5. **Which way + turns.**
   - **+A:** the cradle turns about −X (twin −y), by the cited rule, with the p. 35 caveat.
   - **+B:** the platter turns about −Z at A = 0, a STAND-IN [INFERENCE]: the manual's B turns
     about Y, a tilting rotary's other layout.
   - **Home:** each joint's 0, the cradle level as photographed (133938) and B as built: a
     stand-in.
   - The lab's jog of +A and +B, and its Settings 30 and 78, settle all three (the visit list,
     item 10).
6. **Acceleration.** None is cited for the TR160. The stand-in is twice the top speed per second
   (160 °/s²), decision 0026's rule for the HA5C [INFERENCE: another rotary, another control].
   `--acceleration 0` takes it away with the linear one.
7. **B without limits.** Daniel's check showed Isaac Sim taking a typed target on `b_axis` a turn
   at a time: 360 from 90 went back to 0. Its recorded position wraps between −360° and +360°.
   - (a) **The plan keeps an unlimited joint within ±180°** and refuses a program that goes
     further. `control compare` unwraps recorded angles.
   - (b) Allow any angle and trust the stepped target. Not tested in Isaac Sim, so not taken
     until a check shows how it behaves.
8. **What the stock and the path ride.** The trunnion stands on the table's middle, so the work
   part is the platter.
   - The stand-in stock and the drawn path are children of the platter.
   - The tool tip is taken back through the work's slides, then A, then B (nearest the frame
     first), into the platter's frame at the twin's 0.
   - The tip's machine X, Y and Z stay what `control compare` measures. A and B are measured by
     angle: the largest gap from the plan, the top speed, and arrival within 0.05°.
9. **The VF-3's programs.**
   - **`haas-o40001-basic-program-vf3`:** Haas's O40001 as printed, on the platter. A and B
     stay home.
   - **`moonwalkers-vf3-test-tilt-and-turn`:** a test program written by Claude Code, labelled
     as such, as `rebel-test-joint-moves` is for the arm. Four cuts on a 2 in block:
     - along X;
     - across it after a rapid B90;
     - an arc as B feeds back to 0 at F10. (Setting 79's 2 in, 9.55 °/s);
     - along the top tilted 30° on A.

     Its cut-4 numbers are computed on v1's stand-in geometry and the stand-in +A. The lab has
     shared no program.
10. **Parts hidden in the checks.** The enclosure is a closed shell.
    - (a) **The spec's `hidden_in_checks`:** listed parts are written invisible in every check
      file and program folder, never in `twin.usdc`, and keep their physics. A build with hidden
      parts adds `checks/inside.usdc`, the twin itself with them hidden, for typed targets.
    - (b) Cut windows into the generated mesh. That takes measured cuts per door, and the
      photos show the doors closed.
    - (c) Leave it. The moving parts would not show in any check.

## Decision
- **The reader:** (1a), (2a), (3a), (4a); the directions and homes of (5); the acceleration of
  (6); (7a).
- **The drawing and the measures:** the platter as the work part (8).
- **The programs and the checks:** the two programs of (9), and `hidden_in_checks` (10a).
- **What was built:**
  - `control/haas_gcode.py`: `RotaryMap`, `RotaryAxis`, `MillBinding.to_work`; M10-M13 logged;
  - `control/mill_export.py`: the path, the stock and PROGRAM.md's rotary table;
  - `control/compare.py`: the angles, unwrapped;
  - `pipelines/b/parts_spec.py` and `build.py`, `usd/exporter.py`: the hidden parts.

## Consequences
- A program that positions A and B and cuts with X, Y and Z (3+2) runs on a trunnion twin. A
  program with simultaneous 5-axis motion (G93, CAM output) is refused, with the reason.
- **Stand-ins that stand or fall with the lab's jog and plate:**
  - +B's direction, and both axes' homes;
  - the test program's cut-4 numbers, which follow +A;
  - the TR160's speed and sizes.

  The first three are a change to the machine map and a re-run. The trunnion's model may change
  the twin.
- A turn of B past ±180° is refused until a check shows how Isaac Sim takes it. The spindle stays
  speed-only for the same reason (decision 0035).
- `hidden_in_checks` is new in the spec. The MCP tool `set_spec_frame` does not set it yet (a tool
  gap, logged for the agent's build in Phase 8).

## Seen in Daniel's Isaac Sim check
On 2026-11-17 (Isaac Sim 6.2.0, `docs/setup/isaac-sim-check.md`, section 14) Daniel ran both
programs on `haas/vf3@v1`, from `data/machines/haas-vf3/programs/2026-11-17_*_v1/`, and recorded
them: "Both looked great and the two direction guesses at least seem accurate to what would be
expected". **Level 3 is met for the VF-3.** `control compare` on his recordings:

| Measure | O40001 on the platter | The test that tilts and turns |
| --- | --- | --- |
| Tip from the programmed path, largest | 0.021 mm | 0.019 mm (the arc and the tilted cut included) |
| Tip from the plan at the same time, cutting | 0.019 mm | 0.022 mm |
| A and B from the plan, largest | 0.000° (held home) | A 0.003°, B 0.004° |
| Each block's arrival against the plan | within 0.01 s | within 0.02 s |
| Top speeds from positions | X, Y, Z 423.3 mm/s (cited) | X, Y, Z 423.3 mm/s; B 80.00 °/s (cited); A 66.5 °/s |
| Spindle while cutting | 1000 rpm | 1000 rpm |

- **The directions:** +B turned the platter clockwise from above, and +A turned its face towards
  the column, as section 14 described. Daniel finds them as he would expect. They stay stand-ins
  until the lab's jog of +A and +B (option 5).
- **A's top speed:** the 30° tilt never reaches 80 °/s at the 160 °/s² stand-in. Its plan peaks
  at √(30 × 160) = 69.3 °/s. The recorded 66.5 °/s is the speed over 0.05 s around that sharp
  peak [INFERENCE: that span takes about 2 °/s off a peak this sharp; A stays within 0.003° of the
  plan].
- **Z's lag:** Z lags the plan by up to 1.52 mm (O40001) and 1.48 mm (the test) while the head
  rises at the rapid, along the path, as on the TM-1 (decision 0035).
- **The head's hold:** it ends 0.019 mm low, as in v1's level-2 check.
