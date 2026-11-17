# 0035 - A mill's programs: Haas's G and M codes, read by our own reader, run as the axes' motion

- **Status:** accepted by Daniel on 2026-11-16 (the lab's machines plan, Phase 5): "Looking over
  decision 0035 I approve as proposed", after his Isaac Sim check of both programs
- **Date:** 2026-11-16
- **Decided by:** team (Daniel), proposed by Claude Code
- **Applies:** decisions 0012 (the twin's frame), 0016 and 0026 (program folders, the runner),
  0033 (an arm's programs, whose pattern this follows), 0034 (the TM-1 twin and its hold)

## Context
Level 3 for the Haas TM-1 (`haas/tm1@v3`) is a program from Haas's manual run on the twin,
"measured by the tool tip's distance from the programmed path, in mm, and the time against the
plan" (`docs/lab-machines-plan.md`, Phase 5). What we had:
- program folders and a runner (decisions 0016, 0033) that drive turning joints only, by angle;
- a twin whose X, Y and Z are sliding joints held by a stiff drive (decision 0034), on which a
  target stepped by hand moved an axis at up to 224 mm/s, over the cited 84.7 (Phase 4's
  hand-off: a program must move the target along its path every step, never jump it);
- no tool in the twin: a stand-in spindle nose, and no stated home or direction for the axes.

The research is `docs/research/2026-11-16-haas-mill-programs.md`: the 2009 Classic manual
(96-8000 Rev Y), the 2023 manual and the Tool Room Mill addendum (2002). It answers Daniel's three
questions (which way +X, +Y and +Z go; where home is; what the tool tip is) with pages, and lists
what stays a stand-in. The lab has shared no program for the TM-1.

## Options considered
1. **How a program is written.**
   - (a) **Haas's text as printed,** in `spec["program"]` as `{"format": "haas_gcode", "text":
     ..., "machine": {...}, "setup": {...}}`: the machine's own language, as decisions 0016 and
     0033 chose, so the lab's program can be dropped in as it is.
   - (b) Our own list of moves: simpler, but a translation by hand of every program.
2. **Who reads it.**
   - (a) **Our own reader** (`control/haas_gcode.py`, no new package): the programs use about
     twenty codes, and the meanings that matter are Haas's own and need a page each anyway (a
     number without a decimal point under Setting 77, M codes at the block's end, one M code per
     block, G28 through a point, G00 axes each at the rapid).
   - (b) A G-code library. Daniel's rule: none without his approval (what, why, licence, size).
     A general parser would still leave Haas's meanings to us, so none is proposed.
3. **What is read.** (a) **What Haas's two example programs need, and close neighbours:**
   G00-G04, G17, G20/G21, G28, G40-G43 (cutter compensation only with D = 0), G49, G53, G54-G59,
   G80, G90/G91, G94; M01-M09, M02/M30; T, S, F, H, D, P; refused with the reason: canned cycles,
   offsets in cutter compensation, corner rounding, sub-programs, macros, block delete, other
   planes, M00 (it waits for a person). (b) Everything: weeks of work, and level 3 needs none of
   it. (a) is taken; the refused list is the reader's and the note's.
4. **How Haas's axes find the twin's joints.**
   - (a) **A direction per axis in the twin's frame** (the tool's motion against the table: +X the
     twin's +y, +Y its -x, +Z its +z; research note section 1) **and the end where home is**
     (`plus_end`). The reader works out each joint's sign from its axis and from whether it
     carries the tool or the work, so a twin whose table moves in Z or whose saddle carries X is
     handled without typed signs.
   - (b) Typed signs and offsets per joint: shorter, but a sign typed wrong goes unnoticed.
5. **Timing.**
   - (a) **G00 moves each axis at its cited rapid, on its own** ("all axes will not necessarily
     complete their motions at the same time", 2009 manual, PDF p. 139); **G01, G02 and G03 move
     along the path at F**, refused above an axis's cited top speed ("an alarm (max feedrate
     exceeded)", p. 139) or the cited maximum cutting feed; **every move speeds up and slows down
     at a stand-in 1000 mm/s^2 and ends at rest** (no source gives the axes' acceleration;
     `--acceleration 0` plans without it).
   - (b) Blending between blocks, as a real control does: not cited for the TM-1, and it would
     make the plan's corners guesses.
6. **Where the plan starts.** (a) **At the twin's 0 (its photographed pose), with a zero return
   first,** Z then X and Y at the rapids, as POWER UP does (2009 manual, PDF p. 24; the addendum's
   HOME G28, p. 14). The twin is never jumped home. (b) At home: the first physics step would
   jump every axis, which Phase 4's hand-off rules out.
7. **The tool tip.** (a) **A stand-in tool on the spindle's axis, its length below the nose's face,
   with its length offset H touched off on the twin** as the manual's Tool Offset Measure does
   (PDF p. 67): the machine Z where the tip meets the top of a stand-in block of stock. The
   nose's face and the table's top are measured from the twin's own stage (the lowest level of
   the spindle part with at least 16 points; the highest upward level of the table holding half
   the area of its largest: a line down from the nose falls into a T-slot, and the stand-in table
   is a slab with rails). The tool, the stock and the work offsets are labelled stand-ins in the
   program file. (b) A tool modelled in the twin: a contract change for a stand-in.
8. **In Isaac Sim.**
   - (a) **One runner for every program folder:** `isaac_runner.py` learns sliding joints (the
     "linear" drive, targets in metres) and `moonwalkers:program:positions` beside
     `anglesDeg`; it moves each target along the plan every physics step. The spindle gets only
     its speed (`moonwalkers:program:speedOnly`), on a velocity drive: a turning joint without
     limits wraps its position. Axes and carousel hold with the twin's `hold_drive`.
     `program.usdc` also draws the stand-in tool, the stock and the programmed path (red cutting,
     blue rapids) on the table: pictures, no collision. There is no `program_native.usdc`: a
     spindle's speed is not a time-sampled position.
   - (b) A separate mill runner: two scripts to keep in step.
9. **Measuring.** (a) **`control compare` by the tool tip, from positions only** (the recorder's
   velocities are not trusted under the stiff hold; the spindle's are used, since its position
   wraps): the tip's distance from the plan at the same time and from the programmed path, over
   the whole program and while cutting (largest and 95 %); when each block's move came within
   0.1 mm of its end against the plan; each axis's top speed; where the tip ended; the spindle's
   speed while cutting.

## Decision
Options 1-9 (a): Haas's programs as printed, read by our own reader by the 2009 manual's rules,
run from the twin's 0 through a zero return as the axes' motion at the cited rapids and feeds
with a stand-in acceleration, with a stand-in tool touched off on the twin, driven in Isaac Sim by
the shared runner and measured by the tool tip. The first programs are Haas's O40001 (2023
manual, p. 102) and O40006 (p. 172), packaged in `control/programs/`.

## Consequences
- **Easier:** the lab's TM-1 or VF-3 program can be run as it is, if it keeps to the codes read; a
  refusal names the block and the reason. The VF-3 (the plan's Phase 6) needs only its own machine
  map. The runner drives any sliding joint.
- **Stand-ins, logged in each program file, `PROGRAM.md` and the phase report:** X home (the + end;
  not cited), the axes' acceleration, no blending, no spindle run-up, the tool change's time (1 s
  per pocket) and its starting pocket, ATC FWD's direction, Setting 9 (inch), the tool's length
  (3.0 in), the stock (2.0 in), the work offsets, D01 = 0 in O40006. Y home's place is an
  [INFERENCE]. The lab visit's items 1 and 2 settle the directions and X home.
- **Harder or not done:** cutter compensation with an offset, canned cycles and sub-programs are
  refused, so the 2009 manual's own examples do not run yet. The tool change's Z lift above home
  and the carousel's slide are not modelled.
- **If reversed:** a library would replace `GcodeProgram.from_text` only; the planner, the folder,
  the runner and the measures stay.
- **Seen in Daniel's Isaac Sim check (2026-11-16, level 3 for both programs):** the tool tip
  stayed within 0.017 mm of the programmed path (0.014 mm while cutting), and every block's move
  arrived within 0.01 s of its planned end. Z lags the plan by up to 1.84 mm (22 ms) while the
  head rises at the rapid, along the path, and catches up as the target slows [INFERENCE: the
  joint's speed cap at the cited rapid leaves no margin to catch up while lifting against
  gravity]. Logged, not changed: the cap is the cited rapid.
