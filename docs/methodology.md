# How we work

This is the team's methodology for building the platform. It applies to people and to Claude Code.

## The loop for every task
1. **Question.** State what the task must answer or produce, and how we will know it worked.
2. **Research.** Read primary sources (official docs, READMEs, papers, manufacturer documents).
   Record each source with its URL and access date.
3. **Decide.** When there is a real choice, write a short decision record in `docs/decisions/`:
   the options, what we chose, why, and what it costs us.
4. **Build.** Implement the smallest version that tests the decision.
5. **Verify.** Run tests; for twins, open the `.usd` in Isaac Sim and check the result by hand.
   Record what was checked and what was seen, including failures.
6. **Document.** Update the worklog, the README status, and any affected docs in the same pull request.

## Evidence rules
- Every fact cites a source. In docs, link the source next to the claim.
- Reasoning that no source states is labeled `[INFERENCE]`.
- When sources disagree (for example, the HA5C's maximum speed is 410 °/s on the Haas UK product
  page but 330 or 320 °/s in the 2006 manual), name both, pick one, and say which and why.
- "Not confirmed" is an acceptable answer. A guess presented as fact is not.
- Get as close to the real machine as the sources allow, and log every known inaccuracy: as an
  issue in the twin, in the run's `RUN.md`, and in the phase report's table of inaccuracies
  (advisors, 2026-10-22).
- Twins carry their own provenance: every fact, joint, and control behavior in a `PipelineResult`
  cites at least one `Source`, so users can always see where information came from.

## Human review
- v1 keeps a human in the loop. Results default to `needs_human_review = true`.
- A reviewer approves or rejects a twin; the decision and reason are recorded with the twin version.
- Later versions will let the user choose how much human input they want (a setting, not a rewrite).

## Evaluation
- Use the metrics from Dr. Li's agentic-pipeline deck where they fit (asset retrieval correctness,
  component coverage, count accuracy, spatial-relation plausibility, placement quality, render-vs-input
  visual match, trace quality), plus a **functional-check** measure: do the joints and control logic
  behave as the sources describe?
- The advisors set no fixed list of metrics (2026-10-22). We define our own measures, such as the
  size checks and the functional check, and test against them.
- For the PoC, record per run: input files, generator and version, time taken, success level reached
  (1-3), and reviewer notes.

## Reproducibility
- Record exact versions (Python packages, model weights, Isaac Sim build) in the worklog for every run
  that produces a twin.
- Keep inputs and outputs in `data/` organized by machine and run so any run can be repeated.
