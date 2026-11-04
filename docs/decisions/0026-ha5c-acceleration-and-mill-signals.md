# 0026 - The HA5C controller's acceleration and its signals to a mill (amends 0016)

- **Status:** accepted (Daniel, 2026-11-03: "I accept decisions 0025 and 0026, all looks good." Merged in PR #22). Proposed by Claude Code in the
  drill-press plan's Phase 6, step 6. Its stand-ins still go back to the stakeholders
- **Date:** 2026-11-02
- **Decided by:** team (Daniel), to be brought back to the stakeholders (the advisors asked for
  this on 2026-10-22: "model them if possible; if not, record why")
- **Amends:** decision 0016 ("Acceleration is not modelled"; signals logged "with no motion, no
  wait")

## Context
Decision 0016's interpreter moves the HA5C's spindle at full feed from the start of a step to its
end. It logs the mill's signal codes (G86, G87, G89, G92, G93, G94) as events that take no time.
The advisors asked for the controller's acceleration and its signals to the mill (poc-report,
section 7).

**What the sources give** (`docs/research/2026-10-30-control-logic-research.md`, section 5; the
2006 manual, `data/machines/haas-ha5c/inputs/documents/ha5c-operators-manual-2006.pdf`):
- **Acceleration:** no HA5C value for Parameter 18 or 44 in the 2006, 2012 or 2017 manuals, or in
  any page we could read. All three say Parameter 18 "must be greater than or equal to
  Parameter 19, usually 2X" (2006, p. 43). Parameter 44 is an "Exponential acceleration time
  constant", with no value.
- **The two signals:** "Your equipment tells the Haas control to index (an input), it indexes, then
  sends a signal back to your equipment that the index (an output) has been completed" (p. 10).
  "The remote input consists of a cycle start line and a cycle finish line" (p. 11).
- **Parameter 1:** "0: relay active during indexer motion; 1: relay pulsed for ¼ second at end of
  motion; 2: no relay action" (p. 42). No HA5C value is given.
- **The codes** (p. 34):
  - G86 "turn CNC relay on", G87 "turn CNC relay off", G93 "pulse CNC relay";
  - G89 "wait for remote input", G92 "pulse CNC relay and wait for remote input";
  - G94 "pulse CNC relay and run next L steps automatically".

  The manual adds: "The G codes 86, 87, 89, 92, and 93 should be used with the CNC relay function
  disabled (Parameter 1 = 2)" (p. 33). For G94, "The CNC relay is pulsed at the beginning of the
  step ... The controller then executes the following L steps automatically without waiting for
  start commands" (p. 36). "G97 does not pulse the CNC relay at step completion" (p. 35).
- **Parameter 10:** "0: Stop after each step ... 2: Continue all programs until end code 99 or 95"
  (p. 42).

## Options considered
1. **Acceleration.**
   - (a) **A constant-acceleration ramp** (a trapezoid of speed, or a triangle when a move is too
     short to reach its feed) at a labelled stand-in: twice the top feed per second, the manuals'
     "usually 2X".
   - (b) Leave it out, as decision 0016 did. That ignores what the advisors asked, although the
     mechanism is documented.
   - (c) Add Parameter 44's exponential smoothing too. It has no value, so the only guess would
     be ours.
2. **The relay.**
   - (a) **A timeline of when the relay is closed,** from Parameter 1 and the codes. The runner
     prints its changes and shows it on the joint, and the plan carries it as time samples.
   - (b) Events only, as today. Nothing in Isaac Sim shows them.
3. **The remote input.**
   - (a) **Waits where the manual waits** (G89, G92, and after every step with Parameter 10 = 0).
     A simulated mill answers after a labelled time, so the plan has a timing. In Isaac Sim, a
     person can tick "Cycle Start" in the Property panel instead.
   - (b) Go on at once, as today.

## Decision
1a, 2a and 3a: Claude Code's proposals.
- **Acceleration: 540 deg/s^2,** a stand-in (`interpreter.ACCELERATION_STAND_IN`).
  - [INFERENCE] The rule: Parameter 18 is "usually 2X" Parameter 19 (p. 43), and both use the
    same factor (x 100 in 2006), so a move reaches its top speed in half a second.
  - The top speed is the program's top feed, 270 deg/s ("The feed rate display ranges between
    00.001 and 270.000", p. 34), so 2 x 270 = 540.
  - With the cited 410 deg/s (the Haas UK page) it would be 820. 270 is chosen because no
    program can ask for more.
  - A forum post's snippet gives P19 = 3600 for an older HA5C control, which is 270 deg/s at that
    control's P9/P20. It is not verified (research note).
  - Parameter 44 is left out.
  - `--acceleration 0` (or `acceleration_deg_s2=None`) gives decision 0016's motion.
- **The relay:**
  - **Parameter 1 = 2** when the program uses G86, G87, G89, G92 or G93 (p. 33); otherwise
    **1**, the quarter-second pulse after each move that tells the mill the index is done (p. 10).
    Both are inferred; the HA5C's setting is not given. `--relay` sets it.
  - G93's pulse lasts ¼ s, like Parameter 1's [INFERENCE].
  - G94 pulses at the beginning of its step and frees the next L steps from waiting. G97 does not
    pulse.
- **The remote input:**
  - G89 and G92 wait for it. With `--step-mode` (Parameter 10 = 0), every step does too, except
    the L steps after a G94 and the last step.
  - The simulated mill answers 1 s later (`--mill-answer`, a stand-in for the mill's own work).
- **In Isaac Sim** (`isaac_runner.py`; on the program's joint, in the Property panel's "Raw USD
  Properties", group "MoonWalkers program"):
  - **"CNC relay (to the mill)":** set by the runner, which also prints each change;
  - **"Hold for Cycle Start":** ticked before Play, the runner holds the spindle at each wait
    until "Cycle Start" is ticked, then goes on and unticks it (`PlanClock`).
  - `program_native.usdc` carries the relay as time samples only (no runner, no holding).
- **`PROGRAM.md`** lists the settings, the relay's spans and the waits.

## Consequences
- **The HA5C's moves take longer, and closer to a real controller's** [INFERENCE]: Example #3
  goes from 11.67 s to 15.92 s with its 1 s pauses, because each of its 72 and 90 deg indexes is
  too short to reach 270 deg/s.
- **The mill's side is now visible:** when the relay tells the mill the index is done, and where
  the controller waits for it. One step per Cycle Start (decision 0016's option 2b) can be played
  by hand.
- **Every number added is labelled:** the acceleration, Parameter 1, the pulse length of G93 and
  the mill's answer time. They go back to the stakeholders with the request for the HA5C's real
  parameters (Haas, or a look at a real control's parameter list).
- **Program folders written before this decision** keep decision 0016's motion. New ones get
  acceleration by default.
- **No Isaac Sim check yet:** Daniel's direction is that the HA5C is checked later, if deemed
  necessary (2026-10-30).
- **Reversing it:** `--acceleration 0` and `--mill-answer 0` give decision 0016's timeline. The
  relay then remains as information.
