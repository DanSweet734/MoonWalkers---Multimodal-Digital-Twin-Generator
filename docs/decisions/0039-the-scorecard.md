# 0039 - The scorecard: how "accurately" is measured

- **Status:** accepted by the advisors at the meeting of 2026-11-19 ("accepted as is", Daniel's
  account, 2026-11-25), after their first acceptance on 2026-11-12 ("targets unchanged", "always
  shoot for as close as possible"; worklog 2026-11-16). Recorded by Claude Code for Daniel's
  review with the video plan's draft.
- **Date:** 2026-11-25 (the record); the measures date from 2026-11-09
- **Decided by:** advisors (Dr. Bingbing Li, Dr. Thomas Lu), proposed by Claude Code with Daniel
- **Applies:** the methodology's "Evaluation" (Dr. Li's deck's metrics, plus a functional check);
  decisions 0015 (reviews), 0016, 0025 and 0033-0038 (what level 3 compares)

## Context
The advisors asked for real-world comparisons on the lab's machines (meeting of 2026-11-05) and
set no fixed list of metrics (2026-10-22): "We define our own measures ... and test against them"
(`docs/methodology.md`, "Evaluation"). The lab's machines plan proposed a scorecard on 2026-11-09
([the plan](../lab-machines-plan.md), "How 'accurately' is measured: the scorecard"), Daniel took
it to the weekly meetings, and the plan's list of records held this one "once the meetings have
judged it" (Daniel, 2026-11-18: after the meeting of 2026-11-19).

What it was used for: every lab twin's `score/SCORE.md`, written by
`uv run python -m moonwalkers.pipelines.b.score <run> [--maker <score.json>] [--recording <csv> ...]`
(the lab plan, Phase 2), and the report's table ([lab-machines-report.md](../lab-machines-report.md),
section 4).

## Options considered
1. **Keep the scorecard as proposed, targets unchanged** (the advisors' answer, twice). Eight
   measures; a target where the T33901 set one, none where nothing had been measured. Costs
   nothing; the report's section 4 is its baseline.
2. **Fix targets for the measures that have none** (photo match, shape, joint places), from the
   lab's first builds (for example the TM-1 `v3`'s IoU of 0.751-0.842). Not asked for; a target
   from three twins would be a guess [INFERENCE].
3. **Add a measure of the real machine's motion now.** Needs the real machine moving on video,
   which the visit of 2026-11-19 could not get (no one could jog a machine). Left for the video
   plan, which would amend this record.

## Decision
Option 1. The scorecard, as accepted:

| Measure | How | Machines | Target |
|---|---|---|---|
| Sizes | Every cited dimension against the twin's (the size checks) | All | Within 6% (the T33901 reached -5.9% to +5.8%); over 10% flagged |
| Match with the photos | Each fed photo against the twin's silhouette, placed by `photo_marks.fit_camera`, as IoU | All | None: the lab's builds are the baseline |
| Shape against the maker's model | Distance from the generated mesh to the maker's mesh in the same pose: mean and 95th percentile, in mm | Where a maker's model exists (the arm) | None |
| Parts and joints | Parts and joints in the twin against the sources' list (coverage, count accuracy) | All | Every moving part the sources name; each gap logged |
| Joint axes and places | Each axis's direction (degrees) and position (mm) against the cited frames | Where frames are cited (the arm); the mills by direction | None |
| Ranges | Each joint's range reached in Isaac Sim, from the joint recorder, against the cited range | All | Within 1° or 1 mm |
| Control | The recorded motion against the controller's plan (`control compare`), and its time against the cited speeds | All | The T33901's stroke stayed within 0.63 mm of its plan |
| Evidence | Quotes found on their cited pages (the quote checker); stand-ins and guesses logged | All | Every quote found |

"Always shoot for as close as possible" (the advisors, 2026-11-12): a met target is a floor, not
the aim.

## Consequences
- **Every new twin is scored the same way,** and its `SCORE.md` goes in the plan's report beside
  the earlier ones; a better mesh shows as a higher IoU or a smaller shape distance against the
  same baseline.
- **Known gaps, logged, not fixed here** (the report, section 8.3): the scorer reads one maker's
  model per twin, so the hand is not scored (gap 8); nothing warns that a spec has no size checks
  (gap 9, `haas/tm1@v4`).
- **Level 3 compares the twin with its own plan at the cited speeds,** not with the real machine.
  A measure from video of the real machine's motion (for example the time and direction of a jog
  between two marks [INFERENCE]) is a new row, and a new decision record amending this one.
- **Video input** (approved 2026-11-19) is measured by the same rows: a twin from video frames is
  scored against the same photos and the same cited facts as one from photos, so the two can be
  compared [INFERENCE].
- Reversing it means rewriting the scorer's report (`pipelines/b/score.py`) and the reports'
  tables; nothing in the contract depends on it.
